#!/usr/bin/env python3
"""
Fetch Open Graph images for talks, podcasts, and blogs.
Adds image_url field to entries that don't have one.

Usage:
    python3 scripts/fetch_og_images.py [--file talks.json] [--dry-run]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required packages not installed")
    print("Install with: pip install requests beautifulsoup4")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests
TIMEOUT = 10  # request timeout

# User agent to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def extract_youtube_thumbnail(url):
    """Extract YouTube video thumbnail from URL."""
    # Match various YouTube URL formats
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            # Use maxresdefault for high quality, fallback to hqdefault
            return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

    # YouTube channel - return None (will use placeholder)
    if "youtube.com/c/" in url or "youtube.com/@" in url or "youtube.com/channel/" in url:
        return None

    return None


def fetch_og_image(url):
    """Fetch Open Graph image from a URL."""
    try:
        # First check if it's a YouTube URL
        yt_thumb = extract_youtube_thumbnail(url)
        if yt_thumb:
            return yt_thumb

        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Try og:image first
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        # Try twitter:image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]

        # Try twitter:image:src
        twitter_image_src = soup.find("meta", attrs={"name": "twitter:image:src"})
        if twitter_image_src and twitter_image_src.get("content"):
            return twitter_image_src["content"]

        return None

    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def process_file(filepath, dry_run=False):
    """Process a JSON file and add image_url where missing."""
    print(f"\nProcessing {filepath.name}...")

    with open(filepath) as f:
        data = json.load(f)

    updated = 0
    skipped = 0
    failed = 0

    for item in data:
        name = item.get("name", item.get("title", "Unknown"))
        url = item.get("url", "")

        # Skip if already has image_url
        if item.get("image_url"):
            skipped += 1
            continue

        # Skip if no URL
        if not url:
            continue

        print(f"  Fetching: {name[:50]}...")

        if dry_run:
            print(f"    Would fetch: {url}")
            continue

        image_url = fetch_og_image(url)

        if image_url:
            item["image_url"] = image_url
            updated += 1
            print(f"    Found: {image_url[:60]}...")
        else:
            failed += 1
            print(f"    No image found")

        time.sleep(REQUEST_DELAY)

    if not dry_run and updated > 0:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nSaved {filepath.name}")

    print(f"\nResults for {filepath.name}:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already have image): {skipped}")
    print(f"  Failed: {failed}")

    return updated


def main():
    parser = argparse.ArgumentParser(description="Fetch OG images for content")
    parser.add_argument("--file", help="Specific file to process (e.g., talks.json)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    args = parser.parse_args()

    if args.file:
        filepath = DATA_DIR / args.file
        if not filepath.exists():
            print(f"Error: {filepath} not found")
            sys.exit(1)
        process_file(filepath, args.dry_run)
    else:
        # Process talks.json and community.json by default
        for filename in ["talks.json", "community.json"]:
            filepath = DATA_DIR / filename
            if filepath.exists():
                process_file(filepath, args.dry_run)


if __name__ == "__main__":
    main()
