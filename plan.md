---
chunk_id: "N2-book-cover-fetcher"
builder: "sonnet"
verifier: "opus"
status: "building"
strike_count: 2
criteria_fingerprint: "sha256:dfe687f09d63dc37082656d10fe9f4d6a70c68bb880053b6d83e593f34bf8aa6"
branch: "feat/N2-book-cover-fetcher"
archived_commit: null
---

# Chunk N.2 — Book cover image fetcher (ISBN → Open Library / Google Books)

## Goal
Write `scripts/fetch_book_covers.py`, run it against all 102 books, and commit the
downloaded cover images to `static/images/books/`. Update `image_url` in `books.json`
for every book where a cover was found.

Baseline: 102 books, all `image_url: ""`. 96 have non-empty `isbn`; 6 do not.
Primary API: Open Library (free, no key). Secondary: Google Books JSON (no key for basic
queries). Image files land in `static/images/books/{isbn}.jpg`.

## Acceptance criteria

1. **Script exists**: `scripts/fetch_book_covers.py` is present, importable, and has the
   following callable helpers (for testability): `build_ol_url(isbn) -> str`,
   `build_gb_thumbnail_url(volume_info: dict) -> str | None`,
   `slugify_isbn(isbn) -> str`, `is_placeholder(response_bytes: bytes) -> bool`.
2. **CLI flags**: script accepts `--dry-run` (print what would be fetched, no writes),
   `--limit N` (process only N books), `--skip-existing` (skip books that already have a
   non-empty image_url). Running `python3 scripts/fetch_book_covers.py --dry-run` exits 0.
3. **Rate limiting**: at least 0.5 s delay between requests; configurable at the top of the
   file as `REQUEST_DELAY = 0.5`.
4. **Open Library primary**: for a book with a valid ISBN, the script tries
   `https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false`. If HTTP 200 and
   response body > 2 KB (i.e., not a placeholder redirect), it downloads the image and uses
   it. `is_placeholder(bytes)` returns True when len < 2048.
5. **Google Books secondary**: if Open Library returns 404 or placeholder, the script queries
   `https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}` and extracts
   `items[0].volumeInfo.imageLinks.thumbnail`; strips `&zoom=1` query params; downloads the
   thumbnail. If no items or no thumbnail, image_url stays `""`.
6. **Local cache write**: downloaded images are saved to `static/images/books/{isbn}.jpg`.
   `books.json` `image_url` field is updated to `/images/books/{isbn}.jpg`. Atomic write
   via `lib/data_io.py` write helpers (or write-to-temp-then-rename pattern).
7. **Coverage after full run**: after running `python3 scripts/fetch_book_covers.py` (no
   flags), `books.json` has ≥ 60 entries with non-empty `image_url` (≥ 63% of 96 ISBN books
   — some ISBNs legitimately have no cover on either API).
8. **Static images exist**: `static/images/books/` has ≥ 60 `.jpg` files after the run.
9. **Unit tests**: `tests/python/scripts/test_fetch_book_covers.py` has ≥ 8 test cases with
   mocked HTTP covering: valid OL response → image saved; OL placeholder (< 2 KB) → falls
   to GB; OL 404 → falls to GB; GB has thumbnail → image saved; GB empty → image_url stays
   `""`; `build_ol_url` formats correctly; `is_placeholder` thresholds; `--dry-run` produces
   no file writes.
10. **Validator passes**: `python3 scripts/validate_data.py --skip-links` exits 0.
11. **Python suite stable**: `python3 -m pytest tests/python/ -q` exits 0, count ≥ 2029.
12. **JS suite stable**: `npm test` exits 0 at 714/714.

## Tasks

1. Write `scripts/fetch_book_covers.py` following the pattern of
   `scripts/download_dataset_images.py` (rate limiting, slugify, headers, error handling).
   Add the four testable helper functions named above. Add `main()` with argparse.
2. Write `tests/python/scripts/test_fetch_book_covers.py` with ≥ 8 mocked tests.
3. Run `python3 scripts/fetch_book_covers.py --dry-run` to confirm zero errors.
4. Run `python3 scripts/fetch_book_covers.py` (full run — will make ~96 HTTP calls, may
   take 1–2 minutes). Some books will return empty; that is expected.
5. Confirm coverage: count non-empty `image_url` entries in books.json (criterion 7).
6. Run `python3 scripts/validate_data.py --skip-links`, `pytest`, `npm test`.
7. Commit: script, tests, updated books.json, static/images/books/ image files.
8. Set `status: pending_verification`.

## Verdict

(filled in by verifier)
