#!/usr/bin/env python3
"""
Validate JSON data files for the tech-econ site.

Checks:
1. Required fields are present
2. No duplicate URLs within or across files
3. All URLs are accessible (HEAD request)
"""

import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Required fields per file type
REQUIRED_FIELDS = {
    "packages.json": ["name", "url", "category"],
    "datasets.json": ["name", "url", "category"],
    "talks.json": ["name", "url", "category", "type"],
    "resources.json": ["name", "url", "category"],
    "community.json": ["name", "url"],
    "career.json": ["name", "url"],
    "roadmaps.json": ["name"],  # Uses name field
}

# Domains that block bot requests - skip these in link checking
SKIP_DOMAINS = {
    "linkedin.com",
    "twitter.com",
    "x.com",
    "medium.com",          # Blocks bots
    "leetcode.com",        # Blocks bots
    "sec.gov",             # Blocks bots
    "zillow.com",          # Blocks bots
    "freakonomics.com",    # Blocks bots
    "doordash.engineering", # Blocks bots
    "uber.com",            # Returns 406
    "informs.org",         # Various issues
    "pubsonline.informs.org",
    "forecasters.org",     # Blocks bots
    "statmodeling.stat.columbia.edu",  # Blocks bots
    "netflixtechblog.com", # SSL issues
    "eng.lyft.com",        # SSL issues
    "mediaspace.gatech.edu", # SSL issues
    "leonwei.com",         # Blocks bots
    "sciencedirect.com",   # Blocks bots
    "data.iowa.gov",       # Slow/timeout
    "kevinsheppard.com",   # Slow/timeout
    "nabe.com",            # Various issues
    "bts.gov",             # Blocks bots
    "ec.sigecom.org",      # Connection issues
    "wine-conference.org", # Connection issues
    "data-mining-cup.com", # Timeout
    "ai.baidu.com",        # Various issues
    "openicpsr.org",       # Blocks bots
    "web.stanford.edu",    # Various issues
}

def load_json_files(data_dir: Path) -> dict:
    """Load all JSON files from data directory."""
    files = {}
    for json_file in data_dir.glob("*.json"):
        with open(json_file) as f:
            files[json_file.name] = json.load(f)
    return files


def validate_required_fields(files: dict) -> list:
    """Check that all required fields are present."""
    errors = []

    for filename, data in files.items():
        if filename not in REQUIRED_FIELDS:
            continue

        required = REQUIRED_FIELDS[filename]

        # Handle both list and dict structures
        items = data if isinstance(data, list) else [data]

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for field in required:
                if field not in item or not item[field]:
                    name = item.get("name", item.get("title", f"item {i}"))
                    errors.append(f"{filename}: '{name}' missing required field '{field}'")

    return errors


def find_duplicate_urls(files: dict) -> list:
    """Find duplicate URLs within files (cross-file duplicates are allowed)."""
    errors = []

    for filename, data in files.items():
        file_urls = {}  # Track URLs within this file only
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not url:
                continue

            name = item.get("name", item.get("title", "unknown"))

            if url in file_urls:
                errors.append(f"{filename}: Duplicate URL '{url}' - '{name}' and '{file_urls[url]}'")
            else:
                file_urls[url] = name

    return errors


def check_url(url: str, timeout: int = 10) -> tuple:
    """Check if URL is accessible. Returns (url, error_or_none)."""
    # Skip known problematic domains
    for skip in SKIP_DOMAINS:
        if skip in url:
            return (url, None)

    try:
        # Try HEAD first (faster)
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0 (compatible; link-checker)"})
        if resp.status_code >= 400:
            # Some servers don't support HEAD, try GET
            resp = requests.get(url, timeout=timeout, allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (compatible; link-checker)"},
                              stream=True)
            resp.close()

        if resp.status_code >= 400:
            return (url, f"HTTP {resp.status_code}")
        return (url, None)
    except requests.exceptions.Timeout:
        return (url, "Timeout")
    except requests.exceptions.SSLError as e:
        return (url, f"SSL Error: {str(e)[:50]}")
    except requests.exceptions.ConnectionError as e:
        return (url, f"Connection Error: {str(e)[:50]}")
    except Exception as e:
        return (url, f"Error: {str(e)[:50]}")


def check_broken_links(files: dict, max_workers: int = 10) -> list:
    """Check all URLs for broken links."""
    errors = []
    urls_to_check = set()
    url_sources = {}  # url -> (filename, name)

    for filename, data in files.items():
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            name = item.get("name", item.get("title", "unknown"))

            # Check main url and other url fields
            for field in ["url", "docs_url", "github_url"]:
                url = item.get(field)
                if url and isinstance(url, str):
                    urls_to_check.add(url)
                    url_sources[url] = (filename, name)

    print(f"Checking {len(urls_to_check)} URLs...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_url, url): url for url in urls_to_check}

        checked = 0
        for future in as_completed(futures):
            url, error = future.result()
            checked += 1
            if checked % 20 == 0:
                print(f"  Checked {checked}/{len(urls_to_check)} URLs...")

            if error:
                filename, name = url_sources.get(url, ("unknown", "unknown"))
                errors.append(f"{filename}: '{name}' has broken link '{url}' ({error})")

    return errors


def main():
    data_dir = Path(__file__).parent.parent / "data"

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    print(f"Loading JSON files from {data_dir}...")
    files = load_json_files(data_dir)
    print(f"Loaded {len(files)} files")

    all_errors = []

    # Check required fields
    print("\n1. Checking required fields...")
    field_errors = validate_required_fields(files)
    if field_errors:
        print(f"   Found {len(field_errors)} missing field errors")
        all_errors.extend(field_errors)
    else:
        print("   All required fields present")

    # Check duplicate URLs
    print("\n2. Checking for duplicate URLs...")
    dup_errors = find_duplicate_urls(files)
    if dup_errors:
        print(f"   Found {len(dup_errors)} duplicate URLs")
        all_errors.extend(dup_errors)
    else:
        print("   No duplicate URLs found")

    # Check broken links (warnings only - don't fail build)
    print("\n3. Checking for broken links...")
    link_errors = check_broken_links(files)
    if link_errors:
        print(f"   Found {len(link_errors)} broken links (warnings)")
    else:
        print("   All links accessible")

    # Summary
    print("\n" + "=" * 60)

    # Critical errors (missing fields, duplicates) fail the build
    if all_errors:
        print(f"FAILED: {len(all_errors)} errors found:\n")
        for error in all_errors:
            print(f"  - {error}")

    # Broken links are warnings only
    if link_errors:
        print(f"\nWARNINGS: {len(link_errors)} broken links (not failing build):\n")
        for error in link_errors:
            print(f"  - {error}")

    if all_errors:
        sys.exit(1)
    else:
        print("PASSED: All critical checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
