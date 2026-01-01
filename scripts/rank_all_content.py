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
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

try:
    from implicit.als import AlternatingLeastSquares
    HAS_IMPLICIT = True
except ImportError:
    HAS_IMPLICIT = False
    print("Warning: implicit library not installed. Run: pip install implicit")


# Signal weights for engagement scoring
CLICK_WEIGHT = 5.0
IMPRESSION_WEIGHT = 1.0
DWELL_WEIGHT = 1.0  # per minute
CITATION_WEIGHT = 0  # disabled


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
    seen_names = set()  # Track seen names to deduplicate

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

                    # Deduplicate by normalized name
                    normalized_name = name.lower().strip()
                    if normalized_name in seen_names:
                        continue
                    seen_names.add(normalized_name)

                    items.append({
                        'name': name.lower().strip(),
                        'original_name': name,
                        'type': config['type'],
                        'url': item.get('url') or item.get('github_url') or item.get('docs_url') or '',
                        # Existing fields
                        'category': item.get('category', ''),
                        'tags': item.get('tags', []),
                        'topic_tags': item.get('topic_tags', []),
                        'difficulty': item.get('difficulty', 'intermediate'),
                        'audience': item.get('audience', []),
                        'description': item.get('description', ''),
                        'summary': item.get('summary', ''),
                        # NEW fields
                        'synthetic_questions': item.get('synthetic_questions', []),
                        'use_cases': item.get('use_cases', []),
                        'best_for': item.get('best_for', ''),
                        'citations': item.get('citations', 0),
                        'domain_tags': item.get('domain_tags', []),
                        'key_insights': item.get('key_insights', []),
                        'mentioned_tools': item.get('mentioned_tools', []),
                        'language': item.get('language', ''),
                        'content_format': item.get('content_format', ''),
                        'speaker_expertise': item.get('speaker_expertise', ''),
                        'company_context': item.get('company_context', ''),
                        'experience_level': item.get('experience_level', ''),
                        'data_modality': item.get('data_modality', ''),
                        'related_packages': item.get('related_packages', []),
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


def build_als_model(clicks, impressions, dwell):
    """Build ALS model from all interaction data and return item scores + factors."""
    if not HAS_IMPLICIT:
        return None, None, {}

    print("\nBuilding ALS model from interaction data...")

    # Collect all items from interactions
    all_items = set()
    for row in clicks:
        if row.get('name'):
            all_items.add(row['name'].lower().strip())
    for row in impressions:
        if row.get('name'):
            all_items.add(row['name'].lower().strip())
    for row in dwell:
        if row.get('name'):
            all_items.add(row['name'].lower().strip())

    if len(all_items) < 5:
        print("  Not enough items for ALS model")
        return None, None, {}

    items = sorted(all_items)
    item_idx = {it: i for i, it in enumerate(items)}
    idx_to_item = {i: it for it, i in item_idx.items()}

    # Build sessions from dwell data (real sessions)
    sessions_set = set()
    for row in dwell:
        if row.get('session_id'):
            sessions_set.add(row['session_id'])

    # Create synthetic sessions for click/impression aggregates
    synthetic_counter = 0
    click_sessions = {}
    impression_sessions = {}

    for row in clicks:
        name = row.get('name', '').lower().strip()
        if name and name not in click_sessions:
            click_sessions[name] = f"__click_{synthetic_counter}"
            sessions_set.add(click_sessions[name])
            synthetic_counter += 1

    for row in impressions:
        name = row.get('name', '').lower().strip()
        if name and name not in impression_sessions:
            impression_sessions[name] = f"__imp_{synthetic_counter}"
            sessions_set.add(impression_sessions[name])
            synthetic_counter += 1

    sessions = sorted(sessions_set)
    session_idx = {s: i for i, s in enumerate(sessions)}

    print(f"  Items: {len(items)}, Sessions: {len(sessions)} (real + synthetic)")

    # Build user-item interaction matrix
    interactions = defaultdict(float)

    # Dwell data (strongest signal)
    for row in dwell:
        session = row.get('session_id')
        name = row.get('name', '').lower().strip()
        dwell_ms = row.get('total_dwell') or row.get('dwell_ms') or 0

        if session in session_idx and name in item_idx:
            key = (session_idx[session], item_idx[name])
            interactions[key] += dwell_ms / 1000.0  # seconds

    # Click data (strong signal)
    for row in clicks:
        name = row.get('name', '').lower().strip()
        count = row.get('click_count', 0) or 0

        if name in click_sessions and name in item_idx:
            session = click_sessions[name]
            key = (session_idx[session], item_idx[name])
            interactions[key] += count * 10

    # Impression data (weak signal)
    for row in impressions:
        name = row.get('name', '').lower().strip()
        count = row.get('impression_count', 0) or 0

        if name in impression_sessions and name in item_idx:
            session = impression_sessions[name]
            key = (session_idx[session], item_idx[name])
            interactions[key] += count * 0.5

    # Convert to sparse matrix
    data, rows, cols = [], [], []
    for (row, col), score in interactions.items():
        rows.append(row)
        cols.append(col)
        data.append(score)

    n_users = len(sessions)
    n_items = len(items)
    user_item_matrix = csr_matrix((data, (rows, cols)), shape=(n_users, n_items))

    print(f"  Matrix: {n_users} x {n_items}, {user_item_matrix.nnz} interactions")

    # Train ALS model
    n_factors = min(32, min(n_users, n_items) - 1)
    n_factors = max(n_factors, 5)

    model = AlternatingLeastSquares(
        factors=n_factors,
        regularization=0.1,
        iterations=15,
        random_state=42
    )

    # Fit on item-user matrix
    item_user_matrix = user_item_matrix.T.tocsr()
    model.fit(item_user_matrix)

    print(f"  ALS trained with {n_factors} factors")

    # Compute item popularity scores
    # Score = sum of predicted interactions across all users
    user_factors = model.user_factors  # (n_users, n_factors)
    item_factors = model.item_factors  # (n_items, n_factors)

    # Sum of all user affinities for each item
    user_sum = user_factors.sum(axis=0)  # (n_factors,)
    item_scores = item_factors @ user_sum  # (n_items,)

    # Build score dict
    als_scores = {}
    for i, item in enumerate(items):
        als_scores[item] = float(item_scores[i])

    print(f"  Computed scores for {len(als_scores)} items")

    return model, item_factors, als_scores, idx_to_item


def propagate_als_cold_start(items, als_scores, item_factors, idx_to_item, k=5):
    """Propagate ALS scores to cold-start items using item factor similarity."""
    print(f"\nPropagating ALS scores to cold-start items (k={k})...")

    if item_factors is None or len(als_scores) == 0:
        print("  No ALS model available, returning empty scores")
        return {}

    # Create reverse lookup: item_name -> factor_index
    item_to_als_idx = {name: i for i, name in idx_to_item.items()}

    # Identify observed and cold-start items
    observed_items = []
    observed_indices = []
    observed_scores = []
    cold_items = []

    for item in items:
        name = item['name']
        if name in als_scores:
            observed_items.append(name)
            observed_indices.append(item_to_als_idx[name])
            observed_scores.append(als_scores[name])
        else:
            cold_items.append(item)

    print(f"  Observed: {len(observed_items)}, Cold-start: {len(cold_items)}")

    if not cold_items:
        return {}

    # For cold-start items, we don't have factors, so we fall back to
    # assigning the mean score of similar observed items by type
    type_scores = defaultdict(list)
    for i, name in enumerate(observed_items):
        item_type = next((it['type'] for it in items if it['name'] == name), 'unknown')
        type_scores[item_type].append(observed_scores[i])

    type_avg = {t: np.mean(scores) if scores else 0 for t, scores in type_scores.items()}
    global_avg = np.mean(observed_scores) if observed_scores else 0

    cold_scores = {}
    for item in cold_items:
        cold_scores[item['name']] = type_avg.get(item['type'], global_avg)

    return cold_scores


def safe_join(val):
    """Safely join a field that may be a list, string, or None."""
    if val is None:
        return ''
    if isinstance(val, str):
        return val
    if isinstance(val, list):
        return ' '.join(str(v) for v in val if v)
    return str(val)


def build_content_features(items):
    """Build TF-IDF feature matrix from ALL available metadata."""
    print("\nBuilding content feature vectors (enhanced)...")

    # Combine ALL text features for each item
    texts = []
    for item in items:
        text_parts = [
            # Original fields
            item.get('name', ''),
            item.get('description', ''),
            item.get('summary', ''),
            item.get('category', ''),
            safe_join(item.get('tags', [])),
            safe_join(item.get('topic_tags', [])),
            item.get('difficulty', ''),
            safe_join(item.get('audience', [])),
            item.get('type', ''),
            # NEW fields
            safe_join(item.get('synthetic_questions', [])),  # LLM search queries
            safe_join(item.get('use_cases', [])),             # Applications
            item.get('best_for', ''),                         # Target use
            safe_join(item.get('domain_tags', [])),           # Dataset domains
            safe_join(item.get('key_insights', [])),          # Talk takeaways
            safe_join(item.get('mentioned_tools', [])),       # Tools in talks
            item.get('language', ''),                         # Package language
            item.get('content_format', ''),                   # Resource format
            item.get('speaker_expertise', ''),                # Talk speaker
            item.get('company_context', ''),                  # Career company
            item.get('experience_level', ''),                 # Career level
            item.get('data_modality', ''),                    # Dataset type
            safe_join(item.get('related_packages', [])),      # Package relations
        ]
        texts.append(' '.join(str(p) for p in text_parts if p))

    # Build TF-IDF matrix with more features for richer matching
    vectorizer = TfidfVectorizer(
        max_features=1000,  # Increased for more metadata
        stop_words='english',
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8
    )

    try:
        feature_matrix = vectorizer.fit_transform(texts)
        print(f"  Feature matrix: {feature_matrix.shape}")
        print(f"  Using {len([f for f in vectorizer.get_feature_names_out() if '_' in f])} bigrams")
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


def apply_citations_boost(items, scores):
    """Boost paper scores by log(citations)."""
    # Find max citations for normalization
    max_citations = max((item.get('citations', 0) or 0 for item in items), default=1)
    if max_citations == 0:
        max_citations = 1

    boosted = 0
    for item in items:
        if item['type'] == 'paper':
            citations = item.get('citations', 0) or 0
            if citations > 0:
                # Log-scale boost, normalized to ~0.3 for max citations
                boost = (math.log(citations + 1) / math.log(max_citations + 1)) * CITATION_WEIGHT
                name = item['name']
                if name in scores:
                    scores[name] = min(1.0, scores[name] + boost)
                    boosted += 1

    print(f"  Applied citations boost to {boosted} papers")
    return scores


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

    # Calculate coverage stats
    click_names = {row['name'].lower().strip() for row in clicks}
    impression_names = {row['name'].lower().strip() for row in impressions}
    dwell_names = {row['name'].lower().strip() for row in dwell}
    any_interaction_names = click_names | impression_names | dwell_names

    coverage = {
        'total_items': len(items),
        'items_with_clicks': len(click_names),
        'items_with_impressions': len(impression_names),
        'items_with_dwell': len(dwell_names),
        'items_with_any': len(any_interaction_names),
        'coverage_pct': round(len(any_interaction_names) / len(items) * 100, 1) if items else 0,
    }

    # Step 3: Build engagement scores (for item_signals tracking)
    print("\nBuilding engagement scores...")
    raw_scores, item_signals = build_engagement_scores(clicks, impressions, dwell)
    print(f"  Items with engagement data: {len(raw_scores)}")

    # Step 4: Train ALS model and get scores
    als_result = build_als_model(clicks, impressions, dwell)
    if als_result and len(als_result) == 4:
        model, item_factors, als_scores, idx_to_item = als_result
    else:
        model, item_factors, als_scores, idx_to_item = None, None, {}, {}

    # Step 5: Use ALS scores if available, otherwise fall back to weighted
    if als_scores:
        observed_scores = normalize_scores(als_scores)
        scoring_method = 'als'
    else:
        print("  Falling back to weighted scoring...")
        observed_scores = normalize_scores(raw_scores)
        scoring_method = 'weighted'

    # Step 6: Propagate to cold start items
    cold_scores = propagate_als_cold_start(
        items, observed_scores, item_factors, idx_to_item, k=args.k_neighbors
    )

    # Step 7: Combine all scores
    print("\nCombining scores...")
    combined_scores = {}
    cold_start_flags = {}

    for item in items:
        name = item['name']
        if name in observed_scores:
            combined_scores[name] = observed_scores[name]
            cold_start_flags[name] = False
        elif name in cold_scores:
            combined_scores[name] = cold_scores[name]
            cold_start_flags[name] = True
        else:
            combined_scores[name] = 0.0
            cold_start_flags[name] = True

    # Step 8: Apply citations boost for papers (disabled)
    print("\nApplying citations boost...")
    combined_scores = apply_citations_boost(items, combined_scores)

    # Build final scores dict
    all_scores = {}
    for item in items:
        name = item['name']
        all_scores[name] = {
            'score': combined_scores.get(name, 0.0),
            'cold_start': cold_start_flags.get(name, True),
            'signals': item_signals.get(name, {}),
            'citations': item.get('citations', 0) if item['type'] == 'paper' else None,
        }

    # Step 8: Build ranked output
    rankings = []
    for item in items:
        name = item['name']
        score_info = all_scores.get(name, {'score': 0, 'cold_start': True, 'signals': {}, 'citations': None})

        entry = {
            'name': item.get('original_name', name),
            'type': item['type'],
            'category': item.get('category', ''),
            'description': item.get('description', ''),
            'url': item.get('url', ''),
            'score': round(score_info['score'], 4),
            'cold_start': score_info['cold_start'],
            'signals': score_info['signals'],
        }
        # Add citations for papers
        if item['type'] == 'paper' and item.get('citations'):
            entry['citations'] = item['citations']

        rankings.append(entry)

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
        'algorithm': f'hybrid_als_{scoring_method}',
        'total_items': len(rankings),
        'observed_items': observed_count,
        'cold_start_items': cold_count,
        'coverage': coverage,
        'scoring': {
            'method': scoring_method,
            'als_factors': model.factors if model else None,
            'fallback_weights': {
                'clicks': CLICK_WEIGHT,
                'impressions': IMPRESSION_WEIGHT,
                'dwell_per_minute': DWELL_WEIGHT,
            } if scoring_method == 'weighted' else None,
        },
        'metadata_fields': [
            'name', 'description', 'summary', 'category', 'tags', 'topic_tags',
            'difficulty', 'audience', 'type', 'synthetic_questions', 'use_cases',
            'best_for', 'domain_tags', 'key_insights', 'mentioned_tools',
            'language', 'content_format', 'speaker_expertise', 'company_context',
            'experience_level', 'data_modality', 'related_packages'
        ],
        'rankings': rankings
    }

    # Print summary
    print("\n" + "=" * 60)
    print("RANKING SUMMARY")
    print("=" * 60)
    print(f"Scoring method: {scoring_method.upper()}")
    if model:
        print(f"  ALS factors: {model.factors}")
    print(f"Total items ranked: {len(rankings)}")
    print(f"  With engagement data: {observed_count}")
    print(f"  Cold start (propagated): {cold_count}")

    print("\n" + "-" * 60)
    print("INTERACTION COVERAGE")
    print("-" * 60)
    print(f"Items with clicks:      {coverage['items_with_clicks']:>5} ({coverage['items_with_clicks']/len(items)*100:.1f}%)")
    print(f"Items with impressions: {coverage['items_with_impressions']:>5} ({coverage['items_with_impressions']/len(items)*100:.1f}%)")
    print(f"Items with dwell:       {coverage['items_with_dwell']:>5} ({coverage['items_with_dwell']/len(items)*100:.1f}%)")
    print(f"Items with ANY:         {coverage['items_with_any']:>5} ({coverage['coverage_pct']:.1f}%)")

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

    # Generate homepage trending data (top 12 items with real engagement)
    homepage_items = [r for r in rankings if not r['cold_start']][:12]
    homepage_data = {
        "updated": output['updated'],
        "count": len(homepage_items),
        "items": homepage_items
    }
    homepage_path = data_dir / 'homepage_trending.json'
    with open(homepage_path, 'w') as f:
        json.dump(homepage_data, f, indent=2)
    print(f"Homepage trending saved to: data/homepage_trending.json ({len(homepage_items)} items)")


if __name__ == '__main__':
    main()
