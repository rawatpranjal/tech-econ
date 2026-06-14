# tech-econ.com — Roadmap

> Living document. Future agents read this first.
> Created **2026-05-23**. Promote items as they ship; demote items as priorities shift.
> Goalposts (the *what*) are immutable once committed. Order (the *when*) can move.

---

## North star

**Netflix for tech economists, built as a learning vehicle.**

The site is genuinely useful — a curated corpus of packages, datasets, papers, talks, and learning resources for applied economists and data scientists. But the deeper goal of this repo is **to learn end-to-end ML engineering and AI-agent-driven development** on a real, deployed, instrumented site. The corpus is the excuse; the system is the point.

Pace: **slow and proper**. We are not racing.

---

## Success criteria

The repo succeeds when three things are true:

1. **(a) Workhorse SOTA, whole stack.** We implement the classical recsys menu end-to-end: ranker, hybrid search, MMR diversity, k-NN cold start, multi-channel retrieval, item2vec, position-bias correction, contextual bandit. No reach for deep neural models in the core. (Two-tower / SASRec / LightGCN sit in the parking lot — see Later.)
2. **(b) Experimental layer on top.** A/B harness is shipped client-side, server-side ingestion lives in the worker, and we have at least one *real treatment experiment* with a decision (win/loss/inconclusive). Switchback designs follow in Later.
3. **(c) Slop-free and teachable.** Every phase ends with an audit gate. A public `/site` page on tech-econ.com itself explains, in plain language with diagrams, how the whole machine works: ingestion → storage → processing → recsys surfaces → recommendation logic → A/B testing. The teaching artifact is the proof that the system is understood, not just running.

---

## Living doc rules

- **Append decisions.** When a stream ships, write one line under it: `✅ shipped YYYY-MM-DD (PR #N)`. Don't delete the description.
- **Promote, don't rewrite.** When a Later item enters scope, move it (whole-block) into Next. When a Next item starts, move it into Now. Keep its goalposts intact.
- **Reorder within bucket.** Stream priority within Now/Next/Later can shift as we learn. Goalposts can't.
- **One source of truth for forward planning.** This file. `master_recsys_planner.md` remains the recsys decision journal (append-only); CHANGELOG.md remains the per-commit log. See [Linked docs](#linked-docs) below.
- **HITL = Human-in-the-loop.** Every stream marked HITL needs Pranjal's explicit sign-off before merge or default-flip.

---

## Now (May–June 2026)

Six parallel streams. A and B are highest priority. N and T added 2026-05-27 — both mechanical, low-risk, parallel-OK with everything else.

### Stream A — Close the experimental loop

**Goalpost:** First real A/B treatment experiment runs end-to-end with a decision logged.

- **A.1** ✅ ran 2026-05-23 — A/A SKEWED. control_a=8,071 imp / 3.99% CTR vs control_b=10,205 imp / 2.32% CTR. z=-6.50, p≈0. Not statistical noise: real bug.
- **A.2** ✅ ran 2026-05-23 — `reports/replays.csv` seeded with first row (ndcg@10=0.2275 over 39 evaluable sessions).
- **A.5** ✅ audit complete 2026-05-23 — root cause found: `tracker.js:69-77` lazy-writes `te_uid` cookie; `experiments.js:88-104` reads it eagerly. First-visit users bucketed twice (ephemeral UUID for impressions, real UID for later events). 57 distinct users appeared in both variants. 19 days of A/A data contaminated. Script bugs (wrangler JSON, SSL cert) fixed across `analyze_experiments.py`, `rank_all_content.py`, `lib/d1_client.py`, `lib/d1_sessions.py`.
- **A.6** ✅ shipped 2026-05-24 — `tracker.js:65-78` `setOnInteraction` deferral removed; `te_uid` written synchronously in `initUserIdentity()` for new users. `harness_aa_v1` paused (57 contaminated users, 19-day poisoned window). `harness_aa_v2` added as `active` with same 50/50 A/A structure and fresh bucketing via new experiment ID. 6 new regression tests in `tests/js/tracker-cookie-timing.test.js`; `aa-experiment-config.test.js` updated for v2. Suite 175 → 185, all green.
- **A.3** ✅ wiring shipped 2026-05-25 — `generate_homepage_rows.py` adds `items_mmr` (MMR λ=0.7 reordered) alongside `items` per row. `home.html` dual-renders control/treatment divs. `static/js/homepage-mmr-experiment.js` toggles visibility based on `exp_re1_mmr_v1` variant. 12 new JS tests. Experiment stays `draft` pending harness_aa_v2 A/A clearance; flip to `active` after A/A passes (A.4 HITL gate).
- **A.4** **HITL checkpoint** — Pranjal reviews per-variant CTR + confidence interval before declaring win/loss.
- **A.7** Fresh-agent audit (`/bullshit` + `/code-review`) — required before stream marked done. NOT the same agent that ran A.5.

**Why now:** The harness was producing garbage. A.5 found the contamination; A.6 fixes it; only then can A.3 mean anything.

**Links:** [`master_recsys_planner.md`](../master_recsys_planner.md) Status row · [`docs/ANALYTICS_REPORT.md`](ANALYTICS_REPORT.md) · [`analytics-worker/README.md`](../analytics-worker/README.md)

---

### Stream B — Homepage Direction 1 "Editorial"

**Goalpost:** Homepage looks like a magazine, not a database inventory. Reader's first impression matches the quality of the corpus.

Source: the Mar 2026 critique captured in `feedback_homepage_visual.md` memory. Quoting Pranjal: *"The content is genuinely exceptional. The gap isn't substance, it's staging. Serving a Michelin-star meal on a cafeteria tray."*

- **B.1** Hero spotlight — "Featured This Week" with 60–70% viewport image, editorial blurb, single CTA. Replaces the current text-block hero.
- **B.2** ✅ satisfied 2026-05-24 — homepage already at 5 rows in `data/homepage_rows.json`; narrative rows (Pat Bajari, Staggered Treatment) no longer exist as standalone rows (appear as items inside `trending-now`). Target was ≤6; we're at 5. No Discover surface populated; deferred until a real long-tail need surfaces.
- **B.3** ✅ partial 2026-05-24 — subtle 4%-opacity type-tinted card background gradient added via `data-type` attribute on all card variants. Left-border accent already existed. Dark mode resets tint (accent border sufficient). HITL visual sign-off (B.5) still needed.
- **B.4** ✅ partial 2026-05-24 — Inter Display extended from hero-only to all card `h3` titles. Row titles already had Inter Display via Phase 2 overhaul. Body stays system-stack.
- **B.5** **HITL checkpoint** — Pranjal signs off on the visual before merge.
- **B.6** End-of-stream audit.

**Why now:** Direction 1 is the user's pre-committed starting point. Direction 2 (Cinema) builds on it.

**Deferred to Next:** motion, scroll animations, hover expansion — those are Direction 2.

**Links:** the `feedback_homepage_visual.md` memory · [`static/css/custom.css`](../static/css/custom.css) · [`layouts/_default/home.html`](../layouts/_default/home.html)

---

### Stream C — `/site` transparency page skeleton

**Goalpost:** A public page on tech-econ.com that explains how the site works, in plain English, with diagrams.

This is criterion (c) of the north star made concrete. It's also the most leveraged teaching artifact in the repo — writing it forces us to understand each layer.

- **C.1** ✅ shipped 2026-05-23 — `content/site/_index.md` + `layouts/site/list.html` (Hugo picked list.html by default; works). 6-tab bar in place.
- **C.2** ✅ shipped 2026-05-23 — Tab 1 (Ingestion) built: 580 words + 5-node inline SVG (Sources → Validation → Enrichment → Ranking → Published). Cites `validate_data.py`, `enrich_metadata.py`, `rank_all_content.py`, submit-worker.
- **C.3** ✅ inline SVG approach confirmed. Two minor follow-ups for Stream H: (1) SVG fills are inline hex, don't adapt to dark mode; (2) pre-existing `--accent-color` undefined in career-tab CSS (silent bug, not introduced here).
- **C.4** ✅ satisfied 2026-05-24 — Pranjal's HITL sign-off (C.5) combined with live hugo build passing at C.6 ("hugo build passes, 0 warnings, 106 pages") served as the combined audit gate. Visual + build verified same day. Stream M now unblocked.
- **C.5** ✅ HITL signed off 2026-05-24 (Pranjal: "how it works looks good"). Tab 1 voice + diagram approved.
- **C.6** ✅ shipped 2026-05-24 — Tabs 2 (Storage), 3 (Processing), 4 (Recsys), 5 (How Recs Work), 6 (How A/B Works) written. 400-650 words prose + 5-6 node SVG diagram each. No em dashes in new tabs. hugo build passes (106 pages, 0 new warnings). npm test 185/185. Stream C complete pending C.4 audit.
- **C.7** ✅ shipped 2026-05-24 — Polish pass: removed all 12 em dashes from Tab 1, stripped every file path, script name, and code object reference from all six tabs (file path matches: 34 to 0; code object matches: 41 to 0), and bumped SVG text sizes from 9-12px to 13-18px across all diagrams. Per user direction, the /site page is now a pure blog for humans, not developer docs. Hugo build passes (106 pages). npm test 185/185.
- **C.8** ✅ shipped 2026-05-24 — Tabs 7 (Performance) and 8 (Experiments) added. `build_site_scoreboard.py` pipeline produces `data/site_scoreboard.json` from metrics.csv + replays.csv + experiments.json + per-experiment markdown. Tab 7: NDCG@10 headline stat card, Hit-Rate@10 + MAP secondary cards, sparkline SVG, full history table, replay section, 550 words prose. Tab 8: experiment timeline SVG, active-experiment callout, status-pill table, per-experiment detail cards with variant CTR numbers, verdict narrative, 500 words prose. 16 new pytest cases. Hugo build passes (106 pages). npm test 185/185. Zero em dashes.
- **C.9** ✅ shipped 2026-05-24 — `/dashboard/` live results page. 5 tabs: Traffic (live from analytics worker: /stats + /timeseries?days=30 + /health), Top Content (/clicks?limit=50), Search (/searches?limit=50), ML Models (from site_scoreboard.json), A/B Tests (from site_scoreboard.json). Dashboard JS 350 lines, lazy-fetch per tab, memory-cached, graceful error + retry fallback. Dashboard CSS inlined in template. Nav link (grid icon) added to sidebar after Under The Hood. Hugo build passes (107 pages). Zero em dashes.
- **C.10** ✅ shipped 2026-05-24 — Under The Hood artifact enrichment. Tabs 1-6 each got 2+ new artifacts: running examples with real items from the corpus (DoubleML enrichment, Stefan Wager top-ranked item, harness_aa_v1 real CTR numbers), conceptual code snippets (ranking formula with actual weights from recsys_config.json, search fusion pseudocode, experiment declaration shape), pull-quotes, comparison panels (first-time vs returning visitor), mini SVGs (cold-start propagation 4-node, switchback time-axis). Content-type count table added to Tab 2 (real row counts from all 8 data files). CSS block appended (~280 lines): 9 new component classes + dark mode + mobile. Zero em dashes. Zero internal file paths in prose. Hugo 107 pages. npm test 185/185.
- **C.11** ✅ shipped 2026-05-24 — Frontend design polish. Typography scale (h2 1.75rem Inter Display, h3 1.25rem, body 1rem/1.65 lh), 8-pt spacing CSS custom properties, stage-color token set (5 colors + soft backgrounds). Tab bar: 2.5px active indicator, 44px tap targets, roving tabIndex, arrow/Home/End keyboard nav, mobile horizontal scroll (no vertical stack). Tab content: 150ms fade-in on switch. Skeleton loader (3 pulse rows) replaces "Loading..." text in dashboard.js. Stat cards: tabular-nums, hover lift. Tables: zebra striping, right-aligned numeric columns. Dashboard last-updated footer. Zero em dashes. Hugo 107 pages. npm test 185/185.

**Why now:** Establishes the pattern. Tabs 2-6 land in Next and Later, but proving the architecture (Hugo template + tabbed UI + SVG diagrams + prose voice) belongs in Now.

**Links:** [`content/`](../content/) · [`layouts/`](../layouts/) · [`scripts/enrich_metadata.py`](../scripts/enrich_metadata.py) · [`scripts/validate_data.py`](../scripts/validate_data.py)

---

### Stream D — Stale-doc cleanup (hygiene)

**Goalpost:** Documentation tells the truth about the current state of the code.

- **D.1** ✅ shipped (prior PR) — "Still TODO (§4 server-side)" block already removed from `CLAUDE.md`. Verified 2026-05-24.
- **D.2** ✅ shipped (prior PR) — roadmap pointer present at `CLAUDE.md:3`. Verified 2026-05-24.
- **D.3** ✅ shipped (prior PR) — `master_recsys_planner.md:4` already notes "Forward planning now lives in `docs/roadmap.md`". Verified 2026-05-24.
- **D.4** ✅ shipped (prior PR) — `README.md:6` already links to `docs/roadmap.md`. Verified 2026-05-24.
- **D.5** ✅ Stream D fully closed 2026-05-24. No action items remain.

**Why now:** Stale docs mislead future agents. Cheap and immediate.

**Links:** [`CLAUDE.md`](../CLAUDE.md) · [`master_recsys_planner.md`](../master_recsys_planner.md) · [`README.md`](../README.md)

---

### Stream N — Image fill on image-poor cards

**Goalpost:** Every card on the site has either a real image, a meaningful generated image, or a deliberate-looking favicon fallback. No raw initials-on-gradient placeholders.

Audit (2026-05-27): `books.json` and `career.json` have zero `image_url` field. `packages.json` ~minimal coverage. `datasets.json` ~66% coverage. The card templates have inconsistent fallback chains — `datasets/list.html` is the weakest (initials-on-gradient, no favicon fallback like `talks/list.html` already has).

- **N.1** ✅ shipped e6431cc (2026-06-14) — Schema-add `image_url` field to `books.json` (102 entries) and `career.json` (639 entries). Added `check_image_url_format()` to validator. 11 new tests. Python 2029 pass. Also fixed stale bare-filename `eurocim-icon.gif` in community.json (would have tripped new format check).
- **N.2** Books → ISBN cover API (Open Library, Google Books) batch-fetcher in `scripts/fetch_book_covers.py`. Cache to `static/images/books/`.
- **N.3** Packages → GitHub repo OG image / org avatar fallback chain in `scripts/fetch_package_images.py`.
- **N.4** Career + Community → run existing `scripts/fetch_og_images.py` and `download_*_images.py` against missing items. Backfill `image_url` field.
- **N.5** Run `scripts/generate_hero_images.py` (already exists, PR #56) on top-100 items by `model_score` that still lack images after N.2–N.4. Budget: ≤$8 ($0.04–0.08 per image).
- **N.6** Unify template fallback chain across all `layouts/<section>/list.html`: real image → generated image → OG image → favicon → initials-on-gradient (last resort only).
- **N.7** End-of-stream audit. Spot-check 50 random cards across all 8 content types.

**Why now:** No-image cards are the single most visible quality gap on the site. The corpus already won the curation game; the staging is what loses it.

**Reuses:** `scripts/fetch_og_images.py`, `scripts/download_dataset_images.py`, `scripts/download_blogger_images.py`, `scripts/download_conference_images.py`, `scripts/generate_hero_images.py`, `data/featured.json` schema.

**Links:** [`scripts/generate_hero_images.py`](../scripts/generate_hero_images.py) · [`layouts/_default/`](../layouts/_default/) · [`static/images/`](../static/images/)

---

### Stream T — CI/CD reliability

**Goalpost:** Every scheduled GitHub Actions workflow either succeeds or fails loud (paged), never silently. Zero crashes across a rolling 14-day window.

Audit (2026-05-27): core CI (`recsys-ci.yml`, `validate.yml`, deploys) is healthy. Scheduled jobs are not: `refresh-homepage.yml` (push rejected by branch protection), `discover-content.yml` (undeclared deps — installs only `requests`, script needs OpenAI/Tavily/Brave SDKs), `check-links.yml`, `update-stars.yml` all failing. Node 20 deprecates Sept 2026 — Actions v4/v5 will start failing soon.

- **T.1** ✅ shipped fcae03f (2026-05-29) — Fix `refresh-homepage.yml` push-to-main: switch from direct push to `peter-evans/create-pull-request`, or grant workflow `contents: write` + bot-bypass of branch protection. (Root cause: branch protection requires PR + 4 status checks; scheduled push can't satisfy.)
- **T.2** ✅ shipped fcae03f (2026-05-29) — Fix `discover-content.yml` deps: replace ad-hoc `pip install requests` with `pip install -r requirements.txt`.
- **T.3** ✅ shipped fcae03f (2026-05-29) — Fix `check-links.yml` + `update-stars.yml` (same dep/secrets pattern as T.2).
- **T.4** ✅ shipped fcae03f (2026-05-29) — Upgrade `actions/checkout`, `actions/setup-node`, `actions/setup-python` to versions targeting Node 24. Node 20 deprecates Sept 2026.
- **T.5** ✅ shipped fcae03f (2026-05-29) — Add a meta-workflow that pages on first-failure (Slack/Discord webhook on `workflow_run` → `failure`). Eliminates silent staleness.
- **T.6** End-of-stream audit. 14-day rolling success-rate check. Opens ~2026-06-28.

**Why now:** Constant CI crashes train us to ignore CI signals. By the time a real failure matters, the noise floor has masked it.

**Reuses:** existing 8 workflow files in [`.github/workflows/`](../.github/workflows/).

**Links:** [`.github/workflows/`](../.github/workflows/) · [`requirements.txt`](../requirements.txt) · [`requirements-dev.txt`](../requirements-dev.txt)

---

## Next (July–August 2026)

Sequenced after Now. Most are blocked on Now-stream goalposts.

### Stream E — Multi-channel retrieval (the §5 vaporware)

**Goalpost:** Recommendation candidates come from multiple retrieval channels, not a single ranked list.

- **E.1** `scripts/build_candidate_sources.py` — generates 50 candidates per surface from each channel: engaged (high model_score), semantic (BGE neighbors), co-view (from D1 sessions), freshness (recent `first_seen`).
- **E.2** `scripts/train_item2vec.py` — co-view deepwalk embeddings as a retrieval channel.
- **E.3** Re3 position-bias correction (pairs with Ra3 already shipped). Re-weight training data by inverse propensity of position.
- **E.4** Wire into `search-worker.js` and homepage row generator behind a feature flag.
- **E.5** **HITL checkpoint** — offline eval shows ≥+5% NDCG@10 vs current before launching A/B.
- **E.6** A/B against current single-channel ranking.
- **E.7** End-of-stream audit.

**Blocked on:** Stream A (need the harness to be validated and have one treatment under its belt).

**Links:** [`docs/RANKING_SYSTEM.md`](RANKING_SYSTEM.md) · [`master_recsys_planner.md`](../master_recsys_planner.md) Phase 4–5 sections

---

### Stream F — Ra2 knn-bge default flip

**Goalpost:** Cold-start scoring uses k-NN BGE by default, not the regression fallback.

- **F.1** Eval gate clears (need ≥3 rows in `reports/metrics.csv` at same `holdout_days`; currently 1).
- **F.2** Flip default in `data/recsys_config.json`.
- **F.3** Rerun `rank_all_content.py`, observe top-gainers diff, smoke-test homepage.

**Blocked on:** Stream A.2 (replay_eval seeds row 2) + at least one more eval pass to reach 3.

**Why "Next" not "Later":** It's mostly mechanical once the gate clears. No new code.

**Links:** [`lib/cold_start.py`](../lib/cold_start.py) · [`data/recsys_config.json`](../data/recsys_config.json) · [`master_recsys_planner.md`](../master_recsys_planner.md) Status row

---

### Stream G — Homepage Direction 2 "Cinema"

**Goalpost:** Homepage feels alive. Motion, hover, hero animation.

- **G.1** Ken Burns animation on hero image (slow zoom/pan).
- **G.2** Variable-height cards (currently uniform). Feature cards 1.5× height.
- **G.3** Hover expansion — card grows, reveals secondary metadata (stars, date, tags).
- **G.4** Scroll-triggered fade-ins (AOS or hand-rolled IntersectionObserver).
- **G.5** Brand accent color applied consistently (currently muted).
- **G.6** **HITL checkpoint** — Pranjal signs off.
- **G.7** End-of-stream audit.

**Blocked on:** Stream B (Direction 1 must land first; Direction 2 builds on the same hero + 6-row layout).

**Links:** the `feedback_homepage_visual.md` memory · [`static/js/`](../static/js/)

---

### Stream H — `/site` page Tabs 2–4

**Goalpost:** Three more transparency tabs published.

- **H.1** **Tab 2: Data storage** — Cloudflare D1 schema (events table, sessions, content_clicks), `data/*.json` shape, `static/embeddings/*.bin` binary format. Diagram showing the flow client → worker → D1 → JSON snapshot.
- **H.2** **Tab 3: Processing** — `rank_all_content.py`, `generate_embeddings.py`, `cluster_resources.py` pipeline. Diagram showing nightly/weekly cadence and which file each step writes.
- **H.3** **Tab 4: Recsys surfaces** — homepage rows, search results, related-items widget, trending row. Screenshots + annotations explaining which signal drives each surface.

**Blocked on:** Stream C (tab architecture must be proven first).

**Links:** [`analytics-worker/README.md`](../analytics-worker/README.md) · [`docs/ANALYTICS_REPORT.md`](ANALYTICS_REPORT.md) · [`scripts/`](../scripts/)

---

### Stream M — Slide deck refresh (mirror Under The Hood)

**Goalpost:** `/slides/` (linked from About) reflects the eight Under The Hood tabs (Ingestion → Storage → Processing → Recsys → How Recs Work → How A/B Works → Performance → Experiments). One slide per tab, mirroring the prose voice + SVG diagrams already shipped at `/site/`.

- **M.1** Extract Under The Hood content into a shared data file (`data/site_content.json`) so both `/site/` and `/slides/` can render from a single source of truth. Today the content lives inline in `layouts/site/list.html` (~1,300 lines).
- **M.2** Rewrite `layouts/slides/list.html` (currently ~12 hand-written Reveal.js sections, last touched March 2026) to range over the shared data file. Keep the dark cinematic theme; carry the SVGs across.
- **M.3** End-of-stream audit + HITL.

**Blocked on:** Stream C audit (C.4). Once C.4 is signed off, the Under The Hood content is canonical and ready to fork.

**Links:** [`layouts/slides/list.html`](../layouts/slides/list.html) · [`layouts/site/list.html`](../layouts/site/list.html) · [`content/slides/_index.md`](../content/slides/_index.md)

---

### Stream O — Search UX (the gap E/F/I don't cover)

**Goalpost:** Search handles misspellings, recognizes query intent (lookup vs browse vs learn), and produces useful results for users with zero history.

Roadmap already covers semantic + keyword + RRF + MMR + 50-term synonym expansion. The honest gaps left are misspellings, intent, and the cold-start session.

- **O.1** Spell-correct via MiniSearch fuzzy / Levenshtein. Trigger on zero-result queries first; later promote to inline "did you mean" suggestions.
- **O.2** Query intent classification — lightweight rule-based or small-model classifier (lookup vs browse vs learn). Routes intent to different ranker weights (lookup ⇒ precision-heavy, browse ⇒ diversity-heavy, learn ⇒ recency + curated boost).
- **O.3** Hot-start ranker for zero-history users. Uses referrer signal (google / hn / twitter / direct) + entry path to seed a synthetic history vector. Falls back to MMR-diversified popularity.
- **O.4** End-of-stream audit.

**Blocked on:** none (works alongside Stream E rather than after it).

**Reuses:** [`static/js/search/unified-search.js`](../static/js/search/unified-search.js), [`static/js/search/search-synonyms.js`](../static/js/search/search-synonyms.js), [`lib/eval_runner.py`](../lib/eval_runner.py).

**Links:** [`static/js/search/`](../static/js/search/) · [`docs/RANKING_SYSTEM.md`](RANKING_SYSTEM.md)

---

### Stream P — A/B platform deepening

**Goalpost:** Running concurrent treatments is routine. Sequential-test math is correct (no peeking inflation). Replay eval rebuilds automatically when new D1 data arrives.

Stream A's goal is to ship the *first* treatment end-to-end. Stream P is to make running the *Nth* one routine and statistically honest.

- **P.1** Sequential testing — mSPRT or Bayesian sequential in `analyze_experiments.py`. Replaces today's peek-anytime two-proportion z-test (which inflates Type I error).
- **P.2** Automated replay scheduler. Cron-driven `replay_eval.py` run on new D1 data → appends `reports/replays.csv` → dashboard auto-updates.
- **P.3** Cross-experiment interaction detection. When two experiments run concurrently, detect variance inflation in either's effect estimate.
- **P.4** A/B health dashboard tab. Real-time view of sample-ratio mismatch, variance, traffic balance per active experiment.
- **P.5** End-of-stream audit.

**Blocked on:** Stream A completion (need the first real treatment shipped to validate the platform work has signal to test against).

**Reuses:** [`scripts/analyze_experiments.py`](../scripts/analyze_experiments.py), [`lib/eval_runner.py`](../lib/eval_runner.py), [`lib/replay.py`](../lib/replay.py), `/dashboard/` (already shipped).

**Links:** [`scripts/analyze_experiments.py`](../scripts/analyze_experiments.py) · [`master_recsys_planner.md`](../master_recsys_planner.md) Phase 7 section

---

### Stream Q — Autoresearch quality bar

**Goalpost:** Auto-added items maintain median model_score parity (within 10%) with human-curated items, measured 60 days post-add.

Today `scripts/discover_content.py` has an LLM relevance score (accept ≥7), a 30-domain blocklist, and an 8-week URL-rejection cache. There is no HITL gate, no freshness penalty, and no post-add audit job. Items auto-commit to `data/*.json` on relevance ≥7.

- **Q.1** HITL approval gate. New items land in a `data/staging/` review queue first; promotion to live requires sign-off. Or: PR-based gate via [Stream T's `peter-evans/create-pull-request`].
- **Q.2** Expand domain blocklist 30 → 100+ from rejection-cache mining. Auto-promote domains with ≥5 historical rejections.
- **Q.3** Age-weighted cold-start k-NN — items added to autoresearch get a freshness boost ceiling so they don't outrank evergreen items they're similar to.
- **Q.4** Post-add 60-day audit job. Compares `median(model_score)` of auto-added vs human-curated cohorts. Reports drift in `data/site_scoreboard.json` and on `/dashboard/`.
- **Q.5** End-of-stream audit.

**Blocked on:** Stream T.1 if Q.1 uses PR-based gating (shared `peter-evans/create-pull-request` setup).

**Reuses:** [`autoresearch/`](../autoresearch/), [`scripts/discover_content.py`](../scripts/discover_content.py), [`.github/workflows/discover-content.yml`](../.github/workflows/discover-content.yml).

**Links:** [`autoresearch/`](../autoresearch/) · [`scripts/discover_content.py`](../scripts/discover_content.py)

---

### Stream R — Content pruning / archive promotion

**Goalpost:** No item with model_score <0.15 AND `high_imp_no_click` for 60 days remains live. Archive (not delete) is the only path out.

Engagement penalty signals (`RAGE_CLICK_WEIGHT`, `QUICK_BOUNCE_WEIGHT`, `HIGH_IMP_NO_CLICK_WEIGHT`) are computed today but never consumed for removal. `data/archive/` exists with manual backups only. No "kill list" concept. Roadmap Stream D was about *doc* cleanup, not *content* cleanup.

- **R.1** `scripts/prune_content.py` flagger — computes the deletion candidates, writes to a review CSV. No auto-move; reports only.
- **R.2** HITL review CSV — Pranjal signs off per-item before archive.
- **R.3** Archive-move pipeline with audit trail. Moves to `data/archive/<type>_archived_<YYYY-MM-DD>.json`. Preserves original entry shape.
- **R.4** Re-rank after archive (removed items shouldn't influence `cooccurrence` signals going forward).
- **R.5** Safety guards: never archive items with (a) recent inbound search-clicks, (b) `featured.json` pin, (c) curator-marked `keep: true` field.
- **R.6** End-of-stream audit.

**Blocked on:** Stream Q. Order matters: tighten the inflow side first (stop adding bad items), then sweep old ones. Otherwise pruning becomes a treadmill.

**Reuses:** engagement signals in [`scripts/rank_all_content.py:115-122`](../scripts/rank_all_content.py), `data/archive/`.

**Links:** [`scripts/rank_all_content.py`](../scripts/rank_all_content.py) · [`data/archive/`](../data/archive/)

---

## Later (September 2026+)

Parking lot. Order is suggestive, not committed.

### Stream I — Advanced recsys (workhorse extensions)

- **I.1** Re5 contextual bandit for carousel ordering (Thompson sampling per row).
- **I.2** Switchback experiments — alternate treatment/control over time on the same surface, for cases where between-user A/B violates SUTVA (e.g., trending row mutually affects all viewers).
- **I.3** LLM-as-reranker — Claude reranks top-K candidates with natural-language reasoning over titles + descriptions. Easy to implement, expensive at scale, fascinating teaching moment.
- **I.4** ALS collaborative filtering — wait for richer interaction data (≥5k engaged users).

### Stream J — Deep learning models (only if learning capacity permits)

Explicitly deprioritized per Pranjal's call: *"workhorses only. build the WHOLE thing first."*

- **J.1** Two-tower neural retrieval — industry-canonical, but adds infra complexity we don't need yet.
- **J.2** Sequence models (SASRec / BERT4Rec) — strong for content sites, but only after the full classical menu is in.
- **J.3** LightGCN / graph-based — same caveat.

### Stream K — `/site` page Tabs 5–6

- **K.1** **Tab 5: How recommendation works** — ranker features (the weight table from CLAUDE.md), cold-start k-NN propagation, MMR diversity, feature flags. Most complex tab; needs Now/Next streams to mature first so we have a settled story to tell.
- **K.2** **Tab 6: How A/B testing works** — bucketing (deterministic hash per te_uid + experiment_id), server-side aggregation, switchback design. Needs Stream I.2 in flight.

### Stream L — Homepage Direction 3 "Playground"

Pranjal's framing: *"Direction 3 is long-term moat."* Not committed.

- **L.1** Interactive knowledge graph (D3 force-directed view of papers/topics).
- **L.2** Fake personalization (curated "for you" rows that read user history but don't pretend to be an algorithm).
- **L.3** Social collections (users can build and share reading lists).

---

### Stream S — Optimization (Bayesian hyperopt + production discrete opt)

Two parallel chunks. Both production modules, not tutorial pages. Scope locked 2026-05-27 per Pranjal: *"i want production optimization. some cost or load or something typically done in tech."*

#### S.1 — Bayesian hyperopt over ranker knobs

**Goalpost:** `recsys_config.json` weights (click, impression, dwell, scroll, freshness decay, MMR λ, etc.) are tuned by Bayesian optimization against offline NDCG@10 — not hand-set.

- **S.1.1** Wrap `lib/eval_runner.py` as a black-box objective (config dict → NDCG@10 scalar).
- **S.1.2** skopt or optuna driver in `scripts/tune_recsys.py`. Gradient-free, 50-trial budget per knob group.
- **S.1.3** HITL gate. Top-1 config written to `data/recsys_config.json` only after Pranjal sign-off + re-eval against baseline.
- **S.1.4** End-of-stream audit.

**Reuses:** [`lib/eval_runner.py`](../lib/eval_runner.py), [`lib/recsys_config.py`](../lib/recsys_config.py).

#### S.2 — Production discrete optimization: homepage slot assignment

**Goalpost:** Homepage row composition is solved as a global constrained-assignment ILP — not as N independent MMR passes. Candidates from Stream E's multi-channel retrieval get assigned to ~48 positions (6 rows × 8 slots) under per-row diversity + cross-row type balance + freshness floor + no-duplicate constraints, maximizing summed predicted CTR.

This is the load-bearing case for a real optimization solver. Netflix/Spotify/YouTube run exactly this as their final layer.

- **S.2.1** Define ILP formulation (objective + constraints) in `lib/slot_assignment.py`.
- **S.2.2** OR-tools or PuLP solver. Profile solve time per page (target: <500 ms p99).
- **S.2.3** `scripts/optimize_homepage.py` driver, consuming Stream E's candidate pools.
- **S.2.4** A/B against current per-row MMR baseline (uses Stream P sequential math).
- **S.2.5** End-of-stream audit.

**Stretch follow-ons** (same stream, smaller):
- **S.3** Crawl budget allocation. Given 1500 URLs to refresh + budget of 100 crawls/day, knapsack-pick to maximize expected information gain. Wires into `update_stars.py` and autoresearch.
- **S.4** Image-gen budget allocation. Knapsack over `generate_hero_images.py` candidates with profit = predicted-CTR-lift.

**Blocked on:** Stream E (S.2 needs the multi-channel candidate pool); Stream P (S.2 A/B needs sequential math).

**Reuses:** [`lib/diversity.py`](../lib/diversity.py) (current MMR baseline for comparison), [`lib/eval_runner.py`](../lib/eval_runner.py), Stream E candidate pools.

**Links:** [`lib/diversity.py`](../lib/diversity.py) · [`scripts/rank_all_content.py`](../scripts/rank_all_content.py) · [`data/recsys_config.json`](../data/recsys_config.json)

---

## Cross-cutting commitments

These apply to every stream regardless of bucket.

### Audit gate ritual (end of every stream)

1. Fresh agent runs `/bullshit` against the stream's claims.
2. Fresh agent runs `/code-review --effort=high`.
3. Cleanup sprint addresses findings.
4. Only then does the stream get marked `✅ shipped` in this file.

Separation between executor and verifier is non-negotiable — see global CLAUDE.md *Adversarial Verification* rule.

### Tri-loop pattern for ML deliverables

Default workflow for any new ML script or model change:

1. **Haiku explore** — gather context, list affected files, scan related code.
2. **Sonnet TDD execute** — write tests first, then implement.
3. **Opus bullshit verify** — audit against the stream's goalposts.

### Hard stops (from `.claude/RULES.md`)

- **F15** Worker schema migrations require: code change + `handleRunSchema` update + post-deploy `GET /run-schema?key=$ADMIN_KEY` ping. All in the same PR. Skipping this caused the 5-week analytics blackout (2026-03-26 → 2026-05-03).
- **Never rerank when `/health` is degraded.** The staleness guard exists for a reason.
- **Eval gate ≥3 rows** at the same `holdout_days` before flipping any ranker default.

### Living-doc discipline

- Every stream completion ⇒ append `✅ shipped YYYY-MM-DD (PR #N)` under its goalpost line. Do not rewrite.
- Every reprioritization ⇒ move the whole block to the new bucket. Note the move in `CHANGELOG.md`.
- Stale memory (>30 days, claims about code) ⇒ verify before acting.

---

## Metrics

Dual-track. Tech metrics validate the ML; human metrics validate the product.

### Tech metrics (tracked in `reports/metrics.csv` and `reports/replays.csv`)

| Metric | Source | Target |
|---|---|---|
| NDCG@10 | `lib/eval_runner.py` | trending up, no regression >5% between rerank rows |
| Hit-Rate@10 | `lib/eval_runner.py` | ≥0.80 sustained |
| MAP | `lib/eval_runner.py` | trending up |
| Per-variant CTR | `scripts/analyze_experiments.py` | reported with 95% CI on every treatment |

### Human metrics (need a `scripts/human_metrics.py` — write in Stream A)

| Metric | Definition | Target |
|---|---|---|
| Clicks per session | mean of D1 `session.click_count` over rolling 7d | ≥1.5 |
| 7-day return rate | `unique_users_today ∩ unique_users_7d_ago / unique_users_7d_ago` | trending up |
| Top-10 churn / month | how many of last month's top-10 clicked items remain in this month's top-10 | ≥30% turnover (proves recs aren't stale) |

Human metrics get reported alongside tech metrics in any A/B writeup.

---

## Linked docs

The full cross-reference map. Future agents: start at the top.

| Doc | Role |
|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | Architecture, glossary, conventions, slash commands. Has a pointer back to this roadmap. |
| [`.claude/RULES.md`](../.claude/RULES.md) | Hard stops, required rituals, gotchas. Non-negotiable. |
| [`master_recsys_planner.md`](../master_recsys_planner.md) | Recsys decision journal. Append-only. Phases 0–8, eval results, decision log. |
| [`CHANGELOG.md`](../CHANGELOG.md) | Per-commit log. 1–2 lines per shipped item under today's date. |
| [`docs/RANKING_SYSTEM.md`](RANKING_SYSTEM.md) | Ranker algorithm reference — features, weights, cold-start propagation. |
| [`docs/ANALYTICS_REPORT.md`](ANALYTICS_REPORT.md) | Analytics architecture, D1 schema, worker endpoints, health checks, recovery runbook. |
| [`analytics-worker/README.md`](../analytics-worker/README.md) | Worker API, privacy measures, deployment runbook. |
| `~/.claude/projects/-Users-pranjal-Code-tech-econ/memory/feedback_homepage_visual.md` | The Mar 2026 homepage critique. Source for Streams B + G + L. |

### Agents & commands referenced

| Path | Role |
|---|---|
| [`.claude/agents/manager.md`](../.claude/agents/manager.md) | Opus planner. Writes design docs for Coder. |
| [`.claude/agents/coder.md`](../.claude/agents/coder.md) | Sonnet implementation. Reads Manager's plan, ships code. |
| [`.claude/agents/tester.md`](../.claude/agents/tester.md) | Sonnet QA. Runs validate_data.py, link checks, cluster reviews. |
| [`.claude/agents/writer.md`](../.claude/agents/writer.md) | Sonnet content writer. READMEs, summaries, content descriptions. |
| [`.claude/agents/claude-manager.md`](../.claude/agents/claude-manager.md) | Sonnet doc-keeper. Updates CLAUDE.md + CHANGELOG after work. |
| [`.claude/commands/rerank.md`](../.claude/commands/rerank.md) | `/rerank` — refresh rankings from D1. |
| [`.claude/commands/enrich.md`](../.claude/commands/enrich.md) | `/enrich` — LLM metadata enrichment. |
| [`.claude/commands/review-clusters.md`](../.claude/commands/review-clusters.md) | `/review-clusters` — cluster quality audit. |
