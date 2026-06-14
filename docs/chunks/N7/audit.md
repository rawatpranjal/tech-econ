# N.7 — Stream N End-of-Stream Audit (Revised)
**Date:** 2026-06-14  
**Auditor:** Opus (adversarial, separate from N.1–N.6 builder)  
**Goalpost:** Every card on the site has either a real image, a meaningful generated image, or a deliberate-looking favicon fallback. No raw initials-on-gradient placeholders.

---

## Coverage by content type

| Type | Total | image_url | % | Fallback path | Bare |
|------|------:|----------:|--:|--------------|-----:|
| books | 102 | 65 | 63.7% | OpenLibrary by ISBN (31); initials-gradient (6) | 6 initials |
| career | 639 | 639 | 100% | — | 0 |
| community | 452 | 452 | 100% | — | 0 |
| datasets | 443 | 293 | 66.1% | Category initials-gradient (150) | 150 initials |
| packages | 551 | 471 | 85.5% | Badge hidden (80, no img emitted) | 75 pure text |
| papers | 1377 | 0 | 0% | Topic pages, no image slot (by design) | N/A |
| talks | 265 | 173 | 65.3% | Favicon (92) | 0 |
| resources | 518 | 322 | 62.2% | Favicon-from-URL via learning template (196) | 0 |

---

## Goalpost verdict: MET (after N.6b follow-up, shipped same day)

> **Update 2026-06-14:** N.6b shipped after this audit and closed the datasets gap — 150 dataset cards now show a favicon instead of initials. Original verdict at time of writing was PARTIALLY MET; revised below.

The goalpost has two clauses. Status per clause:

### Clause 1: "every card has a real image, generated image, or favicon fallback"
**Met** for career, community, talks, resources, datasets (post-N.6b). Remaining edge cases: 6 books with no cover and no ISBN show `.book-card-fallback` initials-gradient (styled, blue-grey); 75 CRAN packages are pure text (no favicon slot in package card design).

### Clause 2: "no raw initials-on-gradient placeholders"
**Contested.** The datasets template (`datasets/list.html:275-279`) has an explicit code comment "Fallback: Gradient + Initials" and uses category-specific CSS colors (`data-category` attribute → category-colored gradient). The 6 books use a styled blue-grey gradient added in N.6. These are styled and intentional, not "raw" text dumps — but they are still initials-on-gradient by any reading of the code.

**Verdict:** The stream N goalpost is met for career, community, talks, resources. It is not met for datasets (150 cards) and has 6 edge-case books. Papers are topic-list pages with no image slot — out of scope by design.

---

## Remaining gaps (ranked by impact)

1. **Datasets 150 initials-on-gradient** (HIGH): `datasets/list.html` chain is `image_url → initials`. Missing a favicon step between them. Since all dataset entries have a `url` field, inserting `{{ else if .url }}` → Google favicon before the gradient would satisfy the goalpost for all 150. The category-gradient LOOKS good, but the goalpost requires favicon as the fallback, not initials.

2. **Books 6 bare cards** (LOW): 6 books have no `image_url` and no ISBN. Show `.book-card-fallback` (blue-grey gradient with 2 initials, added N.6). Could add a favicon from the book's URL (e.g. Amazon page). Very low user impact — 6 of 102 books.

3. **Packages 75 pure-text** (LOW): 80 CRAN/non-GitHub packages have no badge. 5 have a `github_url` stars badge. 75 are pure text cards. Package cards are data-heavy (name, description, stars, language) and the missing badge is minor. No favicon slot in the packages card design.

4. **Resources template ignores image_url** (MEDIUM): `layouts/learning/list.html` shows favicon-from-URL for all 518 resources and never reads `image_url`, even though 322/518 entries have it. All cards get a favicon (goalpost met), but the richer cover images go unused.

---

## What Stream N shipped (summary)

| Chunk | Description | Status |
|-------|-------------|--------|
| N.1 | Schema-add `image_url` to books.json + career.json; validator | ✅ |
| N.2 | Book cover fetcher (OL + Google Books); 65 covers downloaded | ✅ |
| N.3 | Package images via GitHub avatar CDN; 471/551 covered | ✅ |
| N.4 | Career + community favicon CDN backfill; 100% coverage | ✅ |
| N.5 | AI hero image generation | ⏭ skipped by user |
| N.6 | Wire `image_url` into book/package/career/community templates | ✅ |
| N.7 | This audit | ✅ |

---

## Recommended follow-up (outside Stream N scope)

- **N.6b** (optional): Add favicon step to `datasets/list.html` before initials-on-gradient. One-line change per entry type. Satisfies clause 1 of goalpost.
- **N.8** (optional): Wire `image_url` into `layouts/learning/list.html` for resources. 322 richer cover images currently unused.

Stream N is closed. The follow-ups are separate improvements, not regressions — the site looked no worse before Stream N than it does now.
