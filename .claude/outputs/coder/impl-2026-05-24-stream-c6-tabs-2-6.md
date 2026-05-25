# Stream C.6 - /site Tabs 2-6
# 2026-05-24

## Files changed

- `layouts/site/list.html` - Replaced all 5 "Coming soon" stub blocks (Tabs 2-6) with full prose + SVG diagrams
- `CHANGELOG.md` - Added 1-line entry under 2026-05-24
- `docs/roadmap.md` - C.6 marked shipped 2026-05-24 with verification summary

## Tabs shipped

| # | Tab name | Prose word count (approx) | SVG nodes | Cited files |
|---|---|---|---|---|
| 2 | Storage | ~480 | 5 (Browser, Edge Worker, D1, Repo Files, Embeddings) | analytics-worker/index.js, analytics-worker/README.md, tracker.js |
| 3 | Processing | ~590 | 5 (Validate, Enrich, Embed, Cluster, Rank) + feedback loop arc | validate_data.py, enrich_metadata.py, generate_embeddings.py, cluster_resources.py, rank_all_content.py |
| 4 | Recsys | ~440 | 9 (cartoon site map: homepage sub-regions, search, section list, personalization, legend) | home.html, because-you-viewed.js, reading-history.js, personalize.js |
| 5 | How Recs Work | ~640 | 11 (signals fan-in to LightGBM, model_score, 3 use-by boxes, cold-start note) | rank_all_content.py, RANKING_SYSTEM.md, generate_embeddings.py, lib/diversity.py |
| 6 | How A/B Works | ~610 | 5 (User Visit, Hash Bucket, Control/Treatment fork, Event Stream, analysis node) | experiments.js, tracker.js, data/experiments.json, analyze_experiments.py |

## Em-dash check (new tabs only)

- Checked lines 180-750 of list.html (tabs 2-6): 0 em dashes
- Lines 69-175 (Tab 1, signed-off): 12 em dashes present, inherited from prior session, not modified

## Verification

- hugo build: PASS (106 pages, 583ms, 2 pre-existing taxonomy WARNs only)
- npm test: PASS (185/185, 10 test files)
- validate_data: Times out on URL link-check in sandboxed env (same behavior as prior session noted in impl-2026-05-23-stream-c-skeleton.md). No data files modified, so schema validation portion trivially passes.
- grep "Coming soon" layouts/site/list.html: 0 (all stubs replaced)
- git diff --name-only: layouts/site/list.html not in modified list (untracked new file); no data/*.json files modified

## SVG style choices

- All 5 diagrams use viewBox="0 0 860 2XX" width="100%", same as Tab 1
- Marker IDs are unique per diagram (arrow-s, arrow-p, arrow-r, arrow-h, arrow-ab) to avoid conflicts when multiple tabs render simultaneously (though only one is visible)
- Color vocabulary exactly matches Tab 1: blue=#4a9eff/fill=#e8f4ff, orange=#f5a623/fill=#fff3e0, green=#4caf50/fill=#e8f5e9, pink=#e91e63/fill=#fce4ec, purple=#9c27b0/fill=#f3e5f5
- Stage label font: font-size="10" font-weight="600" letter-spacing="0.05em" (matches Tab 1)
- Script/file labels: font-size="9" font-style="italic" in matching stroke color (matches Tab 1)

## Voice decisions

- All prose written for curious non-technical reader (same voice as Tab 1)
- Technical terms explained inline: "embedding" (1024 numbers that capture meaning), "LightGBM" (a type of gradient boosted tree), "FNV-1a" (a hash function), "Reciprocal Rank Fusion" (rank by position in either list), "MMR" (prefer diverse top results)
- Each tab opens with a brief orientation sentence placing it in context
- Cross-references used sparingly: Tab 3 refers to Tab 2 (Storage), Tab 5 refers to Tab 3 (Processing), Tab 4 refers to Tab 5 (How Recs Work)

## Open issues

- SVG inline hex colors don't adapt to dark mode (same as Tab 1; follow-up in a future hygiene pass)
- Tab 1 still has 12 em dashes - those are from the signed-off prior session, outside scope
- Stream C.4 (fresh-agent audit) still required before stream is fully done
