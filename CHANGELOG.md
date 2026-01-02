# Changelog

## 2026-01-02
- Added analytics D1 query reference to CLAUDE.md for checking recent clicks/impressions/searches

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
