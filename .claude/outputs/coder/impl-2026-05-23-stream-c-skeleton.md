# Stream C Skeleton — /site page (Tab 1: Ingestion)
# 2026-05-23

## Files created / modified

- `content/site/_index.md` — front-matter only, no body. Title "How It Works", description. Hugo uses layouts/site/list.html automatically (same pattern as about section).
- `layouts/site/list.html` — full tabbed template. Extends baseof.html via `{{ define "main" }}`. Tab bar with 6 buttons. Tab 1 (Ingestion) is fully built; Tabs 2–6 are stubs. Inline JS for tab switching at bottom of file.
- `static/css/custom.css` — appended .site-tabs, .site-tab, .site-tab.active, .site-tab-content, .site-tab-content.active, .site-diagram-container, .site-prose, .site-coming-soon, and responsive stacking below 600px.
- `layouts/_default/baseof.html` — added "How It Works" nav link after the About link, using info-circle icon (circle + line + dot), same li/a/svg structure as all other sidebar links.

## Tab 1 (Ingestion) content

- Word count: approximately 580 words of prose
- SVG diagram: 5 nodes (Sources → Validation → Enrichment → Ranking → Published), each 130×80px with colored borders by stage (blue/orange/green/pink/purple). Arrows between nodes. Stage labels above each node (INPUT / GATE / ENRICH / RANK / PUBLISH). Script names below processing nodes in italic. viewBox 860×220, width 100%.
- Cited scripts: validate_data.py (validation), enrich_metadata.py (enrichment), rank_all_content.py (ranking). Also references submit-worker conceptually.
- Prose sections: What comes in / Where it comes from / Validation / Enrichment / Ranking / Where it lives

## Tab structure

Tabs 2–6 placeholder text (each is identical structure — intro + coming-soon block):

- Tab 2 Storage: "Coming soon — this tab covers the Cloudflare D1 analytics database, the data/*.json content files, and the binary embeddings index. See roadmap Stream H."
- Tab 3 Processing: "Coming soon — this tab covers the ranking pipeline, embedding generation, and clustering scripts. See roadmap Stream H."
- Tab 4 Recsys: "Coming soon — this tab covers the homepage rows, search results, related-items widget, and trending row. See roadmap Stream H."
- Tab 5 How Recs Work: "Coming soon — this tab covers ranker features, cold-start k-NN propagation, MMR diversity re-ranking, and feature flags. See roadmap Stream K."
- Tab 6 How A/B Works: "Coming soon — this tab covers deterministic user bucketing, server-side event ingestion, and switchback experiment design. See roadmap Stream K."

## Verification

- hugo build: PASS (774ms, 106 pages, 2 pre-existing taxonomy WARN lines only — not new)
- public/site/index.html: exists, contains 7 matches for site-tab class variants
- Nav link: confirmed present in public/index.html pointing to /site/
- validate_data: PASS (exit code 0, all required fields present, no duplicate URLs; URL link-checking runs slowly over network but completed clean)
- JSON validity: all data/*.json parse without errors (no data files were touched)

## Open issues / questions

- CSS uses `--accent` (the real variable), not `--accent-color` (undefined reference used in career-tab CSS). Site-tab CSS will render correctly; career-tab active color is silently missing. Could fix the career-tab reference in a future hygiene pass.
- The SVG diagram uses inline hex colors for node fills (e.g. #e8f4ff, #fff3e0) rather than CSS variables because SVG fill attributes don't pick up CSS custom properties in all browsers. This means the node colors won't adapt to dark mode. Could be improved in a later pass by using CSS classes on the SVG rects and setting fill via CSS.
- Tabs 2–6 stub links point to the GitHub repo as a stand-in for the roadmap. Stream H/K tasks will replace this when those tabs are built.
