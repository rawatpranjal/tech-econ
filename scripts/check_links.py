#!/usr/bin/env python3
"""
Check all URLs in data JSON files for broken links.
"""

import json
import asyncio
import aiohttp
import ssl
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
STATIC_DIR = Path(__file__).parent.parent / "static"

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
    # Social media
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    # Content platforms
    "medium.com",
    "substack.com",
    # Academic publishers (block bots with 403)
    "jstor.org",
    "dl.acm.org",
    "academic.oup.com",
    "ieeexplore.ieee.org",
    "tandfonline.com",
    "journals.sagepub.com",
    "journals.uchicago.edu",
    "liebertpub.com",
    "onlinelibrary.wiley.com",
    "link.springer.com",
    "sciencedirect.com",
    "nature.com",
    "pnas.org",
    "aeaweb.org",
    # Tech/business sites
    "leetcode.com",
    "upwork.com",
    "patentsview.org",
    "sec.gov",
    "zillow.com",
    "freakonomics.com",
    "doordash.engineering",
    "uber.com",
    "informs.org",
    "pubsonline.informs.org",
    "forecasters.org",
    "statmodeling.stat.columbia.edu",
    "netflixtechblog.com",
    "eng.lyft.com",
    "mediaspace.gatech.edu",
    "leonwei.com",
    "data.iowa.gov",
    "kevinsheppard.com",
    "nabe.com",
    "bts.gov",
    "ec.sigecom.org",
    "wine-conference.org",
    "data-mining-cup.com",
    "ai.baidu.com",
    "openicpsr.org",
    "web.stanford.edu",
    "ssrn.com",
    "arxiv.org",
    "nber.org",
    # Career sites (often block bots)
    "careers.chime.com",
    "udemy.com",
    "mgmresorts.com",
    "stories.starbucks.com",
    "careersatdoordash.com",
    "careers.kimberly-clark.com",
    "block.xyz",
    "notion.so",
    "wellfound.com",
    "ncbi.nlm.nih.gov",
    "cambridge.org",
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

    # Disable SSL verification (acceptable for link checking)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
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

    # Calculate link health score
    total_checked = ok_count + len(errors) + len(timeouts)
    if total_checked > 0:
        score = round((ok_count / total_checked) * 100, 1)
    else:
        score = 100.0

    # Save link health report
    health_data = {
        "score": score,
        "total": total_checked,
        "working": ok_count,
        "broken": len(errors),
        "timeouts": len(timeouts),
        "skipped": skipped_count,
        "updated": datetime.now(timezone.utc).isoformat()
    }

    health_file = STATIC_DIR / "link-health.json"
    with open(health_file, "w") as f:
        json.dump(health_data, f, indent=2)
        f.write("\n")

    print(f"\nLink health score: {score}%")
    print(f"Saved to {health_file}")

    print("\nLink check complete!")

if __name__ == "__main__":
    asyncio.run(main())
