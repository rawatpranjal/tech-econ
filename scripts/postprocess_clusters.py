#!/usr/bin/env python3
"""
Post-process topic clusters to improve quality.

Fixes:
1. Merges small clusters (1-2 items) into similar larger clusters
2. Consolidates career portal clusters into ~10 industry categories
3. Merges similar/duplicate cluster pairs
4. Regenerates generic labels with stricter LLM prompt

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/postprocess_clusters.py
"""

import json
import os
import time
import numpy as np
from collections import Counter, defaultdict
from pathlib import Path

# Optional OpenAI for LLM labels
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CLUSTERS_FILE = PROJECT_ROOT / "data" / "topic_clusters_all.json"
EMBEDDINGS_DIR = PROJECT_ROOT / "static" / "embeddings"

# Career industry mapping
CAREER_INDUSTRIES = {
    "Tech Industry Careers": [
        "tech", "faang", "google", "meta", "amazon", "microsoft", "apple",
        "startup", "software", "saas", "cloud"
    ],
    "Finance & Fintech Careers": [
        "fintech", "finance", "bank", "trading", "quant", "crypto", "blockchain",
        "wealth", "investment", "lending", "neobank", "payment"
    ],
    "E-Commerce & Retail Careers": [
        "ecommerce", "e-commerce", "retail", "cpg", "grocery", "apparel",
        "fashion", "beauty", "consumer"
    ],
    "Healthcare & Pharma Careers": [
        "health", "pharma", "biotech", "medical", "heor", "biostatistics"
    ],
    "Automotive & Mobility Careers": [
        "automotive", "auto", "vehicle", "mobility", "rideshare", "ride-hail",
        "fleet", "delivery", "logistics"
    ],
    "Gaming & Entertainment Careers": [
        "gaming", "game", "streaming", "entertainment", "media", "music"
    ],
    "Travel & Hospitality Careers": [
        "travel", "hotel", "airline", "hospitality", "booking"
    ],
    "Data & Analytics Careers": [
        "data science", "analytics", "experimentation", "product analytics"
    ],
    "AI & ML Research Careers": [
        "ai research", "ml research", "research scientist"
    ],
}

# Generic terms to avoid in labels
GENERIC_TERMS = [
    "insights", "techniques", "analysis", "overview", "framework",
    "methods", "approaches", "strategies", "resources", "tools"
]


def load_clusters():
    """Load existing clusters."""
    with open(CLUSTERS_FILE) as f:
        return json.load(f)


def load_embeddings():
    """Load embeddings and metadata."""
    metadata_file = EMBEDDINGS_DIR / "search-metadata.json"
    embeddings_file = EMBEDDINGS_DIR / "search-embeddings.bin"

    with open(metadata_file) as f:
        metadata = json.load(f)

    count = metadata['count']
    dim = metadata['dimensions']

    with open(embeddings_file, 'rb') as f:
        data = np.frombuffer(f.read(), dtype=np.float32)
    embeddings = data.reshape(count, dim)

    # Build item_id to index mapping
    id_to_idx = {item['id']: i for i, item in enumerate(metadata['items'])}

    return embeddings, metadata['items'], id_to_idx


def compute_cluster_centroid(cluster, embeddings, id_to_idx, item_to_cluster):
    """Compute centroid embedding for a cluster."""
    cluster_id = cluster['id']
    indices = [id_to_idx[item_id] for item_id, cid in item_to_cluster.items()
               if cid == cluster_id and item_id in id_to_idx]
    if not indices:
        return None
    return embeddings[indices].mean(axis=0)


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def is_career_cluster(cluster):
    """Check if cluster is career-related."""
    label_lower = cluster['label'].lower()
    career_terms = ['career', 'portal', 'job', 'hiring', 'opportunities', 'internship']
    return any(term in label_lower for term in career_terms)


def get_career_industry(cluster):
    """Determine which industry category a career cluster belongs to."""
    label_lower = cluster['label'].lower()
    tags = ' '.join(cluster.get('top_tags', [])).lower()
    text = label_lower + ' ' + tags

    for industry, keywords in CAREER_INDUSTRIES.items():
        if any(kw in text for kw in keywords):
            return industry
    return "Other Industry Careers"


def is_generic_label(label):
    """Check if label contains too many generic terms."""
    label_lower = label.lower()
    count = sum(1 for term in GENERIC_TERMS if term in label_lower)
    return count >= 2


def generate_improved_label(items, top_tags, top_categories, is_career=False):
    """Generate improved label using LLM."""
    if not OPENAI_AVAILABLE:
        return None

    client = OpenAI()

    sample_names = [item.get('name', '')[:40] for item in items[:6]]
    sample_descriptions = [item.get('description', '')[:80] for item in items[:4]]

    if is_career:
        prompt = f"""Generate a concise industry career category label (3-5 words).

Sample items: {', '.join(sample_names)}
Tags: {', '.join(top_tags[:5])}

Rules:
- Format: "[Industry] Careers" or "[Industry] Career Portals"
- Be specific about the industry vertical
- Examples: "Fintech Careers", "E-Commerce Retail Careers", "Gaming Industry Careers"

Label:"""
    else:
        prompt = f"""Generate a specific technical label (3-5 words) for this cluster.

Items: {', '.join(sample_names)}
Tags: {', '.join(top_tags[:5])}
Categories: {', '.join(top_categories[:2])}
Descriptions: {'; '.join(sample_descriptions)}

STRICT RULES:
- NO generic words: insights, techniques, analysis, overview, framework, methods, approaches
- USE specific domain terms: DID, RDD, bandits, uplift, synthetic control, causal forest, etc.
- Format: "[Specific Method] [Domain Application]"
- Examples: "Doubly Robust DiD Estimators", "Thompson Sampling Bandits", "Causal Forest Inference"

Label:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3
        )
        label = response.choices[0].message.content.strip()
        label = label.strip('"\'').rstrip('.')
        time.sleep(0.1)
        return label
    except Exception as e:
        print(f"    [LLM error: {e}]")
        return None


def merge_cluster_data(clusters_to_merge, all_items, id_to_idx, item_to_cluster):
    """Merge multiple clusters into one."""
    merged_items = []
    all_tags = []
    all_categories = []

    for cluster in clusters_to_merge:
        cluster_id = cluster['id']
        for item_id, cid in item_to_cluster.items():
            if cid == cluster_id and item_id in id_to_idx:
                idx = id_to_idx[item_id]
                merged_items.append(all_items[idx])
        all_tags.extend(cluster.get('top_tags', []))
        all_categories.extend(cluster.get('top_categories', []))

    # Get most common tags/categories
    tag_counts = Counter(all_tags)
    cat_counts = Counter(all_categories)
    top_tags = [tag for tag, _ in tag_counts.most_common(5)]
    top_categories = [cat for cat, _ in cat_counts.most_common(3)]

    return merged_items, top_tags, top_categories


def main():
    print("="*60)
    print("CLUSTER POST-PROCESSING")
    print("="*60)

    # Load data
    print("\nLoading clusters...")
    data = load_clusters()
    clusters = data['clusters']
    item_to_cluster = data['item_to_cluster']
    print(f"  Loaded {len(clusters)} clusters")

    print("\nLoading embeddings...")
    embeddings, all_items, id_to_idx = load_embeddings()
    print(f"  Loaded {len(all_items)} items")

    if OPENAI_AVAILABLE:
        print("\nLLM: ENABLED (GPT-4o-mini)")
    else:
        print("\nLLM: DISABLED")

    # Step 1: Identify small clusters and career clusters
    print("\n" + "="*60)
    print("STEP 1: Analyzing clusters")
    print("="*60)

    small_clusters = [c for c in clusters if c['item_count'] <= 2]
    career_clusters = [c for c in clusters if is_career_cluster(c)]
    generic_clusters = [c for c in clusters if is_generic_label(c['label'])]

    print(f"  Small clusters (1-2 items): {len(small_clusters)}")
    print(f"  Career clusters: {len(career_clusters)}")
    print(f"  Generic labels: {len(generic_clusters)}")

    # Step 2: Consolidate career clusters by industry
    print("\n" + "="*60)
    print("STEP 2: Consolidating career clusters")
    print("="*60)

    industry_groups = defaultdict(list)
    non_career_clusters = []

    for cluster in clusters:
        if is_career_cluster(cluster):
            industry = get_career_industry(cluster)
            industry_groups[industry].append(cluster)
        else:
            non_career_clusters.append(cluster)

    print(f"\n  Career clusters by industry:")
    for industry, group in sorted(industry_groups.items(), key=lambda x: -len(x[1])):
        print(f"    {industry}: {len(group)} clusters")

    # Create merged career clusters
    new_career_clusters = []
    for industry, group in industry_groups.items():
        if len(group) == 0:
            continue

        # Merge all clusters in this industry
        merged_items, top_tags, top_categories = merge_cluster_data(
            group, all_items, id_to_idx, item_to_cluster
        )

        # Generate label
        label = generate_improved_label(merged_items, top_tags, top_categories, is_career=True)
        if not label:
            label = industry

        # Collect all item IDs
        all_item_ids = []
        for cluster in group:
            cluster_id = cluster['id']
            for item_id, cid in item_to_cluster.items():
                if cid == cluster_id:
                    all_item_ids.append(item_id)

        new_cluster = {
            "id": -1,  # Will reassign later
            "label": label,
            "top_tags": top_tags,
            "top_categories": top_categories,
            "item_count": len(all_item_ids),
            "sample_items": all_item_ids[:10],
            "_all_items": all_item_ids  # Temporary for item_to_cluster update
        }
        new_career_clusters.append(new_cluster)
        print(f"  Created: {label} ({len(all_item_ids)} items)")

    # Step 3: Merge small non-career clusters into similar larger ones
    print("\n" + "="*60)
    print("STEP 3: Merging small clusters")
    print("="*60)

    # Compute centroids for all non-career clusters
    large_clusters = [c for c in non_career_clusters if c['item_count'] > 2]
    small_non_career = [c for c in non_career_clusters if c['item_count'] <= 2]

    print(f"  Large clusters: {len(large_clusters)}")
    print(f"  Small clusters to merge: {len(small_non_career)}")

    # Compute centroids
    centroids = {}
    for cluster in large_clusters + small_non_career:
        centroid = compute_cluster_centroid(cluster, embeddings, id_to_idx, item_to_cluster)
        if centroid is not None:
            centroids[cluster['id']] = centroid

    # Find best match for each small cluster
    merged_into = {}  # small_cluster_id -> large_cluster_id
    for small in small_non_career:
        if small['id'] not in centroids:
            continue

        small_centroid = centroids[small['id']]
        best_match = None
        best_sim = 0.75  # Minimum threshold

        for large in large_clusters:
            if large['id'] not in centroids:
                continue
            sim = cosine_similarity(small_centroid, centroids[large['id']])
            if sim > best_sim:
                best_sim = sim
                best_match = large

        if best_match:
            merged_into[small['id']] = best_match['id']
            print(f"  Merging '{small['label']}' -> '{best_match['label']}' (sim={best_sim:.2f})")

    # Apply merges to large clusters
    for small_id, large_id in merged_into.items():
        # Find the clusters
        small_cluster = next(c for c in small_non_career if c['id'] == small_id)
        large_cluster = next(c for c in large_clusters if c['id'] == large_id)

        # Transfer items
        for item_id, cid in list(item_to_cluster.items()):
            if cid == small_id:
                item_to_cluster[item_id] = large_id

        # Update count
        large_cluster['item_count'] += small_cluster['item_count']

    # Remove merged small clusters
    remaining_clusters = [c for c in large_clusters]
    remaining_clusters.extend([c for c in small_non_career if c['id'] not in merged_into])

    print(f"\n  Merged {len(merged_into)} small clusters")
    print(f"  Remaining non-career clusters: {len(remaining_clusters)}")

    # Step 4: Improve generic labels
    print("\n" + "="*60)
    print("STEP 4: Improving generic labels")
    print("="*60)

    improved = 0
    for cluster in remaining_clusters:
        if is_generic_label(cluster['label']):
            # Get items for this cluster
            cluster_items = []
            for item_id, cid in item_to_cluster.items():
                if cid == cluster['id'] and item_id in id_to_idx:
                    cluster_items.append(all_items[id_to_idx[item_id]])

            new_label = generate_improved_label(
                cluster_items,
                cluster.get('top_tags', []),
                cluster.get('top_categories', [])
            )
            if new_label and not is_generic_label(new_label):
                print(f"  '{cluster['label']}' -> '{new_label}'")
                cluster['label'] = new_label
                improved += 1

    print(f"\n  Improved {improved} generic labels")

    # Step 5: Combine and reassign IDs
    print("\n" + "="*60)
    print("STEP 5: Finalizing clusters")
    print("="*60)

    final_clusters = remaining_clusters + new_career_clusters

    # Sort by size
    final_clusters.sort(key=lambda x: -x['item_count'])

    # Reassign IDs and update item_to_cluster
    old_to_new_id = {}
    for i, cluster in enumerate(final_clusters):
        old_id = cluster['id']
        cluster['id'] = i
        if old_id >= 0:
            old_to_new_id[old_id] = i
        else:
            # New career cluster - update from _all_items
            for item_id in cluster.get('_all_items', []):
                item_to_cluster[item_id] = i
            if '_all_items' in cluster:
                del cluster['_all_items']

    # Update item_to_cluster for remaining clusters
    for item_id in list(item_to_cluster.keys()):
        old_id = item_to_cluster[item_id]
        if old_id in old_to_new_id:
            item_to_cluster[item_id] = old_to_new_id[old_id]

    # Update sample_items
    for cluster in final_clusters:
        cluster_id = cluster['id']
        cluster_items = [item_id for item_id, cid in item_to_cluster.items() if cid == cluster_id]
        cluster['sample_items'] = cluster_items[:10]
        cluster['item_count'] = len(cluster_items)

    print(f"  Final cluster count: {len(final_clusters)}")

    # Save
    output = {
        "generated_at": data.get('generated_at', ''),
        "postprocessed_at": str(np.datetime64('now')),
        "num_clusters": len(final_clusters),
        "num_items": len(item_to_cluster),
        "clusters": final_clusters,
        "item_to_cluster": item_to_cluster
    }

    print(f"\nSaving to {CLUSTERS_FILE}...")
    with open(CLUSTERS_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    sizes = [c['item_count'] for c in final_clusters]
    print(f"  Total clusters: {len(final_clusters)}")
    print(f"  Single-item clusters: {sum(1 for s in sizes if s == 1)}")
    print(f"  Career clusters: {len(new_career_clusters)}")
    print(f"  Avg items/cluster: {sum(sizes)/len(sizes):.1f}")
    print(f"  Min/Max size: {min(sizes)}/{max(sizes)}")


if __name__ == "__main__":
    main()
