#!/usr/bin/env python3
"""
Validate JSON data files for the tech-econ site.

Checks:
1. Required fields are present
2. papers.json / papers_flat.json count sync
3. No duplicate URLs within or across files
4. All URLs are accessible (HEAD request)
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
    "books.json": ["name", "url", "category", "author"],
    "community.json": ["name", "url"],
    "career.json": ["name", "url"],
    "roadmaps.json": ["name"],  # Uses name field
}

# Domains that block bot requests - skip these in link checking
SKIP_DOMAINS = {
    # Social media
    "linkedin.com",
    "twitter.com",
    "x.com",
    "medium.com",
    # Academic publishers (block bots with 403)
    "dl.acm.org",
    "acm.org",
    "jstor.org",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "academic.oup.com",
    "oup.com",
    "sagepub.com",
    "journals.sagepub.com",
    "tandfonline.com",
    "journals.uchicago.edu",
    "ssrn.com",
    "papers.ssrn.com",
    "pnas.org",
    "annualreviews.org",
    "science.org",
    "sciencemag.org",
    "researchgate.net",
    "springer.com",
    "link.springer.com",
    "cambridge.org",
    "sciencedirect.com",
    "ieee.org",
    "nature.com",
    "aeaweb.org",
    "projecteuclid.org",
    "degruyter.com",
    "nowpublishers.com",
    "morganclaypool.com",
    "acpjournals.org",
    # News & business (block bots)
    "bloomberg.com",
    "hbs.edu",
    "hbswk.hbs.edu",
    "nber.org",
    "rand.org",
    "bls.gov",
    # Tech companies (block bots)
    "uber.com",
    "doordash.engineering",
    "careersatdoordash.com",
    "etsy.com",
    "glassdoor.com",
    "indeed.com",
    "wellfound.com",
    # Career sites (block bots)
    "careers.",
    "career.",
    "jobs.",
    # Government sites (block bots)
    "transit.dot.gov",
    "ferc.gov",
    "nhtsa.gov",
    "eia.gov",
    # Other bot-blocking sites
    "platform.openai.com",
    "patentsview.org",
    "direct.mit.edu",
    "cxotalk.com",
    "gridstatus.io",
    "engineering.fiverr.com",
    "guykawasaki.com",
    "stripe.events",
    "business.columbia.edu",
    "psycnet.apa.org",
    "europeanhealtheconomics.com",
    "infoagepub.com",
    "joincolossus.com",
    "branch.io",
    "coupang.jobs",
    "quora.com",
    "carvana.com",
    "classcentral.com",
    "crates.io",
    "routledge.com",
    "e-elgar.com",
    "mdpi.com",
    # Other known issues
    "leetcode.com",
    "sec.gov",
    "zillow.com",
    "freakonomics.com",
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
        # Handle nested papers.json structure
        if filename == "papers.json" and isinstance(data, dict):
            for topic in data.get("topics", []):
                for subtopic in topic.get("subtopics", []):
                    for paper in subtopic.get("papers", []):
                        for field in ["title", "url"]:
                            if field not in paper or not paper[field]:
                                title = paper.get("title", f"unknown in {subtopic.get('id', '?')}")
                                errors.append(f"papers.json: '{title}' missing required field '{field}'")
            continue

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
    """Find duplicate URLs within files.

    Cross-file duplicates are allowed.
    Same URL with different category/topic is allowed (cross-category indexing).
    Same URL with different name is allowed (legitimate hub URLs — e.g.
    dunnhumby's /source-files/ index page hosts multiple datasets that all
    download from the same landing URL).

    Flags true accidental duplicates only: same URL + same category + same name.
    """
    errors = []

    for filename, data in files.items():
        file_keys = {}  # Track URL+category+name within this file only
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not url:
                continue

            name = item.get("name", item.get("title", "unknown"))

            # Composite key uses the most specific category available.
            # For papers_flat.json, use category ("Topic > Subtopic") not topic —
            # the same paper is legitimately cross-listed in multiple subtopics
            # of the same topic (e.g., a privacy paper under both "Personalized
            # Pricing" and "Algorithmic Pricing" subtopics). Using the broad
            # topic field would falsely flag these as duplicates.
            category = item.get("category", "")

            # Composite key: URL + category + name. Same URL + category +
            # different names is legitimate (multi-asset hub pages).
            key = f"{url}|{category}|{name}"

            if key in file_keys:
                errors.append(f"{filename}: Duplicate URL '{url}' in category '{category}' - '{name}' (entered twice)")
            else:
                file_keys[key] = name

    return errors


def check_featured_json(data_dir: Path) -> list:
    """Validate data/featured.json structure.

    Guards against typos in the editorial override file that silently
    break the homepage hero without any build-time error.
    """
    errors = []
    path = data_dir / "featured.json"
    if not path.exists():
        return errors  # optional file — only validate if present

    try:
        data = json.load(open(path))
    except json.JSONDecodeError as e:
        return [f"featured.json: invalid JSON — {e}"]

    if not isinstance(data, dict):
        return ["featured.json: must be a JSON object"]

    known_keys = {"_doc", "item_name", "image_override", "blurb_override", "cta_text", "label"}
    unknown = [k for k in data if k not in known_keys]
    if unknown:
        errors.append(f"featured.json: unexpected keys {unknown} (typo?)")

    # If item_name is set, it must be a non-empty string
    item_name = data.get("item_name", "")
    if item_name and not isinstance(item_name, str):
        errors.append("featured.json: item_name must be a string")

    # If image_override is a local path (starts with /), check the file exists
    image_override = data.get("image_override", "")
    if image_override and isinstance(image_override, str) and image_override.startswith("/"):
        abs_path = data_dir.parent / image_override.lstrip("/")
        if not abs_path.exists():
            errors.append(
                f"featured.json: image_override '{image_override}' not found at {abs_path}"
            )

    return errors


def check_experiments_json(data_dir: Path) -> list:
    """Validate data/experiments.json structure.

    Catches missing required fields and invalid status values before
    they silently break the A/B harness on the client.
    """
    errors = []
    path = data_dir / "experiments.json"
    if not path.exists():
        return errors  # optional file

    try:
        data = json.load(open(path))
    except json.JSONDecodeError as e:
        return [f"experiments.json: invalid JSON — {e}"]

    if not isinstance(data, dict):
        return ["experiments.json: must be a JSON object"]

    experiments = data.get("experiments")
    if experiments is None:
        return ["experiments.json: missing 'experiments' array"]
    if not isinstance(experiments, list):
        return ["experiments.json: 'experiments' must be an array"]

    valid_statuses = {"active", "paused", "draft", "completed"}
    for exp in experiments:
        if not isinstance(exp, dict):
            errors.append("experiments.json: each experiment must be an object")
            continue
        eid = exp.get("id", "<missing id>")
        for field in ("id", "status", "variants"):
            if field not in exp:
                errors.append(f"experiments.json: '{eid}' missing required field '{field}'")
        status = exp.get("status")
        if status and status not in valid_statuses:
            errors.append(
                f"experiments.json: '{eid}' has invalid status '{status}' "
                f"(must be one of {sorted(valid_statuses)})"
            )
        variants = exp.get("variants")
        if variants is not None:
            if not isinstance(variants, list) or len(variants) < 2:
                errors.append(
                    f"experiments.json: '{eid}' must have at least 2 variants"
                )
            else:
                for v in variants:
                    if not isinstance(v, dict) or "id" not in v:
                        errors.append(
                            f"experiments.json: '{eid}' has a variant missing 'id'"
                        )

    return errors


def check_papers_sync(files: dict) -> list:
    """Verify papers.json and papers_flat.json have the same paper count.

    These are a dual system (RULES.md) — easy to desync when editing
    papers.json without re-running flatten_papers.py.
    """
    errors = []
    papers_nested = files.get("papers.json")
    papers_flat = files.get("papers_flat.json")

    if papers_nested is None or papers_flat is None:
        return errors  # One file missing — validate_required_fields will catch it

    if not isinstance(papers_nested, dict) or not isinstance(papers_flat, list):
        return errors  # Malformed — let field checks report it

    nested_count = sum(
        len(subtopic.get("papers", []))
        for topic in papers_nested.get("topics", [])
        for subtopic in topic.get("subtopics", [])
    )
    flat_count = len(papers_flat)

    if nested_count != flat_count:
        errors.append(
            f"papers.json/papers_flat.json desync: nested has {nested_count} papers, "
            f"flat has {flat_count}. Run: python3 scripts/flatten_papers.py"
        )

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


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Validate JSON data files.")
    parser.add_argument("--skip-links", action="store_true",
                        help="Skip the slow network link-check step (steps 1-3 only)")
    args = parser.parse_args(argv)

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

    # Check papers.json / papers_flat.json sync
    print("\n2. Checking papers.json / papers_flat.json sync...")
    sync_errors = check_papers_sync(files)
    if sync_errors:
        print(f"   Found {len(sync_errors)} sync error(s)")
        all_errors.extend(sync_errors)
    else:
        print("   papers.json and papers_flat.json are in sync")

    # Check duplicate URLs
    print("\n3. Checking for duplicate URLs...")
    dup_errors = find_duplicate_urls(files)
    if dup_errors:
        print(f"   Found {len(dup_errors)} duplicate URLs")
        all_errors.extend(dup_errors)
    else:
        print("   No duplicate URLs found")

    # Check featured.json config
    print("\n4. Checking featured.json...")
    featured_errors = check_featured_json(data_dir)
    if featured_errors:
        print(f"   Found {len(featured_errors)} error(s)")
        all_errors.extend(featured_errors)
    else:
        print("   featured.json valid")

    # Check experiments.json config
    print("\n5. Checking experiments.json...")
    exp_errors = check_experiments_json(data_dir)
    if exp_errors:
        print(f"   Found {len(exp_errors)} error(s)")
        all_errors.extend(exp_errors)
    else:
        print("   experiments.json valid")

    # Check broken links (warnings only - don't fail build)
    link_errors = []
    if args.skip_links:
        print("\n6. Skipping link checks (--skip-links)")
    else:
        print("\n6. Checking for broken links...")
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
