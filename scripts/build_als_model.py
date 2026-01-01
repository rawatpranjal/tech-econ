#!/usr/bin/env python3
"""
Build ALS recommendation model from user interaction data.

Uses ALL interaction types from D1 database (dwell, clicks, impressions,
search queries) to train an ALS model for item-item recommendations.
"""

import subprocess
import json
import os
from collections import defaultdict
import numpy as np
from scipy.sparse import csr_matrix

try:
    from implicit.als import AlternatingLeastSquares
except ImportError:
    print("Please install implicit: pip install implicit")
    exit(1)


def fetch_d1_data(query):
    """Execute D1 query via wrangler and return results."""
    cmd = [
        'npx', 'wrangler', 'd1', 'execute', 'tech-econ-analytics-db',
        '--remote', '--command', query, '--json'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        if data and len(data) > 0 and 'results' in data[0]:
            return data[0]['results']
        return []
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []


def main():
    print("Fetching ALL interaction data from D1...")

    # Fetch all interaction types
    dwell = fetch_d1_data("SELECT session_id, name, dwell_ms FROM content_dwell")
    print(f"  Dwell records: {len(dwell)}")

    clicks = fetch_d1_data("SELECT name, click_count FROM content_clicks")
    print(f"  Click records: {len(clicks)}")

    impressions = fetch_d1_data("SELECT name, impression_count FROM content_impressions")
    print(f"  Impression records: {len(impressions)}")

    search_queries = fetch_d1_data("SELECT session_id, query, click_name FROM search_queries")
    print(f"  Search query records: {len(search_queries)}")

    # Collect all items from all sources
    all_items = set()
    for d in dwell:
        if d.get('name'):
            all_items.add(d['name'].lower())
    for c in clicks:
        if c.get('name'):
            all_items.add(c['name'].lower())
    for i in impressions:
        if i.get('name'):
            all_items.add(i['name'].lower())
    for s in search_queries:
        if s.get('click_name'):
            all_items.add(s['click_name'].lower())

    items = sorted(all_items)
    print(f"\n  Total unique items across all interactions: {len(items)}")

    if len(items) < 5:
        print("Not enough interaction data to train model")
        return

    # Build session indices from all sources
    sessions_set = set()
    for d in dwell:
        if d.get('session_id'):
            sessions_set.add(d['session_id'])
    for s in search_queries:
        if s.get('session_id'):
            sessions_set.add(s['session_id'])

    # Create synthetic sessions for click/impression aggregates
    # Each item with clicks/impressions gets a pseudo-session
    synthetic_session_counter = 0
    click_sessions = {}  # item -> synthetic session
    impression_sessions = {}

    for c in clicks:
        name = c.get('name', '').lower()
        if name and name not in click_sessions:
            click_sessions[name] = f"__click_session_{synthetic_session_counter}"
            sessions_set.add(click_sessions[name])
            synthetic_session_counter += 1

    for i in impressions:
        name = i.get('name', '').lower()
        if name and name not in impression_sessions:
            impression_sessions[name] = f"__imp_session_{synthetic_session_counter}"
            sessions_set.add(impression_sessions[name])
            synthetic_session_counter += 1

    sessions = sorted(sessions_set)
    print(f"  Total sessions (real + synthetic): {len(sessions)}")

    session_idx = {s: i for i, s in enumerate(sessions)}
    item_idx = {it: i for i, it in enumerate(items)}
    idx_to_item = {i: it for it, i in item_idx.items()}

    # Build user-item matrix from ALL interaction types
    interactions = defaultdict(float)  # (session_idx, item_idx) -> score

    # 1. Dwell data (strongest signal)
    for d in dwell:
        session = d.get('session_id')
        name = d.get('name', '').lower()
        dwell_ms = d.get('dwell_ms', 0) or 0

        if session in session_idx and name in item_idx:
            key = (session_idx[session], item_idx[name])
            interactions[key] += dwell_ms / 1000.0  # seconds

    # 2. Click data (strong signal, use synthetic sessions)
    for c in clicks:
        name = c.get('name', '').lower()
        count = c.get('click_count', 0) or 0

        if name in click_sessions and name in item_idx:
            session = click_sessions[name]
            key = (session_idx[session], item_idx[name])
            interactions[key] += count * 10  # Weight clicks heavily

    # 3. Impression data (weak signal, use synthetic sessions)
    for i in impressions:
        name = i.get('name', '').lower()
        count = i.get('impression_count', 0) or 0

        if name in impression_sessions and name in item_idx:
            session = impression_sessions[name]
            key = (session_idx[session], item_idx[name])
            interactions[key] += count * 0.5  # Weak positive

    # 4. Search query clicks (strong signal)
    for s in search_queries:
        session = s.get('session_id')
        click_name = s.get('click_name', '').lower() if s.get('click_name') else None

        if session and click_name and session in session_idx and click_name in item_idx:
            key = (session_idx[session], item_idx[click_name])
            interactions[key] += 5.0  # Search click is strong intent

    # Convert to sparse matrix
    data, rows, cols = [], [], []
    for (row, col), score in interactions.items():
        rows.append(row)
        cols.append(col)
        data.append(score)

    n_users = len(sessions)
    n_items = len(items)
    user_item_matrix = csr_matrix((data, (rows, cols)), shape=(n_users, n_items))

    print(f"\nBuilding matrix: {n_users} sessions x {n_items} items")
    print(f"  Non-zero entries: {user_item_matrix.nnz}")
    print(f"  Sparsity: {100 * (1 - user_item_matrix.nnz / (n_users * n_items)):.2f}%")

    # Train ALS model
    print("\nTraining ALS model...")

    # Use smaller factors for small dataset
    n_factors = min(32, min(n_users, n_items) - 1)
    n_factors = max(n_factors, 5)

    model = AlternatingLeastSquares(
        factors=n_factors,
        regularization=0.1,
        iterations=15,
        random_state=42
    )

    # Fit on item-user matrix for similar_items
    item_user_matrix = user_item_matrix.T.tocsr()
    model.fit(item_user_matrix)

    print(f"  Model trained with {n_factors} factors")

    # Generate item-item recommendations
    print("\nGenerating item recommendations...")
    recommendations = {}
    failed_items = []

    for item_name, idx in item_idx.items():
        try:
            # Get similar items (request more to have buffer after filtering)
            similar_ids, scores = model.similar_items(idx, N=10)

            # Filter out self and format
            similar_items = []
            for sim_idx, score in zip(similar_ids, scores):
                if sim_idx != idx and sim_idx in idx_to_item:
                    # Only include if score is positive
                    if float(score) > 0:
                        similar_items.append({
                            "name": idx_to_item[sim_idx],
                            "score": round(float(score), 4)
                        })

            if similar_items:
                recommendations[item_name] = similar_items[:5]
            else:
                failed_items.append(item_name)
        except Exception as e:
            failed_items.append(f"{item_name}: {str(e)}")
            continue

    print(f"  Generated recommendations for {len(recommendations)} items")
    if failed_items:
        print(f"  Items without recommendations: {len(failed_items)}")

    # Save output
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static', 'data', 'als-recommendations.json'
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(recommendations, f, indent=2)

    print(f"\nSaved to: {output_path}")

    # Show sample
    print("\nSample recommendations:")
    for item, recs in list(recommendations.items())[:3]:
        print(f"  {item}:")
        for r in recs[:3]:
            print(f"    - {r['name']} ({r['score']:.3f})")


if __name__ == "__main__":
    main()
