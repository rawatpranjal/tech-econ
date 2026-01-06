#!/usr/bin/env python3
"""
LLM-Assisted Cluster Assignment for Learning Resources.

Assigns each resource to 1-2 manually curated clusters using OpenAI.
Outputs CSV for human review before final assignment.

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py --limit 50  # Test with 50 items
    OPENAI_API_KEY=sk-... python3 scripts/assign_to_clusters.py --apply      # Apply from reviewed CSV
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
RESOURCES_FILE = PROJECT_ROOT / "data" / "resources.json"
CLUSTER_DEFS_FILE = PROJECT_ROOT / "data" / "cluster_definitions.json"
OUTPUT_CSV = PROJECT_ROOT / "scripts" / "cluster_assignments_review.csv"
OUTPUT_JSON = PROJECT_ROOT / "data" / "resource_clusters.json"

# API settings
MODEL = "gpt-4o-mini"
MAX_CONCURRENT = 10
RATE_LIMIT_DELAY = 0.1


def load_resources():
    """Load resources data."""
    with open(RESOURCES_FILE) as f:
        return json.load(f)


def load_cluster_definitions():
    """Load cluster definitions."""
    with open(CLUSTER_DEFS_FILE) as f:
        return json.load(f)


def build_cluster_prompt(clusters):
    """Build the cluster list for the prompt."""
    lines = []
    for c in clusters:
        lines.append(f"- {c['id']}: {c['label']} - {c['description']}")
    return "\n".join(lines)


async def assign_resource(client: AsyncOpenAI, resource: dict, cluster_prompt: str, semaphore: asyncio.Semaphore) -> dict:
    """Assign a single resource to clusters using LLM."""
    async with semaphore:
        await asyncio.sleep(RATE_LIMIT_DELAY)

        name = resource.get('name', 'Unknown')
        description = resource.get('description', '')
        category = resource.get('category', '')
        url = resource.get('url', '')

        prompt = f"""Assign this learning resource to 1-2 of the curated topic clusters below.

RESOURCE:
- Name: {name}
- Description: {description}
- Category: {category}
- URL: {url}

AVAILABLE CLUSTERS:
{cluster_prompt}

INSTRUCTIONS:
1. Choose 1-2 clusters that best match this resource
2. Primary cluster should be the best fit
3. Secondary cluster is optional (only if clearly relevant)
4. If no cluster fits well, use "none" as primary

Return JSON only:
{{"primary": "cluster-id", "secondary": "cluster-id or null", "confidence": "high/medium/low"}}"""

        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a classifier that assigns learning resources to topic clusters. Return only valid JSON."},
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
                "id": resource.get('id', ''),
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
                "id": resource.get('id', ''),
                "name": name,
                "category": category,
                "primary": "error",
                "secondary": None,
                "confidence": "low",
                "status": f"error: {str(e)}"
            }


async def process_all_resources(client: AsyncOpenAI, resources: list, cluster_prompt: str, limit: int = None):
    """Process all resources with LLM assignment."""
    if limit:
        resources = resources[:limit]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        assign_resource(client, r, cluster_prompt, semaphore)
        for r in resources
    ]

    print(f"\nProcessing {len(tasks)} resources...")
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


def build_clusters_from_assignments(assignments: list, resources: list, cluster_defs: dict) -> dict:
    """Build resource_clusters.json from assignments."""
    # Build resource lookup
    resource_by_id = {r.get('id', ''): r for r in resources}

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

        if len(item_ids) < 4:
            print(f"  Skipping '{cluster_id}' - only {len(item_ids)} items")
            continue

        cluster_def = cluster_by_id[cluster_id]

        # Get original categories
        orig_cats = set()
        for rid in item_ids:
            if rid in resource_by_id:
                cat = resource_by_id[rid].get('category', 'Unknown')
                orig_cats.add(cat)

        # Get items sorted by model_score
        items_with_score = []
        for rid in item_ids:
            if rid in resource_by_id:
                score = resource_by_id[rid].get('model_score', 0)
                items_with_score.append((rid, score))
        items_with_score.sort(key=lambda x: -x[1])

        # Carousel items (top 10)
        carousel_items = [rid for rid, _ in items_with_score[:10]]

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
            "min_cluster_size": 4,
            "max_cluster_size": 10
        },
        "total_clusters": len(output_clusters),
        "total_items": sum(c['item_count'] for c in output_clusters),
        "clusters": output_clusters
    }


async def main():
    parser = argparse.ArgumentParser(description="LLM-assisted cluster assignment")
    parser.add_argument('--limit', type=int, help="Limit number of resources to process")
    parser.add_argument('--apply', action='store_true', help="Apply assignments from reviewed CSV")
    args = parser.parse_args()

    # Load data
    print("Loading data...")
    resources = load_resources()
    cluster_defs = load_cluster_definitions()
    print(f"  {len(resources)} resources")
    print(f"  {len(cluster_defs['clusters'])} cluster definitions")

    if args.apply:
        # Apply from reviewed CSV
        if not OUTPUT_CSV.exists():
            print(f"Error: {OUTPUT_CSV} not found")
            print("Run without --apply first to generate assignments")
            return

        print(f"\nLoading reviewed assignments from {OUTPUT_CSV}...")
        assignments = load_reviewed_csv(OUTPUT_CSV)
        print(f"  {len(assignments)} assignments")

        print("\nBuilding clusters...")
        output = build_clusters_from_assignments(assignments, resources, cluster_defs)

        print(f"\nSaving to {OUTPUT_JSON}...")
        with open(OUTPUT_JSON, 'w') as f:
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

        results = await process_all_resources(client, resources, cluster_prompt, limit=args.limit)

        # Save for review
        save_csv_for_review(results, OUTPUT_CSV)

        # Summary
        success = sum(1 for r in results if r['status'] == 'success')
        high_conf = sum(1 for r in results if r['confidence'] == 'high')
        print(f"\nSummary:")
        print(f"  Success: {success}/{len(results)}")
        print(f"  High confidence: {high_conf}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
