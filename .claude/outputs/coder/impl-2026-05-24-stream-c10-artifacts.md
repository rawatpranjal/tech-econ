# C.10 Under The Hood Artifact Enrichment
Date: 2026-05-24
Tabs: 1 (Ingestion), 2 (Storage), 3 (Processing), 4 (Recsys Surfaces), 5 (How Recs Work), 6 (How A/B Works)

## Summary
Added 16 new artifacts across Tabs 1-6 of layouts/site/list.html. Each tab now has 2-4 concrete artifacts (running examples, pull-quotes, conceptual snippets, comparison panels, mini diagrams, real-data tables) that break up the prose and ground the page in real data.

## Files Modified

- `layouts/site/list.html` — Tabs 1-6 artifact additions only. Tabs 7+8 untouched. Tab nav untouched.
- `static/css/custom.css` — New component block appended after `.site-json-arrow` rules (~280 lines). 9 new classes with dark mode + mobile.
- `CHANGELOG.md` — 1-line entry prepended under 2026-05-24.
- `docs/roadmap.md` — C.10 entry added as shipped 2026-05-24.

## Artifacts Added Per Tab

| Tab | Artifact 1 | Artifact 2 | Artifact 3 |
|---|---|---|---|
| 1 (Ingestion) | Running example: DoubleML raw vs enriched (real item) | Pull-quote: "Curation is a craft, not a pipeline" | |
| 2 (Storage) | Real-data table: 8 content types with actual row counts | Conceptual snippet: illustrative analytics event JSON | Pull-quote: edge computing in plain language |
| 3 (Processing) | Conceptual snippet: ranking formula with actual weights from recsys_config.json | Running example: Stefan Wager top-ranked item (score 1.00, 73 clicks) | Mini SVG: cold-start propagation (4 nodes) |
| 4 (Recsys) | Running example: actual homepage trending row top 5 items (May 2026) | Comparison panel: first-time vs returning visitor side-by-side | |
| 5 (How Recs Work) | Real-data table: 12 signals with actual weights from recsys_config.json | Pull-quote: Daniel Tunkelang paraphrase on relevance | Conceptual snippet: RRF search fusion pseudocode + running example |
| 6 (How A/B Works) | Conceptual snippet: experiment declaration JSON shape | Running example: harness_aa_v1 real CTR numbers (4.0% vs 2.3%, honest framing) | Pull-quote: epistemic humility + mini SVG: switchback time-axis |

## Real Examples Used

- Tab 1: DoubleML (data/packages.json — real enrichment fields)
- Tab 2: All 8 content types with real row counts from python count pass (packages:551, career:639, datasets:443, resources:518, community:452, talks:265, papers:~400+, books:102)
- Tab 3: Stefan Wager "Causal Inference: A Statistical Learning Approach" (data/global_rankings.json — score:1.00, 73 clicks, 487 coviews); DoubleML and causalml as cold-start neighbors
- Tab 3: Ranking weights from data/recsys_config.json (actual: clicks:5.0, search_click:3.0, scroll_90:2.0, deep_session:1.5, dwell:1.0, impressions:0.5, coclick:0.3, coview:0.1, freshness:0.15, rage_click:-2.0, quick_bounce:-1.0, high_imp_no_click:-1.0)
- Tab 4: Homepage trending row top 5 from data/homepage_rows.json (Wager, Facure, JD.com MSOM-20, Causal Econometrics Course, BestBuy)
- Tab 5: Same weights table (recsys_config.json); search example uses "difference in differences" as plausible real query
- Tab 6: harness_aa_v1 real numbers from data/site_scoreboard.json (control_a: 8,071 imp / 4.0% CTR; control_b: 10,205 imp / 2.3% CTR, 57 contaminated users, z=-6.5)

## CSS Additions

Classes added (9 base + variants):
- `.under-hood-callout` (base)
- `.under-hood-callout.callout-quote` (pull-quote with large open-quote glyph)
- `.under-hood-callout.callout-example` (running example with "EXAMPLE" label)
- `.under-hood-callout.callout-aside` (small grey note)
- `.under-hood-snippet-label` (small label above code block)
- `.under-hood-snippet` (dark code block, Catppuccin Mocha palette)
- `.under-hood-comparison` (2-column grid)
- `.under-hood-comparison-pane` + `.pane-before/.pane-after/.pane-left/.pane-right`
- `.under-hood-mini-diagram` + `.under-hood-mini-diagram-label`
- `.under-hood-data-table` + `.ud-pos` / `.ud-neg` (colored weight cells)

All classes have dark mode overrides and mobile (max-width:640px) rules.

## Verification

- hugo --gc --minify: 107 pages, 0 errors
- npm test: 185/185 passed
- validate_data.py: exit code 0 (confirmed via background task completion)
- grep -c U+2014 layouts/site/list.html: 0
- grep -Ec file-path-pattern layouts/site/list.html: 0

## Open Issues

- Hugo page count went from 106 to 107 due to the parallel C.9 dashboard page (not this task). This task touches no content/*.md files, so page count is unaffected by C.10 itself.
- Tab 2 snippet uses `<span>` tags for syntax coloring inside `<pre><code>`. This is safe for display but means the code would not paste cleanly. Acceptable for an illustrative snippet.
