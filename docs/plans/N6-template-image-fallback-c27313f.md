---
chunk_id: "N6-template-image-fallback"
builder: "sonnet"
verifier: "opus"
status: "verified"
strike_count: 1
criteria_fingerprint: "sha256:59aed2759be011017484c3343e847f45a5682ef9ac845039c81ac0ddba7d4b50"
branch: "stream-t-ci-reliability"
archived_commit: "c27313f"
---

# Chunk N.6 — Unify template image fallback chain

## Goal
Wire `image_url` as the primary image source in the four templates that currently ignore it
(books, packages, career, community). N.1–N.4 populated the field; the templates still read
from their old ad-hoc sources. After this chunk, every card type follows:
  image_url → content-type specific fallback → initials-on-gradient (last resort).

Since N.5 was skipped (no AI-generated images) and OG images are not stored as a field,
the practical chain is: `image_url` → section-specific fallback → initials-on-gradient.

## Acceptance criteria

1. **books/list.html**: Image block changed to:
   `{{ if .image_url }}` → `<img src="{{ .image_url }}" ...>` (uses `/images/books/{isbn}.jpg`
   for 65 books that have covers).
   `{{ else if .isbn }}` → OpenLibrary fallback `covers.openlibrary.org/b/isbn/...` (existing).
   `{{ else }}` → initials-on-gradient div: class `book-card-fallback`, span with `{{ substr .name 0 2 | upper }}`.

2. **packages/list.html**: Image block changed to:
   `{{ if .image_url }}` → `<img src="{{ .image_url }}" class="pkg-card-logo" loading="lazy" onerror="this.style.display='none'">`.
   Previous logic (computing owner from `github_url`) removed — `image_url` already has the
   full URL (`https://github.com/{owner}.png?size=128`). Empty `image_url` → no badge shown.

3. **career/list.html** (main card favicon, not role-model `.image`):
   `{{ if .image_url }}` → `<img src="{{ .image_url }}" class="favicon" loading="lazy" onerror="this.style.display='none'">`.
   `{{ else if .url }}` → existing lazy-favicon fallback (current behavior, kept intact).
   `{{ else }}` → nothing (no URL, no favicon, no initials needed — career cards have enough text).

4. **community/list.html** (resource favicon):
   `{{ if .image_url }}` → `<img src="{{ .image_url }}" class="resource-favicon" loading="lazy" onerror="this.style.display='none'">`.
   `{{ else if .url }}` → existing `data-src` lazy-favicon fallback (kept intact).

5. **datasets/list.html**: No change (already `image_url → initials-on-gradient`). Criteria confirms file is untouched.

6. **talks/list.html**: No change (already has full chain including favicon fallback). Criteria confirms file is untouched.

7. **papers/list.html**: No change (topic cards, `image_url` if present, text-only otherwise is correct for this type). Criteria confirms file is untouched.

8. **CSS for book fallback**: `.book-card-fallback` added to `static/css/custom.css`:
   - Same gradient pattern as `.dataset-fallback`: 72×100px (book-proportioned), centered initials, a blue-grey gradient default.
   - `.book-card-cover` wrapper already exists; the new fallback div goes in the same wrapper.

9. **Hugo build**: `npm run build` exits 0 with 0 template errors. Page count does not drop.

10. **JS suite**: `npm test` 714/714 (no JS changes expected).

11. **Python suite**: CI-mirror venv (`python3.11`, `requirements-dev.txt`) `pytest tests/python/` exits 0, ≥ 2126 tests pass (no Python changes expected).

12. **Spot-check script** (inline verification, not a pytest): For 5 books with non-empty `image_url`, confirm the template output contains `src="{{ .image_url }}"` not the OpenLibrary URL. For 5 packages with non-empty `image_url`, confirm badge uses the `image_url` value.
    Note: Hugo template correctness is verified via `npm run build` (0 template errors) + a manual grep of the generated HTML for one known book (e.g. isbn 0262046822).

## Tasks

1. Read `layouts/books/list.html` in full to understand the existing image block and `.book-card-cover` structure.
2. Read `layouts/packages/list.html` in full to understand the badge block.
3. Read `layouts/career/list.html` in full to understand the lazy-favicon block (main cards only, not role-models).
4. Read `layouts/community/list.html` in full to understand the resource-favicon block.
5. Edit `layouts/books/list.html`: add `{{ if .image_url }}` branch before existing OpenLibrary block; add `{{ else }}` initials-on-gradient.
6. Edit `layouts/packages/list.html`: replace `{{ if .github_url }}` badge block with `{{ if .image_url }}` sourcing from `image_url`.
7. Edit `layouts/career/list.html`: wrap existing lazy-favicon img in `{{ if .image_url }}` / `{{ else }}` / `{{ end }}`.
8. Edit `layouts/community/list.html`: wrap existing lazy-favicon img in `{{ if .image_url }}` / `{{ else }}` / `{{ end }}`.
9. Append `.book-card-fallback` CSS to `static/css/custom.css`.
10. Run `npm run build` → confirm 0 errors.
11. Grep generated HTML in `public/` for a known book with a cover to confirm `image_url` is used.
12. Run `npm test` → confirm 714/714.
13. Run CI-mirror venv pytest → confirm ≥ 2126 pass.
14. Commit all changes.
