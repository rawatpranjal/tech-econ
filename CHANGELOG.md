# Changelog

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
