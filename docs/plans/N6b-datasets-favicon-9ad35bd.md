---
chunk_id: "N6b-datasets-favicon-step"
builder: "sonnet"
verifier: "opus"
status: "verified"
strike_count: 0
criteria_fingerprint: "sha256:7c25e41415a2578087c8eb55612bbd6bb52a6ce8b5a329effbe166bb3af441f1"
branch: "stream-t-ci-reliability"
archived_commit: "9ad35bd"
---

# Chunk N.6b — Add favicon step to datasets/list.html before initials-gradient

## Goal
Fix the one remaining goalpost gap from the N.7 audit: 150 dataset cards skip the favicon
step and fall directly to initials-on-gradient. All 150 have a `url` field, so a
`{{ else if .url }}` favicon branch before the gradient eliminates the violation.

## Acceptance criteria

1. **datasets/list.html updated**: Image block at lines 271-280 becomes a three-branch chain:
   - `{{ if .image_url }}` → `<div class="dataset-card-thumbnail"><img src="{{ .image_url }}" ...></div>` (unchanged)
   - `{{ else if .url }}` → `<div class="dataset-card-thumbnail dataset-favicon-placeholder"><img src="https://www.google.com/s2/favicons?domain={{ .url | replaceRE "^https?://([^/]+).*" "$1" }}&sz=128" alt="" class="dataset-favicon-large" loading="lazy" onerror="this.style.display='none'"></div>`
   - `{{ else }}` → `<div class="dataset-card-thumbnail dataset-fallback" data-category="{{ .category }}"><span class="dataset-initials">{{ substr .name 0 2 }}</span></div>` (unchanged)

2. **CSS in datasets/list.html** (inline `<style>` block at top of file): Two new rules appended:
   - `.dataset-favicon-placeholder`: extends `.dataset-card-thumbnail` display to `flex`, `align-items: center`, `justify-content: center`. (`.dataset-card-thumbnail` already sets `width: 100%; aspect-ratio: 16/9; background: var(--bg-hover);`.)
   - `.dataset-favicon-large`: `width: 64px; height: 64px; object-fit: contain; border-radius: 6px;`
   (Note: `dataset-favicon-placeholder` inherits the neutral `background: var(--bg-hover)` from `dataset-card-thumbnail` — no additional background needed.)

3. **Goalpost impact**: 150 dataset cards that previously showed initials-on-gradient now show a favicon on a neutral background. The `{{ else }}` initials branch stays as last resort for any entry with no `url` (currently 0 such entries, but kept for safety).

4. **No data changes**: `data/datasets.json` untouched.

5. **Hugo build**: `npm run build` exits 0, 0 template errors.

6. **JS suite**: `npm test` 714/714 (no JS changes).

7. **Python suite**: `pytest tests/python/` ≥ 2126 pass (no Python changes).

8. **Spot-check**: After `npm run build`, grep `public/datasets/` for a dataset with no `image_url` but with a `url`. Confirm the generated HTML contains `dataset-favicon-placeholder` and `google.com/s2/favicons`.

## Tasks

1. Read `layouts/datasets/list.html` lines 265-285 to confirm the exact existing block.
2. Edit the `{{ if .image_url }}...{{ else }}...{{ end }}` block to add the `{{ else if .url }}` favicon branch.
3. Append the two CSS rules to the existing `<style>` block in `layouts/datasets/list.html`.
4. Run `npm run build` and confirm 0 errors.
5. Spot-check: pick one dataset with no image_url (e.g. "Pastor-Stambaugh Liquidity Factors") and grep the public/ output.
6. Run `npm test` → 714/714.
7. Run Python suite → ≥ 2126 pass.
8. Commit: `feat(N6b): add favicon fallback step to datasets template before initials-gradient`.
