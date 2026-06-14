"""Populate image_url for packages.json using GitHub org/user avatar URLs.

Avatar URLs are deterministic — no HTTP requests needed.
Format: https://github.com/{owner}.png?size=128

Usage:
    python3 scripts/fetch_package_images.py
    python3 scripts/fetch_package_images.py --dry-run
    python3 scripts/fetch_package_images.py --limit 10
    python3 scripts/fetch_package_images.py --skip-existing
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "packages.json"


def parse_github_owner(url: str | None) -> str | None:
    """Extract the first path segment (owner/org) from a GitHub URL.

    Examples:
        "https://github.com/DoubleML/foo"  -> "DoubleML"
        "https://github.com/facebook/Ax"   -> "facebook"
        "https://cran.r-project.org/"      -> None
        None                               -> None
    """
    if not url:
        return None
    if "github.com/" not in url:
        return None
    # Take everything after "github.com/"
    after = url.split("github.com/", 1)[1]
    # First segment is the owner; strip trailing slashes / query strings
    owner = after.split("/")[0].split("?")[0].split("#")[0].strip()
    return owner if owner else None


def build_avatar_url(owner: str) -> str:
    """Return the GitHub avatar URL for an owner/org."""
    return f"https://github.com/{owner}.png?size=128"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen, make no writes")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N entries")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip entries that already have a non-empty image_url")
    args = parser.parse_args(argv)

    packages = json.loads(DATA_PATH.read_text())

    updated = 0
    skipped = 0
    processed = 0

    for pkg in packages:
        if args.limit is not None and processed >= args.limit:
            break

        existing = pkg.get("image_url", "")
        if args.skip_existing and existing:
            skipped += 1
            continue

        # Precedence: github_url first, then url
        owner = parse_github_owner(pkg.get("github_url")) or \
                parse_github_owner(pkg.get("url"))

        image_url = build_avatar_url(owner) if owner else ""

        pkg["image_url"] = image_url
        processed += 1
        if image_url:
            updated += 1

    # Fill any entries not yet touched (beyond --limit) with "" if key missing
    for pkg in packages:
        if "image_url" not in pkg:
            pkg["image_url"] = ""

    coverage = sum(1 for p in packages if p.get("image_url"))
    print(f"Processed {processed} entries — {updated} got avatar URLs, {skipped} skipped")
    print(f"Total coverage: {coverage}/{len(packages)} non-empty image_url")

    if args.dry_run:
        print("Dry run — no writes.")
        return 0

    tmp = str(DATA_PATH) + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(packages, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, DATA_PATH)
    print(f"Wrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
