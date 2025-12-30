#!/usr/bin/env python3
"""
Check all URLs in data JSON files for broken links.
"""

import json
import asyncio
import aiohttp
import os
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Files to check
DATA_FILES = [
    "packages.json",
    "datasets.json",
    "resources.json",
    "talks.json",
    "career.json",
    "community.json",
    "books.json",
]

# URL fields to check
URL_FIELDS = ["url", "github_url", "docs_url", "image_url"]

# Domains to skip (often block automated requests)
SKIP_DOMAINS = [
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
]

async def check_url(session, url, semaphore):
    """Check if a URL is accessible."""
    # Skip certain domains
    for domain in SKIP_DOMAINS:
        if domain in url:
            return url, "skipped", None

    async with semaphore:
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp:
                if resp.status < 400:
                    return url, "ok", resp.status
                # Try GET if HEAD fails
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as resp2:
                    return url, "ok" if resp2.status < 400 else "error", resp2.status
        except asyncio.TimeoutError:
            return url, "timeout", None
        except aiohttp.ClientError as e:
            return url, "error", str(e)
        except Exception as e:
            return url, "error", str(e)

def extract_urls(data, urls_set):
    """Recursively extract URLs from data structure."""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in URL_FIELDS and isinstance(value, str) and value.startswith("http"):
                urls_set.add(value)
            else:
                extract_urls(value, urls_set)
    elif isinstance(data, list):
        for item in data:
            extract_urls(item, urls_set)

async def main():
    # Collect all URLs
    all_urls = set()

    for filename in DATA_FILES:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
                extract_urls(data, all_urls)

    # Also check papers.json (nested structure)
    papers_path = DATA_DIR / "papers.json"
    if papers_path.exists():
        with open(papers_path) as f:
            data = json.load(f)
            extract_urls(data, all_urls)

    print(f"Checking {len(all_urls)} unique URLs...")

    # Check URLs concurrently
    semaphore = asyncio.Semaphore(20)  # Limit concurrent requests
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkChecker/1.0)"}

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [check_url(session, url, semaphore) for url in all_urls]
        results = await asyncio.gather(*tasks)

    # Report results
    errors = []
    timeouts = []
    ok_count = 0
    skipped_count = 0

    for url, status, detail in results:
        if status == "ok":
            ok_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "timeout":
            timeouts.append(url)
        else:
            errors.append((url, detail))

    print(f"\nResults:")
    print(f"  OK: {ok_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Timeouts: {len(timeouts)}")
    print(f"  Errors: {len(errors)}")

    if timeouts:
        print(f"\nTimeouts ({len(timeouts)}):")
        for url in timeouts[:10]:  # Show first 10
            print(f"  - {url}")
        if len(timeouts) > 10:
            print(f"  ... and {len(timeouts) - 10} more")

    if errors:
        print(f"\nBroken links ({len(errors)}):")
        for url, detail in errors[:20]:  # Show first 20
            print(f"  - {url}")
            print(f"    Error: {detail}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")

    # Exit with error if there are broken links
    if errors:
        print(f"\n::warning::Found {len(errors)} broken links")
        # Don't fail the workflow, just warn
        # sys.exit(1)

    print("\nLink check complete!")

if __name__ == "__main__":
    asyncio.run(main())
