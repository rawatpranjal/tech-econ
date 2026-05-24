# Stream C.9 — /dashboard live page
# 2026-05-24
# Cross-links: docs/roadmap.md Stream C.9, CHANGELOG.md 2026-05-24

## Files created

- `content/dashboard/_index.md` — front-matter: title, description, type=page
- `layouts/dashboard/list.html` — full template: 5-tab bar, inline CSS, scoreboard data embed, script tag
- `static/js/dashboard.js` — 354 lines, 8 exported functions, lazy-fetch + memory cache

## Files modified

- `layouts/_default/baseof.html` — added Live Dashboard nav link (grid SVG, after Under The Hood, before sidebar-footer ul close)
- `CHANGELOG.md` — prepended C.9 entry under 2026-05-24
- `docs/roadmap.md` — appended C.9 shipped line under Stream C

## Architecture decisions

### Scoreboard data embed
`data/site_scoreboard.json` is embedded as `<script id="site-scoreboard-data" type="application/json">` via Hugo's `site.Data.site_scoreboard | jsonify`. Tabs 4 and 5 parse it in JS with `JSON.parse`. No live endpoint for ranker metrics exists yet; this approach means the page is self-contained and works with no network. The `type="application/json"` means the browser never executes it.

### Lazy-fetch pattern
`_loaded = {}` tracks which tab IDs have been fetched. `activateTab(tabId)` calls the tab's loader exactly once. Re-switching tabs re-renders from `_cache` (in-memory, keyed by endpoint string). Zero extra network calls on re-switch.

### Traffic tab multi-fetch
Traffic needs three parallel endpoints. Uses `Promise.allSettled` so one failing endpoint (health degraded, for instance) does not break the other two stats. Each result is null on failure; render function checks for null and shows '--' gracefully.

### CSS scoping strategy
Dashboard CSS is inlined in the template `<style>` block. All new classes are prefixed `.dashboard-*`. The tab bar reuses `.site-tab`, `.site-tab-content` from custom.css. No changes to custom.css (parallel agent constraint).

### nav icon
Used four-square grid SVG (four `<rect>` elements) to distinguish the dashboard link visually from the info-circle (Under The Hood) and bar-chart (experiments tab) already on the page.

## Verification results

- `hugo --gc --minify`: Pages 107 (was 106 + 1 new dashboard page)
- `npm test`: 185/185 passed
- `python3 scripts/validate_data.py`: exit code 0
- Em dash check (`grep -Pc "\xe2\x80\x94"`): 0 in list.html, 0 in dashboard.js
- File-path-in-prose check: 0 user-facing prose violations (3 grep hits are CSS comment + HTML comment + asset script src, all non-prose)

## Mental walkthrough of each tab

1. Traffic: page loads, spinner appears immediately in Traffic content div. Promise.allSettled fires three parallel fetches. On resolve: 4 stat cards (events today, sessions, clicks, 24h-events with health pill). 30-bar CSS grid chart appears, each bar height proportional to that day's count, hover shows tooltip via title attribute. "What this means" paragraph below.

2. Top Content: user clicks tab, spinner shows. /clicks?limit=50 fetched. Renders callout ("top 20 = X% of clicks"), optional type filter select, table of 50 rows with rank/name/type-pill/click-count. filterContentRows() wired to select onchange.

3. Search: spinner, /searches?limit=50 fetched. Two stat cards (total searches, zero-result count). Table of top 20 queries. If any zero-result queries exist, orange callout lists up to 10 of them.

4. ML Models: no network fetch. JSON parsed from embedded script tag. Three stat cards (NDCG@10, HR@10, MAP@10). SVG sparkline (single dot if only one row, polyline if multiple). Eval history table. Replay delta section if replay data present.

5. A/B Tests: no network fetch. Active experiments rendered as green-bordered cards with variant CTR blocks. Past experiments in a table with clickable rows that expand to show full verdict + variant stats.

## Error state

All live-fetch tabs: if fetch throws or status non-200, mount shows red error div with SVG icon + "Could not load live data" + Retry button that calls `location.reload()`. Does not blank the page.

## Open issues

- Hover tooltips on bar chart bars use the HTML `title` attribute, which works on desktop but not mobile touch. A future pass could add a touch-tap overlay.
- Timeseries response field name is assumed to be `data` containing objects with `date` + `events` fields. If the worker returns a different shape (e.g. `{timeseries: [...]}` or `{rows: [...]}`), the chart silently falls through to the "not available" message. Quick fix if needed: add more field-name fallbacks to `renderTraffic`.
- Tab 4 (ML Models) and Tab 5 (A/B Tests) are read from build-time scoreboard data, so they lag by however long since last `build_site_scoreboard.py` run. A future live endpoint from the worker could fix this.
