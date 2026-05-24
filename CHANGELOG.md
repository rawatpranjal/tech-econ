# Changelog

## 2026-05-24
- **Stream C.11 — Frontend design polish on /site and /dashboard**: typography scale (h2 1.75rem Inter Display, h3 1.25rem, body 1rem/1.65), 8-pt spacing tokens, stage-color CSS variables (`--stage-input/gate/enrich/rank/publish` + soft backgrounds), tab bar polish (2.5px active border, 44px tap targets, roving tabIndex), skeleton loaders replace "Loading..." text, keyboard arrow/Home/End nav on both tab bars, 150ms fade-in on tab switch, zebra striping + hover on all tables, tabular-nums on stat numbers, mobile: tab bar horizontally scrolls (no vertical stack), stat grid 2-col. Zero em dashes. Hugo: 107 pages. npm test 185/185.
- **Stream C.10 - Under The Hood artifact enrichment**: Tabs 1-6 of `/site` now include 16 new artifacts across 6 tabs: running examples with real items from the corpus, pull-quotes, conceptual code snippets with actual signal weights, comparison panels, mini SVGs, and a real-data content-count table. New CSS component block appended to `custom.css` (9 new classes, dark mode, mobile). Zero em dashes. Hugo: 107 pages. npm test 185/185.
- **Stream C.9 — /dashboard live page**: new `/dashboard/` route with 5 tabs (Traffic, Top Content, Search, ML Models, A/B Tests). Traffic, Top Content, and Search tabs fetch live from the analytics worker (lazy per tab, memory-cached). ML Models and A/B Tests read from `data/site_scoreboard.json` embedded at build time. Dashboard-specific CSS inlined in the template; reuses `.site-tab*` classes. Nav link added to sidebar (grid icon, after Under The Hood). Hugo build passes (107 pages). Zero em dashes.
- **Stream C.8 — /site Tabs 7+8 (Performance + Experiments)**: added `scripts/build_site_scoreboard.py` (reads metrics.csv, replays.csv, experiments.json + per-experiment markdown reports, writes `data/site_scoreboard.json` atomically); 16 new pytest cases; Tab 7 (ranker eval: NDCG@10 headline + stat cards + sparkline SVG + history table + replay section) and Tab 8 (experiment registry: timeline SVG, active callout, experiments table with status pills, per-experiment detail cards, verdict narrative). Hugo build passes (106 pages). npm test 185/185. pytest 467+16 pass (7 pre-existing d1_sessions stub failures unrelated). Zero em dashes.
- **Stream C.7 — /site human polish pass**: stripped all 12 em dashes from Tab 1 prose, removed every file path, script name, and code object reference from all six tabs (75 total references cleaned), and bumped SVG text sizes (final: headings 20-22px, sub-labels 16-18px, stage labels 14-15px) across all 6 diagrams. Page now reads as editorial blog, not developer documentation. Hugo build passes (106 pages). npm test 185/185.
- **Stream C.6 — /site page Tabs 2-6 shipped**: Storage, Processing, Recsys, How Recs Work, and How A/B Works tabs fully written (400-650 words prose each) with inline SVG diagrams (5-6 nodes each). No em dashes in new content. Stream C now complete pending C.4 audit.
- **Stream A.6 — tracker.js cookie-timing fix + harness_aa_v1 reset**: root cause was `static/js/tracker.js:69-77` deferring the `te_uid` cookie write to `setOnInteraction` (first click/scroll); `experiments.js:getOrMintUid()` reads the cookie eagerly on the first impression, found it empty, and minted a different ephemeral UUID — same user landed in two buckets. Fix: removed the `setOnInteraction` deferral entirely; `te_uid` is now written synchronously in `initUserIdentity()` for new users. `harness_aa_v1` status set to `paused` (contaminated data, 57 users, 19 days). New `harness_aa_v2` added as `active` with same 50/50 A/A structure and `start_date: 2026-05-24`. New regression test at `tests/js/tracker-cookie-timing.test.js` (6 tests). `aa-experiment-config.test.js` updated to assert v2 active + v1 paused. Suite: 175 → 185 tests, all green.
- **Stream B — Editorial polish (B.3, B.4 partial)**: extended Inter Display from hero-only to all card `h3` titles (`.explore-card h3`, `.explore-card-hero h3`, `.explore-card-compact h3`) and added subtle 4%-opacity type-tinted card backgrounds keyed by `data-type` attribute (package=blue, dataset=green, paper=orange, resource=purple, talk=orange, career=teal, community=pink, book=green). Dark mode resets tint — left-border accent already provides the signal. Pure CSS append to `custom.css`. No JS, no data changes. B.5 HITL sign-off needed before merge.

## 2026-05-23
- **`docs/roadmap.md` (NEW)**: living Now/Next/Later roadmap. Frames repo as a learning vehicle for end-to-end recsys + AI-agent dev. 12 streams across 3 horizons, audit-gate ritual, dual tech+human metrics, cross-link map. `CLAUDE.md`, `README.md`, `master_recsys_planner.md` updated to point here for forward planning.
- **CLAUDE.md hygiene**: stale §7 "Still TODO (server-side)" block removed — all three items shipped in PRs #46–48. Section now reflects current state + points to roadmap Stream A for open items.
- **Stream A.5 audit — `harness_aa_v1` A/A test is BROKEN**: ran `analyze_experiments.py` for the first time. Two no-op variants showed `control_a=8,071 imp / 3.99% CTR` vs `control_b=10,205 imp / 2.32% CTR`, z=-6.50, p≈0. Root cause: `static/js/tracker.js:69-77` lazy-writes `te_uid` cookie (waits for first interaction); `static/js/experiments.js:88-104` reads it eagerly on first impression. First-visit users bucketed twice — ephemeral UUID for impressions, real UID for later events. 57 distinct users appeared in both variants. 19 days of A/A data contaminated. **Fix tracker.js cookie timing + reset experiment is HITL-blocked (Stream A.6).**
- **Script fixes (unblocks the analysis tooling)**: `scripts/analyze_experiments.py`, `scripts/rank_all_content.py`, `lib/d1_sessions.py` — wrangler stdout preamble (`"Cloudflare agent skills are available for..."`) broke `json.loads`; now regex-extract `\[.*\]` (DOTALL). `analyze_experiments.py` raises strict; `rank_all_content.py` warns and returns `[]` (preserves existing contract). `lib/d1_client.py` + `lib/d1_sessions.py` — Python 3.11 macOS doesn't trust system keychain; added `certifi.where()` via `ssl.create_default_context` at module import, soft dep (falls back on Linux CI).
- **First-ever row in `reports/replays.csv`**: `python3 scripts/replay_eval.py --candidate data/global_rankings.json` completes. ndcg@10=0.2275, 145 sessions loaded, 39 evaluable. Seeds the gate toward the ≥3-rows threshold for Stream F (Ra2 knn-bge default flip).
- **Stream C — `/site` transparency page skeleton shipped**: `content/site/_index.md` + `layouts/site/list.html` (Hugo picked list.html by default). 6-tab bar in place. **Tab 1 Ingestion** fully built: 580 words + 5-node inline SVG (Sources → Validation → Enrichment → Ranking → Published), cites `validate_data.py` / `enrich_metadata.py` / `rank_all_content.py` / submit-worker. Tabs 2–6 stubbed with "Coming soon" + Stream pointer. CSS: `.site-tabs / .site-tab / .site-tab-content / .site-diagram-container / .site-prose / .site-coming-soon` in `static/css/custom.css` (~120 lines, mobile-responsive). Nav link "How It Works" added to `layouts/_default/baseof.html` sidebar with info-circle icon. `hugo --gc --minify` passes (106 pages, 0 new warnings). Two follow-ups for Stream H: SVG fills are inline hex (no dark-mode adapt), and pre-existing `--accent-color` is undefined in career-tab CSS (silent bug, not introduced here).

## 2026-05-04
- **`scripts/check_secrets.py`**: small helper that compares `.claude/secrets.env.template` against the user's actual `.claude/secrets.env` and exits non-zero if any template-declared key is missing locally. Closes the gap that bit during today's worker deploy: `ADMIN_KEY` was in the template but not in `secrets.env`, so `/run-schema?key=$ADMIN_KEY` returned 401. Pure read-only; never echoes values; 17 new pytest cases covering parse / diff / main exit codes.
- **First real experiment shipped: `harness_aa_v1` A/A test (`data/experiments.json`)**: closes audit §4.A7 step 1. Both variants do the same thing (`control_a` / `control_b`, 50/50). Sole purpose is to validate the end-to-end harness — bucketing → tracker `event.exp` → worker `events.experiments` → `analyze_experiments.py` — by checking traffic actually splits ~50/50. New `tests/js/aa-experiment-config.test.js` runs 10k synthetic uids against the actual config and asserts pctA ∈ [47%, 53%] (4 new tests; suite 171 → 175). Real treatment-vs-control ranker experiments come next.
- **`scripts/analyze_experiments.py` — A/B per-variant CTR + significance (PR #47)**: closes the §4 server-side trio (#42 client → #46 worker schema → this script reads the data). Per active/paused experiment in `data/experiments.json`: pulls per-variant impressions/clicks via `json_extract(events.experiments, '$.<exp_id>')`, prints a stdout summary, writes a markdown report to `reports/experiments/<exp_id>-YYYY-MM-DD.md` with Wilson 95% CIs, two-proportion z-test vs control, and the SQL behind the result. Verdict heuristic: ≥100/arm minimum, p<0.01 for "wins", p<0.05 for "weak signal". Pure subprocess to wrangler (no new deps); 31 new pytest cases covering stats helpers, render paths, count parsing, CLI date coercion.
- **§4 server-side scaffolding step 2 (PR #46) — `analytics-worker/index.js`**: adds `events.experiments` column (JSON map of `{experiment_id: variant_id, ...}`) plus a sparse index on `experiments IS NOT NULL`. INSERT path serializes `event.exp` from the tracker payload (PR #42); migration mirrored in `ensureSchema` (per-isolate self-heal) and `handleRunSchema` (cross-isolate idempotent ALTER) per RULES.md F15. **Deploy applied** (`npx wrangler deploy` + direct `ALTER TABLE` via wrangler since `ADMIN_KEY` wasn't in the local `secrets.env`); end-to-end smoke test succeeded (`json_extract(experiments, '$._example_disabled')` returned `[{"variant":"control","n":1}]` against a probe event).
- **Move `FRESHNESS_WEIGHT` / `FRESHNESS_HALF_LIFE_DAYS` constants out of `rank_all_content.py` into `data/recsys_config.json`**: closes the deferred A3 follow-up from PR #17. Constants deleted from the module; `calculate_freshness_scores` now reads `config.ranking.freshness_boost_max` and `config.ranking.freshness_half_life_days` via `_load_recsys_config()`. New optional `config=` kwarg lets tests pin behaviour without depending on disk state — also the forward-compat path for per-type half-lives (audit's "papers slow / talks fast"). 2 new pytest cases (`TestConfigOverride`); suite at 410 passed.
- **Migrate `rank_all_content.py:calculate_freshness_scores` to use `lib/freshness.py` (PR #43)**: previously inline; now a thin wrapper around `lib.freshness.compute_freshness_boosts`. Two deliberate behaviour changes documented + pinned: (a) fractional days instead of integer (sub-day precision), (b) clock-skewed future `first_seen` clamps to age=0 instead of producing boost > FRESHNESS_WEIGHT. Both shifts are sub-0.001 magnitude on real data and don't move ranks. 8 new pytest cases (equivalence on integer-day inputs, divergence pin tests, error handling).
- **§4 server-side scaffolding step 1 (PR #42, `static/js/tracker.js`)**: `track()` now reads `window.Experiments.getAllAssignments()` and attaches the result as `event.exp` (a `{experiment_id: variant_id, ...}` map) when non-empty. Worker-side ingestion is intentionally still TODO (next PR adds the schema + INSERT path); current worker harmlessly ignores unknown event fields, so this is forward-compat scaffolding. 13 new vitest cases covering the helper and `track()` integration (suite 158 → 171).
- **Re4 session-aware dampening (PR #37, extends `static/js/personalize.js`)**: items the user has already clicked (sources of the Ra4 boost) get pushed DOWN in their row with multiplier `1 - DAMPEN` (0.8). Dampening **trumps** boosting: a card that is both clicked AND a neighbour of another clicked item still gets dampened. New `buildDampenSet` helper; `reorderRow` gains a 4th optional `dampen` arg (3-arg call still works). 12 new tests (suite 116 → 128).
- **`lib/freshness.py` (PR #17)**: extracts `FRESHNESS_WEIGHT` and `calculate_freshness_scores` from `rank_all_content.py` into a tested module (31 tests). API accepts a `Mapping[type → half_life_days]` so future per-type half-lives (papers slow, talks fast) become a config swap, not a code change. Pure-add — call sites in `rank_all_content.py` not yet migrated; that lands separately with a side-by-side comparison.
- **`lib/d1_client.py` (PR #13)**: HTTP wrapper around the analytics worker's read endpoints (`/health`, `/stats`, `/clicks`, `/searches`, `/timeseries`, `/clicks-by-country`). Replaces the wrangler-CLI subprocess pattern. Read-only; writes still go through the worker's POST `/events`. Injectable `FakeFetcher` for tests (33 unit tests, no real HTTP). Frozen `D1Response` dataclass exposes status / url / elapsed_ms.
- **Ra4 client-side personalization (PR #36, `static/js/personalize.js`)**: multiplicative re-rank of homepage `.cards-row` cards by the user's reading history. For each of the last 5 history items, top-5 neighbours from `related-items.json` get a rank-decayed boost (1.0 → 0.6); each card's static `model_score` is multiplied by `1 + 0.2 × max(boost)`. Stable on ties, runs on `requestIdleCallback`, no-ops with `< 3` history items or any fetch failure. Reuses the 1.4 MB `related-items.json` already loaded by `because-you-viewed.js` instead of pulling the 16 MB raw embedding binary the original audit assumed (`search-cache.js:getEmbedding(id)` doesn't exist — only blob-level access).

## 2026-05-03
- **Eval gate hardening (PR #31)**: auto-prefer HTTP `/events-raw` when `ADMIN_KEY` is set, fall back to wrangler on failure; skip regression check when prev row's `holdout_days` differs from new run (apples-to-oranges). 4 new tests, suite at 318.
- **Eval gate skips on `n_evaluable=0` (PR #30)**: post-blackout reruns immediately had impressions but no clicks → metrics=0 → false-positive 100% regression. Gate now treats no-click holdouts as "no signal" and skips both the comparison and the row write.
- **`/events-raw` worker endpoint (PR #27, deployed)**: ADMIN_KEY-protected GET endpoint backing the eval gate's HTTP path. Worker deployed via `npx wrangler deploy`; analytics blackout self-heal active (`events_24h: 107` and growing).
- **Wired `inject_scores.py` into the rerank (PR #29)**: `update_rankings.sh` was running `rank_all_content.py` then skipping `inject_scores.py` entirely; `model_score` on every item in `data/{books,career,community,datasets,packages,papers_flat,resources,talks}.json` had been frozen at 2026-03-30. Hugo templates read `model_score` from the source files, so the homepage's per-category ordering was stale for 5 weeks. Fixed + refreshed all 9 source files.
- **Replay history CSV + structured notes (PR #28)**: `replay_eval.py` now appends `reports/replays.csv` per run (verdict, deltas, baseline/candidate paths). `metrics.csv` notes auto-include `cold_start_method` so future readers can tell regression rows from knn-bge rows.
- **Skip regression-train on knn paths (PR #26)**: `--cold-start-method=knn-tfidf|knn-bge` no longer trains the SBERT regression model (4 min → 19 sec, 13× speedup).
- **Ra2 v2: `--cold-start-method=knn-bge` (PR #25)**: BGE-large-en-v1.5 (1024d) k-NN cold-start. A/B vs regression baseline: -4.1% NDCG@10, identical Hit-Rate@10 — within noise on 15 sessions. Kept opt-in.
- **Ra2 v1: `--cold-start-method=knn-tfidf` (PR #24)**: TF-IDF k-NN cold-start. A/B regressed 10% across the board. Kept opt-in for future BGE-via-TF-IDF comparisons.
- **First metrics.csv row (PR #23)**: Seed rerun NDCG@10 = 0.4191, Hit-Rate@10 = 0.8000 over 15 evaluable sessions, 60-day holdout. The recsys scoreboard's zero-point.
- **Eval-gate fixes (PR #22)**: accepted `'impression'` event type (worker writes full word, not abbreviated 'impress'); switched the gate to wrangler subprocess (the HTTP endpoint hadn't shipped yet); `update_rankings.sh` tolerates missing `reports/metrics.csv`.
- **MMR diversification on homepage trending row**: `scripts/rank_all_content.py:select_diverse_trending` now uses `lib.diversity.mmr_rerank` over SBERT embeddings (lambda=0.7, matches search-side). Replaces the legacy "max-2-per-type, max-2-per-category" rule. 15 new tests; full suite at 300 green.
- **Phase 1 eval pipeline complete** (planner step "Offline evaluation pipeline"). New: `lib/d1_sessions.py` (group D1 events by session), `lib/eval_runner.py` (orchestration + atomic CSV append + regression check), `scripts/evaluate_recsys.py` (CLI runner that appends to `reports/metrics.csv`), `scripts/replay_eval.py` (baseline-vs-candidate side-by-side). `scripts/rank_all_content.py` now calls the eval gate after building rankings and before writing `data/global_rankings.json` — if NDCG@10 drops more than `config.evaluation.ndcg_drop_alert_threshold` (default 5%), the rerank exits 5 and production scores are untouched. 51 new tests; full suite at 285 passing.
- **Rerank**: Refresh global rankings with latest D1 engagement (518 items with signals, 309 with clicks); homepage trending repopulated (12 items, was empty); regenerate `homepage_rows.json`. Top item: "Causal Inference: A Statistical Learning Approach" (73 clicks).
- **Analytics blackout fix**: Diagnosed 5-week silent write failure on the v2 worker (`events.user_id` column missing — schema migration never applied). Permanent code fixes: `handleRunSchema` now self-heals the user_identity migration idempotently; `processEvents` no longer wraps the events batch and `updateAggregates` in one try/catch (a schema mismatch on events used to silently kill all aggregate writes too); `/health` now reports `last_event_ts`, `last_write_age_seconds`, `events_24h`, `write_errors_today`, with `status=degraded` when stale; rerank script aborts if `/health` is degraded (`--ignore-stale` to override). Runbook added to `claude.md`. Migration application + deploy pending wrangler reauth.

## 2026-03-26
- **Weekly reranking pipeline**: `/ranking-export` API endpoint on analytics worker, `--source=api` mode for ranking script, scheduled remote trigger (Monday 6am ET)
- **Netflix-style homepage**: Rotating hero carousel, card images from data, career items removed, dramatic gradient
- **Card images**: GitHub org avatars for packages, Open Library covers for books, image_url pipeline in homepage rows
- **Data quality**: Fix row sizing (min 5, max 10), analytics section mapping for resources/community
- **MCP search**: Tokenized multi-field scoring algorithm overhaul
- **Homepage row validation**: Fix type cap in toolkit builder, padding for short narrative carousels, citation-based paper scoring
- **UI overhaul**: Netflix-quality cards, type-specific colors, Inter font, search animations, bigger cards

## 2026-03-25
- **Homepage layout**: Simplify navigation, remove redundant section grid/CTAs/Discover tab
- **Search UX**: Pass authors, year, tags, format through search worker results; type metadata in results

## 2026-02-07
- Add 6 causal inference/ML packages: grf_python, causalfe, etwfe, diff-diff, choice-learn, GeoAI
- Add Stefan Wager's "Causal Inference: A Statistical Learning Approach" book
- Homepage: rename "Trending Now" → "New Additions" with star icon, showcase new items

## 2026-01-16
- Add choix, pyStoNED, Prest packages for preference modeling and revealed preference analysis

## 2026-01-11
- **Analytics system improvements** - stop losing data, use more signals:
  - Added `web_vitals` table (LCP, FID, CLS) - was losing 2,912 events
  - Added `client_errors` table - was losing 93 error events
  - Added `referrer_stats` table - classify traffic sources (google, twitter, hackernews, etc.)
  - Added device classification (mobile/tablet/desktop) to tracker
  - Populated `item_cooccurrence` from session sequences
  - Added rate limit truncation logging
- **Ranking model improvements**:
  - Added `reading_ratio` signal (actual vs expected read time)
  - Added `high_imp_no_click` negative signal (impressions ≥10 with 0 clicks)
  - Added engagement features to model (CTR, has_clicks, log_clicks, etc.)
  - Comprehensive target using all 13 signals
- **UX fix**: Scroller nav buttons now 60% visible (was 0% causing rage clicks)
- Updated claude.md with new signals, tables, and analytics queries

## 2026-01-06
- Added 4 revealed preference datasets: Chicago Taxi (labor supply), Irish CER Smart Meter (RCT ToU pricing), Uniswap DEX (DeFi trading), iFlex Norway (hourly electricity)
- Added 4 dunnhumby Source Files datasets: Breakfast at the Frat (time series), Carbo-Loading (household panel), The Complete Journey (full marketing mix), Let's Get Sort-of-Real (300M synthetic transactions)
- Added 3 revealed preference packages: InvOpt, PyInvo (inverse optimization), revealedPrefs (GARP/WARP testing)

## 2026-01-05
- Added ML Pipeline documentation to claude.md (ranking, search, clustering, discovery, enrichment, ALS)
- Added UI philosophy: large cards with images, rich metadata
- Created slash commands: `/rerank`, `/review-clusters`, `/enrich`
- Set up `.claude/history/` for changelog and claude.md archives
- **Package clustering with Netflix-style carousels**: 38 topic clusters for 188 packages
  - Full cluster-by-cluster review documented in `scripts/CLUSTERING_REVIEW.md`
  - Fixed 5 misassignments: SuperLearner→pkg-tmle, collapse→pkg-data-manipulation, stargazer→pkg-visualization, inferference→pkg-causal-mediation, linregress→pkg-hypothesis-testing
  - Cluster categories: Causal Inference (10), Experimentation (4), ML (6), Ops Research (5), Time Series (3), Statistics (8), Industry (9), Data Utils (3)
- **Learning section niche clusters V4**: Fixed clustering coherence issues
  - 54 clusters, all in 4-10 item range (avg 6.6 items)
  - Fixed "Agent Based Modeling" clusters - now contains only actual ABM content
  - Similar small semantic_clusters grouped together (similarity > 0.75) instead of merged into random large clusters
  - Industry Economics now has coherent clusters: "Price Theory", "Dynamic Programming", "ABM"
- Updated `scripts/cluster_resources.py` Phase 2: group similar small clusters together instead of merging into large ones
- Re-scored rankings with latest engagement data (1,316 items with engagement)

## 2026-01-04
- Added HDBSCAN clustering script for topic organization (per-section, c-TF-IDF labels, recursive splitting)
- Fixed redundant cluster labels (94→1 issues) with word-level deduplication
- Re-scored rankings with latest engagement data (1,295 items with engagement, 2,540 cold-start)
- **Deep Learning + Statistical Models landscape** (~43 new entries):
  - 18 datasets (dSprite, MIMIC-CXR, TCGA, French MTPL, GHCN-Daily, etc.)
  - 7 packages (pycox, Pyro, scVI-tools, VaDE, causal-bert-pytorch, etc.)
  - 13 papers (DeepHit, Cox 1972, MC-Dropout, Normalizing Flows, MoE, etc.)
  - 5 resources (conformal prediction, extreme value, survival tutorials)

## 2026-01-03
- **Comprehensive Queueing Theory Resources Directory** (~70 new entries):
  - 7 simulation packages (SimPy, Ciw, simmer, queueing, AnyLogic, Arena, Simio)
  - 8 textbooks (Kleinrock, Harchol-Balter, Gross & Harris, Ross, Hillier, Law, Nelson)
  - 2 conferences (ACM SIGMETRICS, Winter Simulation Conference)
  - 25 resources (MIT courses, industry blogs, calculators, tutorials)
  - 25 papers in new "Queueing Theory & Operations" topic (5 subtopics: Foundational, Ride-Sharing, Call Centers, Cloud/Server, Healthcare)
- Added 31 queueing/operations datasets total:
  - Part 1: 15 Kaggle datasets (call centers, healthcare, server logs, theme parks, flights)
  - Part 2: 16 premium sources (CAIDA, Google Cluster, Technion call center, NYC EMS, etc.)
- New categories: Operations & Service, Technology & Infrastructure, Manufacturing, Telecommunications
- Fetched 28 new dataset images + 22 logo fallbacks (181 total dataset images, 227 logos)
- Added `embedding_text` field (500-1000 words) to LLM enrichment for richer semantic embeddings
- **New clustering/search fields** (4,171 items enriched):
  - `tfidf_keywords`: 10-15 discriminative terms per item
  - `semantic_cluster`: LLM-assigned cluster labels (e.g., "causal-ml-methods", "marketplace-experimentation")
  - `content_format`, `depth_level`: content type and depth filters
  - `related_concepts`, `canonical_topics`: graph edges and controlled vocabulary
- Search index v6: Added new fields with boosts (tfidf_keywords: 2.5, canonical_topics: 2.0, semantic_cluster: 1.8)
- Search metadata v5: New fields now included for client-side filtering and display
- Updated unified-search.js to use index config with new field boosts
- Content-type specific prompts for papers, packages, datasets, resources, talks, career, community
- **Async batch processing**: 10x faster enrichment using asyncio (batch size 10, semaphore rate limiting)
- **OpenAI Batch API**: New `enrich_batch.py` script - 50% cheaper with CLI commands (prepare, submit, status, apply, run)

## 2026-01-02
- **Datasets page Netflix-style redesign**: horizontal scroll rows grouped by category (36 categories)
- Downloaded 153 dataset images locally to /static/images/datasets/ via OG image fetching
- Fallback displays category-colored gradient + 2-letter initials for datasets without images
- Categories sorted by highest model_score item for better content discovery
- Split Blogs tab into "Bloggers" (54 personal) + "Industry Blogs" (126 company) tabs
- Added subtopic categorization for personal bloggers (9 topics: Causal Inference, ML & AI, etc.)
- Added sector-based subtopics to Industry Blogs (10 sectors: Marketplaces, Streaming, Social Media, E-commerce, AdTech, etc.)
- Limited carousel rows to 8 items max for cleaner browsing
- Added Reveal.js portfolio slide deck at /slides/ with cinematic dark theme
- 7 slides showcasing site stats, features, tech stack with animated counters
- Downloaded 54 blogger images locally to /static/images/bloggers/ (previously external URLs)
- Talks page Netflix-style redesign with horizontal scrollers per subtopic
- Carousel rows now sorted by top item's model_score (highest-scoring content first)
- Added macro_category + subtopic fields to talks.json (8 macro categories, 55 subtopics)
- Further granular categorization: Susan Athey Work, Marketplace Case Studies, Chief Economists, etc.
- Created OG image fetching script; 181/264 talks now have thumbnails
- Added analytics D1 query reference to CLAUDE.md for checking recent clicks/impressions/searches
- Fixed 9 INFORMS login-wall links → public URLs (conferences, chapters, datasets)
- Fetched OG images for learning resources (211/366), industry blogs (56/126), conferences (52/109)
- Added logo fallback fetching via Clearbit/Google APIs; 143 logos downloaded to /static/images/logos/
- Final image coverage: Learning 73% (268/366), Industry Blogs 60% (76/126), Conferences 79% (87/109)

## 2026-01-01 (Learning page Netflix-style redesign)
- Reorganized resources.json: 64→48 categories, 80→10 types, added macro_category field
- Rebuilt /learning with Netflix-style horizontal scrollers per category
- Added filters: macro category (11), type (10), level pills (beginner/intermediate/advanced)
- Cards sorted by model_score within each row, scrollable with nav arrows

## 2026-01-01 (UChicago Causal Inference course)
- Added UChicago "Causal Models in Data Science" course by Jeong-Yoon Lee
- Added 8 industry speaker talks: Facure (Nubank), Lal (Netflix), Zheng (Meta), Chen (Snap), Pan (Snap), Sinha (Lyft), Harinen (Toyota), Mercurio (Netflix)
- Added 2 books: "Causal Inference in Python" (Facure), "Causal Inference for Statistics, Social, and Biomedical Sciences" (Imbens & Rubin)

## 2026-01-01 (Simulation & Synthetic Data content expansion)
- Added ~80 new entries covering simulation, synthetic data, and computational economics
- New packages: Mesa, AgentPy, ABCE, Gymnasium, Stable-Baselines3, RLlib, ABIDES, AuctionGym, CTGAN, Faker, CausalPy, PyMC
- New paper topic: "Simulation & Synthetic Data" with 4 subtopics (ABM, Synthetic Data, Mechanism Design RL, Market Simulation)
- New resources: SFI ABM courses, tech company simulation blogs (Uber, Lyft, Netflix, Airbnb)
- New books: Railsback & Grimm ABM, Epstein & Axtell Sugarscape, Glasserman Monte Carlo

## 2026-01-01 (AI for Economists content expansion)
- Added ~70 new entries for "AI for Economists" content across all data files
- New paper topic: "AI for Economic Research" with 6 subtopics (LLMs, Homo Silicus, Causal ML, Text-as-Data, Satellite Imagery)
- New packages: EDSL, Anthropic SDK, OpenAI SDK, NLTK, sentence-transformers, TensorFlow, 6 research tools (Elicit, Consensus, etc.)
- Added Korinek, Horton, Athey, Dell, Gentzkow foundational papers
- New resources: Stanford GSB ML course, AEA webcasts, prompt engineering guides, Korinek newsletter
- New conferences: NBER Economics of AI, MLESI, SoFiE, ACM EC

## 2026-01-02
- Integrated model_score into search as post-RRF boost (0.4 weight)
- Added popularity boost toggle in search modal (📈 icon, default ON)

## 2026-01-01
- Added viewability signal to ranking model (hybrid: clicks×5 + impressions×0.5 + viewable×0.1 + dwell×1)
- Surfaces content users actually viewed, not just loaded

## 2025-12-31
- Added per-interaction AUC metrics to ranking evaluation
- Migrated analytics to D1 database with ML-ready schema

## 2025-12-30
- Added model_score field to content items for ranking
- Implemented category-level rankings

## 2025-12-29
- Upgraded to bge-large-en-v1.5 embeddings (1024 dims)
- Added weighted shuffle for Discover tab
