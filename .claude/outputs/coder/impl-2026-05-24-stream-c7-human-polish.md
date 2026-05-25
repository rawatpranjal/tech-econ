# Stream C.7 - /site Human Polish Pass
# 2026-05-24

## Summary

Polish pass on layouts/site/list.html: removed all em dashes from Tab 1, stripped every
file path / script name / code object reference from all six tabs, and bumped SVG text
sizes from 9-12px developer-doc scale to 13-18px editorial scale.

## Files changed

- `layouts/site/list.html` — all three changes applied (em dashes, code refs, SVG text sizes)
- `CHANGELOG.md` — 1-line entry prepended under 2026-05-24
- `docs/roadmap.md` — C.7 line added after C.6

## Em dash count

- Before: 12 (all in Tab 1 prose)
- After: 0
- Method: replaced with commas, parentheses, colons, or split into two sentences per context

## Code reference count

- File path matches `[a-z_]+\.(py|js|json|html|css|toml|md)`: 34 before / 0 after
- Code object matches `(model_score|te_uid|te_sn|event\.exp|homepage_rows|...)`: 41 before / 0 after
- Every code ref was rewritten to plain English. See "Paraphrases" section below.

## SVG text size bumps

All six diagrams updated. Before/after by element type:

| Element | Before | After |
|---|---|---|
| Node heading (bold label) | 12px | 15px (most) / 18px (Tab 5 key boxes) |
| Sub-label inside node | 10px | 13px |
| Stage label above row | 10px | 14px |
| Script/file italic under node | 9px | Removed entirely (no code refs allowed) |
| Arrow/note labels | 9px | 12-13px |
| Feedback arc label (Tab 3) | 9px | 13px |
| Cold-start note (Tab 5) | 9px | 13px |

viewBox heights adjusted where needed: Tab 1 (220 to 240), Tab 3 (270 to 290),
Tab 4 (270 to 290), Tab 5 (260 to 280), Tab 6 (230 to 250). Tab 2 (240 to 260).

## Key paraphrases (where removing a code ref cost meaning)

1. `model_score` in all prose and SVGs -> "ranking score" or "score" depending on context.
   The concept is preserved; the internal field name is gone.

2. `te_uid`, `te_sn` in Storage SVG and prose -> "user ID cookie" and "session counter."
   Concrete enough for readers.

3. `D1 Database` node in Storage SVG -> "Analytics DB." Italic sub-label changed from
   `Cloudflare SQL (edge)` (kept because it's a company/concept, not a code object).

4. `data/global_rankings.json`, `data/homepage_rows.json` in Storage prose ->
   "A ranking snapshot stores every item's current score" and "A separate pre-computed
   homepage layout describes a list of named rows." Same information, no file paths.

5. `static/embeddings/search-embeddings.bin`, `related-items.json` ->
   "A compact binary file (roughly 16 MB)" and "A third file stores precomputed
   similar-item lists." Size and purpose preserved.

6. `scripts/validate_data.py` (3 occurrences across Tabs 1-3) ->
   "Before anything publishes, we run a quick schema check" / "The gatekeeper runs
   automatically." Process and intent preserved.

7. `scripts/enrich_metadata.py` -> "The enrichment step calls the Claude API."
   Tabs 1 and 3.

8. `scripts/generate_embeddings.py` -> "The embedding step turns each item's text..."
   Tab 3.

9. `scripts/cluster_resources.py` -> "The clustering step groups items..."

10. `scripts/rank_all_content.py` -> "The ranking step is the most complex part..."
    Also: "a machine-learning model" in place of "LightGBM."

11. `LightGBM` in Tab 5 prose and SVG node label -> "Ranking" (SVG) / "a machine-learning
    model (a type of gradient boosted tree, ...)" in prose. The parenthetical keeps the
    technical explanation without the library name.

12. `MMR (Maximal Marginal Relevance)` in Tabs 4 and 5 -> "a diversity pass" (Tab 4) /
    "a diversity pass" with explanation inline (Tab 5). The concept and how it works
    are fully explained; the acronym is gone.

13. `RRF` and "Reciprocal Rank Fusion" kept by name in Tab 5 (it's an algorithm name,
    not a code object, and it's spelled out and explained inline). Removed "MMR" acronym
    from Tab 4 but kept the concept.

14. `event.exp`, `{"harness_aa_v2": "control_a"}` in Tab 6 SVG node ->
    "experiment ID tagged / on every event." In prose: removed the raw JSON example
    and the `exp` field ref; replaced with "something like 'harness_aa_v2: control_a'."
    The concept of what gets tagged is preserved in plain English.

15. `scripts/analyze_experiments.py` in Tab 6 -> "An analysis script then reads those
    events...". SVG analysis node label changed from the script name to "Statistical
    analysis."

16. `harness_aa_v2`, `harness_aa_v1` in Tab 6 prose -> "the current experiment" and
    "an earlier version." Experiment names are internal IDs, not reader-facing.

17. `tracker.js + D1 storage` italic in Tab 6 SVG -> removed (was a code ref label).

18. Tab 5 SVG OUTPUT column node: label changed from `model_score` to `Ranking Score`.
    Sub-label "written to data/*.json" changed to "written to content files."

19. Tab 4 SVG Legend: "ML model score (model_score)" changed to "ML ranking score."
    Section page rank sub-labels: "model_score" changed to "ranking score."

20. Tab 4 Hero Banner sub-label: "top 5 by model_score" changed to "top 5 by ranking score."
    Section Pages sub-labels changed from "model_score" to "ranking score."

21. Tab 2 Storage SVG: "Repo Files" node relabeled "Content Files"; sub-labels
    "data/*.json", "global_rankings.json", "homepage_rows.json" changed to
    "packages, papers, etc." and "rankings output." Edge Worker italic sub-label
    `analytics-worker/index.js` removed; replaced with "Cloudflare edge."
    Embeddings node: file-name sub-labels replaced with "vector embeddings" / "related items."
    Browser node: "te_uid cookie" / "te_sn cookie" changed to "user ID cookie" / "reading history."

## Verification

- `grep -c $'—' layouts/site/list.html`: 0
- `grep -c $'–' layouts/site/list.html`: 0
- `grep -Ec "[a-z_]+\.(py|js|json|html|css|toml|md)" layouts/site/list.html`: 0
- `grep -Ec "(model_score|te_uid|te_sn|event\.exp|homepage_rows|data-type|explore-card|D1|RRF|MMR|LightGBM|BGE|bge-large)" layouts/site/list.html`: 0
- `hugo --gc --minify`: PASS (106 pages, 0 new warnings, same 2 pre-existing taxonomy WARNs)
- `npm test`: PASS (185/185, 10 test files)
- No JS files modified, no CSS files modified, no data files modified.

## Open issues

- SVG inline hex colors still don't adapt to dark mode (pre-existing; scheduled for Stream H).
- Tab 5 mentions "Reciprocal Rank Fusion" by full name with inline explanation. This is
  an algorithm name (like "K-means"), not a code identifier. Left in as acceptable.
- The `harness_aa_v2` ID appeared in Tab 6 prose as an illustrative example. Replaced
  with plain English ("something like...") since it's an internal experiment handle.
