#!/usr/bin/env python3
"""
Split oversized clusters into sub-clusters using LLM assignment.
"""

import json
import os
import asyncio
from pathlib import Path

try:
    from openai import AsyncOpenAI
except ImportError:
    print("Error: pip install openai")
    exit(1)

PROJECT_ROOT = Path(__file__).parent.parent
MODEL = "gpt-4o-mini"

# Sub-cluster definitions for each oversized cluster
RESOURCE_SUBCLUSTERS = {
    "Marketplace Design": [
        {"id": "marketplace-platform-strategy", "label": "Platform Strategy & Business Models"},
        {"id": "marketplace-matching", "label": "Matching & Search"},
        {"id": "marketplace-trust", "label": "Trust, Reviews & Quality"},
        {"id": "marketplace-pricing", "label": "Marketplace Pricing"},
        {"id": "marketplace-liquidity", "label": "Liquidity & Growth"},
        {"id": "marketplace-governance", "label": "Platform Governance"},
    ],
    "ML for Economists": [
        {"id": "ml-intro", "label": "ML Fundamentals for Economists"},
        {"id": "ml-causal", "label": "Causal ML & Treatment Effects"},
        {"id": "ml-prediction", "label": "Prediction & Forecasting"},
        {"id": "ml-feature-eng", "label": "Feature Engineering"},
        {"id": "ml-interpretability", "label": "Interpretability & Explainability"},
        {"id": "ml-production", "label": "Production ML & MLOps"},
    ],
    "Network Effects & Aggregation": [
        {"id": "network-theory", "label": "Network Effects Theory"},
        {"id": "network-growth", "label": "Virality & Growth Loops"},
        {"id": "network-competition", "label": "Platform Competition"},
        {"id": "network-ecosystem", "label": "Ecosystem Strategy"},
    ],
    "A/B Testing Foundations": [
        {"id": "ab-design", "label": "Experiment Design"},
        {"id": "ab-statistics", "label": "Statistical Methods"},
        {"id": "ab-variance", "label": "Variance Reduction (CUPED)"},
        {"id": "ab-platforms", "label": "Experimentation Platforms"},
    ],
    "Linear Programming": [
        {"id": "lp-fundamentals", "label": "LP Fundamentals"},
        {"id": "lp-mip", "label": "MIP & Integer Programming"},
        {"id": "lp-modeling", "label": "Optimization Modeling"},
    ],
    "Vehicle Routing & Logistics": [
        {"id": "vrp-fundamentals", "label": "VRP Fundamentals"},
        {"id": "vrp-dispatch", "label": "Dispatch & Last Mile"},
    ],
    "CLV & Retention": [
        {"id": "clv-modeling", "label": "Customer Lifetime Value"},
        {"id": "clv-churn", "label": "Retention & Churn"},
    ],
    "Pricing & Revenue Management": [
        {"id": "pricing-dynamic", "label": "Dynamic Pricing"},
        {"id": "pricing-revenue", "label": "Revenue Management"},
    ],
}

PACKAGE_SUBCLUSTERS = {
    "DiD & Synthetic Control": [
        {"id": "did-classic", "label": "Classic DiD"},
        {"id": "did-staggered", "label": "Staggered DiD"},
        {"id": "did-synth", "label": "Synthetic Control"},
        {"id": "did-extensions", "label": "DiD Extensions"},
    ],
    "Statistical Testing": [
        {"id": "stats-hypothesis", "label": "Hypothesis Testing"},
        {"id": "stats-multiple", "label": "Multiple Testing Correction"},
        {"id": "stats-power", "label": "Power Analysis"},
        {"id": "stats-bayesian", "label": "Bayesian Testing"},
    ],
    "Structural Econometrics": [
        {"id": "struct-blp", "label": "BLP & Demand Estimation"},
        {"id": "struct-dynamic", "label": "Dynamic Models"},
        {"id": "struct-estimation", "label": "Structural Estimation"},
    ],
    "Discrete Event Simulation": [
        {"id": "des-simpy", "label": "SimPy & DES Frameworks"},
        {"id": "des-queue", "label": "Queue Simulation"},
    ],
}


async def assign_to_subcluster(client, item_name, item_desc, subclusters):
    """Assign an item to one of the subclusters using LLM."""
    subcluster_list = "\n".join([f"- {s['id']}: {s['label']}" for s in subclusters])
    
    prompt = f"""Assign this item to exactly ONE of the sub-clusters below.

ITEM:
- Name: {item_name}
- Description: {item_desc[:500]}

SUB-CLUSTERS:
{subcluster_list}

Return ONLY the sub-cluster ID, nothing else."""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=50
        )
        result = response.choices[0].message.content.strip()
        # Validate it's a valid subcluster
        valid_ids = [s['id'] for s in subclusters]
        if result in valid_ids:
            return result
        # Try to find partial match
        for vid in valid_ids:
            if vid in result:
                return vid
        return subclusters[0]['id']  # Default to first
    except Exception as e:
        print(f"  Error: {e}")
        return subclusters[0]['id']


async def split_cluster(client, cluster, items_data, subclusters, content_type):
    """Split a cluster into sub-clusters."""
    print(f"\nSplitting '{cluster['label']}' ({cluster['item_count']} items) into {len(subclusters)} sub-clusters...")
    
    # Build item lookup
    item_lookup = {item.get('name', item.get('id', '')): item for item in items_data}
    
    # Assign each item to a subcluster
    assignments = {}
    for item_id in cluster['items']:
        # Find item data
        item = None
        for i in items_data:
            if i.get('name') == item_id or i.get('id') == item_id:
                item = i
                break
        
        if item:
            name = item.get('name', item_id)
            desc = item.get('description', '')
            subcluster_id = await assign_to_subcluster(client, name, desc, subclusters)
        else:
            subcluster_id = subclusters[0]['id']
        
        if subcluster_id not in assignments:
            assignments[subcluster_id] = []
        assignments[subcluster_id].append(item_id)
    
    # Create new cluster entries
    new_clusters = []
    for sc in subclusters:
        items = assignments.get(sc['id'], [])
        if len(items) >= 3:  # Only create if at least 3 items
            new_clusters.append({
                "id": f"cluster-{sc['id']}",
                "label": sc['label'],
                "cluster_id": sc['id'],
                "macro_category": cluster.get('macro_category', 'Other'),
                "original_categories": cluster.get('original_categories', []),
                "item_count": len(items),
                "items": items,
                "carousel_items": items[:10]
            })
            print(f"  {sc['label']}: {len(items)} items")
    
    return new_clusters


async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        return
    
    client = AsyncOpenAI(api_key=api_key)
    
    # Process resources
    print("=== SPLITTING RESOURCE CLUSTERS ===")
    
    with open(PROJECT_ROOT / "data" / "resources.json") as f:
        resources = json.load(f)
    
    with open(PROJECT_ROOT / "data" / "resource_clusters.json") as f:
        resource_clusters = json.load(f)
    
    new_clusters = []
    for cluster in resource_clusters['clusters']:
        if cluster['label'] in RESOURCE_SUBCLUSTERS:
            subclusters = RESOURCE_SUBCLUSTERS[cluster['label']]
            split = await split_cluster(client, cluster, resources, subclusters, 'resources')
            new_clusters.extend(split)
        else:
            new_clusters.append(cluster)
    
    resource_clusters['clusters'] = new_clusters
    resource_clusters['total_clusters'] = len(new_clusters)
    resource_clusters['total_items'] = sum(c['item_count'] for c in new_clusters)
    
    with open(PROJECT_ROOT / "data" / "resource_clusters.json", 'w') as f:
        json.dump(resource_clusters, f, indent=2)
    
    print(f"\nResource clusters: {resource_clusters['total_clusters']} clusters, {resource_clusters['total_items']} items")
    
    # Process packages
    print("\n=== SPLITTING PACKAGE CLUSTERS ===")
    
    with open(PROJECT_ROOT / "data" / "packages.json") as f:
        packages = json.load(f)
    
    with open(PROJECT_ROOT / "data" / "package_clusters.json") as f:
        package_clusters = json.load(f)
    
    new_clusters = []
    for cluster in package_clusters['clusters']:
        if cluster['label'] in PACKAGE_SUBCLUSTERS:
            subclusters = PACKAGE_SUBCLUSTERS[cluster['label']]
            split = await split_cluster(client, cluster, packages, subclusters, 'packages')
            new_clusters.extend(split)
        else:
            new_clusters.append(cluster)
    
    package_clusters['clusters'] = new_clusters
    package_clusters['total_clusters'] = len(new_clusters)
    package_clusters['total_items'] = sum(c['item_count'] for c in new_clusters)
    
    with open(PROJECT_ROOT / "data" / "package_clusters.json", 'w') as f:
        json.dump(package_clusters, f, indent=2)
    
    print(f"\nPackage clusters: {package_clusters['total_clusters']} clusters, {package_clusters['total_items']} items")


if __name__ == "__main__":
    asyncio.run(main())
