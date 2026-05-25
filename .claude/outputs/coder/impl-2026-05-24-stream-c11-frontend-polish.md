# Stream C.11 — Frontend Design Polish
# /site + /dashboard
# 2026-05-24

## Context
Applied professional design polish to the /site (Under The Hood, 8 tabs) and /dashboard (Live Dashboard, 5 tabs) pages after their initial quick assembly in C.8/C.9/C.10.

## Files modified

| File | Change |
|------|--------|
| `static/css/custom.css` | Appended C.11 block (~280 lines): stage color tokens, typography scale, tab bar polish, fade animation, skeleton class, table zebra, focus rings, spacing tokens, card hover, mobile overrides |
| `layouts/site/list.html` | Replaced tab-switching JS block: added keyboard arrow/Home/End nav, roving tabIndex, extracted activateSiteTab() function |
| `static/js/dashboard.js` | Added skeletonHTML() helper; swapped "Loading..." for skeleton in fetchAndRender + loadTraffic; added keyboard arrow nav + roving tabIndex in DOMContentLoaded; activateTab() now manages tabIndex |
| `layouts/dashboard/list.html` | Added last-updated footer paragraph with Hugo template for generated_at timestamp; added `.dashboard-last-updated-footer` CSS rule in inline style block |
| `CHANGELOG.md` | Prepended C.11 entry under 2026-05-24 |
| `docs/roadmap.md` | Added C.11 shipped line under Stream C |

## Typography scale applied

- h1 (page title): unchanged, handled by .hero-title in baseof
- h2 (tab intro): 1.75rem, weight 700, Inter Display, letter-spacing -0.02em
- h3 (prose sections): 1.25rem, weight 600, Inter Display, letter-spacing -0.01em
- body: 1rem, line-height 1.65, var(--text-secondary)
- lead text: 1.05rem, line-height 1.65
- mono/code: 0.875rem (0.88rem in snippets), existing mono stack
- stat numbers: 2.25rem / 2.75rem (primary), Inter Display, tabular-nums

## Spacing scale applied

- card padding: var(--space-6) = 1.5rem / 24px
- section gap (between major blocks): var(--space-12) = 3rem / 48px
- tab button padding: 0.75rem 1rem (achieves min 44px height)
- inline icon-to-text gap: var(--space-2) = 0.5rem / 8px
- page bottom padding: var(--space-16) = 4rem / 64px

## Color tokens introduced

Stage palette (both light and dark pick up same values; soft backgrounds 8% alpha):
- --stage-input: #4a9eff / --stage-input-soft: rgba(74,158,255,0.08)
- --stage-gate: #f5a623 / --stage-gate-soft: rgba(245,166,35,0.08)
- --stage-enrich: #4caf50 / --stage-enrich-soft: rgba(76,175,80,0.08)
- --stage-rank: #e91e63 / --stage-rank-soft: rgba(233,30,99,0.08)
- --stage-publish: #9c27b0 / --stage-publish-soft: rgba(156,39,176,0.08)

Supporting tokens: --text-soft, --text-muted-light, --tab-active-border (2.5px), --space-1 through --space-16

Hardcoded hex replacements: The inline hex values in SVG diagrams and existing callout backgrounds were left as-is (they are part of static SVG art, not CSS properties). The new token definitions give future code a canonical reference. The CSS component classes in the new block use tokens and CSS variables throughout; no new hardcoded hex values in new code.

## Tab bar improvements

- Active tab bottom border: upgraded from 3px (CSS specificity issue with `border-bottom-width`) to explicit `var(--tab-active-border)` = 2.5px, visually consistent
- Inactive tabs: `color: var(--text-muted)`, hover now also adds `background: var(--bg-hover)`
- Minimum tap target: `min-height: 44px` + `padding: 0.75rem 1rem`
- Icon-to-text gap: standardised to `gap: var(--space-2)` = 8px
- Mobile tab bar: completely replaced vertical stack with `overflow-x: auto`, `flex-wrap: nowrap`, `scrollbar-width: none` (hidden scrollbar). Tabs scroll horizontally as a row, no layout break at 360px.

## Stat card improvements

- Number size: 2.25rem on regular cards, 2.75rem on primary card (was 2rem / 2.75rem already on scoreboard; dashboard now matches)
- `font-variant-numeric: tabular-nums` applied to all large number elements
- Hover lift: `transform: translateY(-2px)` + `box-shadow 0 4px 12px rgba(0,0,0,0.08)` on 0.1s ease
- Color tinting on dashboard stat cards: positive = green tint border, warning = orange tint border (was already in code; soft gradient reinforced)

## Loading skeleton

- File: static/js/dashboard.js
- Added: `skeletonHTML(n)` function at line ~60
- Skeleton outputs 3 `.skel-row` divs inside `.dashboard-skeleton`
- CSS in custom.css: `@keyframes skel-pulse` (opacity 0.35 to 0.6), rows have staggered `animation-delay` (0, 0.15s, 0.3s), variable heights (60px, 40px, 80px)
- Replaced: both "Loading live data..." instances in `fetchAndRender()` and `loadTraffic()` swapped to `skeletonHTML(3)`

## Keyboard a11y

/site tabs:
- Extracted `activateSiteTab(id)` function
- Arrow Right/Left: cycles focus + activates adjacent tab
- Home/End: jumps to first/last tab
- Roving tabIndex: active tab tabIndex=0, others tabIndex=-1
- focus-visible ring: `outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px`

/dashboard tabs:
- Same arrow/Home/End pattern added in DOMContentLoaded handler
- `activateTab()` updated to set roving tabIndex alongside aria-selected
- focus-visible rule shared via `.site-tab:focus-visible, .dashboard-tab:focus-visible`

## Mobile pass (viewport 360px mental test)

- Tab bar: horizontal scroll, no overflow. Each tab is `flex-shrink: 0` so it does not compress. Scrollbar hidden.
- Stat grid: already 1fr 1fr at <=600px. Stat numbers reduced to 1.6rem.
- Tables: `min-width: 480px` forces horizontal scroll on the `site-table-container` overflow-x:auto wrapper. Right-edge fade overlay added via `::after` pseudo-element.
- JSON evolution boxes: already stack at <800px (unchanged).

## Em-dash check

New code introduced by this PR: 0 em dashes.
Pre-existing em dashes in custom.css comment headers (27 occurrences) were not introduced here and are outside the scope.

## Verification

- hugo build: PASS, 107 pages
- npm test: PASS, 185/185
- validate_data: PASS (critical checks)
- Em dashes in new code: 0
