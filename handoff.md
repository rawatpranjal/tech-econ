# Handoff — 2026-05-24 — feat/wrap-2026-05-24

## Where we left off
PR #51 open with /site (Under The Hood) + /dashboard (Live Dashboard) pages, A/A bucketing fix, roadmap, scoreboard pipeline. Branch protection requires 4 CI checks + merge. Local `main` is 1 commit ahead of `origin/main` (the same change as PR #51); sync after merge.

## Active streams (clustered)

**[A] Experimental loop**
- A.1, A.2, A.5, A.6 shipped (in PR #51, not yet deployed).
- A.3 Re1 MMR first treatment — ready to recon. **BLOCKED** on tracker.js deploy + harness_aa_v2 producing clean A/A data for 1-2 days.
- A.7 fresh-agent audit pending.

**[B] Homepage Editorial**
- B.3 + B.4 shipped (in PR #51). **HITL pending**: visual sign-off on Inter Display + type-tinted cards. Open `hugo server`, eyeball homepage.
- B.6 end-of-stream audit pending. SEQUENTIAL.

**[C] Under The Hood + Live Dashboard**
- C.1 through C.11 shipped (in PR #51). 8 explainer tabs + 5 dashboard tabs live.
- C.4 fresh-agent audit on all 13 tabs pending. PARALLEL.

**[F] Ra2 knn-bge default flip**
- Replay row 1 seeded (ndcg@10=0.2275). Need 2+ more metrics.csv rows at same holdout_days before flip. Mechanical once gate clears.

## Decisions made this session
- Public-page voice = editorial, not developer. No em dashes, no internal file paths, no code object names. Real running examples from `data/*.json`. See CLAUDE.md proposed Learned Rules (not yet added; user declined this turn).
- Single bundled PR (not split per stream) — kept atomic so A/A fix ships with new pages.
- Workhorses only, no NN reach. Deep models (two-tower, SASRec, LightGCN) parked in roadmap "Later". LLM-as-reranker later.

## Open questions
- **Privacy posture**: tracker.js now writes `te_uid` eagerly (was deferred until user gesture). GDPR/consent implication if relevant?
- **URL rename**: `/site/` URL still says `/site/` even though label says "Under The Hood". Rename to `/under-the-hood/`?
- **Scoreboard cadence**: `scripts/build_site_scoreboard.py` runs manually before deploy. Wire to schedule?
- **ADMIN_KEY**: secrets.env has placeholder `PASTE_FROM_CLOUDFLARE_DASHBOARD_OR_ROTATE`. Paste real value or rotate via wrangler.

## Landmines / gotchas
- **Tracker.js fix unshipped**: lives in PR #51. Until merged + Cloudflare-deployed, harness_aa_v2 also collects contaminated data. Worker schema already has the column (PR #46).
- **Build-time scoreboard staleness**: `data/site_scoreboard.json` snapshot at last `build_site_scoreboard.py` run. Tabs go stale until rerun. Rerun before each deploy.
- **Local main 1 commit ahead of origin**: after PR #51 merges, do `git fetch && git pull origin main` (or `git reset --hard origin/main` if no local-only work; but reset is destructive, ask first).
- **Pre-existing pytest failures**: `tests/python/test_d1_sessions.py` 7 stubs failing, unrelated to this work. Pre-existing from earlier session.
- **CLAUDE.md line 177**: fixed this session (`search-cache.js` → `static/js/search/search-cache.js`).

## Suggested next move
Watch PR #51 CI. When green, merge + deploy via Cloudflare so tracker.js fix lands. Then monitor harness_aa_v2 for 1-2 days; once split is healthy, recon A.3 (Re1 MMR first treatment).
