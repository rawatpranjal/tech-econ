#!/usr/bin/env python3
"""Fetch and locally cache book cover images.

For each book with a non-empty isbn:
  1. Try Open Library cover CDN (fast, usually has classics).
  2. Fall back to Google Books thumbnail (broader catalogue, no key needed).

Saves covers to static/images/books/{clean_isbn}.jpg and updates
data/books.json image_url field in place.  Atomic write so a crash never
leaves books.json half-written.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, urlunsplit

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]  # checked in main()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = _REPO_ROOT / "data" / "books.json"
OUTPUT_DIR = _REPO_ROOT / "static" / "images" / "books"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQUEST_DELAY = 0.5          # seconds between outbound HTTP calls
TIMEOUT = 15                 # per-request timeout (seconds)
PLACEHOLDER_THRESHOLD = 2048 # bytes — OL returns a tiny body when cover missing

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Pure helpers (importable for tests)
# ---------------------------------------------------------------------------

def build_ol_url(isbn: str) -> str:
    """Return the Open Library cover URL for *isbn* (clean or raw)."""
    clean = slugify_isbn(isbn)
    return f"https://covers.openlibrary.org/b/isbn/{clean}-M.jpg?default=false"


def build_gb_thumbnail_url(volume_info: dict) -> str | None:
    """Extract and clean the thumbnail URL from a Google Books volumeInfo dict.

    Strips the ``&zoom=1`` query param that Google sometimes appends.
    Returns None when no thumbnail is present.
    """
    image_links = volume_info.get("imageLinks", {})
    thumbnail = image_links.get("thumbnail")
    if not thumbnail:
        return None
    # Strip zoom=1 (and any other zoom param) from the query string
    parsed = urlparse(thumbnail)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs.pop("zoom", None)
    new_query = "&".join(
        f"{k}={v[0]}" for k, v in qs.items()
    )
    cleaned = parsed._replace(query=new_query)
    return cleaned.geturl()


def slugify_isbn(isbn: str) -> str:
    """Strip hyphens and spaces from an ISBN string, returning clean digits."""
    return isbn.replace("-", "").replace(" ", "")


def is_placeholder(response_bytes: bytes) -> bool:
    """Return True when *response_bytes* is suspiciously small (OL fallback image)."""
    return len(response_bytes) < PLACEHOLDER_THRESHOLD


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------

def _try_open_library(clean_isbn: str) -> bytes | None:
    """Attempt to fetch a cover from Open Library.

    Returns raw image bytes on success (HTTP 200 + not a placeholder),
    None on failure or placeholder.
    """
    url = f"https://covers.openlibrary.org/b/isbn/{clean_isbn}-M.jpg?default=false"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"    OL request error: {exc}")
        return None

    if resp.status_code != 200:
        print(f"    OL: HTTP {resp.status_code}")
        return None

    if is_placeholder(resp.content):
        print(f"    OL: placeholder ({len(resp.content)} bytes)")
        return None

    return resp.content


def _try_google_books(isbn: str) -> bytes | None:
    """Query Google Books API and download the first result's thumbnail.

    Returns raw image bytes on success, None on any failure.
    """
    api_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        print(f"    GB API error: {exc}")
        return None

    items = data.get("items", [])
    if not items:
        print("    GB: no results")
        return None

    volume_info = items[0].get("volumeInfo", {})
    thumbnail = build_gb_thumbnail_url(volume_info)
    if not thumbnail:
        print("    GB: no thumbnail in volumeInfo")
        return None

    time.sleep(REQUEST_DELAY)
    try:
        img_resp = requests.get(thumbnail, headers=HEADERS, timeout=TIMEOUT)
        img_resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"    GB thumbnail download error: {exc}")
        return None

    if is_placeholder(img_resp.content):
        print(f"    GB: thumbnail placeholder ({len(img_resp.content)} bytes)")
        return None

    return img_resp.content


def _save_image(data: bytes, path: Path) -> None:
    """Write *data* to *path*, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    if requests is None:
        print("Error: requests not installed. Run: pip install requests")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Fetch book cover images.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would happen; make no writes.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N books.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip books where image_url is already non-empty.")
    args = parser.parse_args(argv)

    # Load books
    with open(DATA_PATH, encoding="utf-8") as f:
        books: list[dict] = json.load(f)

    total = len(books)
    print(f"Loaded {total} books from {DATA_PATH}")

    if args.dry_run:
        has_isbn = [b for b in books if b.get("isbn", "").strip()]
        print(f"--dry-run: would attempt covers for {len(has_isbn)} books with ISBN.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    processed = 0
    fetched = 0
    skipped_no_isbn = 0
    skipped_existing = 0
    failed = 0

    candidates = [b for b in books if b.get("isbn", "").strip()]
    if args.limit is not None:
        candidates = candidates[: args.limit]

    for book in candidates:
        name = book.get("name", "Unknown")[:50]
        isbn = book.get("isbn", "").strip()
        clean_isbn = slugify_isbn(isbn)
        current_image = book.get("image_url", "")
        local_path = OUTPUT_DIR / f"{clean_isbn}.jpg"

        processed += 1
        print(f"[{processed}] {name}")

        # Already has a local image on disk → just ensure image_url is set
        if local_path.exists():
            relative = f"/images/books/{clean_isbn}.jpg"
            if book.get("image_url") != relative:
                book["image_url"] = relative
                fetched += 1
                print(f"  Already on disk: {clean_isbn}.jpg")
            else:
                skipped_existing += 1
                print(f"  Up to date: {clean_isbn}.jpg")
            continue

        # --skip-existing: skip if image_url already set
        if args.skip_existing and current_image:
            skipped_existing += 1
            print(f"  Skipping (image_url already set)")
            continue

        # Strategy 1 — Open Library
        print(f"  Trying Open Library (ISBN {clean_isbn})…")
        img_bytes = _try_open_library(clean_isbn)
        time.sleep(REQUEST_DELAY)

        # Strategy 2 — Google Books fallback
        if img_bytes is None:
            print(f"  Falling back to Google Books…")
            img_bytes = _try_google_books(isbn)
            time.sleep(REQUEST_DELAY)

        if img_bytes is not None:
            _save_image(img_bytes, local_path)
            book["image_url"] = f"/images/books/{clean_isbn}.jpg"
            fetched += 1
            print(f"  Saved {clean_isbn}.jpg ({len(img_bytes):,} bytes)")
        else:
            failed += 1
            print(f"  No cover found.")

    # Atomic write of updated books.json
    tmp_path = DATA_PATH.with_suffix(".json.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(books, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, DATA_PATH)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    # Summary
    print(f"\nResults:")
    print(f"  Fetched / updated : {fetched}")
    print(f"  Skipped (existing): {skipped_existing}")
    print(f"  No ISBN           : {skipped_no_isbn}")
    print(f"  Failed            : {failed}")
    print(f"\nImages saved to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
