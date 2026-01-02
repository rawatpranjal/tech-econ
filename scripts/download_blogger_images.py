#!/usr/bin/env python3
"""Download blogger images for local storage.

Downloads images from external URLs in community.json (Blogs category)
and stores them locally in /static/images/bloggers/.
"""

import json
import os
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
OUTPUT_DIR = Path(__file__).parent.parent / "static" / "images" / "bloggers"

# Rate limiting
REQUEST_DELAY = 0.5
TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def slugify(name):
    """Convert name to safe filename."""
    # Remove special chars, lowercase, replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def get_extension(url, content_type=None):
    """Determine file extension from URL or content type."""
    # Try from URL path
    path = urlparse(url).path.lower()
    for ext in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.svg']:
        if path.endswith(ext):
            return ext

    # Try from content type
    if content_type:
        ct = content_type.lower()
        if 'webp' in ct:
            return '.webp'
        elif 'png' in ct:
            return '.png'
        elif 'gif' in ct:
            return '.gif'
        elif 'svg' in ct:
            return '.svg'
        elif 'jpeg' in ct or 'jpg' in ct:
            return '.jpg'

    # Default to jpg
    return '.jpg'


def fetch_og_image(url):
    """Fetch Open Graph image URL from a page."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Try og:image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        # Try twitter:image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]

        return None
    except Exception as e:
        print(f"    Error fetching OG image: {e}")
        return None


def download_image(image_url, output_path):
    """Download image from URL to local path."""
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        response.raise_for_status()

        # Get actual extension from content type
        content_type = response.headers.get('Content-Type', '')
        ext = get_extension(image_url, content_type)

        # Update path with correct extension
        output_path = output_path.with_suffix(ext)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path
    except Exception as e:
        print(f"    Error downloading: {e}")
        return None


def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load community data
    data_path = DATA_DIR / "community.json"
    with open(data_path) as f:
        data = json.load(f)

    # Filter blogs
    blogs = [item for item in data if item.get("category") == "Blogs"]
    print(f"Found {len(blogs)} blogs")
    print(f"Downloading to: {OUTPUT_DIR}\n")

    updated = 0
    skipped = 0
    failed = 0

    for blog in blogs:
        name = blog.get("name", "Unknown")
        url = blog.get("url", "")
        current_image = blog.get("image_url", "")

        print(f"Processing: {name}")

        # Generate local filename
        slug = slugify(name)
        local_path = OUTPUT_DIR / f"{slug}.jpg"  # Extension may change

        # Check if already downloaded (any extension)
        existing = list(OUTPUT_DIR.glob(f"{slug}.*"))
        if existing:
            local_file = existing[0]
            relative_path = f"/images/bloggers/{local_file.name}"
            if blog.get("image_url") != relative_path:
                blog["image_url"] = relative_path
                updated += 1
                print(f"  Already exists: {local_file.name}")
            else:
                skipped += 1
                print(f"  Already up to date: {local_file.name}")
            continue

        # Get image URL to download
        image_url = current_image

        # If no image_url, try to fetch OG image
        if not image_url and url:
            print(f"  No image_url, fetching OG image...")
            image_url = fetch_og_image(url)
            time.sleep(REQUEST_DELAY)

        if not image_url:
            print(f"  No image found, skipping")
            failed += 1
            continue

        # Download the image
        print(f"  Downloading: {image_url[:60]}...")
        downloaded_path = download_image(image_url, local_path)

        if downloaded_path:
            relative_path = f"/images/bloggers/{downloaded_path.name}"
            blog["image_url"] = relative_path
            updated += 1
            print(f"  Saved: {downloaded_path.name}")
        else:
            failed += 1

        time.sleep(REQUEST_DELAY)

    # Save updated data
    if updated > 0:
        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nUpdated community.json")

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"\nImages saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
