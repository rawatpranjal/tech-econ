#!/usr/bin/env python3
"""
Cluster resources into niche topic groups for the Learning section.

V3: Improved algorithm that:
1. Groups by semantic_cluster (method-specific)
2. Merges small semantic_clusters with similar ones
3. Creates new clusters from orphans using K-means
4. Strictly enforces 5-10 item cluster sizes

Usage:
    python3 scripts/cluster_resources.py

Output: data/resource_clusters.json
"""

import json
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from sklearn.cluster import KMeans

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
RESOURCES_FILE = PROJECT_ROOT / "data" / "resources.json"
EMBEDDINGS_DIR = PROJECT_ROOT / "static" / "embeddings"
OUTPUT_FILE = PROJECT_ROOT / "data" / "resource_clusters.json"

# Clustering parameters
MIN_CLUSTER_SIZE = 4
MAX_CLUSTER_SIZE = 10
TARGET_CLUSTER_SIZE = 7


def load_resources():
    """Load resources data."""
    with open(RESOURCES_FILE) as f:
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

    # Build item_id to index mapping for resource items
    id_to_idx = {}
    for i, item in enumerate(metadata['items']):
        if item['id'].startswith('resource-'):
            id_to_idx[item['id']] = i

    return embeddings, id_to_idx


def get_resource_id(resource):
    """Get or generate resource ID."""
    if 'id' in resource and resource['id']:
        return resource['id']
    name = resource.get('name', '')
    slug = name.lower()
    for char in [':', ',', "'", '"', '(', ')', '[', ']', '{', '}', '&', '?', '!', '.', '/']:
        slug = slug.replace(char, '')
    slug = slug.replace(' ', '-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')[:50]
    return f"resource-{slug}"


def format_label(semantic_cluster):
    """Format semantic_cluster into readable label."""
    if not semantic_cluster:
        return "Other"

    # Convert hyphenated to title case
    words = semantic_cluster.replace('-', ' ').replace('_', ' ').split()
    formatted = ' '.join(w.capitalize() for w in words)

    # Handle common abbreviations
    replacements = {
        'Ml ': 'ML ',
        'Ai ': 'AI ',
        'Ab ': 'A/B ',
        'Llm': 'LLM',
        'Nlp': 'NLP',
        'Clv': 'CLV',
        'Did': 'DiD',
        'Rdd': 'RDD',
        'Api': 'API',
        'Sql': 'SQL',
        'Etl': 'ETL',
    }
    for old, new in replacements.items():
        formatted = formatted.replace(old, new)

    return formatted


def get_embedding(resource, embeddings, id_to_idx):
    """Get normalized embedding for a resource."""
    rid = get_resource_id(resource)
    if rid not in id_to_idx:
        return None
    idx = id_to_idx[rid]
    emb = embeddings[idx]
    norm = np.linalg.norm(emb)
    if norm > 0:
        return emb / norm
    return emb


def compute_centroid(items, embeddings, id_to_idx):
    """Compute centroid of item embeddings."""
    embs = []
    for item in items:
        emb = get_embedding(item, embeddings, id_to_idx)
        if emb is not None:
            embs.append(emb)
    if not embs:
        return None
    centroid = np.mean(embs, axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        return centroid / norm
    return centroid


def cluster_items_kmeans(items, embeddings, id_to_idx, target_size=7, max_recursion=3):
    """Cluster items using K-means, targeting specific cluster size.

    Uses recursive splitting to ensure no cluster exceeds MAX_CLUSTER_SIZE.
    """
    # Get embeddings for items
    valid_items = []
    item_embs = []
    for item in items:
        emb = get_embedding(item, embeddings, id_to_idx)
        if emb is not None:
            valid_items.append(item)
            item_embs.append(emb)

    if len(valid_items) < MIN_CLUSTER_SIZE:
        return [valid_items] if valid_items else []

    if len(valid_items) <= MAX_CLUSTER_SIZE:
        return [valid_items]

    # Calculate number of clusters - aim for target_size
    n_clusters = max(2, len(valid_items) // target_size)
    n_clusters = min(n_clusters, len(valid_items) // MIN_CLUSTER_SIZE)

    # Run K-means
    item_embs = np.array(item_embs)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(item_embs)

    # Group by cluster
    initial_clusters = []
    for k in range(n_clusters):
        cluster_items = [valid_items[i] for i in range(len(valid_items)) if labels[i] == k]
        if cluster_items:
            initial_clusters.append(cluster_items)

    # Recursively split any clusters that are still too large
    final_clusters = []
    for cluster in initial_clusters:
        if len(cluster) > MAX_CLUSTER_SIZE and max_recursion > 0:
            # Recursively split
            sub_clusters = cluster_items_kmeans(
                cluster, embeddings, id_to_idx,
                target_size=target_size,
                max_recursion=max_recursion - 1
            )
            final_clusters.extend(sub_clusters)
        else:
            final_clusters.append(cluster)

    return final_clusters


def generate_label_from_items(items):
    """Generate a label from item attributes."""
    # Count topic_tags and categories
    tag_counts = Counter()
    cat_counts = Counter()

    for item in items:
        tags = item.get('topic_tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        for tag in tags:
            if tag:
                tag_counts[tag] += 1

        cat = item.get('category', '')
        if cat:
            cat_counts[cat] += 1

    # Use most common tag or category
    if tag_counts:
        label = tag_counts.most_common(1)[0][0]
    elif cat_counts:
        label = cat_counts.most_common(1)[0][0]
    else:
        label = "General Topics"

    return format_label(label)


def generate_sublabel(items, parent_label, existing_labels=None):
    """Generate a more specific label for a sub-cluster."""
    existing_labels = existing_labels or []

    # Find most common topic_tags that aren't in parent label
    tag_counts = Counter()
    cat_counts = Counter()
    for item in items:
        tags = item.get('topic_tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]
        for tag in tags:
            if tag:
                tag_counts[tag] += 1
        cat = item.get('category', '')
        if cat:
            cat_counts[cat] += 1

    parent_words = set(parent_label.lower().replace('-', ' ').split())

    # Try topic_tags first
    for tag, count in tag_counts.most_common(15):
        tag_words = set(tag.lower().replace('-', ' ').split())
        if not tag_words.intersection(parent_words):
            candidate = f"{parent_label}: {format_label(tag)}"
            if candidate not in existing_labels:
                return candidate

    # Try categories
    for cat, count in cat_counts.most_common(5):
        cat_words = set(cat.lower().replace('-', ' ').split())
        if not cat_words.intersection(parent_words):
            candidate = f"{parent_label}: {format_label(cat)}"
            if candidate not in existing_labels:
                return candidate

    # Fallback with index
    base = parent_label
    idx = 1
    while f"{base} #{idx}" in existing_labels:
        idx += 1
    return f"{base} #{idx}"


def compute_mmr_order(items, embeddings, id_to_idx, max_items=10):
    """Order items using MMR for diversity."""
    if len(items) <= max_items:
        # Sort by model_score
        sorted_items = sorted(items, key=lambda x: x.get('model_score', 0), reverse=True)
        return [get_resource_id(item) for item in sorted_items]

    # Get embeddings for items
    item_data = []
    for item in items:
        emb = get_embedding(item, embeddings, id_to_idx)
        if emb is not None:
            rid = get_resource_id(item)
            item_data.append((item, rid, emb))

    if not item_data:
        return [get_resource_id(item) for item in items[:max_items]]

    # Compute centroid
    all_embs = np.array([d[2] for d in item_data])
    centroid = all_embs.mean(axis=0)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-9)

    # Compute relevance scores
    relevance = {}
    for item, rid, emb in item_data:
        centroid_sim = np.dot(emb, centroid)
        model_score = item.get('model_score', 0.5)
        relevance[rid] = 0.5 * centroid_sim + 0.5 * model_score

    # MMR selection
    lambda_param = 0.6
    selected = []
    remaining = list(item_data)

    while len(selected) < max_items and remaining:
        best_item = None
        best_rid = None
        best_emb = None
        best_mmr = float('-inf')

        for item, rid, emb in remaining:
            rel = relevance.get(rid, 0)
            max_sim = 0
            for _, _, sel_emb in selected:
                sim = np.dot(emb, sel_emb)
                max_sim = max(max_sim, sim)
            mmr = lambda_param * rel - (1 - lambda_param) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_item = item
                best_rid = rid
                best_emb = emb

        if best_item:
            selected.append((best_item, best_rid, best_emb))
            remaining = [(i, r, e) for i, r, e in remaining if r != best_rid]

    return [rid for _, rid, _ in selected]


def main():
    print("=" * 60)
    print("RESOURCE CLUSTERING V3 (semantic_cluster + orphan clustering)")
    print("=" * 60)

    # Load data
    print("\nLoading resources...")
    resources = load_resources()
    print(f"  Loaded {len(resources)} resources")

    print("\nLoading embeddings...")
    embeddings, id_to_idx = load_embeddings()
    print(f"  Matched {len(id_to_idx)} resource embeddings")

    # Phase 1: Group by (macro_category, semantic_cluster)
    print("\n" + "=" * 60)
    print("PHASE 1: Group by semantic_cluster")
    print("=" * 60)

    sem_groups = defaultdict(list)  # (macro, semantic_cluster) -> [items]
    orphans_by_macro = defaultdict(list)  # macro -> [items without semantic_cluster]

    for r in resources:
        sem = r.get('semantic_cluster', None)
        macro = r.get('macro_category', 'Other')

        if sem and sem.strip():
            key = (macro, sem)
            sem_groups[key].append(r)
        else:
            orphans_by_macro[macro].append(r)

    print(f"  Unique semantic_cluster groups: {len(sem_groups)}")
    print(f"  Items without semantic_cluster: {sum(len(v) for v in orphans_by_macro.values())}")

    # Analyze semantic_cluster distribution
    size_dist = Counter(len(v) for v in sem_groups.values())
    print(f"\n  Semantic cluster size distribution:")
    for size in sorted(size_dist.keys()):
        print(f"    {size} items: {size_dist[size]} clusters")

    # Phase 2: Merge small semantic_clusters with similar ones
    print("\n" + "=" * 60)
    print("PHASE 2: Merge small semantic_clusters (<{} items)".format(MIN_CLUSTER_SIZE))
    print("=" * 60)

    # Group semantic_clusters by macro_category
    macro_to_sem_groups = defaultdict(list)
    for (macro, sem), items in sem_groups.items():
        macro_to_sem_groups[macro].append((sem, items))

    merged_clusters = []  # [(macro, label, semantic_cluster, items), ...]

    for macro, sem_list in macro_to_sem_groups.items():
        # Separate large and small groups
        large_groups = [(sem, items) for sem, items in sem_list if len(items) >= MIN_CLUSTER_SIZE]
        small_groups = [(sem, items) for sem, items in sem_list if len(items) < MIN_CLUSTER_SIZE]

        print(f"\n  {macro}: {len(large_groups)} large, {len(small_groups)} small groups")

        # Add large groups directly
        for sem, items in large_groups:
            merged_clusters.append((macro, format_label(sem), sem, items))

        # Merge small groups with similar ones
        if small_groups:
            # Compute centroids for large groups
            large_centroids = []
            for sem, items in large_groups:
                centroid = compute_centroid(items, embeddings, id_to_idx)
                large_centroids.append((sem, items, centroid))

            # Try to merge each small group
            unmerged_items = []
            for sem, items in small_groups:
                centroid = compute_centroid(items, embeddings, id_to_idx)
                if centroid is None:
                    unmerged_items.extend(items)
                    continue

                # Find best matching large group
                best_idx = None
                best_sim = 0.5  # Minimum similarity threshold

                for i, (_, _, large_centroid) in enumerate(large_centroids):
                    if large_centroid is not None:
                        sim = np.dot(centroid, large_centroid)
                        if sim > best_sim:
                            best_sim = sim
                            best_idx = i

                if best_idx is not None:
                    # Merge into large group
                    large_sem, large_items, large_centroid = large_centroids[best_idx]
                    large_items.extend(items)
                    # Update centroid
                    new_centroid = compute_centroid(large_items, embeddings, id_to_idx)
                    large_centroids[best_idx] = (large_sem, large_items, new_centroid)
                else:
                    unmerged_items.extend(items)

            # Add unmerged items to orphans
            orphans_by_macro[macro].extend(unmerged_items)
            print(f"    Added {len(unmerged_items)} unmerged items to orphans")

    print(f"\n  Merged clusters: {len(merged_clusters)}")

    # Phase 3: Split large clusters
    print("\n" + "=" * 60)
    print("PHASE 3: Split large clusters (>{} items)".format(MAX_CLUSTER_SIZE))
    print("=" * 60)

    split_clusters = []
    additional_orphans = defaultdict(list)
    used_labels = set()

    for macro, label, sem, items in merged_clusters:
        if len(items) > MAX_CLUSTER_SIZE:
            print(f"  Splitting '{label}' ({len(items)} items)")
            sub_clusters = cluster_items_kmeans(items, embeddings, id_to_idx, target_size=TARGET_CLUSTER_SIZE)

            for i, sub_items in enumerate(sub_clusters):
                if len(sub_items) >= MIN_CLUSTER_SIZE:
                    if len(sub_clusters) > 1:
                        sub_label = generate_sublabel(sub_items, label, list(used_labels))
                    else:
                        sub_label = label
                    used_labels.add(sub_label)
                    split_clusters.append((macro, sub_label, sem, sub_items))
                    print(f"    → {sub_label} ({len(sub_items)} items)")
                else:
                    additional_orphans[macro].extend(sub_items)
        else:
            used_labels.add(label)
            split_clusters.append((macro, label, sem, items))

    # Add additional orphans
    for macro, items in additional_orphans.items():
        orphans_by_macro[macro].extend(items)

    print(f"\n  Clusters after splitting: {len(split_clusters)}")
    print(f"  Total orphans: {sum(len(v) for v in orphans_by_macro.values())}")

    # Phase 4: Create new clusters from orphans
    print("\n" + "=" * 60)
    print("PHASE 4: Create clusters from orphans")
    print("=" * 60)

    orphan_clusters = []
    for macro, orphans in orphans_by_macro.items():
        if len(orphans) < MIN_CLUSTER_SIZE:
            print(f"  {macro}: {len(orphans)} orphans (too few to cluster)")
            continue

        print(f"  {macro}: Clustering {len(orphans)} orphans...")
        sub_clusters = cluster_items_kmeans(orphans, embeddings, id_to_idx, target_size=TARGET_CLUSTER_SIZE)

        for sub_items in sub_clusters:
            if len(sub_items) >= MIN_CLUSTER_SIZE:
                label = generate_label_from_items(sub_items)
                # Make label unique by adding suffix if needed
                existing_labels = [c[1] for c in split_clusters + orphan_clusters]
                if label in existing_labels:
                    count = sum(1 for l in existing_labels if l.startswith(label))
                    label = f"{label} #{count + 1}"
                orphan_clusters.append((macro, label, 'orphan-cluster', sub_items))
                print(f"    → {label} ({len(sub_items)} items)")

    print(f"\n  New clusters from orphans: {len(orphan_clusters)}")

    # Phase 5: Combine and build output
    print("\n" + "=" * 60)
    print("PHASE 5: Build output")
    print("=" * 60)

    all_clusters = split_clusters + orphan_clusters

    output_clusters = []
    for macro, label, sem, items in all_clusters:
        if len(items) < MIN_CLUSTER_SIZE:
            continue

        # Get original categories represented
        orig_cats = list(set(item.get('category', 'Unknown') for item in items))

        # Compute MMR-ordered carousel items
        carousel_items = compute_mmr_order(items, embeddings, id_to_idx, MAX_CLUSTER_SIZE)

        # Create unique ID
        cluster_id = f"cluster-{sem[:30]}" if sem != 'orphan-cluster' else f"cluster-{label.lower().replace(' ', '-')[:30]}"

        output_clusters.append({
            "id": cluster_id,
            "label": label,
            "semantic_cluster": sem,
            "macro_category": macro,
            "original_categories": orig_cats,
            "item_count": len(items),
            "items": [get_resource_id(item) for item in items],
            "carousel_items": carousel_items
        })

    # Sort by macro_category then by item_count
    output_clusters.sort(key=lambda x: (x['macro_category'], -x['item_count']))

    # Build output
    output = {
        "generated_at": datetime.now().isoformat(),
        "algorithm": "semantic_cluster_v3",
        "params": {
            "min_cluster_size": MIN_CLUSTER_SIZE,
            "max_cluster_size": MAX_CLUSTER_SIZE,
            "target_cluster_size": TARGET_CLUSTER_SIZE
        },
        "total_clusters": len(output_clusters),
        "total_items": sum(c['item_count'] for c in output_clusters),
        "clusters": output_clusters
    }

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    sizes = [c['item_count'] for c in output_clusters]
    print(f"  Total clusters: {len(output_clusters)}")
    print(f"  Total items: {sum(sizes)}")
    print(f"  Avg items/cluster: {sum(sizes) / len(sizes):.1f}" if sizes else "  No clusters")
    print(f"  Min/Max size: {min(sizes)}/{max(sizes)}" if sizes else "")
    print(f"  Clusters with 4-10 items: {sum(1 for s in sizes if MIN_CLUSTER_SIZE <= s <= MAX_CLUSTER_SIZE)}/{len(sizes)}")

    # Size distribution
    print("\n  Size distribution:")
    size_counts = Counter(sizes)
    for size in sorted(size_counts.keys()):
        bar = '█' * size_counts[size]
        print(f"    {size:2d} items: {bar} ({size_counts[size]})")

    # Show sample clusters by macro
    print("\n  Sample clusters by macro_category:")
    current_macro = None
    shown = 0
    for c in output_clusters:
        if c['macro_category'] != current_macro:
            current_macro = c['macro_category']
            print(f"\n    [{current_macro}]")
            shown = 0
        if shown < 3:
            cats = ', '.join(c['original_categories'][:2])
            print(f"      • {c['label']} ({c['item_count']}) - {cats}")
            shown += 1

    # Save
    print(f"\nSaving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
