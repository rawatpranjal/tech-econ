#!/usr/bin/env python3
"""Download dataset images for local storage.

Downloads images from dataset URLs (OG images, favicons) and stores
them locally in /static/images/datasets/.
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
OUTPUT_DIR = Path(__file__).parent.parent / "static" / "images" / "datasets"

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
    return slug[:80]  # Limit length


def get_extension(url, content_type=None):
    """Determine file extension from URL or content type."""
    path = urlparse(url).path.lower()
    for ext in ['.webp', '.png', '.jpg', '.jpeg', '.gif', '.svg']:
        if path.endswith(ext):
            return ext

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
            img_url = og_image["content"]
            # Make absolute if relative
            if img_url.startswith('/'):
                parsed = urlparse(url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
            return img_url

        # Try twitter:image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img_url = twitter_image["content"]
            if img_url.startswith('/'):
                parsed = urlparse(url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
            return img_url

        return None
    except Exception as e:
        print(f"    Error fetching OG image: {e}")
        return None


def get_github_avatar(github_url):
    """Extract GitHub owner avatar URL from repo URL."""
    if not github_url:
        return None
    # Extract owner from URL like https://github.com/owner/repo
    match = re.search(r'github\.com/([^/]+)', github_url)
    if match:
        owner = match.group(1)
        return f"https://github.com/{owner}.png?size=256"
    return None


def get_favicon_url(url):
    """Get high-res favicon URL via Google's service."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split('/')[0]
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"


def download_image(image_url, output_path):
    """Download image from URL to local path."""
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        response.raise_for_status()

        # Check content length - skip very small images (likely placeholders)
        content_length = int(response.headers.get('Content-Length', 0))
        if content_length > 0 and content_length < 1000:
            print(f"    Image too small ({content_length} bytes), skipping")
            return None

        content_type = response.headers.get('Content-Type', '')
        ext = get_extension(image_url, content_type)
        output_path = output_path.with_suffix(ext)

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify file size after download
        if output_path.stat().st_size < 1000:
            print(f"    Downloaded file too small, removing")
            output_path.unlink()
            return None

        return output_path
    except Exception as e:
        print(f"    Error downloading: {e}")
        return None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load dataset data
    data_path = DATA_DIR / "datasets.json"
    with open(data_path) as f:
        data = json.load(f)

    print(f"Found {len(data)} datasets")
    print(f"Downloading to: {OUTPUT_DIR}\n")

    updated = 0
    skipped = 0
    failed = 0
    already_has_image = 0

    for i, dataset in enumerate(data):
        name = dataset.get("name", "Unknown")
        url = dataset.get("url", "")
        github_url = dataset.get("github_url", "")
        current_image = dataset.get("image_url", "")

        print(f"[{i+1}/{len(data)}] {name}")

        # Generate local filename
        slug = slugify(name)
        local_path = OUTPUT_DIR / f"{slug}.jpg"

        # Check if already downloaded (any extension)
        existing = list(OUTPUT_DIR.glob(f"{slug}.*"))
        if existing:
            local_file = existing[0]
            relative_path = f"/images/datasets/{local_file.name}"
            if dataset.get("image_url") != relative_path:
                dataset["image_url"] = relative_path
                updated += 1
                print(f"  Already exists: {local_file.name}")
            else:
                skipped += 1
                print(f"  Already up to date: {local_file.name}")
            continue

        # Skip if already has a valid local image_url
        if current_image and current_image.startswith("/images/datasets/"):
            skipped += 1
            print(f"  Already has local image_url")
            continue

        image_url = None

        # Strategy 1: Try OG image from the dataset URL
        if url:
            print(f"  Fetching OG image from {urlparse(url).netloc}...")
            image_url = fetch_og_image(url)
            time.sleep(REQUEST_DELAY)

        # Strategy 2: Try GitHub avatar if github_url exists
        if not image_url and github_url:
            print(f"  Trying GitHub avatar...")
            image_url = get_github_avatar(github_url)

        # Strategy 3: Fallback to favicon (but don't save - let template handle it)
        if not image_url:
            print(f"  No OG image found, will use fallback")
            failed += 1
            continue

        # Download the image
        print(f"  Downloading: {image_url[:70]}...")
        downloaded_path = download_image(image_url, local_path)

        if downloaded_path:
            relative_path = f"/images/datasets/{downloaded_path.name}"
            dataset["image_url"] = relative_path
            updated += 1
            print(f"  Saved: {downloaded_path.name}")
        else:
            failed += 1

        time.sleep(REQUEST_DELAY)

    # Save updated data
    if updated > 0:
        with open(data_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nUpdated datasets.json")

    print(f"\nResults:")
    print(f"  Downloaded/Updated: {updated}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Failed (will use fallback): {failed}")
    print(f"\nImages saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
