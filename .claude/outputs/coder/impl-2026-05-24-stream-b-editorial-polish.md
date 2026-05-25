# Stream B — Editorial Polish
# impl-2026-05-24-stream-b-editorial-polish.md
# Coder agent / 2026-05-24
# Cross-ref: docs/roadmap.md §Stream B (B.3, B.4)

## What this covers
B.3 (card color coding) and B.4 (display font extension) from Stream B.
B.1, B.2, B.5, B.6 are NOT touched here.

---

## Files changed

- `static/css/custom.css` — appended ~80-line "Stream B editorial polish" block at end of file (line 11272+)
- `CHANGELOG.md` — 1-line entry under 2026-05-24
- `docs/roadmap.md` — B.3 and B.4 marked partial ✅ with date and detail

No template changes were needed (see Card class wiring below).

---

## Display font extensions

### .explore-row-title
Already handled — two rules already existed before this session:
- Line 10386-10391: `.hero-headline, .home-row .explore-row-title, .section-card h3, .cta-text h2` → `font-family: 'Inter Display'`
- Line 10316-10322: `.home-row .explore-row-title` → `font-size: 1.45rem; font-weight: 700`
No change needed here.

### .explore-card h3 (and hero/compact variants)
Before: inherits body font (system-ui stack), weight 600, no letter-spacing.
After (appended at line 11272): `font-family: 'Inter Display', -apple-system, system-ui, sans-serif; font-weight: 600; letter-spacing: -0.01em`.
Selectors targeted: `.explore-card h3, .explore-card-hero h3, .explore-card-compact h3, .home-trending .explore-card h3`.
The `.home-trending` selector overrides the earlier h3 rule at line 9551-9561 (which had no font-family).

---

## Card color tints

Palette used (matches existing badge colors at line 9371-9385):
- package: rgba(21, 101, 192, 0.04) — blue (#1565c0)
- dataset: rgba(46, 125, 50, 0.04) — green (#2e7d32)
- paper: rgba(230, 81, 0, 0.04) — orange (#e65100)
- resource: rgba(123, 31, 162, 0.04) — purple (#7b1fa2)
- talk: rgba(230, 81, 0, 0.04) — orange-red (#e65100, same family as talk badge)
- career: rgba(0, 131, 143, 0.04) — teal (#00838f)
- community: rgba(194, 24, 91, 0.04) — pink (#c2185b)
- book: rgba(85, 139, 47, 0.04) — olive-green (#558b2f)

Implementation: `linear-gradient(170deg, rgba(..., 0.04) 0%, var(--bg-card) 60%)` — fade from type-tinted top-left to neutral card background. 4% is below the threshold where it reads as "colored" but enough to distinguish types when scanning a row.

Dark mode behavior: **reset to neutral**. The appended rule `[data-theme="dark"] .explore-card[data-type], .explore-card-hero[data-type], .explore-card-compact[data-type]` restores `background: linear-gradient(180deg, #2a2a2e 0%, #232326 100%)` (same as the Phase 2 dark card rule at line 10256-10262). The left-border accent (3px solid, already at line 10264-10288) provides sufficient type signal on dark backgrounds.

Card class wiring: **no template change needed**. All three card partials already emit `data-type="{{ .type }}"` on the root anchor element:
- `row-standard.html` line 12: `data-type="{{ .type }}"`
- `row-hero.html` line 12: `data-type="{{ .type }}"`
- `row-compact.html` line 12: `data-type="{{ .type }}"`

The existing "Type Accent Borders" block at line 10264-10288 also uses `[data-type]`, confirming the pattern was already established.

---

## Verification

- hugo build: PASS (711ms, 0 errors, 0 warnings, 78 HTML files indexed)
- npm test (vitest): PASS — 179 tests across 9 test files, all green
- validate_data.py: PASS (exit code 0)
- Mental browser check: Section row titles ("Trending Now", "New This Month", etc.) render in Inter Display weight 700 with the underline accent. Card titles render in Inter Display weight 600 with -0.01em tracking — tighter, more editorial than the previous system-ui fallback. Each card has a barely-perceptible top-left wash of its type color fading to the card background — packages have a faint blue tinge, datasets faint green, papers faint orange, etc. On dark mode, all cards revert to the standard dark gradient and only the left-border accent distinguishes types (legibility preserved).

---

## Pre-merge checklist

- [x] hugo build passes
- [x] npm test passes (179/179)
- [x] validate_data.py passes
- [ ] B.5 HITL — Pranjal opens `hugo server` and signs off on the visual
- [ ] Commit (Pranjal reviews before any commit per project rules)

---

## Open issues

1. `talk` type tint reuses the paper/orange palette (rgba(230, 81, 0, 0.04)). The talk badge has `#e65100` background with `background: #fff3e0` — so the actual badge accent is orange. The rgba above matches that. However if Pranjal wants talk to feel visually distinct from paper, the talk tint could shift to amber `rgba(255, 143, 0, 0.04)`. Minor — raise at B.5 HITL review.

2. The `data-type` + Inter Display combination produces a small font-specificity interaction: `.home-trending .explore-card h3` had explicit size+weight at line 9551. The new rule adds `font-family` only, so size/weight from line 9551 are preserved. This is correct behavior but worth confirming visually during B.5.

3. There is no `type-paper` entry in the existing `.explore-card-type` badge rules (line 9371-9377 only has package/resource/dataset/talk/career/community/book). Papers appear in the homepage rows via `papers_flat.json` and will hit the card tint rule correctly via `data-type="paper"`, but the badge for papers will have no background color (transparent, default). This is a pre-existing gap not introduced here.
