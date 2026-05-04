# Tech-econ recsys & search improvement audit

**Date:** 2026-05-03
**Last verified:** 2026-05-04 (status table at top of doc)
**Inputs:**
- Repo audit (3 parallel Explore agents, see plan file)
- Cover-to-cover read of *Deep Learning Recommender Systems* (5 parallel Explore agents → `books/deep-learning-recsys/crosswalk.md`)

**Companion docs:**
- `obvious-wins-2026-05-03.md` — quick wins ≤1 day each (no model training)
- `books/deep-learning-recsys/crosswalk.md` — every book technique → repo status

---

## STATUS AS OF 2026-05-04

The body of this doc is the original audit, kept verbatim for historical context. **Several items in the original audit were either already implemented (the audit's Phase-1 explore missed them) or are not applicable to the actual repo architecture.** The table below is the source of truth for "what's done, what's left." When this doc and the table disagree, the table wins.

| Item | Original audit said | Verified 2026-05-04 | Evidence |
|---|---|---|---|
| **R1** Related-items widget on single-item pages | TODO | **N/A** | The site has no per-item single pages (only `papers/single.html` exists, and it's a topic page that lists all papers in a topic). Cards on every list page link out via `target="_blank"`. The audit's "if they have single pages" caveat in `obvious-wins-2026-05-03.md` was correct; the audit itself was over-broad. |
| **R2** "Because you viewed X" row | TODO | **DONE** | `static/js/because-you-viewed.js`; section at `layouts/index.html:39`. |
| **R3** "Continue Reading" row from localStorage | TODO | **DONE** | `static/js/reading-history.js:121` `renderHistorySection()`; auto-runs on `DOMContentLoaded` (line 161); CSS at `static/css/custom.css:8933+`. The `display: none` on the placeholder is the empty state — flips to `block` once the user has any reading history. |
| **R4** Multi-channel candidate generation | TODO | TODO | No `scripts/build_candidate_sources.py`. |
| **R5** Item2vec / DeepWalk on co-view | TODO | TODO | No `scripts/train_item2vec.py`. |
| **R6** ANN index | DEFER | DEFER | Catalog still ~4k items. |
| **Ra1** Watch-time-weighted positives | TODO | **DONE** | `compute_sample_weights` + `sample_weight=` at `scripts/rank_all_content.py:947`. |
| **Ra2** bge cold-start k-NN | TODO | **PARTIAL** | `--cold-start-method=knn-bge` flag exists (PR #25); default still `'regression'` (`rank_all_content.py:1404,1630`). PR #25's A/B was -4.1% NDCG@10 within noise on N=15 — needs more eval rows before flipping default. |
| **Ra3** Use search rank as feature | TODO | **DONE** | PR #33 (search-rank bonus on click signal) + PR #35 (rank-at-click into regression features). |
| **Ra4** User-pref vector multiplier | TODO | **DONE** | PR #36 (this session): `static/js/personalize.js`. Note: original plan called for cosine over bge embeddings via `search-cache.js:getEmbedding(id)`. That helper does not exist (search-cache only has blob-level access to a 16 MB binary). Implementation uses `related-items.json` neighbour-set approximation instead. |
| **Ra5** Multi-task ranker (click+dwell+scroll) | DEFER until Ra1-Ra4 plateau | DEFER | Ra4 just shipped — observe before scoping Ra5. |
| **Ra6** Wide & Deep | DEFER | DEFER | |
| **Ra7** Persist trained model | TODO | **DONE** | `_save_model_artifact` at `scripts/rank_all_content.py:998`. |
| **Re1** MMR diversity rerank for SEARCH | TODO | **DONE** | `static/js/search/mmr.js` imported into `search-worker.js:10,305`. |
| **Re2** Search spellcheck fallback | TODO | **DONE** | `static/js/search/spellcheck.js`; "Did you mean" banner in `unified-search.js:341`. |
| **Re3** Position-bias correction | TODO | TODO | Pairs with Ra3 logging — Ra3 done, Re3 not started. |
| **Re4** Session-aware dampening | TODO | TODO | Depends on Ra4 (now done). |
| **Re5** Contextual bandit over carousel orderings | TODO | TODO | Depends on A/B harness. |
| **Re6** DPP at scale | DEFER | DEFER | |
| **§4 A/B testing harness** (A1-A8) | TODO | **PARTIAL — client side in flight** | PR #18 ships `data/experiments.json`, `static/js/experiments.js`, inlined config in `baseof.html`, deterministic `te_uid + experiment_id` bucketing, 30 vitest tests. Server-side (tracker.js extension + D1 `experiment_id`/`variant_id` columns + `analyze_experiments.py`) is still TODO. PR #18 also needed a `safeJS` fix during the merge-check — a Hugo auto-escape bug had silently double-encoded the inlined config (caught by parsing rendered HTML; see `RULES.md` "ALWAYS verify rendered HTML" for the codified protocol). |
| **§4 server-side** (tracker logging + D1 schema + `analyze_experiments.py`) | TODO | TODO | First real experiment can't run without these. |
| **§5b Evaluation pipeline** | TODO | **DONE** | PR #21 onward: `lib/d1_sessions.py`, `lib/eval_runner.py`, `scripts/evaluate_recsys.py`, `scripts/replay_eval.py`, `reports/metrics.csv`, `reports/replays.csv`, regression gate in `update_rankings.sh`. |
| **`lib/d1_client.py`** (HTTP wrapper for analytics worker) | n/a (added during impl) | **DONE** | PR #13. Read-only typed endpoints; injectable `FakeFetcher` for tests; replaces wrangler subprocess pattern in upcoming `evaluate_recsys.py` work. |
| **`lib/freshness.py`** (extract `FRESHNESS_WEIGHT` from rank_all_content.py) | n/a (added during impl) | **DONE** | PR #17. Pure-add lib + 31 tests. Ready for per-type half-lives via `Mapping[type → half_life_days]` arg. Migration of call sites in `rank_all_content.py` is deferred. |

**Score:** 11 done · 2 partial (Ra2 default flip; A/B harness client-side) · 8 todo · 1 N/A (R1) · 5 deferred.

**Next decision point:** The "obvious wins" + Phase 2 ranker work is fully closed. The two remaining substantive blocks are §4 (A/B harness) and Phase 5 (multi-channel retrieval + Item2vec). My read: §4 first — without it, Phase 5's gains are unmeasurable at our session count.

**Lessons learned (audit hygiene):**
1. The Phase-1 exploration that fed this audit missed `renderHistorySection()` in `reading-history.js` (R3 was already shipped). Audits decay even from the moment they're written. Always re-verify any "TODO" claim against the current code before planning work.
2. The audit assumed several files/helpers existed that don't (`search-cache.js:getEmbedding(id)`, single-item pages for non-paper types). When a plan depends on a specific helper or file path, grep for it BEFORE writing the plan.
3. See `RULES.md` for the full set of protocols added after this session.

---

This doc is organized by the four canonical recsys stages plus a fifth section for embeddings and evaluation:

1. **Retrieval** — how candidates are generated
2. **Ranking** — how candidates are scored
3. **Re-ranking** — final ordering, diversity, business rules
4. **A/B testing harness** — how to validate everything above
5. **Cross-cutting** — embeddings (currency of all stages) + evaluation (nervous system)

Each item lists: **Effort** (S/M/L), **Impact** (⬆/⬆⬆/⬆⬆⬆), **Files**, **Dependencies**, **Book ref**.

---

## Where we are today (one-page state of the system)

**Catalog:** ~4,034 items (papers, packages, datasets, talks, resources, books).
**Traffic:** ~tens of sessions/day. Cookie ID only (`te_uid`); no logged-in users.
**Retrain cadence:** weekly batch via `python3 scripts/rank_all_content.py`.
**Serve:** static JSON baked into Hugo build; client-side ranking & semantic search via Transformers.js.

| Stage | Today | Biggest gap |
|---|---|---|
| Retrieval (recs) | absent — homepage rows pre-computed at build time | no live candidate generation |
| Retrieval (search) | hybrid MiniSearch BM25 + Transformers.js semantic + RRF (k=60) — solid | no LTR, no spellcheck |
| Ranking | LightGBM binary classifier, ~409 features, single global score | zero personalization |
| Re-ranking | hardcoded "max-2-per-type", intent regex (search), weighted shuffle (homepage) | no MMR/DPP, no position-bias correction, no bandit |
| Evaluation | none | no holdout, no NDCG, no A/B framework |

**Computed but unused (free wins):**
- `static/embeddings/related-items.json` — top-5 semantic neighbors per item, never rendered
- ALS item-item similarities — script `scripts/build_als_model.py` exists, output ignored
- Co-view / co-click counts in D1 — used in batch retrain, never live
- `static/js/reading-history.js` — last 10 clicks in localStorage, never displayed
- Search-click `rank` (position) — captured in tracker, ignored by ranking model

---

## Section 1 — RETRIEVAL

### Today
- Search: working hybrid keyword+semantic with RRF.
- Recs: nothing. The "homepage rows" are static `data/homepage_rows.json` produced at build time. There is no per-request candidate generation.

### Goal end-state
A multi-channel retrieval layer for recs that produces ~50 candidates per surface, from multiple complementary sources, ready for the ranking stage. Book §5.2.2 calls this "multi-channel retrieval" and treats it as table stakes.

### R1. Surface `related-items.json` as Item-CF on every single-item page  ⬆⬆⬆ S
- **Why:** Already computed (§4.5.3 + §2.2.4). Unrendered. Highest ROI in the entire roadmap.
- **Files:** `layouts/{papers,packages,datasets,talks,resources,books}/single.html` + new `layouts/partials/related-items.html` + new `static/js/related-items.js`.
- **Dependency:** none.
- **Book ref:** Ch 2.2.4 (Item-CF), Ch 4.5.3 (embedding-based retrieval).

### R2. Session-based "Because you viewed X" row on the homepage  ⬆⬆⬆ M
- **Why:** Light personalization with zero infra. Take last item from `reading-history.js`, cosine vs all items via `search-embeddings.bin` already loaded by search-cache.js, exclude already-clicked.
- **Files:** new `static/js/recommendations.js`; `layouts/_default/home.html` (new section); reuse `static/js/search/search-cache.js:getEmbedding(id)`.
- **Dependency:** none — embeddings already in client memory after first search.
- **Book ref:** Ch 8.1.x (Facebook cookie-based personalization), Ch 8.2.2 (Airbnb session embeddings).

### R3. "Continue Reading" row from localStorage  ⬆⬆ S
- **Why:** `reading-history.js` is captured but unrendered. Pure UI plumbing.
- **Files:** `layouts/_default/home.html`, `static/js/reading-history.js` (export `renderContinueReading`).
- **Dependency:** none.
- **Book ref:** Ch 8.2.x (session continuity).

### R4. Build a real multi-channel retrieval stage in the ranking script  ⬆⬆⬆ L
- **Why:** Today rec scoring runs on the entire corpus every retrain; per-surface candidate gen would let us run different models per channel and fuse. This is what the book treats as the foundational architectural change in §5.2.
- **Channels to start with (each ~200 candidates):**
  1. **Embedding NN** — bge-large k-NN of (a recent-clicked-or-trending centroid) → top 200
  2. **Co-view** — items most-co-viewed with the user's last item (D1 `item_cooccurrence`)
  3. **Same semantic cluster** — items in same cluster as last clicked (already in `cluster_resources.py` output)
  4. **Recency** — top items added in last 14 days
  5. **Trending** — current global model_score top-200
  Fuse via score-normalized union → top 50 → ranker.
- **Files:** new `scripts/build_candidate_sources.py`; `scripts/rank_all_content.py` integrates; new `data/candidate_sources.json` baked into homepage build.
- **Dependency:** none, but R1-R3 prove the surfaces first.
- **Book ref:** Ch 5.2.2 (multi-channel retrieval).

### R5. Item2vec / DeepWalk on co-view graph for behavioral embeddings  ⬆⬆ M
- **Why:** Our bge embeddings are *semantic* (text similarity). Co-view is *behavioral*. Different signal. Combine.
- **Approach:** Train Gensim Word2vec skip-gram on D1 session sequences (each session = "sentence" of items, ordered by timestamp). 128-dim embedding. Save to `static/embeddings/behavioral.bin`. Ensemble with bge in retrieval (e.g., `0.6 * bge_sim + 0.4 * behavioral_sim`).
- **Files:** new `scripts/train_item2vec.py`, modify `scripts/generate_embeddings.py` to ensemble.
- **Dependency:** D1 has session_id + sequence — already there.
- **Book ref:** Ch 4.3 (Item2vec), Ch 4.4.1 (DeepWalk), Ch 8.2.2 (Airbnb).

### R6. ANN index (skip until corpus ≥100 k items)  ⬆ — defer
- **Why:** Exhaustive cosine over 4 k items takes ~1 ms. Not worth the dependency until we 25× the catalog.
- **Files:** when the time comes, hnswlib or `sqlite-vec`.
- **Book ref:** Ch 4.6 (LSH).

---

## Section 2 — RANKING

### Today
- `scripts/rank_all_content.py:777` trains a LightGBM binary classifier (objective=binary, 150 trees, depth 6, balanced class weights).
- Features: 10 categorical, 8 content, 7 engagement, 384 sentence-BERT embedding dims = ~409 total.
- Cold-start: TF-IDF k-NN with 30% discount (`rank_all_content.py:972`).
- Citations boost (papers), 30-day half-life freshness boost.
- Output: `model_score` ∈ [0,1] baked into all `data/*.json`.

### Goal end-state
The model still produces a single `model_score` for the static homepage build, but starts incorporating richer objectives (dwell-weighted), better cold-start (bge embeddings), and eventually a user-aware feature.

### Ra1. **Watch-time-weighted positive samples**  ⬆⬆⬆ S
- **Why:** YouTube §8.3.2. Today every click contributes equally. A 5-second click and a 5-minute deeply-read session both = 1 positive. Use `dwell_seconds` as `sample_weight` in the LightGBM training. One-line change with outsized impact.
- **Files:** `scripts/rank_all_content.py` (training loop, ~line 800).
- **Dependency:** D1 dwell signal — already collected.
- **Book ref:** Ch 8.3.2.

### Ra2. **Replace TF-IDF cold-start k-NN with bge embeddings**  ⬆⬆ S
- **Why:** We compute bge-large embeddings already; TF-IDF on metadata is strictly weaker. Better neighbors → better cold scores.
- **Files:** `scripts/rank_all_content.py:propagate_cold_start_scores` (~line 920–1042).
- **Dependency:** `static/embeddings/search-embeddings.bin` must be regenerated first if stale.
- **Book ref:** Ch 4.5.3, Ch 5.6.

### Ra3. **Use search result `rank` as a feature**  ⬆ S
- **Why:** `tracker.js:487-526` already logs the position at which a clicked search result appeared. The ranking script ignores this, so high-position click bias is uncorrected.
- **Approach:** Pull `avg_rank_at_click`, `min_rank_at_click` per item from D1 `search_sessions.clicks` JSON. A click at rank 1 is partially position-driven; a click at rank 20 is strong intent. Weight clicks accordingly.
- **Files:** `analytics-worker/index.js` (expose `/search-clicks-with-rank`), `scripts/rank_all_content.py:fetch_engagement_data`.
- **Dependency:** none — data already there.
- **Book ref:** Ch 7 (position bias is implicit in evaluation discussion); explicit in click-model literature.

### Ra4. **Light personalization: user-pref vector as ranking feature**  ⬆⬆ M
- **Why:** Take a user's last-N clicked item embeddings, average them, dot-product against each candidate at scoring time. Add as 1 feature. Massively improves returning-user experience without user IDs.
- **Approach (build-time, since we don't have a server-side ranker):** because ranking happens at build, we can't bake per-user features in. So this lives at the **client side** as a multiplicative reranker: at page load, if `reading-history.js` has ≥3 items, compute the user-pref vector, multiply each card's `model_score` by `1 + 0.2 * cosine(user_pref, item_emb)`.
- **Files:** new `static/js/personalize.js`; called from `home.html` after rows render.
- **Dependency:** R3 ("Continue Reading") establishes the data flow; this rides on it.
- **Book ref:** Ch 8.1.x (Facebook cookie-based), Ch 8.2.3 (Airbnb long-term + short-term interest).

### Ra5. **Multi-task ranker: predict {click, dwell, scroll} jointly**  ⬆⬆ L
- **Why:** Book §5.4 (MMoE/PLE). Click is a noisy positive (click-bait). Joint optimization with dwell + scroll tilts toward genuinely-engaging content. Adds robustness.
- **Approach:** Three LightGBM heads sharing the same feature set, weighted-sum the outputs. Or a single multi-output model (LightGBM doesn't natively, but can train 3 models in parallel).
- **Files:** `scripts/rank_all_content.py` (substantial refactor).
- **Dependency:** Ra1 (watch-time weighting) is the simplest precursor; Ra5 is the full version.
- **Book ref:** Ch 5.4.3 (Shared-Bottom → MoE → MMoE → PLE).

### Ra6. **Add a deep "Wide & Deep"-style branch**  ⬆ L (defer)
- **Why:** Optional architectural upgrade. LightGBM is the "wide" branch. Add a small MLP "deep" branch on the embedding features.
- **When:** only if Ra1-Ra5 stop producing gains.
- **Book ref:** Ch 3.6.

### Ra7. **Persist trained model to disk**  ⬆ S
- **Why:** Today the model is retrained from scratch every run. Save it to `data/.model_cache/lightgbm_v1.txt` so we can do incremental rerank-of-new-items without full retrain.
- **Files:** `scripts/rank_all_content.py` (add `model.save_model` + `Booster.load`).
- **Dependency:** none.
- **Book ref:** Ch 6.5 (engineering practice).

---

## Section 3 — RE-RANKING

### Today
- **Search:** post-RRF intent reranker (30+ regex), audience boost, model_score multiplier, adaptive RRF weighting (`search-worker.js:829-842`).
- **Homepage:** Python-side "max-2-per-type, max-2-per-category" diversity in `select_diverse_trending` (`rank_all_content.py:1373`); JS-side weighted Fisher-Yates shuffle (`home.html:248-264`).
- **Explore:** shuffle + deprioritized/prioritized cluster label lists (`explore.js`).

### Goal end-state
Replace ad-hoc rules with principled mechanisms: MMR for diversity, position-bias-aware reweighting, session-aware dampening, and bandit exploration.

### Re1. **MMR diversity rerank for top-50 search results**  ⬆⬆ S
- **Why:** Book §5.7-adjacent + Ch 4 (embeddings make this trivial). Today's top-10 for "causal inference" can be five Pearl introductions in a row. MMR with λ=0.7 fixes this with embeddings already in client memory.
- **Files:** `static/js/search/search-worker.js` after `handleHybridSearch()` RRF (~line 829).
- **Dependency:** none.
- **Book ref:** Ch 5.5 (re-ranking practice), Ch 4 (embedding similarity).

### Re2. **Search spellcheck fallback on zero-result queries**  ⬆⬆ S
- **Why:** Currently "causal inferance" returns nothing. Add a Levenshtein-based correction against the MiniSearch vocabulary; offer "Did you mean…".
- **Files:** `static/js/search/search-worker.js`, `static/js/search/unified-search.js` (banner UI).
- **Dependency:** none.
- **Book ref:** §implicit — covered under retrieval fallback chains.

### Re3. **Position-bias correction in ranking-feedback loop**  ⬆⬆ M
- **Why:** Pairs with Ra3 (logging). With per-item `avg_rank_at_click`, train a lightweight position-bias model (DBN or PBM): `P(click | rank, relevance)`. Then at retraining, use *corrected* relevance instead of raw clicks.
- **Files:** new `scripts/fit_position_bias.py`; `scripts/rank_all_content.py` consumes corrections.
- **Dependency:** Ra3.
- **Book ref:** Ch 7-adjacent (book treats this lightly; literature is `Position Bias Estimation for Unbiased Learning to Rank`).

### Re4. **Session-aware dampening**  ⬆⬆ M
- **Why:** Within a session, don't show items the user just clicked or viewed. Use the live `reading-history.js` to filter/down-weight at page-render time.
- **Files:** `static/js/personalize.js` (extends Ra4).
- **Dependency:** Ra4.
- **Book ref:** Ch 8.2.x (Airbnb session-aware).

### Re5. **Contextual bandit over carousel ordering on the homepage**  ⬆⬆ L
- **Why:** Different cohorts (mobile vs desktop, returning vs new, week vs weekend) likely prefer different row orders. A Thompson-sampling bandit with ~10 arms (= row orderings) could learn this.
- **Approach:** Server-side (Cloudflare Worker) picks a row order per request based on a cookie cohort hash. Each surface logs `arm_id` to D1 with each impression. Daily, a Python script fits Beta posteriors on per-arm CTR.
- **Files:** new Worker route, `analytics-worker/` schema add `arm_assignments` table, `scripts/fit_bandit.py`.
- **Dependency:** A/B harness (§4) — bandit is a generalization.
- **Book ref:** Ch 5.7 (multi-armed bandit), Ch 5.7.2 (LinUCB if we add features).

### Re6. **Replace hardcoded "max-2-per-type" with DPP at scale**  ⬆ L (defer)
- **Why:** DPP is the principled cousin of MMR; expensive but better at "diverse subset selection". Only worth it if Re1's MMR proves insufficient.
- **Book ref:** Ch 5.7-adjacent.

---

## Section 4 — A/B TESTING HARNESS (design-only, not implemented this turn)

This section is the design doc. Implementation is a separate session.

### Today
- Nothing. Ranking changes ship globally. No bucketing, no logging, no analysis.

### Goal end-state
A lightweight, cookie-based A/B harness that lets us validate every change in §1-3 before global rollout. Multi-layer evaluation funnel per book Ch 7.

### A1. Bucketing (cookie-based, deterministic)
- **Bucket key:** existing `te_uid` cookie (365-day, `static/js/tracker.js:50`).
- **Hash function:** `bucket = hash(te_uid + experiment_id) % 100`. The `+ experiment_id` ensures users aren't permanently in "treatment" across all experiments.
- **Variants:** allocate via `data/experiments.json` (see A2). A user falls into a variant for a given experiment based on `bucket < cumulative_traffic`.
- **Storage:** purely client-side. Worker re-derives the variant from cookie + `experiments.json` on each request.

### A2. `data/experiments.json` schema
```json
{
  "experiments": [
    {
      "id": "homepage_row_mmr_vs_baseline",
      "status": "active",
      "started_at": "2026-05-15",
      "ends_at": null,
      "primary_metric": "ctr_top10",
      "guardrails": ["session_depth", "search_zero_result_rate"],
      "variants": [
        { "id": "control", "traffic": 50, "config": { "rerank": "weighted_shuffle" } },
        { "id": "treatment", "traffic": 50, "config": { "rerank": "mmr_lambda_0_7" } }
      ]
    }
  ]
}
```

This file is shipped as an inline `<script id="experiments-config">` in `baseof.html`, so the client picks variants without any extra round-trip.

### A3. Variant injection points
- **Ranking:** the build script can produce *N* parallel `model_score` columns (one per variant). At render time, JS picks the correct column based on bucket.
- **Re-ranking:** different MMR λ values, different intent-boost weights, etc. — all client-side `if`-branches keyed off the variant ID.
- **UI:** different row orderings, different card layouts.

For now, only **ranking** and **re-ranking** variants. UI variants come later.

### A4. Logging (extend `tracker.js` + `analytics-worker/`)
- Every event (impression, click, dwell, scroll, search, search-click) gains two fields: `experiment_id`, `variant_id`.
- D1 schema: new table `experiment_events` (or just add columns to existing tables — pick one and stick with it).
- Per-bucket aggregations computed nightly.

### A5. Analysis script
- New `scripts/analyze_experiments.py`:
  - Pull events for an experiment, group by variant.
  - Compute primary metric (e.g., `ctr_top10 = clicks_in_top10 / impressions_in_top10`) and guardrails.
  - **Statistical test:** two-proportion z-test or Bayesian (Beta posteriors).
  - **Sequential test (mSPRT or Bayesian sequential):** avoid the "peeking" problem — many small tests inflate false positive rate.
  - Output: a markdown report with point estimate, CI, and verdict (`continue / stop-treatment-wins / stop-control-wins / no-effect`).

### A6. Multi-layer evaluation funnel (book Ch 7)
Pre-launch order of operations for any new ranker:
1. **Offline holdout** (temporal split: last 14 days are test). Compute NDCG@10, Precision@5, Hit-Rate@10. **Stop here if NDCG drops > 3%.**
2. **Replay** on the holdout: chronologically simulate each session, score model's top-K vs the actual click. Lift on `Hit-Rate@10` should be ≥ +2%.
3. **Interleaving** (optional, advanced): mix top-5 from control + top-5 from treatment. Measure click-share. Faster than full A/B but only valid for ranker comparisons.
4. **Full A/B** with traffic ramp 5% → 25% → 50%. Sequential test until `n` per variant ≥ 100 clicks.
5. **Roll out** if winner crosses pre-registered threshold on primary metric and no guardrail violation.

### A7. Implementation order (when we get there)
1. `data/experiments.json` schema + a no-op A/A test (control vs control)
2. D1 `experiment_events` table + `tracker.js` extension
3. `analyze_experiments.py` + a manual run on the A/A to verify ~50/50 bucketing
4. First real experiment: MMR vs baseline (Re1)

### A8. What we explicitly skip
- **Mutually-exclusive vs overlapping experiments:** start with mutually exclusive (one experiment at a time per surface). Overlapping is for later.
- **Holdout/holdback population:** small (1-2%) keeps showing the original baseline forever to detect long-term drift. Defer.
- **Live exploration bandit:** Re5 generalizes A/B; build A/B first.

---

## Section 5 — CROSS-CUTTING

### 5a. Embeddings

**Today:** bge-large-en-v1.5 (1024d server) + gte-small (384d browser) + sentence-BERT-MiniLM (384d in ranking script). Three different embedding models in three different places — semi-accidental.

| Action | Effort | Impact |
|---|---|---|
| **Train Item2vec on D1 session sequences** (R5) | M | ⬆⬆ |
| **Use bge for cold-start k-NN** (Ra2) | S | ⬆⬆ |
| **Render `related-items.json`** (R1) | S | ⬆⬆⬆ |
| Consolidate to one server-side encoder for new items | M | ⬆ |
| Fine-tune bge on co-view pairs | L | ⬆ (defer) |

### 5b. Evaluation

**Today:** none.

| Action | Effort | Impact | Book ref |
|---|---|---|---|
| **Holdout-based offline metrics** (NDCG@10, Precision@5, Hit-Rate@10) on every weekly retrain | M | ⬆⬆⬆ | 7.1, 7.2 |
| **Temporal split**, NOT random | S | ⬆⬆ | 7.3.2 |
| **Replay** evaluation script | M | ⬆⬆ | 7.3.1 |
| **A/B harness** (Section 4) | M | ⬆⬆⬆ | 7.4 |
| **Interleaving** (deferred — sample-efficient online ranker comparison) | M | ⬆ | 7.5.2 |
| Per-rerank score-distribution checks (avoid silent regressions) | S | ⬆ | 7-meta |

---

## Recommended sequencing

A pragmatic 8-week plan, assuming solo dev with limited evening time. Each phase ends with the user able to ship & verify.

### Phase 1 — Surface what we already compute (week 1)
- [R1] Render `related-items.json` on single-item pages — visible quick win
- [R3] "Continue Reading" row from localStorage
- [Re2] Search spellcheck fallback
- [Re1] MMR diversity rerank in search

*Outcome: 4 visible new surfaces / behaviors with zero model retraining.*

### Phase 2 — Ranker quality + light personalization (week 2-3)
- [Ra1] Watch-time-weighted positive samples — single-line change, big lift
- [Ra2] bge cold-start k-NN
- [Ra3] Position-aware logging in analytics-worker
- [Ra7] Persist trained model to disk
- [R2] "Because you viewed X" client-side row
- [Ra4] User-pref vector as client-side multiplier

*Outcome: ranker uses better signals, returning users see personalized rows.*

### Phase 3 — Evaluation pipeline (week 4)
- [5b] Holdout (temporal) + NDCG@10 + Precision@5 + Hit-Rate@10 reporting in `rank_all_content.py`
- [5b] Replay script for offline lift estimation
- Establishes the "is this change actually better?" muscle before any further model changes.

*Outcome: every weekly retrain emits a metrics report; regressions caught automatically.*

### Phase 4 — A/B testing harness (week 5-6)
- [A1-A5] Cookie bucketing → `experiments.json` → tracker logging → D1 table → analysis script
- First real experiment: Re1 (MMR) vs control. Validates the entire pipeline end-to-end.

*Outcome: any future change ships through A/B, not globally.*

### Phase 5 — Real retrieval layer (week 7-8)
- [R5] Train Item2vec embeddings on session sequences
- [R4] Multi-channel candidate gen (`build_candidate_sources.py`)
- Switch homepage from static `homepage_rows.json` to dynamic candidates fused from 5 channels, then ranked.

*Outcome: tech-econ has a real recsys for the first time.*

### Phase 6 — Bandit exploration (week 9+, optional)
- [Re5] Thompson-sampling over carousel orderings.
- Re3 (position-bias correction) feeds in as a more rigorous training signal.

---

## What we are NOT doing

These were considered and rejected for our scale:

- **Two-tower neural retrieval** (book §8.3.3) — Phase 5's Item2vec covers ~80% of the value at 10% of the implementation cost. Revisit if we 10× the catalog.
- **DIN/DIEN/MIMN attention models** (book §3.8-3.9) — needs sequence data we don't have at scale.
- **TensorFlow Serving / parameter servers** — pre-baked JSON beats it for static sites.
- **Full real-time retrain** — weekly batch is fine for tens of sessions/day.
- **Stream processors (Kafka/Flink)** — D1 with a daily aggregation cron is enough.
- **DPP for diversity** — MMR (Re1) covers it.
- **DRN / RL-based ranker** (book §3.10) — orders of magnitude more complex than our problem warrants.

---

## Appendix — quick reference: file → relevant items

| File | Items |
|---|---|
| `scripts/rank_all_content.py` | Ra1, Ra2, Ra3, Ra5, Ra7, evaluation hooks |
| `scripts/generate_embeddings.py` | R5 (ensemble), Ra2 |
| `scripts/cluster_resources.py` | input to R4 channel #3 |
| `scripts/build_als_model.py` | revisit only as candidate channel for R4 |
| new `scripts/build_candidate_sources.py` | R4 |
| new `scripts/train_item2vec.py` | R5 |
| new `scripts/analyze_experiments.py` | A5 |
| new `scripts/fit_position_bias.py` | Re3 |
| `static/js/search/search-worker.js` | Re1, Re2 |
| `static/js/search/unified-search.js` | Re2 (UI) |
| `static/js/reading-history.js` | R3 |
| new `static/js/recommendations.js` | R2 |
| new `static/js/related-items.js` | R1 |
| new `static/js/personalize.js` | Ra4, Re4 |
| `static/js/tracker.js` | A4 (logging extension) |
| `analytics-worker/index.js` | A4 (D1 schema), Ra3 (rank exposure) |
| `layouts/_default/home.html` | R2, R3 |
| `layouts/{type}/single.html` | R1 |
| new `layouts/partials/related-items.html` | R1 |
| new `data/experiments.json` | A2 |

---

*End of audit. Next session: pick 2-3 from Phase 1 and ship.*
