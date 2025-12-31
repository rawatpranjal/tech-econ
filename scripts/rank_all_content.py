#!/usr/bin/env python3
"""
Universal Content Ranking Script
Ranks ALL content items using engagement data + content similarity for cold start.

Usage:
    python scripts/rank_all_content.py
    python scripts/rank_all_content.py --output data/global_rankings.json
"""

import json
import subprocess
import argparse
import math
from datetime import datetime
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Signal weights for engagement scoring
CLICK_WEIGHT = 3.0
IMPRESSION_WEIGHT = 0.5
DWELL_WEIGHT = 1.0  # per minute


def fetch_d1_data(query):
    """Execute D1 query via wrangler and return results."""
    cmd = [
        'npx', 'wrangler', 'd1', 'execute', 'tech-econ-analytics-db',
        '--remote', '--command', query, '--json'
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd='/Users/pranjal/metrics-packages/analytics-worker'
    )

    if result.returncode != 0:
        print(f"  Warning: D1 query failed: {result.stderr[:100]}")
        return []

    try:
        data = json.loads(result.stdout)
        return data[0]['results'] if data and data[0].get('results') else []
    except (json.JSONDecodeError, IndexError, KeyError):
        return []


def load_all_content(data_dir):
    """Load all content items from data/*.json files."""
    items = []

    # Content files and their structure
    content_files = {
        'papers_flat.json': {'name_field': 'name', 'type': 'paper'},
        'packages.json': {'name_field': 'name', 'type': 'package'},
        'datasets.json': {'name_field': 'name', 'type': 'dataset'},
        'resources.json': {'name_field': 'name', 'type': 'resource'},
        'career.json': {'name_field': 'name', 'type': 'career'},
        'community.json': {'name_field': 'name', 'type': 'community'},
        'talks.json': {'name_field': 'name', 'type': 'talk'},
        'books.json': {'name_field': 'name', 'type': 'book'},
    }

    for filename, config in content_files.items():
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  Warning: {filename} not found")
            continue

        try:
            with open(filepath) as f:
                data = json.load(f)

            # Handle flat arrays
            if isinstance(data, list):
                for item in data:
                    name = item.get(config['name_field']) or item.get('title', '')
                    if not name:
                        continue

                    items.append({
                        'name': name.lower().strip(),
                        'original_name': name,
                        'type': config['type'],
                        'category': item.get('category', ''),
                        'tags': item.get('tags', []),
                        'topic_tags': item.get('topic_tags', []),
                        'difficulty': item.get('difficulty', 'intermediate'),
                        'audience': item.get('audience', []),
                        'description': item.get('description', ''),
                        'summary': item.get('summary', ''),
                    })

            print(f"  {filename}: {len([i for i in items if i['type'] == config['type']])} items")

        except Exception as e:
            print(f"  Error loading {filename}: {e}")

    return items


def fetch_engagement_data():
    """Fetch all engagement signals from D1."""
    print("\nFetching engagement data from D1...")

    clicks = fetch_d1_data("SELECT name, section, click_count FROM content_clicks")
    print(f"  Clicks: {len(clicks)} items")

    impressions = fetch_d1_data("SELECT name, section, impression_count FROM content_impressions")
    print(f"  Impressions: {len(impressions)} items")

    dwell = fetch_d1_data(
        "SELECT name, section, SUM(dwell_ms) as total_dwell "
        "FROM content_dwell GROUP BY name, section"
    )
    print(f"  Dwell: {len(dwell)} items")

    return clicks, impressions, dwell


def build_engagement_scores(clicks, impressions, dwell):
    """Build weighted engagement scores for observed items."""
    scores = defaultdict(float)
    item_signals = defaultdict(lambda: {'clicks': 0, 'impressions': 0, 'dwell_ms': 0})

    # Aggregate clicks
    for row in clicks:
        name = row['name'].lower().strip()
        count = row.get('click_count', 0) or 0
        scores[name] += count * CLICK_WEIGHT
        item_signals[name]['clicks'] += count

    # Aggregate impressions
    for row in impressions:
        name = row['name'].lower().strip()
        count = row.get('impression_count', 0) or 0
        scores[name] += count * IMPRESSION_WEIGHT
        item_signals[name]['impressions'] += count

    # Aggregate dwell time
    for row in dwell:
        name = row['name'].lower().strip()
        ms = row.get('total_dwell', 0) or 0
        minutes = ms / 60000.0
        scores[name] += minutes * DWELL_WEIGHT
        item_signals[name]['dwell_ms'] += ms

    return dict(scores), dict(item_signals)


def build_content_features(items):
    """Build TF-IDF feature matrix from content metadata."""
    print("\nBuilding content feature vectors...")

    # Combine text features for each item
    texts = []
    for item in items:
        # Handle fields that may be lists or strings
        tags = item.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        topic_tags = item.get('topic_tags', [])
        if isinstance(topic_tags, str):
            topic_tags = [topic_tags]
        audience = item.get('audience', [])
        if isinstance(audience, str):
            audience = [audience]

        text_parts = [
            item['name'],
            item.get('description', ''),
            item.get('summary', ''),
            item.get('category', ''),
            ' '.join(tags) if tags else '',
            ' '.join(topic_tags) if topic_tags else '',
            item.get('difficulty', ''),
            ' '.join(audience) if audience else '',
            item.get('type', ''),
        ]
        texts.append(' '.join(str(p) for p in text_parts if p))

    # Build TF-IDF matrix
    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8
    )

    try:
        feature_matrix = vectorizer.fit_transform(texts)
        print(f"  Feature matrix: {feature_matrix.shape}")
        return feature_matrix, vectorizer
    except Exception as e:
        print(f"  Error building features: {e}")
        return None, None


def propagate_cold_start_scores(items, observed_scores, feature_matrix, k=5):
    """Propagate scores to cold start items via k-NN similarity."""
    print(f"\nPropagating scores to cold start items (k={k})...")

    # Find observed and cold start indices
    observed_indices = []
    cold_indices = []
    observed_score_list = []

    for i, item in enumerate(items):
        if item['name'] in observed_scores:
            observed_indices.append(i)
            observed_score_list.append(observed_scores[item['name']])
        else:
            cold_indices.append(i)

    print(f"  Observed items: {len(observed_indices)}")
    print(f"  Cold start items: {len(cold_indices)}")

    if not observed_indices or feature_matrix is None:
        # No observed items or no features - use type averages
        print("  Using type averages as fallback...")
        type_scores = defaultdict(list)
        for i in observed_indices:
            type_scores[items[i]['type']].append(observed_scores[items[i]['name']])

        type_avg = {t: np.mean(scores) if scores else 0 for t, scores in type_scores.items()}
        global_avg = np.mean(observed_score_list) if observed_score_list else 0

        cold_scores = {}
        for i in cold_indices:
            cold_scores[items[i]['name']] = type_avg.get(items[i]['type'], global_avg)

        return cold_scores

    # Extract feature vectors for observed items
    observed_features = feature_matrix[observed_indices]
    observed_score_arr = np.array(observed_score_list)

    # For each cold item, find k nearest observed neighbors
    cold_scores = {}
    batch_size = 500

    for batch_start in range(0, len(cold_indices), batch_size):
        batch_indices = cold_indices[batch_start:batch_start + batch_size]
        batch_features = feature_matrix[batch_indices]

        # Compute similarities to all observed items
        similarities = cosine_similarity(batch_features, observed_features)

        for j, cold_idx in enumerate(batch_indices):
            sims = similarities[j]

            # Get top-k neighbors
            if len(sims) <= k:
                top_k_idx = np.arange(len(sims))
            else:
                top_k_idx = np.argpartition(sims, -k)[-k:]

            top_k_sims = sims[top_k_idx]
            top_k_scores = observed_score_arr[top_k_idx]

            # Weighted average (avoid division by zero)
            if top_k_sims.sum() > 0:
                score = np.average(top_k_scores, weights=top_k_sims)
            else:
                score = np.mean(observed_score_arr)  # fallback to global average

            cold_scores[items[cold_idx]['name']] = score

    return cold_scores


def normalize_scores(scores):
    """Normalize scores to 0-1 range."""
    if not scores:
        return {}

    values = list(scores.values())
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return {k: 0.5 for k in scores}

    return {k: (v - min_val) / (max_val - min_val) for k, v in scores.items()}


def main():
    parser = argparse.ArgumentParser(description='Rank all content items')
    parser.add_argument('--output', '-o', default='data/global_rankings.json',
                        help='Output file path')
    parser.add_argument('--k-neighbors', '-k', type=int, default=5,
                        help='Number of neighbors for cold start (default: 5)')
    args = parser.parse_args()

    data_dir = Path('/Users/pranjal/metrics-packages/data')

    # Step 1: Load all content
    print("Loading content catalog...")
    items = load_all_content(data_dir)
    print(f"\nTotal content items: {len(items)}")

    # Create name -> item lookup
    item_lookup = {item['name']: item for item in items}

    # Step 2: Fetch engagement data
    clicks, impressions, dwell = fetch_engagement_data()

    # Step 3: Build engagement scores for observed items
    print("\nBuilding engagement scores...")
    raw_scores, item_signals = build_engagement_scores(clicks, impressions, dwell)
    print(f"  Items with engagement data: {len(raw_scores)}")

    # Normalize observed scores
    observed_scores = normalize_scores(raw_scores)

    # Step 4: Build content features
    feature_matrix, vectorizer = build_content_features(items)

    # Step 5: Propagate to cold start items
    cold_scores = propagate_cold_start_scores(
        items, observed_scores, feature_matrix, k=args.k_neighbors
    )

    # Step 6: Combine all scores
    print("\nCombining scores...")
    all_scores = {}
    for item in items:
        name = item['name']
        if name in observed_scores:
            all_scores[name] = {
                'score': observed_scores[name],
                'cold_start': False,
                'signals': item_signals.get(name, {})
            }
        elif name in cold_scores:
            all_scores[name] = {
                'score': cold_scores[name],
                'cold_start': True,
                'signals': {}
            }
        else:
            all_scores[name] = {
                'score': 0.0,
                'cold_start': True,
                'signals': {}
            }

    # Step 7: Build ranked output
    rankings = []
    for item in items:
        name = item['name']
        score_info = all_scores.get(name, {'score': 0, 'cold_start': True, 'signals': {}})

        rankings.append({
            'name': item.get('original_name', name),
            'type': item['type'],
            'category': item.get('category', ''),
            'score': round(score_info['score'], 4),
            'cold_start': score_info['cold_start'],
            'signals': score_info['signals'],
        })

    # Sort by score descending
    rankings.sort(key=lambda x: x['score'], reverse=True)

    # Add ranks
    for i, item in enumerate(rankings, 1):
        item['rank'] = i

    # Count stats
    observed_count = sum(1 for r in rankings if not r['cold_start'])
    cold_count = sum(1 for r in rankings if r['cold_start'])

    # Build output
    output = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'algorithm': 'weighted_engagement_with_knn_coldstart',
        'total_items': len(rankings),
        'observed_items': observed_count,
        'cold_start_items': cold_count,
        'weights': {
            'clicks': CLICK_WEIGHT,
            'impressions': IMPRESSION_WEIGHT,
            'dwell_per_minute': DWELL_WEIGHT,
        },
        'rankings': rankings
    }

    # Print summary
    print("\n" + "=" * 60)
    print("RANKING SUMMARY")
    print("=" * 60)
    print(f"Total items ranked: {len(rankings)}")
    print(f"  With engagement data: {observed_count}")
    print(f"  Cold start (propagated): {cold_count}")

    print("\n" + "-" * 60)
    print("TOP 20 ITEMS")
    print("-" * 60)
    print(f"{'Rank':<5} {'Score':<7} {'Type':<10} {'Name'}")
    print("-" * 60)
    for item in rankings[:20]:
        name_display = item['name'][:45] + '...' if len(item['name']) > 45 else item['name']
        cs = "*" if item['cold_start'] else ""
        print(f"{item['rank']:<5} {item['score']:<7.3f} {item['type']:<10} {name_display}{cs}")

    print("\n" + "-" * 60)
    print("TOP ITEMS BY TYPE")
    print("-" * 60)

    type_rankings = defaultdict(list)
    for item in rankings:
        type_rankings[item['type']].append(item)

    for content_type in sorted(type_rankings.keys()):
        top = type_rankings[content_type][:3]
        print(f"\n{content_type.upper()}:")
        for item in top:
            name_display = item['name'][:50] + '...' if len(item['name']) > 50 else item['name']
            print(f"  #{item['rank']} ({item['score']:.3f}) {name_display}")

    # Save output
    output_path = data_dir.parent / args.output
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n\nRankings saved to: {args.output}")


if __name__ == '__main__':
    main()
