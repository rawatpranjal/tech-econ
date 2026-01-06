#!/usr/bin/env python3
"""
LLM-Assisted Cluster Assignment for Packages.

Assigns each package to 1-2 manually curated clusters using OpenAI.
Outputs CSV for human review before final assignment.

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/assign_packages_to_clusters.py
    OPENAI_API_KEY=sk-... python3 scripts/assign_packages_to_clusters.py --limit 50  # Test with 50 items
    OPENAI_API_KEY=sk-... python3 scripts/assign_packages_to_clusters.py --apply      # Apply from reviewed CSV
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
PACKAGES_FILE = PROJECT_ROOT / "data" / "packages.json"
CLUSTER_DEFS_FILE = PROJECT_ROOT / "data" / "package_cluster_definitions.json"
OUTPUT_CSV = PROJECT_ROOT / "scripts" / "package_cluster_assignments_review.csv"
OUTPUT_JSON = PROJECT_ROOT / "data" / "package_clusters.json"

# API settings
MODEL = "gpt-4o-mini"
MAX_CONCURRENT = 10
RATE_LIMIT_DELAY = 0.1


def load_packages():
    """Load packages data."""
    with open(PACKAGES_FILE) as f:
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


async def assign_package(client: AsyncOpenAI, package: dict, cluster_prompt: str, semaphore: asyncio.Semaphore) -> dict:
    """Assign a single package to clusters using LLM."""
    async with semaphore:
        await asyncio.sleep(RATE_LIMIT_DELAY)

        name = package.get('name', 'Unknown')
        description = package.get('description', '')
        category = package.get('category', '')
        language = package.get('language', '')
        tags = ', '.join(package.get('tags', [])[:5])

        prompt = f"""Assign this Python/R package to 1-2 of the curated topic clusters below.

PACKAGE:
- Name: {name}
- Description: {description}
- Category: {category}
- Language: {language}
- Tags: {tags}

AVAILABLE CLUSTERS:
{cluster_prompt}

INSTRUCTIONS:
1. Choose 1-2 clusters that best match this package's functionality
2. Primary cluster should be the best fit
3. Secondary cluster is optional (only if clearly relevant)
4. If no cluster fits well, use "none" as primary

Return JSON only:
{{"primary": "cluster-id", "secondary": "cluster-id or null", "confidence": "high/medium/low"}}"""

        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a classifier that assigns Python/R packages to topic clusters. Return only valid JSON."},
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
                "id": package.get('name', '').lower().replace(' ', '-').replace('(', '').replace(')', ''),
                "name": name,
                "category": category,
                "language": language,
                "primary": result.get('primary', 'none'),
                "secondary": result.get('secondary'),
                "confidence": result.get('confidence', 'medium'),
                "status": "success"
            }

        except Exception as e:
            print(f"  Error processing '{name}': {e}")
            return {
                "id": package.get('name', '').lower().replace(' ', '-'),
                "name": name,
                "category": category,
                "language": language,
                "primary": "error",
                "secondary": None,
                "confidence": "low",
                "status": f"error: {str(e)}"
            }


async def process_all_packages(client: AsyncOpenAI, packages: list, cluster_prompt: str, limit: int = None):
    """Process all packages with LLM assignment."""
    if limit:
        packages = packages[:limit]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [
        assign_package(client, p, cluster_prompt, semaphore)
        for p in packages
    ]

    print(f"\nProcessing {len(tasks)} packages...")
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
            'id', 'name', 'category', 'language', 'primary', 'secondary', 'confidence', 'status'
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


def build_clusters_from_assignments(assignments: list, packages: list, cluster_defs: dict) -> dict:
    """Build package_clusters.json from assignments."""
    # Build package lookup by name (lowercase, normalized)
    package_by_name = {}
    for p in packages:
        name = p.get('name', '')
        key = name.lower().replace(' ', '-').replace('(', '').replace(')', '')
        package_by_name[key] = p
        # Also store by exact name for fallback
        package_by_name[name] = p

    # Build cluster lookup
    cluster_by_id = {c['id']: c for c in cluster_defs['clusters']}

    # Group assignments by cluster
    cluster_items = {}
    for a in assignments:
        pkg_id = a['id']
        name = a['name']
        primary = a['primary']
        secondary = a.get('secondary')

        if primary and primary != 'none' and primary != 'error':
            if primary not in cluster_items:
                cluster_items[primary] = []
            cluster_items[primary].append(name)

        if secondary and secondary != 'null' and secondary != 'None':
            if secondary not in cluster_items:
                cluster_items[secondary] = []
            if name not in cluster_items[secondary]:
                cluster_items[secondary].append(name)

    # Build output clusters
    output_clusters = []
    for cluster_id, pkg_names in cluster_items.items():
        if cluster_id not in cluster_by_id:
            print(f"  Warning: Unknown cluster '{cluster_id}'")
            continue

        if len(pkg_names) < 4:
            print(f"  Skipping '{cluster_id}' - only {len(pkg_names)} items")
            continue

        cluster_def = cluster_by_id[cluster_id]

        # Get original categories
        orig_cats = set()
        languages = set()
        for name in pkg_names:
            pkg = package_by_name.get(name)
            if pkg:
                cat = pkg.get('category', 'Unknown')
                lang = pkg.get('language', 'Unknown')
                orig_cats.add(cat)
                languages.add(lang)

        # Get items sorted by model_score
        items_with_score = []
        for name in pkg_names:
            pkg = package_by_name.get(name)
            if pkg:
                score = pkg.get('model_score', 0)
                items_with_score.append((name, score))
        items_with_score.sort(key=lambda x: -x[1])

        # Carousel items (top 10)
        carousel_items = [name for name, _ in items_with_score[:10]]

        output_clusters.append({
            "id": f"cluster-{cluster_id}",
            "label": cluster_def['label'],
            "cluster_id": cluster_id,
            "macro_category": cluster_def['macro_category'],
            "original_categories": list(orig_cats),
            "languages": list(languages),
            "item_count": len(pkg_names),
            "items": pkg_names,
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
    parser = argparse.ArgumentParser(description="LLM-assisted package cluster assignment")
    parser.add_argument('--limit', type=int, help="Limit number of packages to process")
    parser.add_argument('--apply', action='store_true', help="Apply assignments from reviewed CSV")
    args = parser.parse_args()

    # Load data
    print("Loading data...")
    packages = load_packages()
    cluster_defs = load_cluster_definitions()
    print(f"  {len(packages)} packages")
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
        output = build_clusters_from_assignments(assignments, packages, cluster_defs)

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

        results = await process_all_packages(client, packages, cluster_prompt, limit=args.limit)

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
