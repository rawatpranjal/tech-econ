#!/usr/bin/env python3
"""
Homepage Row Generator — Simplified
Generates 5 algorithmic rows. Zero manual curation required.

Rows:
  0. Trending Now  (hero template)    — top engaged non-cold-start, type-diverse
  1. New This Month (standard)        — impressions > 0, deep_sessions < 5
  2. Top Packages   (standard)        — packages.json sorted by model_score
  3. Top Datasets   (standard)        — datasets.json sorted by model_score
  4. Talks Worth Watching (standard)  — talks.json sorted by model_score

Usage:
    python3 scripts/generate_homepage_rows.py
    python3 scripts/generate_homepage_rows.py --output data/homepage_rows.json
"""

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


DATA_DIR = Path(__file__).parent.parent / "data"

TEMPLATE_HERO = "hero"
TEMPLATE_STANDARD = "standard"

MAX_SAME_TYPE_PER_ROW = 3
ROW_ITEMS = 8  # target items per non-hero row
HERO_ITEMS = 10  # target items for hero/trending row


def load_json(path: Path) -> dict | list | None:
    """Load a JSON file, return None if missing or invalid."""
    if not path.exists():
        print(f"  Warning: {path.name} not found, skipping")
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Warning: Failed to load {path.name}: {e}")
        return None


def load_content_lookup(data_dir: Path) -> dict[str, dict]:
    """Build name -> metadata dict from all content files."""
    lookup: dict[str, dict] = {}
    content_files = {
        "packages.json": "package",
        "datasets.json": "dataset",
        "resources.json": "resource",
        "papers_flat.json": "paper",
        "talks.json": "talk",
        "career.json": "career",
        "community.json": "community",
        "books.json": "book",
    }
    for filename, content_type in content_files.items():
        data = load_json(data_dir / filename)
        if data is None:
            continue
        items = data if isinstance(data, list) else []
        for item in items:
            name = item.get("name") or item.get("title", "")
            if not name:
                continue
            url = (
                item.get("url")
                or item.get("github_url")
                or item.get("docs_url")
                or ""
            )
            image_url = item.get("image_url", "")
            if not image_url:
                if content_type == "package":
                    github_url = item.get("github_url") or ""
                    if "github.com/" in github_url:
                        owner = github_url.split("github.com/")[1].split("/")[0]
                        image_url = f"https://github.com/{owner}.png?size=128"
                elif content_type == "book":
                    isbn = item.get("isbn") or ""
                    if isbn:
                        image_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
            key = name.lower().strip()
            lookup[key] = {
                "name": name,
                "type": content_type,
                "category": item.get("category", ""),
                "description": item.get("description") or item.get("summary", ""),
                "url": url,
                "image_url": image_url,
                "tags": item.get("tags", []),
                "model_score": item.get("model_score", 0.0),
            }
    return lookup


def build_score_lookup(rankings: list[dict]) -> dict[str, float]:
    """Build name -> score lookup from global_rankings."""
    return {r["name"].lower().strip(): r.get("score", 0.0) for r in rankings}


def make_item(ranking_entry: dict, content_lookup: dict) -> dict:
    """Build a normalized item dict from a ranking entry + content metadata."""
    name = ranking_entry.get("name", "")
    key = name.lower().strip()
    meta = content_lookup.get(key, {})
    return {
        "name": name,
        "type": ranking_entry.get("type", meta.get("type", "unknown")),
        "category": ranking_entry.get("category", meta.get("category", "")),
        "description": ranking_entry.get("description", meta.get("description", "")),
        "url": ranking_entry.get("url", meta.get("url", "")),
        "image_url": ranking_entry.get("image_url", meta.get("image_url", "")),
        "score": ranking_entry.get("score", 0.0),
        "cold_start": ranking_entry.get("cold_start", True),
        "signals": ranking_entry.get("signals", {}),
    }


def make_item_from_meta(meta: dict, score_lookup: dict) -> dict:
    """Build a normalized item dict from content metadata, with score from rankings."""
    name = meta.get("name", "")
    key = name.lower().strip()
    # Prefer engagement-based score from rankings; fall back to model_score from content file
    score = score_lookup[key] if key in score_lookup else meta.get("model_score", 0.0)
    return {
        "name": name,
        "type": meta.get("type", "unknown"),
        "category": meta.get("category", ""),
        "description": meta.get("description", ""),
        "url": meta.get("url", ""),
        "image_url": meta.get("image_url", ""),
        "score": score,
        "cold_start": key not in score_lookup,
        "signals": {},
    }


def apply_type_cap(items: list[dict], max_same_type: int) -> list[dict]:
    """Cap items to max_same_type per content type."""
    type_counts: dict[str, int] = defaultdict(int)
    result = []
    for item in items:
        t = item.get("type", "unknown")
        if type_counts[t] < max_same_type:
            type_counts[t] += 1
            result.append(item)
    return result


def dedup_against_used(items: list[dict], used: set[str]) -> list[dict]:
    """Remove items already in the used set."""
    return [i for i in items if i["name"].lower().strip() not in used]


def mark_used(items: list[dict], used: set[str]) -> None:
    """Record item names as used."""
    for item in items:
        used.add(item["name"].lower().strip())


def build_trending_now(
    rankings: list[dict], content_lookup: dict, used: set[str]
) -> dict:
    """Row 0: top engaged non-cold-start items, max 3 per type.
    Falls back to top-scored items from full rankings when no engagement data exists."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if not r.get("cold_start", True)
    ]
    if not candidates:
        # No engagement data yet — fall back to top-scored items
        candidates = [make_item(r, content_lookup) for r in rankings]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    items = candidates[:HERO_ITEMS]
    mark_used(items, used)
    return {
        "id": "trending-now",
        "row_type": "trending",
        "title": "Trending Now",
        "description": "What the community is reading and clicking most",
        "template": TEMPLATE_HERO,
        "items": items,
    }


def build_new_this_month(
    rankings: list[dict], content_lookup: dict, used: set[str]
) -> dict:
    """Row 1: items with some impressions but few deep sessions (recently discovered).
    Falls back to top cold-start items by score when no impression data exists."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("signals", {}).get("impressions", 0) > 0
        and r.get("signals", {}).get("deep_sessions", 0) < 5
    ]
    has_engagement = bool(candidates)
    if not candidates:
        # No impression data — use cold-start items as "new/undiscovered" content
        candidates = [
            make_item(r, content_lookup)
            for r in rankings
            if r.get("cold_start", True)
        ]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    if has_engagement:
        candidates.sort(
            key=lambda x: x.get("signals", {}).get("impressions", 0), reverse=True
        )
    else:
        candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    items = candidates[:ROW_ITEMS]
    mark_used(items, used)
    return {
        "id": "new-this-month",
        "row_type": "new_this_month",
        "title": "New This Month",
        "description": "Recently surfaced — getting noticed but not yet deep-dived",
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def build_type_row(
    type_filter: str,
    row_id: str,
    title: str,
    description: str,
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Generic row: filter by type, sort by score, take top ROW_ITEMS."""
    candidates = [
        make_item_from_meta(meta, score_lookup)
        for meta in content_lookup.values()
        if meta.get("type") == type_filter
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    items = candidates[:ROW_ITEMS]
    mark_used(items, used)
    return {
        "id": row_id,
        "row_type": type_filter,
        "title": title,
        "description": description,
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def generate_rows(data_dir: Path) -> dict:
    """Build all 5 rows and return the homepage_rows.json payload."""
    rankings_data = load_json(data_dir / "global_rankings.json") or {}
    rankings: list[dict] = rankings_data.get("rankings", [])

    content_lookup = load_content_lookup(data_dir)
    score_lookup = build_score_lookup(rankings)

    used: set[str] = set()
    rows = [
        build_trending_now(rankings, content_lookup, used),
        build_new_this_month(rankings, content_lookup, used),
        build_type_row(
            "package", "top-packages", "Top Packages",
            "The most-used tools and libraries in the tech-econ stack",
            content_lookup, score_lookup, used,
        ),
        build_type_row(
            "dataset", "top-datasets", "Top Datasets",
            "Datasets researchers keep coming back to",
            content_lookup, score_lookup, used,
        ),
        build_type_row(
            "talk", "talks-worth-watching", "Talks Worth Watching",
            "Lectures, interviews, and keynotes worth your time",
            content_lookup, score_lookup, used,
        ),
    ]

    total_items = sum(len(r["items"]) for r in rows)
    unique_types: set[str] = set(
        item.get("type", "unknown")
        for row in rows
        for item in row["items"]
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_rows": len(rows),
            "total_items": total_items,
            "unique_types": sorted(unique_types),
            "type_count": len(unique_types),
            "critique_iterations": 0,
        },
        "critique_log": [],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate homepage rows (5 algorithmic rows, zero manual curation)"
    )
    parser.add_argument(
        "--output",
        default="data/homepage_rows.json",
        help="Output file path (default: data/homepage_rows.json)",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    output_path = Path(__file__).parent.parent / args.output

    print("Homepage Row Generator")
    print("=" * 50)
    result = generate_rows(data_dir)

    print(f"\nWriting {len(result['rows'])} rows to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"\nDone.")
    print(f"  Rows:   {result['stats']['total_rows']}")
    print(f"  Items:  {result['stats']['total_items']}")
    print(f"  Types:  {', '.join(result['stats']['unique_types'])}")


if __name__ == "__main__":
    main()
