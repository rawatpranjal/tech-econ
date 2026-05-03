# Crosswalk: *Deep Learning Recommender Systems* → tech-econ repo

**Date:** 2026-05-03
**Source:** `source.md` (22.9 MB docling output of the 26 MB PDF, processed in 104 s)
**Method:** Cover-to-cover read by 5 parallel Explore agents, each assigned a chapter slice, plus a baseline repo audit by 3 prior Explore agents.
**Repo state:** see top of `recsys-audit-2026-05-03.md` for the same summary.

---

## Status legend

- ✅ **implemented** — present in production with file:line citation
- ⚠️ **partial** — exists but underused or shipped half-built
- ❌ **missing** — not in the repo
- 🆓 **free win** — data/output already exists and just needs to be wired in
- 🔭 **architecture-only** — conceptual, no code action

## Applicability legend (for our context: ~4 k items, ~tens of sessions/day, cookie-only IDs, solo dev)

- **high** — fits our scale and constraints, and would visibly move metrics
- **medium** — works but with caveats (needs infra, more data, or careful tuning)
- **low** — overkill or premature
- **none** — needs scale or data we don't have

---

## Book overall framing

The book proposes a canonical 3-stage pipeline that *every* recsys should follow:

```
        ┌────────────┐     ┌──────────┐     ┌───────────┐
data →  │  RETRIEVAL │  →  │ RANKING  │  →  │ RE-RANKING│  → top-N
        │ (recall K) │     │ (score)  │     │ (diversity│
        │ multi-     │     │ DL model │     │  freshness│
        │ channel    │     │          │     │  rules)   │
        └────────────┘     └──────────┘     └───────────┘
```

Plus two cross-cutting pieces:

- **Embeddings** as the universal currency (Word2vec → Item2vec → graph emb → BERT)
- **Evaluation** as a multi-layer funnel (offline metrics → Replay → Interleaving → A/B → online)

Where tech-econ stands today (one-line):

| Stage | tech-econ today | Gap |
|---|---|---|
| Retrieval | absent for recs (everything pre-computed); search has hybrid MiniSearch+semantic | No multi-channel candidate gen for recs |
| Ranking | LightGBM binary classifier, 409 features, single global score | No personalization, no MTL, no LTR objective |
| Re-ranking | hardcoded "max-2-per-type", intent regex, weighted shuffle | No principled diversity, no position-bias correction, no bandit |
| Embeddings | bge-large 1024d items + gte-small 384d browser; `related-items.json` unrendered | No graph/Item2vec; embeddings unused as ranking features |
| Evaluation | none — no holdout, no NDCG, no A/B harness | Entire layer missing |

---

## Chapter 1 — Growth Engine of the Internet (lines 536–713)

**Slice summary.** Establishes the recsys problem statement `f(U, I, C) → preference`, and the 3-stage architecture. Explains the role of the data plane (real-time client → quasi-real-time stream → offline batch) and the model plane (offline training + online updating + serving). Frames deep learning's contribution as: dense embeddings, end-to-end feature learning, multi-task objectives.

| § | Concept | Stage | Status | Action |
|---|---|---|---|---|
| 1.2.1 | `f(U, I, C) → score` framing | architecture | 🔭 | document this as the project's canonical statement |
| 1.2.2 | Retrieval → Ranking → Re-ranking | architecture | ⚠️ partial | only ranking + ad-hoc reranking exist; build retrieval stage for recs |
| 1.2.3 | Real-time client + quasi-real-time stream + offline batch | infra | ⚠️ partial | client (`tracker.js`) + offline batch (`rank_all_content.py`) exist; no stream layer (and likely don't need one at our scale) |
| 1.2.4 | Offline training + online updating | infra | ⚠️ partial | offline only, weekly retrain; online updating not justified yet |

---

## Chapter 2 — Pre-Deep Learning Era (lines 714–1611)

**Slice summary.** Walks through CF (User-CF, Item-CF) → MF → LR → POLY2 → FM → FFM → GBDT+LR → LS-PLM. Each model addresses a specific limitation of its predecessor. The chapter ends by establishing the conceptual bridge to deep learning: latent factors → embeddings, manual feature crosses → automatic ones, piecewise-linear regions → MLP layers.

| § | Concept | Stage | Status | Action |
|---|---|---|---|---|
| 2.2.1 | User-CF | retrieval | ❌ | skip — superseded by embeddings |
| 2.2.4 | **Item-CF** (item-item k-NN) | retrieval | 🆓 | **wire `related-items.json` everywhere** — this *is* Item-CF, just unrendered |
| 2.2.6 | CF cold-start, Matthew effect | architecture | 🔭 | informs why we need a content-based fallback (we already have one) |
| 2.3 | Matrix Factorization | retrieval | ⚠️ | `build_als_model.py` dormant; revisit only if we get more interaction data |
| 2.3.3 | Bias terms (μ, μ_u, μ_i) | ranking | ❌ | LightGBM captures implicitly; skip |
| 2.4 | LR for CTR | ranking | ✅ | LightGBM is the modern stand-in (`scripts/rank_all_content.py:777`) |
| 2.5.2 | Factorization Machines | ranking | ❌ | tree ensembles dominate; skip |
| 2.5.3 | FFM (field-aware FM) | ranking | ❌ | skip |
| 2.6.1 | **GBDT + LR stacking** (leaf indices → LR) | ranking | ⚠️ | we use pure LightGBM; could try leaf-features → LR for the calibrated probability, but small gain |
| 2.7.1 | LS-PLM (Alibaba pre-DL) | ranking | ❌ | skip |

**Take-away from Ch2**: Item-CF is already implicitly built; the only missing piece is rendering it. That's the biggest "free win" in the entire book for us.

---

## Chapter 3 — Deep Learning Era (lines 1612–3777, **largest chapter**)

**Slice summary.** Family tree of DL recsys: AutoRec (2015) → Deep Crossing → Wide&Deep → Neural CF → PNN → FNN/DeepFM/NFM → AFM → DIN → DIEN → DRN (RL) → BERT4Rec → LLM-based. Each model adds one capability: residual depth, generalization+memorization, learned crosses, attention over user history, sequence modeling, and finally LLM-as-encoder/feature-generator.

**Top techniques applicable to us (4 k items, low traffic, cookie IDs):**
- DIN-style item attention over the user's session history (we have `reading-history.js` already capturing it)
- Wide & Deep architecture is the natural shape of our LightGBM ranker, but we could add a small MLP "deep" branch
- LLM-as-feature-encoder for cold items (Claude API to enrich descriptions → better embeddings)

| § | Model | Stage | Status | Applicability | Action |
|---|---|---|---|---|---|
| 3.2 | AutoRec | retrieval | ❌ | low | skip |
| 3.3 | Deep Crossing (Microsoft 2016) | ranking | ❌ | medium | optional — try residual blocks if we move from LightGBM to MLP |
| 3.4 | Neural CF | ranking | ❌ | low | needs more interaction data |
| 3.5 | PNN | ranking | ❌ | medium | LightGBM trees already learn crosses |
| 3.6 | **Wide & Deep** | ranking | ⚠️ | high | our ranker is "wide" only; adding a deep branch is a multi-day experiment |
| 3.6.3 | DCN (Deep & Cross) | ranking | ❌ | medium | alternative to PNN; defer |
| 3.7.1 | FNN | ranking | ❌ | low | skip |
| 3.7.2 | **DeepFM** | ranking | ❌ | medium | possible LightGBM successor; benchmark only |
| 3.7.3 | NFM | ranking | ❌ | low | skip |
| 3.8.1 | AFM | ranking | ❌ | low | skip |
| 3.8.2 | **DIN** (item attention over history) | ranking | ❌ | high | needs reading-history → server. Defer until we ship "Continue Reading" + "Because you viewed X" first to validate engagement |
| 3.9 | DIEN (GRU over history) | ranking | ❌ | low | needs more session data |
| 3.10 | DRN / DQN (RL recsys) | ranking | ❌ | none | requires online serving + exploration; skip |
| 3.11.2 | BERT4Rec | retrieval | ❌ | low | needs longer sequences than we'll ever have |
| 3.12.1.1 | **LLM as feature encoder / enrichment** | feature-eng | ⚠️ | high | we already enrich via Claude in `enrich_metadata.py`; ensure cold items always pass through it |
| 3.12.1.2 | LLM as embedding generator | embeddings | ⚠️ | medium | bge-large is strong; could test OpenAI text-embedding-3-large for marginal lift |
| 3.12.1.3 | LLM as ranker | ranking | ❌ | low | too slow; only viable for top-K rerank offline |

**Take-away from Ch3**: Most DL models assume Alibaba/YouTube data. The relevant ones for us are Wide & Deep (architectural shape) and DIN (attention over our `reading-history` once we surface it server-side). LLM enrichment is already happening; we just need to make it gap-fill cold items reliably.

---

## Chapter 4 — Embedding Technology (lines 3779–4462)

**Slice summary.** Embeddings are the universal building block. Word2vec skip-gram with negative sampling → Item2vec on item sequences → DeepWalk (random walks on co-view graph) → Node2vec (BFS/DFS bias for homophily vs structural equivalence) → EGES (side-info fusion) → embedding pre-training, embedding-based retrieval, LSH/ANN for serving.

| § | Technique | Stage | Status | Applicability | Action |
|---|---|---|---|---|---|
| 4.1 | Dense vs sparse representations | embeddings | ✅ | high | bge-large in production (`generate_embeddings.py`) |
| 4.2 | Word2vec skip-gram + negative sampling | embeddings | ❌ | medium | not for items; superseded by BERT-class encoders |
| 4.3 | **Item2vec** on co-view sequences | embeddings | ❌ | high | 🆓 we have session_id + click sequences in D1; one-script Gensim job; gives us *behavioral* item similarity to complement *semantic* bge |
| 4.4.1 | **DeepWalk** on co-view graph | embeddings | ❌ | high | same data as Item2vec; pick one to start |
| 4.4.2 | Node2vec (biased walks) | embeddings | ❌ | medium | iterate on DeepWalk if it works |
| 4.4.3 | EGES (side-info fusion) | embeddings | ❌ | medium | only after we have a graph |
| 4.5.1 | Embedding layer in DNNs | embeddings | ✅ | high | implicit in LightGBM via BERT features |
| 4.5.2 | Pre-training generic vs task-specific | embeddings | ⚠️ | medium | could fine-tune bge on our co-view pairs as auxiliary task — defer |
| 4.5.3 | **Embedding-based retrieval** for candidate gen | retrieval | ❌ | high | this is exactly the missing recsys-side retrieval stage |
| 4.6 | LSH / ANN for fast nearest neighbor | retrieval/infra | ❌ | low | exhaustive cosine over 4 k items is ~1 ms; ANN unnecessary until ≥100 k |

**Take-away from Ch4**: Item2vec / DeepWalk on our co-view data is a high-value, low-cost addition. Build *behavioral* embeddings to sit alongside the *semantic* bge ones — combine via simple ensemble.

---

## Chapter 5 — Multiple Perspectives (lines 4463–5548)

**Slice summary.** Seven perspectives: feature engineering, retrieval strategies, real-time, optimization objectives, model structure, cold-start, exploration/exploitation. Centerpiece: **multi-channel retrieval** (embedding + rules + tags + trending + recency are all complementary candidate sources). Cold-start gets formal treatment via UCB/Thompson sampling. Multi-task learning (Shared-Bottom → MoE → MMoE → PLE) gets a chapter-section.

| § | Concept | Stage | Status | Applicability | Action |
|---|---|---|---|---|---|
| 5.1.2 | **Feature engineering taxonomy** (behavior, relationship, content, context, statistical, combined) | ranking | ⚠️ | high | audit our 409 features against this taxonomy — likely gap is *contextual* (time-of-day, device) and *statistical* (item age × CTR) |
| 5.1.3 | Continuous vs categorical preprocessing | ranking | ✅ | high | LightGBM handles natively |
| 5.2.1 | Retrieval as separate stage | retrieval | ❌ | high | we don't have one for recs |
| 5.2.2 | **Multi-channel retrieval** | retrieval | ❌ | high | proposed channels: embedding-NN, semantic cluster, co-view, recency, trending — each ~200 candidates → fuse → top-50 to ranker |
| 5.2.3 | Embedding-based retrieval (single-channel) | retrieval | ❌ | high | piece of 5.2.2 |
| 5.3.1 | Real-time recsys motivation | infra | ⚠️ | medium | we batch weekly; OK for our traffic |
| 5.3.3 | Update strategies: full / incremental / online / partial / client-side | infra | ⚠️ | low | full-batch is fine |
| 5.3.4 | "Wooden Bucket" — find the bottleneck | meta | ❌ | high | for us the bottleneck is *retrieval surface coverage*, not model accuracy |
| 5.4.1 | **Optimization objective alignment** | ranking | ⚠️ | high | we predict "any engagement"; YouTube-style watch-time-weighted positive samples is a much better objective |
| 5.4.3 | Multi-task learning (Shared-Bottom / MoE / MMoE / PLE) | ranking | ❌ | medium | could predict {click, dwell, scroll} jointly via MMoE — meaningful but not urgent |
| 5.5 | Attention as reusable mechanism | ranking | ❌ | medium | only relevant if we move beyond LightGBM |
| 5.6 | Cold-start: rules + content + transfer + exploration | cold-start | ⚠️ | high | we use TF-IDF k-NN; upgrade to bge embeddings (Ch4 alignment) |
| 5.6.3.3 | Cold-start via **exploration** (UCB / Thompson) | cold-start/bandit | ❌ | high | combine with A/B harness — bandits get our exploration budget |
| 5.7 | **Multi-armed bandit framework** | bandit | ❌ | high | apply to carousel ordering on homepage, not item-level |
| 5.7.2 | LinUCB (contextual bandit) | bandit/personalization | ❌ | medium | needs a context vector; possible after we have session embeddings |
| 5.7.3 | Network-perturbation exploration (DRN) | bandit/DL | ❌ | low | overkill |

**Take-away from Ch5**: This chapter alone justifies *most* of our roadmap. Multi-channel retrieval + bandits + watch-time-weighted training are three large levers we don't pull at all.

---

## Chapter 6 — Engineering Implementations (lines 5549–6277)

**Slice summary.** Three pillars: data pipelines (batch / stream / Lambda / Kappa), offline training infra (Spark / Parameter Server / TensorFlow), online serving (5 strategies from "pre-baked into Redis" to "TF Serving with gRPC"). Closes with engineering trade-offs: model capacity vs cache size, schedule vs technology, hardware vs complexity.

For a solo-dev static-site project, most of this is reference-only. The relevant lesson: **we already have the simplest possible serving — pre-compute + JSON + browser** — and we should keep it. Don't add Redis or TF Serving until traffic forces us.

| § | Concept | Stage | Status | Applicability | Action |
|---|---|---|---|---|---|
| 6.1.1 | Batch / MapReduce | training | ✅ | high | weekly LightGBM batch is correct shape |
| 6.1.2 | Stream processing (Kafka, Flink) | training | ❌ | low | not needed at our scale |
| 6.1.3 | Lambda architecture | training | ❌ | low | overkill |
| 6.1.4 | Kappa architecture | training | ❌ | low | overkill |
| 6.2 | Spark MLlib | training | ❌ | low | LightGBM + numpy fits in RAM |
| 6.3 | Parameter Server | training | ❌ | none | LinkedIn/Google scale |
| 6.4 | TensorFlow distributed training | training | ❌ | medium | option if we move to neural nets |
| 6.5.1 | **Pre-stored results in cache** (= our build-time JSON) | serving | ✅ | high | exactly our pattern |
| 6.5.3 | Pre-trained embeddings + lightweight online model | serving | ⚠️ | medium | could ship a tiny rerank MLP to browser; modest gain |
| 6.5.5 | TF Serving | serving | ❌ | low | not needed |
| 6.6.x | Engineering trade-off philosophy | meta | ✅ | high | we follow this implicitly: ship-on-schedule > technical purity |

---

## Chapter 7 — Evaluation (lines 6278–6894, **most useful for us**)

**Slice summary.** Multi-layer evaluation funnel: offline metrics (Precision/Recall/AUC, NDCG, MAP) → **Replay** (offline simulation of online with chronological data) → **Interleaving** (mix top-K from two rankers, infer winner from clicks, ~10× more sample-efficient than A/B) → **online A/B** (final source of truth). Each layer has different trade-offs between speed and correctness.

| § | Concept | Stage | Status | Applicability | Action |
|---|---|---|---|---|---|
| 7.1.1.1 | **Holdout test set** | evaluation | ❌ | high | absent — must add |
| 7.1.1.2 | k-fold CV | evaluation | ❌ | medium | optional for our small data |
| 7.1.2.2 | Precision@N / Recall@N | evaluation | ❌ | high | implement as primary metric |
| 7.1.2.3 | RMSE | evaluation | ❌ | low | wrong metric for ranking |
| 7.2.2 | ROC-AUC | evaluation | ❌ | medium | useful if we add binary classifier loss |
| 7.2.3 | **NDCG@k / MAP** | evaluation | ❌ | high | gold metric — implement |
| 7.3.1 | **Replay** (chronological offline simulation) | evaluation | ❌ | high | we have the data in D1; high-value addition |
| 7.3.2 | Time-aware holdout (no random shuffle) | evaluation | ❌ | high | training/test split must be temporal |
| 7.4.1 | Online A/B testing | a-b-testing | ❌ | high | nonexistent — must build harness |
| 7.4.2 | Hash-based bucketing | a-b-testing | ❌ | high | use `te_uid` cookie hash |
| 7.4.3 | Online metrics (CTR, engagement, revenue) | a-b-testing | 🆓 | high | D1 has it all |
| 7.5.2 | **Interleaving** | a-b-testing | ❌ | medium | beautiful idea; defer until we have basic A/B working |
| 7.6 | Multi-layer evaluation funnel | meta | ❌ | high | our target end-state |

**Take-away from Ch7**: This chapter is the spine of the audit's A/B testing harness section. Specific design decisions (temporal holdout, NDCG@10, hash bucketing, replay-then-interleave-then-A/B funnel) come straight from here.

---

## Chapter 8 — Frontier Practice (lines 6895–7866)

**Slice summary.** Industry case studies:

1. **Facebook GBDT+LR (2014) → DLRM (2019)** — pragmatic feature engineering via tree leaves; later, dense+sparse split with hybrid model+data parallelism.
2. **Airbnb (2018)** — session+booking-aware skip-gram embeddings, real-time updates, attribute-based cold-start.
3. **YouTube (2016+)** — two-tower architecture: deep candidate gen (with **watch-time-weighted positives**) → deep ranker.
4. **Alibaba** — DIN → DIEN → MIMN → SIM, progression of attention-over-history models. Requires e-commerce-scale data.

**Patterns we should steal:**

| Pattern | From | Stage | Why us | Cost | Priority |
|---|---|---|---|---|---|
| **Watch-time-weighted positive samples** | YouTube §8.3.2 | ranking training | one-line change to LightGBM `sample_weight=dwell_seconds`; immediately favors deeply-engaging content over click-bait | S | top-3 |
| **Two-tower lightweight candidate gen** | YouTube §8.3.3 | retrieval | replace static homepage rows with dynamic candidates from session-pooled query embedding × item embeddings | M | top-3 |
| **Item2vec / skip-gram on session sequences** | Airbnb §8.2.2 | embeddings | behavioral signal complements semantic bge; uses D1 data we already collect | M | top-3 |
| **Long-term + short-term interest split** | Airbnb §8.2.3 | ranking | session vector for now + history vector for returning users | M | medium |
| **Cookie-based light personalization** | Facebook §8.1.x | ranking | weight items by dot-product with last-N-items embedding; no user IDs needed | S | top-3 |

**Patterns to explicitly NOT copy:**

- **Alibaba MIMN/SIM** — requires user IDs and dense interaction sequences; we have neither.
- **Facebook DLRM model+data parallelism** — billions of params; ours fits in a process.
- **TF Serving / parameter servers** — premature; pre-baked JSON beats it for static sites.
- **Online RNN ranking (DIEN)** — RNN serving infra is a tax we can't afford for marginal gain.

---

## Chapter 9 — Build Your Own Knowledge Framework (lines 7867–8029)

**Slice summary.** Wrap-up. The book's final framing is that a recsys engineer must (a) know the model family tree, (b) understand the business they're optimizing for, and (c) think about engineering trade-offs holistically. Reinforces: pick the simplest model that meets the bar, instrument everything, evaluate before deploying.

No new concepts. The audit's "principles" section pulls from here.

---

## Synthesis — top 12 ideas across the whole book, ranked by ROI for us

| # | Idea | Stage | Effort | Source ch. |
|---|---|---|---|---|
| 1 | Render `related-items.json` everywhere (= Item-CF surfaced) | rerank | S | 2.2.4 |
| 2 | Watch-time-weighted positive samples in LightGBM | ranking | S | 8.3.2 |
| 3 | "Continue Reading" + "Because you viewed X" rows from `reading-history.js` | retrieval (light) | S–M | 8.1.x |
| 4 | bge cold-start k-NN (replace TF-IDF) | ranking cold-start | S | 4.5.3 + 5.6 |
| 5 | Multi-channel retrieval layer for recs (embedding NN + co-view + cluster + recency + trending) | retrieval | M–L | 5.2.2 |
| 6 | Item2vec / DeepWalk on co-view graph | embeddings | M | 4.3 + 4.4.1 |
| 7 | Two-tower lightweight candidate gen (session-pooled query × item) | retrieval | M | 8.3.3 |
| 8 | A/B testing harness (cookie hash → bucket → variant → D1 logging → analysis script) | a/b | M | 7.4 + 7.5 |
| 9 | Holdout + NDCG@10 + Replay evaluation pipeline | evaluation | M | 7.1 + 7.3 |
| 10 | MMR diversity rerank at search time | rerank | S | 5.7-adjacent (book endorses diversity) |
| 11 | Position-bias-aware logging + correction | ranking | S–M | 7-adjacent (book mentions implicit) |
| 12 | Multi-task ranker (click + dwell + scroll) via MMoE-lite | ranking | L | 5.4.3 |

The full audit (`recsys-audit-2026-05-03.md`) maps each of these to specific files, dependencies, and implementation notes.
