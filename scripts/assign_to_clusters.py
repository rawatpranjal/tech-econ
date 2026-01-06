#!/usr/bin/env python3
"""
LLM-Assisted Cluster Assignment for Content (Resources, Talks, Datasets).

Assigns each item to 1-2 manually curated clusters using OpenAI.
Outputs CSV for human review before final assignment.

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py --content-type talks
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py --content-type datasets --limit 50
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py --content-type talks --apply
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from openai import AsyncOpenAI
except ImportError:
    print("Error: openai package not installed")
    print("Install with: pip install openai")
    sys.exit(1)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent

# Content type configurations
CONTENT_CONFIGS = {
    "resources": {
        "data_file": PROJECT_ROOT / "data" / "resources.json",
        "defs_file": PROJECT_ROOT / "data" / "cluster_definitions.json",
        "output_csv": PROJECT_ROOT / "scripts" / "cluster_assignments_review.csv",
        "output_json": PROJECT_ROOT / "data" / "resource_clusters.json",
        "min_cluster_size": 4,
        "max_carousel": 10,
        "item_type": "learning resource"
    },
    "talks": {
        "data_file": PROJECT_ROOT / "data" / "talks.json",
        "defs_file": PROJECT_ROOT / "data" / "talk_cluster_definitions.json",
        "output_csv": PROJECT_ROOT / "scripts" / "talk_cluster_assignments_review.csv",
        "output_json": PROJECT_ROOT / "data" / "talk_clusters.json",
        "min_cluster_size": 3,
        "max_carousel": 7,
        "item_type": "talk/video"
    },
    "datasets": {
        "data_file": PROJECT_ROOT / "data" / "datasets.json",
        "defs_file": PROJECT_ROOT / "data" / "dataset_cluster_definitions.json",
        "output_csv": PROJECT_ROOT / "scripts" / "dataset_cluster_assignments_review.csv",
        "output_json": PROJECT_ROOT / "data" / "dataset_clusters.json",
        "min_cluster_size": 3,
        "max_carousel": 10,
        "item_type": "dataset"
    },
    "packages": {
        "data_file": PROJECT_ROOT / "data" / "packages.json",
        "defs_file": PROJECT_ROOT / "data" / "package_cluster_definitions.json",
        "output_csv": PROJECT_ROOT / "scripts" / "package_cluster_assignments_review.csv",
        "output_json": PROJECT_ROOT / "data" / "package_clusters.json",
        "min_cluster_size": 4,
        "max_carousel": 10,
        "item_type": "software package/library"
    }
}

# API settings
MODEL = "gpt-4o-mini"
MAX_CONCURRENT = 10
RATE_LIMIT_DELAY = 0.1


def load_content(content_type: str):
    """Load content data for the specified type."""
    config = CONTENT_CONFIGS[content_type]
    with open(config["data_file"]) as f:
        return json.load(f)


def load_cluster_definitions(content_type: str):
    """Load cluster definitions for the specified type."""
    config = CONTENT_CONFIGS[content_type]
    with open(config["defs_file"]) as f:
        return json.load(f)


def build_cluster_prompt(clusters):
    """Build the cluster list for the prompt."""
    lines = []
    for c in clusters:
        lines.append(f"- {c['id']}: {c['label']} - {c['description']}")
    return "\n".join(lines)


async def assign_item(client: AsyncOpenAI, item: dict, cluster_prompt: str, item_type: str, semaphore: asyncio.Semaphore) -> dict:
    """Assign a single item to clusters using LLM."""
    async with semaphore:
        await asyncio.sleep(RATE_LIMIT_DELAY)

        name = item.get('name', item.get('title', 'Unknown'))
        description = item.get('description', '')
        category = item.get('category', '')
        url = item.get('url', '')

        prompt = f"""Assign this {item_type} to 1-2 of the curated topic clusters below.

ITEM:
- Name: {name}
- Description: {description}
- Category: {category}
- URL: {url}

AVAILABLE CLUSTERS:
{cluster_prompt}

INSTRUCTIONS:
1. Choose 1-2 clusters that best match this {item_type}
2. Primary cluster should be the best fit
3. Secondary cluster is optional (only if clearly relevant)
4. If no cluster fits well, use "none" as primary

Return JSON only:
{{"primary": "cluster-id", "secondary": "cluster-id or null", "confidence": "high/medium/low"}}"""

        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": f"You are a classifier that assigns {item_type}s to topic clusters. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            content = response.choices[0].message.content.strip()
            # Parse JSON from response
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)

            return {
                "id": item.get('id', ''),
                "name": name,
                "category": category,
                "primary": result.get('primary', 'none'),
                "secondary": result.get('secondary'),
                "confidence": result.get('confidence', 'medium'),
                "status": "success"
            }

        except Exception as e:
            print(f"  Error processing '{name}': {e}")
            return {
                "id": item.get('id', ''),
                "name": name,
                "category": category,
                "primary": "error",
                "secondary": None,
                "confidence": "low",
                "status": f"error: {str(e)}"
            }


async def process_all_items(client: AsyncOpenAI, items: list, cluster_prompt: str, item_type: str, limit: int = None):
    """Process all items with LLM assignment."""
    if limit:
        items = items[:limit]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        assign_item(client, item, cluster_prompt, item_type, semaphore)
        for item in items
    ]

    print(f"\nProcessing {len(tasks)} {item_type}s...")
    results = []
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro
        results.append(result)
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(tasks)}")

    return results


def save_csv_for_review(results: list, output_path: Path):
    """Save results to CSV for human review."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'id', 'name', 'category', 'primary', 'secondary', 'confidence', 'status'
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nSaved {len(results)} assignments to {output_path}")
    print("Review this CSV and correct any misassignments before running --apply")


def load_reviewed_csv(csv_path: Path) -> list:
    """Load reviewed CSV with corrections."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_clusters_from_assignments(assignments: list, items: list, cluster_defs: dict, content_type: str) -> dict:
    """Build clusters JSON from assignments."""
    config = CONTENT_CONFIGS[content_type]
    min_cluster_size = config["min_cluster_size"]
    max_carousel = config["max_carousel"]

    # Build item lookup
    item_by_id = {r.get('id', ''): r for r in items}

    # Build cluster lookup
    cluster_by_id = {c['id']: c for c in cluster_defs['clusters']}

    # Group assignments by cluster
    cluster_items = {}
    for a in assignments:
        rid = a['id']
        primary = a['primary']
        secondary = a.get('secondary')

        if primary and primary != 'none' and primary != 'error':
            if primary not in cluster_items:
                cluster_items[primary] = []
            cluster_items[primary].append(rid)

        if secondary and secondary != 'null' and secondary != 'None':
            if secondary not in cluster_items:
                cluster_items[secondary] = []
            if rid not in cluster_items[secondary]:
                cluster_items[secondary].append(rid)

    # Build output clusters
    output_clusters = []
    for cluster_id, item_ids in cluster_items.items():
        if cluster_id not in cluster_by_id:
            print(f"  Warning: Unknown cluster '{cluster_id}'")
            continue

        if len(item_ids) < min_cluster_size:
            print(f"  Skipping '{cluster_id}' - only {len(item_ids)} items (min: {min_cluster_size})")
            continue

        cluster_def = cluster_by_id[cluster_id]

        # Get original categories
        orig_cats = set()
        for rid in item_ids:
            if rid in item_by_id:
                cat = item_by_id[rid].get('category', 'Unknown')
                orig_cats.add(cat)

        # Get items sorted by model_score
        items_with_score = []
        for rid in item_ids:
            if rid in item_by_id:
                score = item_by_id[rid].get('model_score', 0)
                items_with_score.append((rid, score))
        items_with_score.sort(key=lambda x: -x[1])

        # Carousel items (top N based on content type)
        carousel_items = [rid for rid, _ in items_with_score[:max_carousel]]

        output_clusters.append({
            "id": f"cluster-{cluster_id}",
            "label": cluster_def['label'],
            "cluster_id": cluster_id,
            "macro_category": cluster_def['macro_category'],
            "original_categories": list(orig_cats),
            "item_count": len(item_ids),
            "items": item_ids,
            "carousel_items": carousel_items
        })

    # Sort by macro_category then item_count
    output_clusters.sort(key=lambda x: (x['macro_category'], -x['item_count']))

    return {
        "generated_at": datetime.now().isoformat(),
        "algorithm": "manual_curation_v1",
        "params": {
            "min_cluster_size": min_cluster_size,
            "max_cluster_size": max_carousel
        },
        "total_clusters": len(output_clusters),
        "total_items": sum(c['item_count'] for c in output_clusters),
        "clusters": output_clusters
    }


async def main():
    parser = argparse.ArgumentParser(description="LLM-assisted cluster assignment")
    parser.add_argument('--content-type', type=str, default='resources',
                        choices=['resources', 'talks', 'datasets', 'packages'],
                        help="Content type to process (default: resources)")
    parser.add_argument('--limit', type=int, help="Limit number of items to process")
    parser.add_argument('--apply', action='store_true', help="Apply assignments from reviewed CSV")
    args = parser.parse_args()

    content_type = args.content_type
    config = CONTENT_CONFIGS[content_type]

    # Load data
    print(f"Loading {content_type} data...")
    items = load_content(content_type)
    cluster_defs = load_cluster_definitions(content_type)
    print(f"  {len(items)} {content_type}")
    print(f"  {len(cluster_defs['clusters'])} cluster definitions")

    output_csv = config["output_csv"]
    output_json = config["output_json"]
    item_type = config["item_type"]

    if args.apply:
        # Apply from reviewed CSV
        if not output_csv.exists():
            print(f"Error: {output_csv} not found")
            print("Run without --apply first to generate assignments")
            return

        print(f"\nLoading reviewed assignments from {output_csv}...")
        assignments = load_reviewed_csv(output_csv)
        print(f"  {len(assignments)} assignments")

        print("\nBuilding clusters...")
        output = build_clusters_from_assignments(assignments, items, cluster_defs, content_type)

        print(f"\nSaving to {output_json}...")
        with open(output_json, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nDone! Created {output['total_clusters']} clusters with {output['total_items']} items")

    else:
        # Run LLM assignment
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set")
            print("Set with: export OPENAI_API_KEY=sk-...")
            return

        client = AsyncOpenAI(api_key=api_key)
        cluster_prompt = build_cluster_prompt(cluster_defs['clusters'])

        results = await process_all_items(client, items, cluster_prompt, item_type, limit=args.limit)

        # Save for review
        save_csv_for_review(results, output_csv)

        # Summary
        success = sum(1 for r in results if r['status'] == 'success')
        high_conf = sum(1 for r in results if r['confidence'] == 'high')
        print(f"\nSummary:")
        print(f"  Success: {success}/{len(results)}")
        print(f"  High confidence: {high_conf}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
