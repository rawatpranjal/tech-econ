# Stream A.6 — tracker.js cookie timing fix + harness_aa_v1 reset
# 2026-05-24
# What this file contains: implementation notes for the A.6 coder run.
# Cross-links: docs/roadmap.md A.6, .claude/outputs/coder/impl-2026-05-23-stream-a5-audit.md

---

## What was done

Fixed the `te_uid` cookie-timing bug that caused 57 users to appear in both
variants of `harness_aa_v1`, poisoning 19 days of A/A data. Paused v1.
Added `harness_aa_v2` as the clean-start replacement. Added 6 regression
tests. Updated config tests, CHANGELOG, and roadmap.

---

## Files changed

- `static/js/tracker.js` — removed `setOnInteraction` deferral; te_uid now written synchronously in `initUserIdentity()` for new users
- `data/experiments.json` — `harness_aa_v1` status → `paused`; `harness_aa_v2` added as `active`
- `tests/js/tracker-cookie-timing.test.js` — NEW: 6 regression tests for cookie-timing fix
- `tests/js/aa-experiment-config.test.js` — updated to assert v2 active, v1 paused; 4 old tests replaced with 8 new tests
- `CHANGELOG.md` — 1-line entry under 2026-05-24
- `docs/roadmap.md` — A.6 marked ✅ shipped 2026-05-24

---

## tracker.js fix

**Lazy-write call site (before):** lines 65–78 in `initUserIdentity()`.
The `else` branch (new user) generated a UUID and stored it in the module-level
`userId` variable, but only called `setCookie('te_uid', ...)` inside a
`setOnInteraction` closure registered on `document.click` and `document.scroll`
(both `{ once: true, passive: true }`). Cookie was not written until the user
interacted.

**Replacement (after):** The `setOnInteraction` closure and its two
`addEventListener` calls are gone. In their place, the `else` branch now
calls `setCookie('te_uid', userId, 365)` and `setCookie('te_sn', '1', 365)`
synchronously, immediately after generating the UUID. `cookieReady` is set
to `true` at the same point.

**Cookie attributes confirmed (from `setCookie()` lines 43–53, unchanged):**
- `path=/`
- `max-age=31536000` (365 × 86400)
- `SameSite=Lax`
- `Secure` (only when `location.protocol === 'https:'`)
- No `Domain` attribute (host-only cookie)

---

## data/experiments.json

**v1 status:** changed from `"active"` to `"paused"`. `ended_at: "2026-05-23"` added. `doc` updated to explain contamination and point to v2.

**v2 added:**
- `id`: `harness_aa_v2`
- `status`: `active`
- `started_at`: `2026-05-24`
- `variants`: `[{"id":"control_a","traffic":50},{"id":"control_b","traffic":50}]`
- `doc`: "v2, post tracker.js fix. New experiment ID produces fresh bucketing for every user..."

---

## Tests

**npm test result:** 185 passed (185), 0 failed. 10 test files.
Previous count was 175 (per CHANGELOG 2026-05-04 entry). Delta: +10 tests.

**New regression test file:** `tests/js/tracker-cookie-timing.test.js`
- `tracker.js cookie timing — regression for A.5 bug > writes te_uid cookie before any user interaction on a first-visit page load`
- `tracker.js cookie timing — regression for A.5 bug > te_uid written at load is a valid UUID-like string`
- `tracker.js cookie timing — regression for A.5 bug > te_sn session number cookie is also written eagerly for new users`
- `tracker.js cookie timing — regression for A.5 bug > returning user preserves existing te_uid without overwriting`
- `experiments.js reads the te_uid that tracker.js wrote > getOrMintUid in experiments.js returns the tracker-written te_uid, not an ephemeral id`
- `experiments.js reads the te_uid that tracker.js wrote > same uid produces same variant across first impression and later events`

**aa-experiment-config.test.js changes:** 4 original v1-centric tests replaced
with 8 tests covering: v1 paused config integrity, v1 returns null for all uids,
v1 not in getAllAssignments, v2 active config integrity, v2 10k-uid 47%-53%
split, v2 deterministic, v2 in getAllAssignments (v1 not), v2 v1 independent.

---

## Verification

- `npm test`: 185 passed, 0 failed
- `hugo --gc --minify`: 106 pages, 0 errors (pre-existing WARN on taxonomy/term layout, not introduced here)
- `python3 -c "import json; json.load(open('data/experiments.json'))"`: valid JSON
- experiments.json structure confirmed: 3 experiments (harness_aa_v1=paused, harness_aa_v2=active, _example_disabled=draft)

---

## Open issues for Pranjal to review before merge

1. **Privacy note:** The old lazy-write was almost certainly intentional — writing
   a persistent cookie immediately on page load (without interaction) is a stricter
   data-collection posture. The fix trades that posture for bucketing correctness.
   If the original deferral was a deliberate privacy choice (GDPR consent-before-
   persistent-ID pattern), Pranjal should decide whether to add a consent gate
   instead. The fix as written is correct for the A/B harness requirement; the
   privacy question is HITL.

2. **`harness_aa_v2` clean window start:** The fix deploys on 2026-05-24. Data
   collected before deploy will have the old bug. `analyze_experiments.py` should
   only be run against the post-deploy window. The `started_at: "2026-05-24"` in
   the config is a reference date — the actual clean cutoff is the deploy timestamp.
   Add a `WHERE ts >= <deploy_epoch>` filter to queries or wait for
   `analyze_experiments.py` to grow a `--since` flag before the first v2 readout.

3. **experiments.js ephemeral fallback still exists:** `getOrMintUid()` in
   `experiments.js` still has the fallback path that mints an ephemeral UUID when
   `getCookie('te_uid')` returns empty. This fallback should now fire only in two
   edge cases: (a) a user with DNT/GPC enabled (tracker.js exits early, never
   calls initUserIdentity), (b) a browser that blocks all cookies. Both are
   legitimate scenarios where the ephemeral fallback is the right behaviour. The
   code is correct as-is; documenting for clarity.

4. **Test count discrepancy:** CHANGELOG says suite was 175 after 2026-05-04
   ("+4 tests" from aa-experiment-config.test.js). Current baseline before this
   PR was actually 175. We added 10 net tests (6 new file + 4 aa-config replacements
   → net +4 in that file) = 185 total. The delta is consistent.
