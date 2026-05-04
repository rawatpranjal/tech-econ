# RULES — strict protocols for working in this repo

This file is **load-bearing**. CLAUDE.md links here. Every working session begins by glancing at this list. Lines are imperative on purpose — "always" / "never" mean what they say.

The three sections below are ordered by priority:
1. **HARD STOPS** — things that, if violated, can damage production, lose work, or silently corrupt data. These are non-negotiable.
2. **REQUIRED RITUALS** — process that prevents wasted effort and false-positive "done" claims.
3. **REPO-SPECIFIC GOTCHAS** — the canonical list of things in this repo that look fine but break in non-obvious ways.

Each entry includes **Why** (the underlying incident or principle) and **How to apply** (the concrete check or action). Skipping the why makes future-us ignore the rule when an edge case shows up.

---

## 1. HARD STOPS — NEVER

### NEVER skip the worker schema migration after editing `analytics-worker/index.js`
- **Why:** On 2026-03-26 a column was added to an INSERT in the worker but the matching ALTER never ran in D1. Result: 5-week silent analytics blackout — `/events` returned 200 OK while every D1 write rejected. Reranks ran with zero engagement signal.
- **How to apply:** If the worker's INSERT/SELECT touches a column not in the schema file, add it to `handleRunSchema` (idempotent) AND hit `GET /run-schema?key=$ADMIN_KEY` immediately after `npx wrangler deploy`. Verify via `/health` that `last_write_age_seconds < 3600` and `write_errors_today=0` BEFORE moving on.

### NEVER run a rerank when `/health` is degraded
- **Why:** Same incident. `rank_all_content.py --source=api` will refuse if `/health.status=degraded`. Bypassing with `--ignore-stale` rubber-stamps a model trained on zero data and overwrites production scores. Items with engagement count silently drops to 0 and the homepage is filled with cold-start k-NN noise.
- **How to apply:** Before any rerank, `curl https://tech-econ-analytics-v2.pp712.workers.dev/health | python3 -m json.tool`. If degraded, follow the recovery runbook in `CLAUDE.md` — schema replay + smoke test — before touching the ranker.

### NEVER `git checkout` inside `autoresearch/run.sh`
- **Why:** `autoresearch/` runs concurrent sessions in isolated `/tmp/` worktrees so they don't collide with the main checkout. Past commits switched it back to `git checkout` and concurrent sessions deleted each other's files mid-write.
- **How to apply:** If you're touching `autoresearch/run.sh`, the `git worktree add /tmp/...` block is load-bearing. Don't "simplify" it.

### NEVER commit `.claude/secrets.env`, D1 backups, or `data/.cache/` artifacts
- **Why:** D1 dumps contain raw IPs and weak user IDs. Secrets are obvious. Caches bloat the repo and rot fast.
- **How to apply:** `.gitignore` already covers these. Before any `git add -A`, run `git status` and confirm no `secrets.env` / `backups/*.sql` / `.cache/` paths are listed. Prefer `git add <specific files>` over `-A` / `.`.

### NEVER edit `papers.json` and `papers_flat.json` independently
- **Why:** Dual representation. `papers.json` is the authoring source (nested by topic/subtopic); `papers_flat.json` is the rendered-flat version that ranking + search consume. Editing one without the other desyncs them silently.
- **How to apply:** Edit `papers.json` only. Regenerate `papers_flat.json` via the existing build step before committing.

### NEVER use `--no-verify` / `--no-gpg-sign` / `-c commit.gpgsign=false` to bypass a hook
- **Why:** Pre-commit hooks here run `validate_data.py` and JSON parse. Skipping them ships malformed data. Bypassing the signing config makes provenance unclear later.
- **How to apply:** If a hook fails, fix the underlying issue. Re-stage. Make a NEW commit (don't `--amend` after a hook-blocked commit; the prior commit is still there and the amend would silently rewrite it).

### NEVER claim a UI change "works" without a browser test
- **Why:** Type-check and unit tests verify code correctness, not feature correctness. A re-rank script that compiles can still fail to render a card; a CSS change that lints can still leave a row invisible.
- **How to apply:** For any UI/frontend change, run `hugo server` locally and exercise the feature path before reporting done. If the harness can't open a browser, **say so explicitly** in the report. Phrase: "I have not tested this in a browser; please verify the path X manually." Do not paper over with "looks good" / "should work."

### NEVER mark a task "completed" with failing tests, partial implementation, or unresolved errors
- **Why:** Stale "completed" tasks lie to future-us. We start the next session thinking work is done that isn't.
- **How to apply:** Status stays `in_progress` until tests pass AND the change is end-to-end verifiable. When blocked, create a follow-up task describing exactly what's outstanding.

### NEVER act on subagent claims about "NOT DONE" without verifying the file yourself
- **Why:** This session burned ~20 minutes planning PRs for R1 and R3. R3 was already shipped — the Explore agent reported it as missing because it grepped for the wrong pattern and missed `renderHistorySection()` in `reading-history.js`. R1 turned out to have no target architecture.
- **How to apply:** Subagent says "X is missing"? Open the relevant file end-to-end (Read, no offset/limit) and confirm. "Subagent says it's missing" is a hypothesis, not a fact. The cost of one extra read is far below the cost of building a duplicate of a feature that already exists.

---

## 2. REQUIRED RITUALS — ALWAYS

### ALWAYS verify audit/plan freshness before executing
- **Why:** Audit docs decay. The audit at `.claude/outputs/manager/recsys-audit-2026-05-03.md` was one day old when consulted on 2026-05-04 and three of its "TODO" items were already done.
- **How to apply:** When a plan or audit doc is more than ~3 days old, treat its status claims as hypotheses. Spot-check 3 random items against the current code before acting on the rest. If you find one stale claim, the whole doc is suspect — re-verify or write a "STATUS AS OF" addendum like the one at the top of the recsys audit.

### ALWAYS verify file paths and helper functions exist before recommending reuse
- **Why:** The original Ra4 plan said "reuse `search-cache.js:getEmbedding(id)`". That helper does not exist — search-cache only has blob-level access. Building Ra4 against a non-existent helper would have produced runtime errors.
- **How to apply:** When a plan says "reuse X", grep for X. When a plan says "modify file Y", `ls` it. Plans that assume code into existence will produce broken implementations.

### ALWAYS run validation + build before committing
- **Why:** No CI on the dev loop catches broken JSON until merge time. Validation is fast (<5 sec); the build is fast (<30 sec).
- **How to apply:** Before any commit that touches `data/*.json`, `static/`, or `layouts/`:
  ```
  python3 scripts/validate_data.py && npm run build && npm test
  ```

### ALWAYS write pure-helper tests for new client-side modules
- **Why:** Browser testing is not always available. Pure helpers can be exercised in jsdom without a server. Catches regressions early.
- **How to apply:** Mirror the pattern in `tests/js/because-you-viewed.test.js` and `tests/js/personalize.test.js`. Public API on `window.X` for testability. Each pure function gets a describe block; init() gets an end-to-end describe with mocked `fetch` + `window.TechEconHistory`.

### ALWAYS append to CHANGELOG.md under today's date when finishing work
- **Why:** Future-us reading the changelog should be able to reconstruct what shipped without `git log` archaeology.
- **How to apply:** 1-2 line entry. Lead with what shipped (PR number if known), then a one-clause "why". Archive to `.claude/history/changelog-YYYY-MM-DD.md` when CHANGELOG.md exceeds ~150 lines.

### ALWAYS keep `model_score` propagation through the rerank
- **Why:** `update_rankings.sh` was running `rank_all_content.py` then *skipping* `inject_scores.py` for 5 weeks (until PR #29). Hugo templates read `model_score` from the source files, so the homepage was frozen for 5 weeks while looking like it was reranking.
- **How to apply:** Touch `update_rankings.sh`? Verify the chain `rank_all_content.py` → `inject_scores.py` → write to `data/*.json` is intact. The homepage rendering depends on `data/{books,career,community,datasets,packages,papers_flat,resources,talks}.json`'s per-item `model_score`.

### ALWAYS pause and ask when scope shifts mid-session
- **Why:** The user said "let's crank through" but the plan was based on a stale audit. Three of three planned PRs turned out to be moot. Continuing without re-scoping would have been wasted work.
- **How to apply:** If verification reveals the plan's premises are wrong, STOP and use `AskUserQuestion`. Do not silently rewrite the plan. The user knows things you don't (priorities, deadlines, what's measurable now).

---

## 3. REPO-SPECIFIC GOTCHAS

### Architecture surprises
- **No per-item single pages exist.** Cards on every list page link out via `target="_blank"` to external URLs. Only `papers/single.html` exists, and it's a *topic* page (lists all papers in a topic), not a per-paper detail page. Plans assuming "render X on each item's detail page" need to pivot to list-page hover, search-result hover, or topic-page footer.
- **`reading-history-section` placeholder has `display: none` because that's the empty state.** Don't read the static markup as "feature not built." `static/js/reading-history.js:121` `renderHistorySection()` flips it to `block` once history exists. Same applies to `because-you-viewed-section`.
- **`search-cache.js` is an IndexedDB cache wrapper, not an embeddings index.** It exposes `getEmbeddings()` (blob-level) and `setEmbeddings()`, no `getEmbedding(id)` helper. The 16 MB embedding binary loads lazily after first search. Don't trigger that download on the homepage critical path.
- **Two embedding sets exist for different purposes.** `static/embeddings/related-items.json` (1.4 MB, top-5 neighbours per item) is fetched eagerly by `because-you-viewed.js` and is the right reuse target for any homepage personalization. `static/embeddings/search-embeddings.bin` (16 MB, full bge-large 1024d vectors) is search-only.
- **Hugo cards expose `data-name` lowercased.** When matching cards to embedding ids, you must lowercase both sides. `search-metadata.json` carries names in original case.

### Worker / D1
- See HARD STOPS for the schema migration rule.
- The v2 worker is at `tech-econ-analytics-v2.pp712.workers.dev` (D1 DB `1515d5fb`). The old worker at `tech-econ-analytics.rawat-pranjal010.workers.dev` is read-only rollback — don't write to it.
- `/events-raw` (admin-protected, requires `ADMIN_KEY`) is the eval gate's HTTP path. If the key is set but the endpoint 401s, the gate falls back to wrangler subprocess.

### Eval scoreboard
- `reports/metrics.csv` is the source of truth for offline ranker quality (NDCG@10, Hit-Rate@10, etc.). Each row is one rerank.
- `reports/replays.csv` records baseline-vs-candidate replays from `replay_eval.py` for ad-hoc A/Bs.
- The eval gate refuses rerank-of-rerank comparisons when `holdout_days` differs (apples vs oranges). If you change the holdout config, accept that the next row breaks the regression check until N≥2 rows accumulate at the new value.
- **Do not flip a default in the ranker until the scoreboard has at least 2-3 baseline rows at the same `holdout_days`.** N=1 + N=15 sessions cannot tell signal from noise.

### Static-site quirks
- `npm run build` does Hugo + Pagefind. `hugo server` does not run Pagefind, so the search modal will be stale during dev.
- `static/embeddings/*.bin` files are git-tracked — they regenerate via `scripts/generate_embeddings.py` and must be re-committed when content changes meaningfully.

---

## 4. WHEN IN DOUBT

- **Reversibility test:** If the action can be undone with one command, proceed. If it requires history rewriting, third-party clean-up, or a deploy, ASK FIRST.
- **Blast-radius test:** If the action affects only the local checkout, proceed. If it pushes, deploys, modifies a shared system, sends messages, or uploads to a third-party tool, ASK FIRST.
- **Authorization scope:** A user approving one git push does not approve all future pushes. Treat each session's approvals as scoped to that session's tasks.

---

*This file is canonical. When CLAUDE.md and this file disagree, this file wins. When this file and reality disagree, fix the file — but only after verifying reality is what you think it is.*
