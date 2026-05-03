# Obvious Wins — Recsys / Search

**Date:** 2026-05-03
**Source:** Repo audit only (pre-book). The full audit (`recsys-audit-2026-05-03.md`) layers in book-driven techniques.
**Selection criterion:** ≤1 day each, no model training, mostly wiring up things we already produce.

---

## Effort / impact legend

- **Effort:** S = ≤2 hr, M = ≤1 day, L = >1 day (these wins are S/M only)
- **Impact:** ⬆⬆⬆ user-visible new surface · ⬆⬆ improves an existing surface · ⬆ infra / measurement

---

## 1. Render `related-items.json` on every single-item page  ⬆⬆⬆ S

**What:** `scripts/generate_embeddings.py` already produces `static/embeddings/related-items.json` (1.4 MB) — top-5 semantic neighbors per item. **It is never rendered anywhere.**

**Why this is #1:** The single biggest "we have it, just plug it in" win on the site. Single-item pages currently have no related-items widget.

**Files to touch:**
- `layouts/papers/single.html` — add a `{{ partial "related-items.html" . }}` block under the main content
- `layouts/packages/single.html` (and the equivalent for `datasets`, `talks`, `resources`, `books` if they have single pages)
- New: `layouts/partials/related-items.html` — fetches the JSON, finds the current item by ID, renders 5 cards
- New: `static/js/related-items.js` — small loader (lazy-fetch the JSON on idle, render cards into the partial's container)

**Estimated LOC:** ~80 (partial + JS + CSS tweak)
**Dependency:** None — file already exists.
**Verification:** `curl http://localhost:1313/papers/some-paper/` shows a "Related" row with 5 cards; clicking goes to other items.

---

## 2. "Continue Reading" row on the homepage  ⬆⬆⬆ S

**What:** `static/js/reading-history.js` already stores the user's last 10 clicked items in localStorage (`name`, `url`, `type`, `category`, `description`, `viewedAt`). **Never read back.** Add a homepage row that renders these.

**Files to touch:**
- `layouts/_default/home.html` — add a `<section id="continue-reading" hidden>` block near the top (only un-hides when JS finds 1+ history items)
- `static/js/reading-history.js` — export a `renderContinueReading(containerId)` function
- `static/js/home.js` (or inline in `home.html`) — call `renderContinueReading('continue-reading')` on DOMContentLoaded

**Estimated LOC:** ~60
**Dependency:** None — data already collected.
**Verification:** Visit a few items, return to homepage, "Continue Reading" row shows them most-recent-first.

---

## 3. "Because you viewed X" row (session-based, client-side)  ⬆⬆⬆ M

**What:** Session-based personalization with zero infra:
1. Read last item from `reading-history.js`
2. Fetch its 384d embedding from `static/embeddings/search-metadata.json` + `search-embeddings.bin`
3. Compute cosine vs all items (already in client memory if search has been used)
4. Exclude items already in reading history
5. Render top 8 as a row labeled "Because you viewed *<name>*"

**Files to touch:**
- New: `static/js/recommendations.js` — single function `getSessionRecs(lastItemId, k=8)`
- `static/js/search/search-cache.js` — already loads embeddings; expose a `getEmbedding(id)` helper
- `layouts/_default/home.html` — second hidden `<section>` next to "Continue Reading"

**Estimated LOC:** ~120
**Dependency:** Item #2 (Continue Reading) for the localStorage read pattern.
**Verification:** Click an item, return home, see a row whose contents shift based on what was clicked.

---

## 4. Search spellcheck fallback on zero-result queries  ⬆⬆ S

**What:** Today, "causal inferance" returns nothing. Add a fallback: when MiniSearch returns 0 hits, run a Levenshtein-based correction against the index's vocabulary and offer "Did you mean *causal inference*?"

**Files to touch:**
- `static/js/search/search-worker.js` — when `keywordResults.length === 0`, build a vocabulary set from MiniSearch's index and find closest term (edit distance ≤ 2)
- `static/js/search/unified-search.js` — render the suggestion as a clickable banner above the empty state

**Estimated LOC:** ~50 (no library — small SymSpell-lite is fine for 4k items)
**Dependency:** None.
**Verification:** Search "neurel netwrok" → banner offers "neural network".

---

## 5. MMR diversity rerank on top-50 search results  ⬆⬆ S

**What:** Today, search results for broad queries are often near-duplicates (e.g., five Pearl-style intro papers). Rerank top-50 with Maximal Marginal Relevance: `λ=0.7 × relevance − 0.3 × max-similarity-to-already-shown`. Embeddings are already in client memory.

**Files to touch:**
- `static/js/search/search-worker.js` — after the RRF fusion in `handleHybridSearch()` (~line 829-842), apply MMR over the top-50 with embeddings, then truncate to display N

**Estimated LOC:** ~40
**Dependency:** None.
**Verification:** Search "causal inference" → results visibly span more sub-topics than before; the same paper doesn't appear three times in the top 10.

---

## 6. Replace TF-IDF cold-start with bge embeddings  ⬆⬆ S

**What:** `scripts/rank_all_content.py:920-970` builds a TF-IDF matrix over metadata for k-NN cold-start propagation. We already produce 1024d bge-large embeddings in `generate_embeddings.py`. Use those instead — they're far more semantically meaningful.

**Files to touch:**
- `scripts/rank_all_content.py:propagate_cold_start_scores` — load `static/embeddings/search-embeddings.bin` + metadata, swap `cosine_similarity(tfidf_matrix)` for `cosine_similarity(bge_matrix)`

**Estimated LOC:** ~30 swap-out
**Dependency:** Embeddings file must exist (always run before rank script per CLAUDE.md).
**Verification:** Run `python3 scripts/rank_all_content.py`; cold-start neighbor lists should look more topically coherent (compare before/after for 5 cold items).

---

## 7. Use search result `rank` for click-through analytics  ⬆ S

**What:** `static/js/tracker.js:487-526` already logs `rank` (the position) on every search-click. The ranking script ignores this. Add it as a feature in the next retrain so we can measure (and eventually correct) position bias.

**Files to touch:**
- `analytics-worker/index.js` — surface `rank` in the `/search-clicks` endpoint output (it's already in `search_sessions.clicks` JSON)
- `scripts/rank_all_content.py:fetch_engagement_data` — include `avg_rank_at_click`, `min_rank_at_click` per item; treat lower rank with more weight (a click at rank-1 means little; a click at rank-20 means the user worked for it)

**Estimated LOC:** ~50
**Dependency:** None.
**Verification:** A new column `avg_rank_at_click` appears in the ranking script's debug output and is non-null for items with search clicks.

---

## 8. Wire `related-items.json` into search result hover  ⬆⬆ S

**What:** Stretch on item #1: when hovering a search result, show 3 related items in a tooltip ("Also see..."). Drives lateral exploration without a click.

**Files to touch:**
- `static/js/search/unified-search.js` — `renderResult()` adds a `data-related-id` attribute
- New: `static/js/related-items.js` (shared with item #1) — `getRelated(id, k=3)` lookup
- CSS for the tooltip

**Estimated LOC:** ~70 (50 reused from item #1)
**Dependency:** Item #1.
**Verification:** Hover any search result for >300ms → tooltip with 3 related items appears.

---

## 9. Surface `model_score` debug info in dev mode  ⬆ S

**What:** Hard to evaluate ranking quality without seeing scores. Add a `?debug=1` URL flag that overlays each card with its `model_score`, `freshness_boost`, `cold_start` flag. Pure UI / debug, but accelerates every future ranking change.

**Files to touch:**
- `layouts/partials/card.html` (or wherever cards render) — `{{ if eq (querify "debug") "debug=1" }} <small>{{ .model_score }}</small> {{ end }}` (or do it in JS via URL param)
- Probably easier as a tiny `static/js/debug-overlay.js` that injects badges when `?debug=1`

**Estimated LOC:** ~50
**Dependency:** None.
**Verification:** Visit `/?debug=1`; every card shows a small score badge.

---

## Summary table

| # | Win | Stage | Effort | Impact | Files | Free? |
|---|-----|-------|--------|--------|-------|-------|
| 1 | Related-items widget | rerank/UI | S | ⬆⬆⬆ | `layouts/*/single.html` + partial + JS | 🆓 data exists |
| 2 | Continue Reading row | UI | S | ⬆⬆⬆ | `home.html` + reading-history.js | 🆓 data exists |
| 3 | "Because you viewed X" | retrieval (light) | M | ⬆⬆⬆ | new `recommendations.js` | embeddings exist |
| 4 | Spellcheck fallback | retrieval | S | ⬆⬆ | `search-worker.js` | new |
| 5 | MMR diversity rerank | rerank | S | ⬆⬆ | `search-worker.js` | embeddings exist |
| 6 | bge cold-start k-NN | ranking | S | ⬆⬆ | `rank_all_content.py` | embeddings exist |
| 7 | Position-aware logging | ranking | S | ⬆ | `analytics-worker/`, `rank_all_content.py` | data exists, unused |
| 8 | Related on search hover | rerank/UI | S | ⬆⬆ | `unified-search.js` | depends on #1 |
| 9 | Score debug overlay | infra | S | ⬆ | `card.html` or new JS | new |

**Recommended order if you implement them sequentially:**

Start with **1 → 2 → 3** (visible new surfaces, build user-facing momentum). Then **5 → 6** (search/ranking quality). Then **4, 7, 8, 9** (polish + measurement).

Total time if a single engineer does all 9 sequentially: ~5–6 working days.
