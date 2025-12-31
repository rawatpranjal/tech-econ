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


# ============================================================================
# MMR-BASED DIVERSITY SELECTION
# ============================================================================

# Media type priority for hero selection (higher = preferred)
HERO_TYPE_PRIORITY = {
    'talk': 100,      # Highest - engaging video content
    'resource': 80,   # Tutorials, guides
    'book': 70,       # In-depth content
    'paper': 60,      # Academic reference
    'package': 50,    # Tools
    'dataset': 40,    # Data resources
    'community': 30,  # Community links
    'career': 20,     # Career portals (lowest)
    'roadmap': 10,    # Learning paths
    'domain': 5,      # Domain pages
}

# Difficulty level scores
DIFFICULTY_SCORES = {
    'beginner': 0.2,
    'intermediate': 0.5,
    'advanced': 0.8
}


def load_papers_citations():
    """Load citations data from papers_flat.json."""
    papers_file = PROJECT_ROOT / "data" / "papers_flat.json"
    if not papers_file.exists():
        return {}

    with open(papers_file) as f:
        papers = json.load(f)

    # Build id -> citations mapping
    citations = {}
    for paper in papers:
        paper_id = f"paper-{paper.get('slug', '')}"
        if not paper_id or paper_id == 'paper-':
            # Try building from name
            name = paper.get('name', paper.get('title', ''))
            if name:
                slug = name.lower().replace(' ', '-').replace(':', '').replace(',', '')[:50]
                paper_id = f"paper-{slug}"
        citations[paper_id] = paper.get('citations', 0)

    return citations


def compute_relevance_scores(cluster_item_ids, all_items, id_to_idx, embeddings,
                              cluster_centroid, citations_data):
    """
    Compute composite relevance score for each item in a cluster.

    Components (normalized to 0-1 range):
    1. Citations (papers only): log-normalized citations (30%)
    2. Difficulty: beginner=0.2, intermediate=0.5, advanced=0.8 (20%)
    3. Centrality: cosine similarity to cluster centroid (50%)

    Returns:
        Dict mapping item_id -> relevance score (0-1)
    """
    scores = {}

    # Find max citations for normalization (across all papers in cluster)
    max_log_citations = 1.0
    for item_id in cluster_item_ids:
        if item_id in citations_data:
            cit = citations_data.get(item_id) or 0
            if cit and cit > 0:
                max_log_citations = max(max_log_citations, np.log1p(cit))

    for item_id in cluster_item_ids:
        if item_id not in id_to_idx:
            scores[item_id] = 0.0
            continue

        idx = id_to_idx[item_id]
        item = all_items[idx]
        item_type = item.get('type', 'resource')

        # Component 1: Citations (papers only, 0-1)
        citation_score = 0.5  # Default for non-papers
        if item_type == 'paper' and item_id in citations_data:
            citations = citations_data.get(item_id) or 0
            if max_log_citations > 0 and citations and citations > 0:
                citation_score = np.log1p(citations) / max_log_citations

        # Component 2: Difficulty (0.2-0.8)
        difficulty = item.get('difficulty', 'intermediate')
        difficulty_score = DIFFICULTY_SCORES.get(difficulty, 0.5)

        # Component 3: Centrality (0-1)
        item_embedding = embeddings[idx]
        centrality = cosine_similarity(item_embedding, cluster_centroid)
        # Normalize from [-1,1] to [0,1]
        centrality_score = (centrality + 1) / 2

        # Weighted combination: 30% citations, 20% difficulty, 50% centrality
        final_score = (
            0.3 * citation_score +
            0.2 * difficulty_score +
            0.5 * centrality_score
        )

        scores[item_id] = final_score

    return scores


def select_hero(cluster_item_ids, all_items, id_to_idx, relevance_scores):
    """
    Select the hero item for a cluster based on type priority and relevance.

    Returns:
        Item ID of the hero, or None if cluster is empty
    """
    if not cluster_item_ids:
        return None

    best_hero = None
    best_score = float('-inf')

    for item_id in cluster_item_ids:
        if item_id not in id_to_idx:
            continue

        item = all_items[id_to_idx[item_id]]
        item_type = item.get('type', 'resource')

        # Combined score: type priority + relevance boost
        type_priority = HERO_TYPE_PRIORITY.get(item_type, 30)
        relevance = relevance_scores.get(item_id, 0.0)

        # Hero score: primarily type-driven, relevance as tiebreaker
        hero_score = type_priority + (relevance * 10)

        if hero_score > best_score:
            best_score = hero_score
            best_hero = item_id

    return best_hero


def ensure_type_coverage(cluster_item_ids, all_items, id_to_idx, relevance_scores):
    """
    Select one best item per content type to ensure diversity.

    Returns:
        List of item IDs (one per type present in cluster)
    """
    type_best = {}  # type -> (item_id, relevance_score)

    for item_id in cluster_item_ids:
        if item_id not in id_to_idx:
            continue

        item = all_items[id_to_idx[item_id]]
        item_type = item.get('type', 'resource')
        relevance = relevance_scores.get(item_id, 0.0)

        if item_type not in type_best or relevance > type_best[item_type][1]:
            type_best[item_type] = (item_id, relevance)

    # Return in priority order
    type_order = ['talk', 'resource', 'book', 'paper', 'package', 'dataset', 'community', 'career']
    coverage = []
    for t in type_order:
        if t in type_best:
            coverage.append(type_best[t][0])

    return coverage


def mmr_select(candidate_ids, embeddings, id_to_idx, relevance_scores,
               num_select, lambda_param=0.5):
    """
    Select items using Maximal Marginal Relevance.

    MMR = lambda * Relevance(item) - (1 - lambda) * max(Similarity(item, selected))

    Args:
        candidate_ids: List of item IDs to select from
        embeddings: Numpy array of all embeddings (n_items x dim)
        id_to_idx: Mapping from item_id to embedding index
        relevance_scores: Pre-computed relevance score for each item
        num_select: Number of items to select
        lambda_param: Balance between relevance (1.0) and diversity (0.0)

    Returns:
        List of selected item IDs in MMR order
    """
    if len(candidate_ids) <= num_select:
        return list(candidate_ids)

    selected = []
    remaining = set(candidate_ids)

    # Get embeddings for candidates
    candidate_embeddings = {}
    for item_id in candidate_ids:
        if item_id in id_to_idx:
            candidate_embeddings[item_id] = embeddings[id_to_idx[item_id]]

    while len(selected) < num_select and remaining:
        best_item = None
        best_mmr_score = float('-inf')

        for item_id in remaining:
            if item_id not in candidate_embeddings:
                continue

            # Relevance component
            rel_score = relevance_scores.get(item_id, 0.0)

            # Diversity component: max similarity to already selected items
            max_sim = 0.0
            if selected:
                item_emb = candidate_embeddings[item_id]
                for sel_id in selected:
                    if sel_id in candidate_embeddings:
                        sim = cosine_similarity(item_emb, candidate_embeddings[sel_id])
                        max_sim = max(max_sim, sim)

            # MMR score
            mmr_score = lambda_param * rel_score - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_item = item_id

        if best_item:
            selected.append(best_item)
            remaining.remove(best_item)
        else:
            break

    return selected


def select_diverse_items(cluster_id, cluster_item_ids, embeddings, all_items,
                         id_to_idx, citations_data, max_items=15):
    """
    Full diversity selection pipeline for a cluster.

    Two-phase approach:
    1. Type coverage: Ensure one of each content type
    2. MMR fill: Fill remaining slots with MMR-selected items

    Returns:
        Dict with 'hero', 'type_coverage', 'ordered_items' keys
    """
    if not cluster_item_ids:
        return {'hero': None, 'type_coverage': [], 'ordered_items': []}

    # Compute cluster centroid
    cluster_embeddings = []
    for item_id in cluster_item_ids:
        if item_id in id_to_idx:
            cluster_embeddings.append(embeddings[id_to_idx[item_id]])

    if not cluster_embeddings:
        return {'hero': None, 'type_coverage': [], 'ordered_items': list(cluster_item_ids)[:max_items]}

    centroid = np.mean(cluster_embeddings, axis=0)

    # Compute relevance scores
    relevance_scores = compute_relevance_scores(
        cluster_item_ids, all_items, id_to_idx, embeddings, centroid, citations_data
    )

    # Phase 1: Select hero
    hero = select_hero(cluster_item_ids, all_items, id_to_idx, relevance_scores)

    # Phase 2: Type coverage
    type_coverage = ensure_type_coverage(
        cluster_item_ids, all_items, id_to_idx, relevance_scores
    )

    # Phase 3: MMR for remaining slots
    already_selected = set(type_coverage)
    remaining_candidates = [id for id in cluster_item_ids if id not in already_selected]

    slots_remaining = max_items - len(type_coverage)
    if slots_remaining > 0 and remaining_candidates:
        mmr_selected = mmr_select(
            remaining_candidates,
            embeddings,
            id_to_idx,
            relevance_scores,
            num_select=slots_remaining,
            lambda_param=0.5
        )
    else:
        mmr_selected = []

    # Final ordered list: type_coverage first, then MMR items
    ordered_items = type_coverage + mmr_selected

    # Move hero to front if not already there
    if hero and hero in ordered_items:
        ordered_items.remove(hero)
        ordered_items.insert(0, hero)
    elif hero:
        ordered_items.insert(0, hero)
        ordered_items = ordered_items[:max_items]

    # Get types represented
    types_in_carousel = set()
    for item_id in ordered_items:
        if item_id in id_to_idx:
            types_in_carousel.add(all_items[id_to_idx[item_id]].get('type', 'resource'))

    return {
        'hero': hero,
        'type_coverage': list(types_in_carousel),
        'ordered_items': ordered_items
    }


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

    print("\nLoading citations data...")
    citations_data = load_papers_citations()
    print(f"  Loaded citations for {len(citations_data)} papers")

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

    # Step 6: Compute MMR diverse selections
    print("\n" + "="*60)
    print("STEP 6: Computing MMR diverse selections")
    print("="*60)

    mmr_stats = {'talk': 0, 'resource': 0, 'paper': 0, 'package': 0, 'other': 0}

    for cluster in final_clusters:
        cluster_id = cluster['id']
        cluster_item_ids = [item_id for item_id, cid in item_to_cluster.items()
                           if cid == cluster_id]

        selection = select_diverse_items(
            cluster_id=cluster_id,
            cluster_item_ids=cluster_item_ids,
            embeddings=embeddings,
            all_items=all_items,
            id_to_idx=id_to_idx,
            citations_data=citations_data,
            max_items=15
        )

        cluster['hero_item'] = selection['hero']
        cluster['carousel_items'] = selection['ordered_items']
        cluster['type_coverage'] = selection['type_coverage']

        # Track hero type stats
        if selection['hero'] and selection['hero'] in id_to_idx:
            hero_type = all_items[id_to_idx[selection['hero']]].get('type', 'other')
            if hero_type in mmr_stats:
                mmr_stats[hero_type] += 1
            else:
                mmr_stats['other'] += 1

    print(f"  Processed {len(final_clusters)} clusters")
    print(f"  Hero types: talk={mmr_stats['talk']}, resource={mmr_stats['resource']}, "
          f"paper={mmr_stats['paper']}, package={mmr_stats['package']}, other={mmr_stats['other']}")

    # Save
    output = {
        "generated_at": data.get('generated_at', ''),
        "postprocessed_at": str(np.datetime64('now')),
        "mmr_generated_at": str(np.datetime64('now')),
        "num_clusters": len(final_clusters),
        "num_items": len(item_to_cluster),
        "mmr_config": {
            "lambda": 0.5,
            "max_items_per_cluster": 15,
            "relevance_weights": {
                "citations": 0.3,
                "difficulty": 0.2,
                "centrality": 0.5
            }
        },
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
