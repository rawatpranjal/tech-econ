#!/usr/bin/env python3
"""
Cluster items by topic using HDBSCAN on semantic embeddings.

Supports per-section clustering for cleaner topic groupings.

Usage:
    python3 scripts/cluster_hdbscan.py                    # All sections
    python3 scripts/cluster_hdbscan.py --section packages # Single section

Output: data/topic_clusters_all.json
"""

import argparse
import json
import os
import time
import numpy as np
from collections import Counter
from datetime import datetime
from pathlib import Path

import hdbscan
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

# Optional OpenAI for LLM label refinement
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

_openai_client = None

# Section-specific HDBSCAN parameters
SECTION_PARAMS = {
    'package':   {'min_cluster_size': 3, 'min_samples': 2},
    'dataset':   {'min_cluster_size': 3, 'min_samples': 2},
    'resource':  {'min_cluster_size': 3, 'min_samples': 2},
    'paper':     {'min_cluster_size': 3, 'min_samples': 2},
    'talk':      {'min_cluster_size': 3, 'min_samples': 2},
    'career':    {'min_cluster_size': 3, 'min_samples': 2},
    'community': {'min_cluster_size': 3, 'min_samples': 2},
    'book':      {'min_cluster_size': 3, 'min_samples': 2},
    'roadmap':   {'min_cluster_size': 3, 'min_samples': 2},
}

# Target cluster size range
MAX_CLUSTER_SIZE = 20  # Recursively split clusters larger than this
MIN_CLUSTER_SIZE = 5   # Don't split clusters smaller than this

# All sections to process
ALL_SECTIONS = ['package', 'dataset', 'resource', 'paper', 'talk', 'career', 'community', 'book']


def get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None and OPENAI_AVAILABLE:
        _openai_client = OpenAI()
    return _openai_client


def load_embeddings(embeddings_file: Path, count: int, dim: int) -> np.ndarray:
    """Load binary Float32 embeddings."""
    with open(embeddings_file, 'rb') as f:
        data = np.frombuffer(f.read(), dtype=np.float32)
    return data.reshape(count, dim)


def load_metadata(metadata_file: Path) -> dict:
    """Load search metadata JSON."""
    with open(metadata_file) as f:
        return json.load(f)


def get_section_from_id(item_id: str) -> str:
    """Extract section from item ID (e.g., 'package-pandas' -> 'package')."""
    return item_id.split('-')[0]


def filter_by_section(items: list, indices: list, embeddings: np.ndarray, section: str):
    """Filter items and embeddings by section."""
    filtered_indices = []
    filtered_items = []

    for i, idx in enumerate(indices):
        item = items[idx]
        if get_section_from_id(item['id']) == section:
            filtered_indices.append(idx)
            filtered_items.append(item)

    if not filtered_indices:
        return [], [], np.array([])

    filtered_embeddings = embeddings[filtered_indices]
    return filtered_items, filtered_indices, filtered_embeddings


def get_item_text(item: dict) -> str:
    """Extract text from item for c-TF-IDF."""
    parts = []

    if item.get('name'):
        parts.append(item['name'])

    if item.get('embedding_text'):
        parts.append(item['embedding_text'])
    elif item.get('description'):
        parts.append(item['description'])

    topic_tags = item.get('topic_tags', '')
    if topic_tags:
        if isinstance(topic_tags, str):
            parts.append(topic_tags.replace(',', ' ').replace('-', ' '))
        else:
            parts.append(' '.join(t.replace('-', ' ') for t in topic_tags))

    canonical = item.get('canonical_topics', [])
    if canonical:
        parts.append(' '.join(canonical))

    return ' '.join(parts)


def generate_ctfidf_labels(cluster_items: dict, items: list, item_index_map: dict) -> dict:
    """Generate cluster labels using c-TF-IDF."""
    cluster_texts = {}
    for cid, item_ids in cluster_items.items():
        if cid == -1:
            continue
        texts = []
        for item_id in item_ids:
            idx = item_index_map.get(item_id)
            if idx is not None:
                texts.append(get_item_text(items[idx]))
        if texts:
            cluster_texts[cid] = ' '.join(texts)

    if not cluster_texts:
        return {}

    sorted_cids = sorted(cluster_texts.keys())
    corpus = [cluster_texts[cid] for cid in sorted_cids]

    vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words='english',
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.95,
        token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9_-]+\b'
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
    except ValueError:
        return {cid: f"Cluster {cid}" for cid in sorted_cids}

    labels = {}
    for i, cid in enumerate(sorted_cids):
        scores = tfidf_matrix[i].toarray().flatten()
        top_indices = scores.argsort()[-10:][::-1]
        top_terms = [feature_names[j] for j in top_indices]
        labels[cid] = format_ctfidf_label(top_terms)

    return labels


def format_ctfidf_label(terms: list) -> str:
    """Format top c-TF-IDF terms into readable label."""
    SKIP = {
        'python', 'data', 'using', 'learning', 'methods', 'analysis',
        'research', 'tools', 'based', 'new', 'use', 'models', 'model',
        'provides', 'library', 'package', 'datasets', 'code', 'open',
        'source', 'free', 'available', 'comprehensive', 'introduction',
        'guide', 'tutorial', 'course', 'book', 'paper', 'video',
        'career', 'job', 'jobs', 'company', 'companies', 'interview',
        'community', 'meetup', 'conference', 'event'
    }

    filtered = []
    seen_stems = set()

    for term in terms:
        term_lower = term.lower()
        if term_lower in SKIP:
            continue
        stem = term_lower[:5] if len(term_lower) > 5 else term_lower
        if stem in seen_stems:
            continue
        if len(term) < 2:
            continue
        seen_stems.add(stem)
        filtered.append(term)
        if len(filtered) >= 2:
            break

    if len(filtered) >= 2:
        return f"{filtered[0].title()} & {filtered[1].title()}"
    elif filtered:
        return filtered[0].title()
    else:
        return "Miscellaneous"


def compute_cluster_centroids(embeddings: np.ndarray, cluster_labels: np.ndarray) -> dict:
    """Compute centroid for each cluster."""
    centroids = {}
    unique_labels = set(cluster_labels)

    for label in unique_labels:
        if label == -1:
            continue
        mask = cluster_labels == label
        cluster_embs = embeddings[mask]
        centroid = cluster_embs.mean(axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        centroids[label] = centroid

    return centroids


def assign_noise_to_nearest(noise_indices: list, embeddings: np.ndarray,
                           centroids: dict, threshold: float = 0.65) -> dict:
    """Assign noise items to nearest cluster if similarity > threshold."""
    assignments = {}
    for idx in noise_indices:
        item_emb = embeddings[idx]
        best_cluster = -1
        best_sim = threshold
        for cid, centroid in centroids.items():
            sim = np.dot(item_emb, centroid)
            if sim > best_sim:
                best_sim = sim
                best_cluster = cid
        assignments[idx] = best_cluster
    return assignments


def split_large_cluster(cluster_local_indices: list, section_embeddings: np.ndarray,
                        section_items: list, parent_label: str, max_size: int = 20) -> list:
    """
    Recursively split a large cluster into smaller sub-clusters.
    Returns list of (local_indices, label) tuples.
    """
    if len(cluster_local_indices) <= max_size:
        return [(cluster_local_indices, parent_label)]

    # Get embeddings for this cluster
    cluster_embeddings = section_embeddings[cluster_local_indices]

    # Try to split with HDBSCAN
    sub_clusterer = hdbscan.HDBSCAN(
        min_cluster_size=3,
        min_samples=2,
        metric='euclidean',
        cluster_selection_method='leaf',
    )
    sub_labels = sub_clusterer.fit_predict(cluster_embeddings)

    # Check if we got meaningful splits
    unique_labels = set(sub_labels) - {-1}
    if len(unique_labels) <= 1:
        # HDBSCAN couldn't split - use K-means as fallback
        from sklearn.cluster import KMeans
        n_clusters = max(2, len(cluster_local_indices) // 10)  # ~10 items per cluster
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        sub_labels = kmeans.fit_predict(cluster_embeddings)
        unique_labels = set(sub_labels)

    # Build sub-clusters
    sub_clusters = {}
    for i, sub_label in enumerate(sub_labels):
        if sub_label not in sub_clusters:
            sub_clusters[sub_label] = []
        sub_clusters[sub_label].append(cluster_local_indices[i])

    # Generate sub-labels and recurse if needed
    results = []
    for sub_id, sub_indices in sub_clusters.items():
        # Generate sub-label from items
        sub_items = [section_items[i] for i in sub_indices]
        sub_label_suffix = generate_sublabel(sub_items)
        full_label = f"{parent_label}: {sub_label_suffix}" if sub_label_suffix else parent_label

        # Recurse if still too large
        if len(sub_indices) > max_size:
            results.extend(split_large_cluster(
                sub_indices, section_embeddings, section_items, full_label, max_size
            ))
        else:
            results.append((sub_indices, full_label))

    return results


def generate_sublabel(items: list) -> str:
    """Generate a label suffix for a sub-cluster based on its items."""
    # Collect all tags
    all_tags = []
    for item in items:
        tags = item.get('topic_tags', '')
        if tags:
            if isinstance(tags, str):
                all_tags.extend([t.strip() for t in tags.split(',')])
            else:
                all_tags.extend(tags)

    if not all_tags:
        # Try names
        names = [item.get('name', '') for item in items[:3]]
        # Find common words
        words = []
        for name in names:
            words.extend(name.lower().split())
        if words:
            word_counts = Counter(words)
            common = [w for w, c in word_counts.most_common(3) if len(w) > 3 and c > 1]
            if common:
                return common[0].title()
        return ""

    # Find most distinctive tag
    tag_counts = Counter(all_tags)
    SKIP = {'causal-inference', 'machine-learning', 'statistics', 'data-science',
            'economics', 'python', 'r', 'networking', 'community'}

    for tag, count in tag_counts.most_common(5):
        if tag.lower() not in SKIP:
            return tag.replace('-', ' ').title()

    # Fall back to most common
    if tag_counts:
        return tag_counts.most_common(1)[0][0].replace('-', ' ').title()

    return ""


def dedupe_labels(clusters: list) -> None:
    """Deduplicate cluster labels by adding differentiators."""
    from collections import defaultdict

    used_labels = set()
    label_clusters = defaultdict(list)

    for c in clusters:
        label_clusters[c['label']].append(c)

    for label, dupes in label_clusters.items():
        if len(dupes) <= 1:
            used_labels.add(label)
            continue

        for i, c in enumerate(dupes):
            cats = c.get('top_categories', [])
            extra_tags = c.get('top_tags', [])[2:5]
            new_label = None

            for cat in cats:
                if cat and '>' in cat:
                    cat = cat.split('>')[-1].strip()
                if cat and cat.lower() not in label.lower() and len(cat) < 30:
                    candidate = f"{label}: {cat}"
                    if candidate not in used_labels:
                        new_label = candidate
                        break

            if not new_label:
                for tag in extra_tags:
                    tag_clean = tag.replace('-', ' ').title()
                    if tag_clean.lower() not in label.lower():
                        candidate = f"{label}: {tag_clean}"
                        if candidate not in used_labels:
                            new_label = candidate
                            break

            if not new_label:
                num = 2
                while f"{label} #{num}" in used_labels:
                    num += 1
                if i == 0:
                    new_label = label
                    if new_label in used_labels:
                        new_label = f"{label} #{num}"
                else:
                    new_label = f"{label} #{num}"

            c['label'] = new_label
            used_labels.add(new_label)


def cluster_section(section: str, items: list, all_indices: list,
                    embeddings_norm: np.ndarray, all_items: list) -> dict:
    """Cluster a single section and return section data."""
    print(f"\n{'='*60}")
    print(f"SECTION: {section.upper()}")
    print('='*60)

    # Filter to this section
    section_items, section_indices, section_embeddings = filter_by_section(
        all_items, all_indices, embeddings_norm, section
    )

    if len(section_items) < 3:
        print(f"  Skipping: only {len(section_items)} items")
        return None

    print(f"  Items: {len(section_items)}")

    # Get section-specific params
    params = SECTION_PARAMS.get(section, {'min_cluster_size': 3, 'min_samples': 2})
    print(f"  Params: {params}")

    # Run HDBSCAN
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=params['min_cluster_size'],
        min_samples=params['min_samples'],
        metric='euclidean',
        cluster_selection_method='leaf',
        core_dist_n_jobs=-1,
    )

    cluster_labels = clusterer.fit_predict(section_embeddings)

    # Statistics
    unique_labels = set(cluster_labels)
    n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
    n_noise = (cluster_labels == -1).sum()

    print(f"  Clusters: {n_clusters}")
    print(f"  Noise: {n_noise} ({100*n_noise/len(section_items):.1f}%)")

    # Silhouette score
    mask = cluster_labels != -1
    if mask.sum() > 1 and n_clusters > 1:
        sil_score = silhouette_score(
            section_embeddings[mask],
            cluster_labels[mask],
            sample_size=min(2000, mask.sum())
        )
        print(f"  Silhouette: {sil_score:.4f}")

    # Build cluster -> local indices mapping
    local_cluster_items = {}
    for local_idx, label in enumerate(cluster_labels):
        if label not in local_cluster_items:
            local_cluster_items[label] = []
        local_cluster_items[label].append(local_idx)

    # Assign noise to nearest clusters
    centroids = compute_cluster_centroids(section_embeddings, cluster_labels)
    noise_local_indices = local_cluster_items.get(-1, [])

    if noise_local_indices and centroids:
        noise_assignments = assign_noise_to_nearest(
            noise_local_indices, section_embeddings, centroids, threshold=0.60
        )

        reassigned = 0
        for local_idx, new_cluster in noise_assignments.items():
            if new_cluster != -1:
                local_cluster_items[new_cluster].append(local_idx)
                cluster_labels[local_idx] = new_cluster
                reassigned += 1

        if reassigned:
            print(f"  Reassigned noise: {reassigned}")

        # Update noise list
        if -1 in local_cluster_items:
            local_cluster_items[-1] = [idx for idx in local_cluster_items[-1]
                                        if noise_assignments.get(idx, -1) == -1]
            if not local_cluster_items[-1]:
                del local_cluster_items[-1]

    # Build cluster_items with item IDs (not local indices)
    cluster_items_by_id = {}
    for cid, local_indices in local_cluster_items.items():
        cluster_items_by_id[cid] = [section_items[i]['id'] for i in local_indices]

    # Create item index map for c-TF-IDF
    item_index_map = {item['id']: i for i, item in enumerate(section_items)}

    # Generate initial labels
    ctfidf_labels = generate_ctfidf_labels(cluster_items_by_id, section_items, item_index_map)

    # Split large clusters recursively
    print(f"  Splitting large clusters (max {MAX_CLUSTER_SIZE} items)...")
    split_cluster_data = []  # List of (local_indices, label) tuples

    for cluster_id in sorted(local_cluster_items.keys()):
        if cluster_id == -1:
            continue

        local_indices = local_cluster_items[cluster_id]
        initial_label = ctfidf_labels.get(cluster_id, f"Cluster {cluster_id}")

        if len(local_indices) > MAX_CLUSTER_SIZE:
            # Split this cluster
            sub_clusters = split_large_cluster(
                local_indices, section_embeddings, section_items,
                initial_label, MAX_CLUSTER_SIZE
            )
            split_cluster_data.extend(sub_clusters)
        else:
            split_cluster_data.append((local_indices, initial_label))

    # Handle noise items
    if -1 in local_cluster_items and local_cluster_items[-1]:
        split_cluster_data.append((local_cluster_items[-1], "Other"))

    print(f"  After splitting: {len(split_cluster_data)} clusters")

    # Build cluster profiles from split data
    clusters = []
    item_to_cluster = {}

    for cluster_id, (local_indices, label) in enumerate(split_cluster_data):
        is_noise = (label == "Other")

        # Collect metadata
        all_tags = []
        all_categories = []

        for local_idx in local_indices:
            item = section_items[local_idx]
            tags = item.get('topic_tags', '')
            if tags:
                if isinstance(tags, str):
                    all_tags.extend([t.strip() for t in tags.split(',')])
                else:
                    all_tags.extend(tags)
            cat = item.get('category', '')
            if cat:
                all_categories.append(cat)

        tag_counts = Counter(all_tags)
        cat_counts = Counter(all_categories)

        top_tags = [tag for tag, _ in tag_counts.most_common(5)]
        top_categories = [cat for cat, _ in cat_counts.most_common(3)]

        item_ids = [section_items[i]['id'] for i in local_indices]

        for item_id in item_ids:
            item_to_cluster[item_id] = cluster_id

        cluster_entry = {
            "id": cluster_id,
            "label": label,
            "top_tags": top_tags,
            "top_categories": top_categories,
            "item_count": len(local_indices),
            "sample_items": item_ids[:10]
        }
        if is_noise:
            cluster_entry["is_noise"] = True
        clusters.append(cluster_entry)

    # Sort by size
    clusters.sort(key=lambda x: -x['item_count'])

    # Reassign IDs
    id_map = {c['id']: i for i, c in enumerate(clusters)}
    for c in clusters:
        c['id'] = id_map[c['id']]
    for item_id in item_to_cluster:
        old_cluster = item_to_cluster[item_id]
        item_to_cluster[item_id] = id_map.get(old_cluster, old_cluster)

    # Dedupe labels
    dedupe_labels(clusters)

    # Print top clusters
    print(f"\n  Top clusters:")
    for c in clusters[:5]:
        noise_marker = " [noise]" if c.get('is_noise') else ""
        print(f"    [{c['id']}] {c['label']} ({c['item_count']}){noise_marker}")

    return {
        "num_clusters": len([c for c in clusters if not c.get('is_noise')]),
        "num_items": len(section_items),
        "clusters": clusters,
        "item_to_cluster": item_to_cluster
    }


def main():
    parser = argparse.ArgumentParser(description='Cluster items by section using HDBSCAN')
    parser.add_argument('--section', type=str, default='all',
                       help='Section to cluster (or "all" for all sections)')
    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent
    embeddings_dir = project_root / "static" / "embeddings"
    output_file = project_root / "data" / "topic_clusters_all.json"

    # Load data
    print("Loading metadata...")
    metadata = load_metadata(embeddings_dir / "search-metadata.json")
    count = metadata['count']
    dim = metadata['dimensions']
    items = metadata['items']
    print(f"  {count} items, {dim} dimensions")

    print("Loading embeddings...")
    embeddings = load_embeddings(embeddings_dir / "search-embeddings.bin", count, dim)

    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings_norm = embeddings / norms

    # LLM status
    if OPENAI_AVAILABLE:
        print("LLM: ENABLED")
    else:
        print("LLM: DISABLED")

    # Determine sections to process
    if args.section == 'all':
        sections = ALL_SECTIONS
    else:
        sections = [args.section]

    # All indices
    all_indices = list(range(len(items)))

    # Cluster each section
    results = {}
    for section in sections:
        section_data = cluster_section(section, items, all_indices, embeddings_norm, items)
        if section_data:
            results[section] = section_data

    # Build output
    output = {
        "generated_at": datetime.now().isoformat(),
        "algorithm": "hdbscan",
        "algorithm_params": SECTION_PARAMS,
        "sections": results
    }

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    total_clusters = 0
    total_items = 0
    for section, data in results.items():
        total_clusters += data['num_clusters']
        total_items += data['num_items']
        print(f"  {section:12} {data['num_clusters']:3} clusters, {data['num_items']:4} items")
    print(f"  {'TOTAL':12} {total_clusters:3} clusters, {total_items:4} items")

    # Save
    print(f"\nWriting to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
