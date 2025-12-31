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


# Hero scoring weights (Netflix-style multi-signal)
HERO_WEIGHTS = {
    'media_richness': 0.20,   # video=1.0, audio=0.75, text=0.4
    'authority': 0.25,        # citations, speaker fame
    'engagement_proxy': 0.30, # stars, views (or type average)
    'recency': 0.25           # exponential decay
}

# Media richness scores by content type
MEDIA_RICHNESS = {
    'talk': 1.0,      # Video content
    'resource': 0.5,  # Mixed (some video tutorials)
    'book': 0.4,      # Text
    'paper': 0.4,     # Text
    'package': 0.3,   # Code
    'dataset': 0.3,   # Data
    'community': 0.2, # Links
    'career': 0.1,    # Job postings
}

# Default engagement scores by type (when no explicit data)
TYPE_ENGAGEMENT_DEFAULTS = {
    'talk': 0.8,
    'resource': 0.6,
    'paper': 0.5,
    'book': 0.5,
    'package': 0.4,
    'dataset': 0.3,
    'community': 0.2,
    'career': 0.1,
}


def compute_hero_score(item, item_id, citations_data, relevance_scores):
    """
    Compute multi-signal hero score for an item.

    Components:
    1. Media richness (0.20): video > audio > text
    2. Authority (0.25): citations, type-based
    3. Engagement proxy (0.30): stars, or type default
    4. Recency (0.25): exponential decay from 2024

    Returns:
        Float score in [0, 1]
    """
    item_type = item.get('type', 'resource')

    # Component 1: Media richness
    media_score = MEDIA_RICHNESS.get(item_type, 0.4)

    # Component 2: Authority (citations + type boost)
    authority_score = 0.3  # Default
    if item_type == 'paper' and item_id in citations_data:
        citations = citations_data.get(item_id) or 0
        # Log-scale: 1000 citations = 1.0
        if citations > 0:
            authority_score = min(1.0, np.log1p(citations) / np.log1p(1000))
    elif item_type == 'talk':
        # Talks from known speakers get boost
        authority_score = 0.6
    elif item_type == 'book':
        authority_score = 0.5

    # Component 3: Engagement proxy
    # Use stars if available, otherwise type default
    stars = item.get('stars', item.get('github_stars', 0)) or 0
    if stars > 0:
        # Log-scale: 10k stars = 1.0
        engagement_score = min(1.0, np.log1p(stars) / np.log1p(10000))
    else:
        engagement_score = TYPE_ENGAGEMENT_DEFAULTS.get(item_type, 0.3)

    # Component 4: Recency
    # Parse year from date field or default
    year = 2020  # Default
    if 'date' in item and item['date']:
        try:
            year = int(str(item['date'])[:4])
        except:
            pass
    elif 'year' in item and item['year']:
        try:
            year = int(item['year'])
        except:
            pass

    # Exponential decay: items from 2024 get 1.0, 2020 gets ~0.5
    years_old = max(0, 2024 - year)
    recency_score = np.exp(-0.15 * years_old)

    # Weighted combination
    hero_score = (
        HERO_WEIGHTS['media_richness'] * media_score +
        HERO_WEIGHTS['authority'] * authority_score +
        HERO_WEIGHTS['engagement_proxy'] * engagement_score +
        HERO_WEIGHTS['recency'] * recency_score
    )

    return hero_score


def select_hero(cluster_item_ids, all_items, id_to_idx, relevance_scores, citations_data=None):
    """
    Select the hero item for a cluster using multi-signal scoring.

    Signals:
    1. Media richness: video > audio > text
    2. Authority: citations, speaker fame
    3. Engagement proxy: stars, views, or type average
    4. Recency: exponential decay

    Returns:
        Item ID of the hero, or None if cluster is empty
    """
    if not cluster_item_ids:
        return None

    if citations_data is None:
        citations_data = {}

    best_hero = None
    best_score = float('-inf')

    for item_id in cluster_item_ids:
        if item_id not in id_to_idx:
            continue

        item = all_items[id_to_idx[item_id]]
        hero_score = compute_hero_score(item, item_id, citations_data, relevance_scores)

        if hero_score > best_score:
            best_score = hero_score
            best_hero = item_id

    return best_hero


# Minimum items per type for constrained selection
MIN_PER_TYPE = {
    'paper': 2,      # Want variety in academic content
    'talk': 1,       # Engaging video content
    'resource': 1,   # Tutorials/guides
    'package': 1,    # Tools
    'book': 1,       # In-depth content
    'dataset': 0,    # Optional
    'community': 0,  # Optional
    'career': 0,     # Deprioritized
}


def ensure_type_coverage(cluster_item_ids, all_items, id_to_idx, relevance_scores,
                         min_per_type=None, embeddings=None):
    """
    Select items with minimum constraints per content type.

    Phase 1: Satisfy minimum constraints per type (use MMR within each type)
    Phase 2: Remaining slots filled by MMR across all types (in select_diverse_items)

    Returns:
        List of item IDs satisfying type minimums
    """
    if min_per_type is None:
        min_per_type = MIN_PER_TYPE

    # Group items by type
    items_by_type = {}
    for item_id in cluster_item_ids:
        if item_id not in id_to_idx:
            continue
        item = all_items[id_to_idx[item_id]]
        item_type = item.get('type', 'resource')
        if item_type not in items_by_type:
            items_by_type[item_type] = []
        items_by_type[item_type].append(item_id)

    coverage = []
    type_order = ['talk', 'resource', 'book', 'paper', 'package', 'dataset', 'community', 'career']

    for item_type in type_order:
        min_count = min_per_type.get(item_type, 0)
        type_items = items_by_type.get(item_type, [])

        if not type_items or min_count == 0:
            continue

        # Select up to min_count items from this type
        # Use relevance score ordering for diversity within type
        type_items_with_scores = [
            (item_id, relevance_scores.get(item_id, 0.0))
            for item_id in type_items
        ]
        type_items_with_scores.sort(key=lambda x: -x[1])  # Highest relevance first

        # Take top items for this type, respecting minimum
        for item_id, _ in type_items_with_scores[:min_count]:
            if item_id not in coverage:
                coverage.append(item_id)

    return coverage


def mmr_select(candidate_ids, embeddings, id_to_idx, relevance_scores,
               num_select, lambda_param=0.6):
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


def calculate_ild(item_ids, embeddings, id_to_idx):
    """
    Calculate Intra-List Diversity (ILD) score for a list of items.

    ILD = average pairwise distance between items in the list.
    Higher values (0.3-0.7) indicate more diverse selections.

    Args:
        item_ids: List of item IDs in the carousel
        embeddings: Numpy array of all embeddings
        id_to_idx: Mapping from item_id to embedding index

    Returns:
        Float ILD score in [0, 1], or 0.0 if insufficient items
    """
    # Get embeddings for items in the list
    item_embeddings = []
    for item_id in item_ids:
        if item_id in id_to_idx:
            item_embeddings.append(embeddings[id_to_idx[item_id]])

    n = len(item_embeddings)
    if n < 2:
        return 0.0

    # Calculate average pairwise cosine distance
    distances = []
    for i in range(n):
        for j in range(i + 1, n):
            # Cosine distance = 1 - cosine_similarity
            sim = np.dot(item_embeddings[i], item_embeddings[j])
            sim /= (np.linalg.norm(item_embeddings[i]) * np.linalg.norm(item_embeddings[j]))
            dist = 1 - sim
            distances.append(dist)

    return float(np.mean(distances))


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
        return {'hero': None, 'type_coverage': [], 'ordered_items': [], 'ild_score': 0.0}

    # Compute cluster centroid
    cluster_embeddings = []
    for item_id in cluster_item_ids:
        if item_id in id_to_idx:
            cluster_embeddings.append(embeddings[id_to_idx[item_id]])

    if not cluster_embeddings:
        return {'hero': None, 'type_coverage': [], 'ordered_items': list(cluster_item_ids)[:max_items], 'ild_score': 0.0}

    centroid = np.mean(cluster_embeddings, axis=0)

    # Compute relevance scores
    relevance_scores = compute_relevance_scores(
        cluster_item_ids, all_items, id_to_idx, embeddings, centroid, citations_data
    )

    # Phase 1: Select hero
    hero = select_hero(cluster_item_ids, all_items, id_to_idx, relevance_scores, citations_data)

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
            lambda_param=0.6
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

    # Calculate ILD (Intra-List Diversity)
    ild_score = calculate_ild(ordered_items, embeddings, id_to_idx)

    return {
        'hero': hero,
        'type_coverage': list(types_in_carousel),
        'ordered_items': ordered_items,
        'ild_score': round(ild_score, 3)
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
        cluster['ild_score'] = selection['ild_score']

        # Track hero type stats
        if selection['hero'] and selection['hero'] in id_to_idx:
            hero_type = all_items[id_to_idx[selection['hero']]].get('type', 'other')
            if hero_type in mmr_stats:
                mmr_stats[hero_type] += 1
            else:
                mmr_stats['other'] += 1

    # Calculate ILD statistics
    ild_scores = [c.get('ild_score', 0) for c in final_clusters if c.get('ild_score')]
    avg_ild = np.mean(ild_scores) if ild_scores else 0
    min_ild = min(ild_scores) if ild_scores else 0
    max_ild = max(ild_scores) if ild_scores else 0
    good_ild = sum(1 for s in ild_scores if 0.3 <= s <= 0.7)

    print(f"  Processed {len(final_clusters)} clusters")
    print(f"  Hero types: talk={mmr_stats['talk']}, resource={mmr_stats['resource']}, "
          f"paper={mmr_stats['paper']}, package={mmr_stats['package']}, other={mmr_stats['other']}")
    print(f"  ILD scores: avg={avg_ild:.3f}, min={min_ild:.3f}, max={max_ild:.3f}")
    print(f"  Clusters with optimal ILD (0.3-0.7): {good_ild}/{len(ild_scores)}")

    # Step 7: Quality filtering and reordering
    print("\n" + "="*60)
    print("STEP 7: Quality filtering and reordering")
    print("="*60)

    # Filter out empty clusters
    non_empty = [c for c in final_clusters if c['item_count'] > 0]
    print(f"  Removed {len(final_clusters) - len(non_empty)} empty clusters")

    # Detect all-career clusters and mark/relabel them
    technical_terms = ['causal', 'inference', 'ml', 'algorithm', 'model', 'bayesian',
                       'regression', 'neural', 'optimization', 'statistical']
    relabeled_count = 0
    all_career_count = 0
    for c in non_empty:
        types = c.get('type_coverage', [])
        is_all_career = types == ['career']
        label_lower = c['label'].lower()

        if is_all_career:
            all_career_count += 1
            c['_is_career_cluster'] = True
            # Relabel mislabeled technical ones
            is_technical = any(t in label_lower for t in technical_terms)
            if is_technical:
                old_label = c['label']
                c['label'] = 'Finance & Investment Careers'
                print(f"    Relabeled: '{old_label}' -> 'Finance & Investment Careers'")
                relabeled_count += 1
        else:
            c['_is_career_cluster'] = 'career' in label_lower

    if relabeled_count:
        print(f"  Relabeled {relabeled_count} mislabeled clusters")
    print(f"  Found {all_career_count} all-career clusters")

    # Deprioritize homogeneous clusters (single content type)
    homogeneous_count = 0
    for c in non_empty:
        types = c.get('type_coverage', [])
        if len(types) == 1:
            homogeneous_count += 1
            # Mark as homogeneous for sorting
            c['_homogeneous'] = True
        else:
            c['_homogeneous'] = False

    print(f"  Found {homogeneous_count} homogeneous clusters (will be deprioritized)")

    # Reorder: diverse technical first, homogeneous later, careers last
    def cluster_sort_key(c):
        label = c['label'].lower()
        is_homogeneous = c.get('_homogeneous', False)
        is_career = c.get('_is_career_cluster', False)

        # Career clusters (either by label or by content) go to the very end
        if is_career:
            return (4, -c['item_count'])
        # Homogeneous technical clusters go after diverse ones
        if is_homogeneous:
            if any(t in label for t in technical_terms):
                return (2, -c['item_count'])  # homogeneous technical
            return (3, -c['item_count'])  # homogeneous non-technical
        # Diverse technical clusters go first
        if any(t in label for t in technical_terms):
            return (0, -c['item_count'])
        # Diverse non-technical in the middle
        return (1, -c['item_count'])

    non_empty.sort(key=cluster_sort_key)
    print(f"  Reordered clusters (technical first, careers last)")

    # Clean up temporary fields
    for c in non_empty:
        if '_homogeneous' in c:
            del c['_homogeneous']
        if '_is_career_cluster' in c:
            del c['_is_career_cluster']

    final_clusters = non_empty
    print(f"  Final cluster count: {len(final_clusters)}")

    # Save
    output = {
        "generated_at": data.get('generated_at', ''),
        "postprocessed_at": str(np.datetime64('now')),
        "mmr_generated_at": str(np.datetime64('now')),
        "num_clusters": len(final_clusters),
        "num_items": len(item_to_cluster),
        "mmr_config": {
            "lambda": 0.6,
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
