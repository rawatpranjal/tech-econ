"""Populate image_url for career.json and community.json using Google favicon URLs.

Favicon URLs are deterministic — no HTTP requests needed.
Format: https://www.google.com/s2/favicons?domain={domain}&sz=128

Usage:
    python3 scripts/fetch_career_community_images.py
    python3 scripts/fetch_career_community_images.py --dry-run
    python3 scripts/fetch_career_community_images.py --limit 10
    python3 scripts/fetch_career_community_images.py --skip-existing
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

CAREER_PATH = Path(__file__).resolve().parents[1] / "data" / "career.json"
COMMUNITY_PATH = Path(__file__).resolve().parents[1] / "data" / "community.json"


def extract_domain(url: str | None) -> str | None:
    """Extract the netloc from a URL, stripping the www. prefix.

    Examples:
        "https://www.linkedin.com/in/foo"  -> "linkedin.com"
        "https://instacart.careers/"       -> "instacart.careers"
        "https://recsys.acm.org/"          -> "recsys.acm.org"
        None                               -> None
        ""                                 -> None
        "not-a-url"                        -> None
    """
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc
        if not netloc:
            return None
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else None
    except Exception:
        return None


def build_favicon_url(domain: str) -> str:
    """Return the Google favicon URL for a domain."""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"


def _process(
    data: list[dict],
    skip_existing: bool,
    limit: int | None,
) -> tuple[list[dict], int, int, int]:
    """Process entries in-place. Returns (data, updated, skipped, processed)."""
    updated = skipped = processed = 0

    for item in data:
        if limit is not None and processed >= limit:
            break

        existing = item.get("image_url", "")
        if skip_existing and existing:
            skipped += 1
            continue

        domain = extract_domain(item.get("url"))
        image_url = build_favicon_url(domain) if domain else ""

        item["image_url"] = image_url
        processed += 1
        if image_url:
            updated += 1

    # Ensure the key exists on ALL entries (safe even beyond --limit)
    for item in data:
        if "image_url" not in item:
            item["image_url"] = ""

    return data, updated, skipped, processed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen, make no writes")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N entries per file")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip entries that already have a non-empty image_url")
    args = parser.parse_args(argv)

    for path in (CAREER_PATH, COMMUNITY_PATH):
        data = json.loads(path.read_text())
        data, updated, skipped, processed = _process(data, args.skip_existing, args.limit)

        coverage = sum(1 for item in data if item.get("image_url"))
        label = path.stem  # "career" or "community"
        print(
            f"[{label}] Processed {processed} — {updated} got favicon URLs, "
            f"{skipped} skipped"
        )
        print(f"[{label}] Coverage: {coverage}/{len(data)} non-empty image_url")

        if args.dry_run:
            print(f"[{label}] Dry run — no write.")
            continue

        tmp = str(path) + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
        print(f"[{label}] Wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
