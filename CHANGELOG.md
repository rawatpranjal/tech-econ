# Changelog

## 2026-05-03
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
