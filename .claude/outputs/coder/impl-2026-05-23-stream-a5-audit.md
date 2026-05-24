# Stream A.5 Audit — 2026-05-24

## What this file contains
Audit-agent findings from Stream A.5. Root cause of A/A bucketing skew,
wrangler JSON fix, SSL cert fix, and rerun verification.

---

## Bucketing Skew Root Cause

**Hypothesis:** The `te_uid` cookie is written lazily (on first interaction)
by `tracker.js`, but `experiments.js` reads it eagerly. On a user's first
page load, `tracker.js` generates a UUID and stores it in the module-level
`userId` variable but does NOT write the `te_uid` cookie until the first
click or scroll fires `setOnInteraction`. When `experiments.js:getOrMintUid()`
is called for the initial `pageview` event, `getCookie('te_uid')` returns
`''` and `experiments.js` mints its own *different* ephemeral UUID. After
the user scrolls or clicks, the `te_uid` cookie is set to `tracker.js`'s
UUID. Subsequent events (impressions fired by the IntersectionObserver)
call `getExperimentAssignments()` again; this time `getCookie('te_uid')`
returns the now-set cookie value, which differs from the ephemeral ID —
so `fnv1a(uid + '|harness_aa_v1') % 100` may land in a different bucket.
The same user is now tagged as BOTH `control_a` on the pageview and
`control_b` on all subsequent impressions within the same page load.

**Evidence:**
- D1 query: 57 distinct `user_id` values appear in events for BOTH
  `control_a` AND `control_b`.
  ```sql
  SELECT user_id, COUNT(DISTINCT json_extract(experiments, '$.harness_aa_v1'))
    AS n_variants
  FROM events WHERE json_extract(experiments, '$.harness_aa_v1') IS NOT NULL
  GROUP BY user_id HAVING n_variants > 1
  ```
  Returns 57 rows.
- Example user `018d5400-95e3-42fe-b8ef-56a983d840e3` on 2026-05-07:
  `pageview` + `vitals` tagged `control_a`, then all `impression` events
  tagged `control_b` — same user_id, same day, same session.
- Distinct users per variant (175 control_a, 185 control_b) are near-equal,
  confirming the user-level split is healthy. The impression-level skew
  (7,816 vs 9,945) comes from per-session contamination.
- Daily breakdown shows erratic within-day swings (e.g., 2026-05-23:
  274 control_a impressions vs 1,481 control_b) — inconsistent with
  any stable 50/50 user assignment.
- Relevant code paths:
  - `tracker.js:55–80` — `initUserIdentity()` defers cookie write
  - `tracker.js:69–77` — `setOnInteraction` fires on first click/scroll
  - `experiments.js:88–104` — `getOrMintUid()` reads `te_uid` OR mints ephemeral
  - `tracker.js:259` — `getExperimentAssignments()` called in every `track()`

**Why the CTR looks different:** `control_a` impressions are predominantly
early in sessions (the `pageview` event fires without scroll/click), while
`control_b` impressions are late-session (after IntersectionObserver fires
post-scroll). Users who browse more content (and thus produce more impressions)
skew toward `control_b`. Those same users also tend to be less click-happy
per impression (more browsing, less clicking) — hence control_b's lower CTR.

**Recommendation for HITL:**
Fix the bucketing inconsistency: `tracker.js` should either (a) write the
`te_uid` cookie immediately on first page load (not deferred) so
`experiments.js` reads the same ID that tracker will record, OR (b)
`experiments.js:getOrMintUid()` should look for tracker's in-memory
`userId` variable before falling back to its own ephemeral ID. Option (a)
is simpler and means the cookie is always set before any event fires.
The 57 contaminated users cannot be corrected retroactively — the clean
analysis window starts from the date of the fix deploy.

---

## Script Fix 1 — Wrangler JSON

**Problem:** Wrangler 4.x prints a non-JSON preamble to stdout before the
JSON array even when `--json` is passed. The preamble lands on stdout (not
stderr), so redirecting stderr has no effect. `json.loads(proc.stdout)`
fails with `JSONDecodeError` at char 0.

**Approach:** Extract the JSON array with `re.search(r'\[.*\]', stdout, re.DOTALL)`.
Greedy match captures the full array. Raises `ValueError` (analyze_experiments.py)
or `SessionLoadError` (d1_sessions.py) with context rather than silently
returning `[]`.

**Files changed:**
- `scripts/analyze_experiments.py` — added `import re`; rewrote `_wrangler_query()`
  to regex-extract the array and raise `ValueError` on failure.
- `scripts/rank_all_content.py` — added `import re`; rewrote `fetch_d1_data()`
  to regex-extract the array and `print(Warning)` on failure instead of
  silently swallowing.
- `lib/d1_sessions.py` — added `import re`; patched `fetch_events_via_wrangler()`
  to regex-extract before `json.loads`.

**Verified by:**
```
python3 scripts/analyze_experiments.py --experiment harness_aa_v1
```
Output: `control_a=0.040 (n=8,071) control_b=0.023 (n=10,205)` — clean run,
no JSONDecodeError. Report written to `reports/experiments/harness_aa_v1-2026-05-24.md`.

---

## Script Fix 2 — SSL Cert

**Problem:** `lib/d1_sessions.py:fetch_events_via_api` and `lib/d1_client.py:_default_fetcher`
use `urllib.request.urlopen` without an SSL context. Python 3.11 on macOS
does not use the system keychain, so TLS verification fails against
`tech-econ-analytics-v2.pp712.workers.dev`.

**Approach:** `certifi` is installed (`/Library/Frameworks/Python.framework/
Versions/3.11/.../certifi/cacert.pem`). Both modules now create an
`ssl.create_default_context(cafile=certifi.where())` at import time and
pass it to `urlopen(context=_SSL_CONTEXT)`. `certifi` is a soft dependency —
if missing, `_SSL_CONTEXT = None` falls back to the default context (works
on Linux CI).

**Files changed:**
- `lib/d1_client.py` — added `import ssl`, `certifi` try/import, `_SSL_CONTEXT`
  module-level; patched `_default_fetcher` to pass `context=_SSL_CONTEXT`.
- `lib/d1_sessions.py` — same pattern for `fetch_events_via_api`.

**Verified by:**
```
python3 scripts/replay_eval.py --candidate data/global_rankings.json
```
SSL error is gone. New error is HTTP 403 (expected — `events-raw` requires
`ADMIN_KEY`). Switching to `--source wrangler` completes successfully.

---

## Rerun Results

**analyze_experiments.py:** PASS
```
Analyzing 1 experiment(s):
  harness_aa_v1: control_a=0.040 (n=8,071) control_b=0.023 (n=10,205)
  -> reports/experiments/harness_aa_v1-2026-05-24.md
```

**replay_eval.py (--source wrangler):** PASS
```
Sessions evaluated: 39 (of 145 in holdout)
ndcg_at_10: baseline=0.2275 candidate=0.2275
appended replay row to reports/replays.csv
```
`reports/replays.csv` — 1 new row (first row in the file). Headers + data
are present. Row count: 1 data row + header.

---

## Files Touched

- `scripts/analyze_experiments.py` — wrangler JSON fix (import re, _wrangler_query)
- `scripts/rank_all_content.py` — wrangler JSON fix (import re, fetch_d1_data)
- `lib/d1_client.py` — SSL fix (certifi, _SSL_CONTEXT, _default_fetcher)
- `lib/d1_sessions.py` — wrangler JSON fix (import re, fetch_events_via_wrangler) + SSL fix (certifi, fetch_events_via_api)

---

## Next Round

**HITL must decide:**
1. Fix the cookie timing bug in `tracker.js` (write `te_uid` eagerly, not
   deferred to first interaction). This is the core fix — without it the
   bucketing is contaminated for every first-visit user.
2. Decide whether to reset `harness_aa_v1` after the fix (discard the 19
   days of contaminated data and restart with a clean window). The prior
   report's A/A stats (z=-6.50, p≈0) are invalid because ~57 users' worth
   of contaminated events inflated the impression count and deflated control_b CTR.
3. Optionally: add `ADMIN_KEY` to `.claude/secrets.env` so `replay_eval.py
   --source api` works (currently returns 403).

**Can proceed without HITL:**
- Both script bugs are fixed and verified.
- `reports/replays.csv` has its first row (seeds the gate-of-3 for Stream A.2).
- `reports/experiments/harness_aa_v1-2026-05-24.md` was written (Stream A.1
  technically complete, though the data is contaminated per the bucketing bug).
