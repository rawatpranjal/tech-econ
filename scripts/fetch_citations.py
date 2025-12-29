#!/usr/bin/env python3
"""
Fetch citation counts from OpenAlex API for all papers in papers.json.

OpenAlex is free, no auth required, and has generous rate limits (10 requests/second).

Usage:
    python scripts/fetch_citations.py
"""

import json
import time
import re
import ssl
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from difflib import SequenceMatcher

# Create SSL context
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
PAPERS_FILE = DATA_DIR / "papers.json"
PROGRESS_FILE = DATA_DIR / "citations_progress.json"

# API config - OpenAlex has generous rate limits (10/second for polite pool)
API_BASE = "https://api.openalex.org"
RATE_LIMIT_DELAY = 0.2  # 200ms between requests (5 requests/second, being polite)
EMAIL = "metrics-packages@example.com"  # For polite pool


def extract_doi(url: str) -> str | None:
    """Extract DOI from URL if present."""
    patterns = [
        r'doi\.org/(10\.\d{4,}/[^\s]+)',
        r'doi/(10\.\d{4,}/[^\s]+)',
        r'(10\.\d{4,}/[^\s]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            doi = match.group(1)
            doi = doi.rstrip('.,;:)')
            return doi
    return None


def similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def api_request(url: str, retry_count: int = 0) -> dict | None:
    """Make API request with retry logic."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', f'MetricsPackages/1.0 (mailto:{EMAIL})')

        with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as response:
            return json.loads(response.read().decode('utf-8'))

    except urllib.error.HTTPError as e:
        if e.code == 429:  # Rate limited
            wait_time = min(10 * (2 ** retry_count), 60)
            print(f"  Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            if retry_count < 3:
                return api_request(url, retry_count + 1)
            return None
        elif e.code == 404:
            return None
        print(f"  HTTP Error {e.code}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def fetch_by_doi(doi: str) -> int | None:
    """Fetch citation count by DOI from OpenAlex."""
    encoded_doi = urllib.parse.quote(doi, safe='')
    url = f"{API_BASE}/works/https://doi.org/{encoded_doi}?mailto={EMAIL}"
    data = api_request(url)
    if data:
        return data.get('cited_by_count')
    return None


def fetch_by_title(title: str, year: int) -> int | None:
    """Fetch citation count by title search from OpenAlex."""
    # Clean title for search
    clean_title = re.sub(r'[^\w\s]', ' ', title)
    query = urllib.parse.quote(clean_title[:200])
    url = f"{API_BASE}/works?search={query}&mailto={EMAIL}"

    data = api_request(url)
    if not data or not data.get('results'):
        return None

    # Find best match by title similarity and year
    best_match = None
    best_score = 0

    for work in data['results'][:10]:
        work_title = work.get('title', '')
        work_year = work.get('publication_year')

        if not work_title:
            continue

        title_sim = similarity(title, work_title)
        year_bonus = 0.15 if work_year == year else 0
        score = title_sim + year_bonus

        if score > best_score and title_sim > 0.6:
            best_score = score
            best_match = work

    if best_match:
        return best_match.get('cited_by_count')

    return None


def fetch_citation_count(paper: dict) -> int | None:
    """Fetch citation count for a paper, trying DOI first then title search."""
    url = paper.get('url', '')
    title = paper['title']
    year = paper.get('year', 0)

    # Try DOI first (most reliable)
    doi = extract_doi(url)
    if doi:
        citations = fetch_by_doi(doi)
        if citations is not None:
            return citations
        time.sleep(RATE_LIMIT_DELAY)

    # Fall back to title search
    return fetch_by_title(title, year)


def load_progress() -> dict:
    """Load progress from previous run."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    """Save progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def main():
    # Load papers
    with open(PAPERS_FILE, 'r') as f:
        data = json.load(f)

    # Load previous progress (only keep non-null values)
    old_progress = load_progress()
    progress = {k: v for k, v in old_progress.items() if v is not None}

    # Count total papers
    total_papers = 0
    for topic in data['topics']:
        for subtopic in topic.get('subtopics', []):
            total_papers += len(subtopic.get('papers', []))

    print(f"Found {total_papers} papers to process")
    print(f"Papers with cached citations: {len(progress)}")
    print("-" * 50)

    # Process papers
    processed = 0
    updated = 0
    not_found = []

    for topic in data['topics']:
        for subtopic in topic.get('subtopics', []):
            for paper in subtopic.get('papers', []):
                processed += 1
                title = paper['title']

                # Check if already fetched
                if title in progress:
                    citations = progress[title]
                    paper['citations'] = citations
                    updated += 1
                    print(f"[{processed}/{total_papers}] (cached) {title[:40]}... -> {citations}")
                    continue

                print(f"[{processed}/{total_papers}] {title[:50]}...", end=" ", flush=True)

                citations = fetch_citation_count(paper)

                # Save progress
                progress[title] = citations
                save_progress(progress)

                if citations is not None:
                    paper['citations'] = citations
                    updated += 1
                    print(f"-> {citations}")
                else:
                    not_found.append(title)
                    print(f"-> NOT FOUND")

                time.sleep(RATE_LIMIT_DELAY)

    # Save updated papers.json
    with open(PAPERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print("-" * 50)
    print(f"Done! Updated {updated}/{total_papers} papers with citation counts")

    if not_found:
        print(f"\nPapers not found ({len(not_found)}):")
        for title in not_found[:20]:
            print(f"  - {title}")
        if len(not_found) > 20:
            print(f"  ... and {len(not_found) - 20} more")


if __name__ == "__main__":
    main()
