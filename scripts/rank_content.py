#!/usr/bin/env python3
"""
Content Ranking Script
Ranks content items by engagement signals from D1 analytics data.

Usage:
    python scripts/rank_content.py
    python scripts/rank_content.py --output data/content_rankings.json
"""

import json
import subprocess
import argparse
import math
from datetime import datetime
from collections import defaultdict


def wilson_lower_bound(pos, n, z=1.96):
    """
    Wilson score confidence interval lower bound.
    Used for ranking items with few observations.

    Args:
        pos: Number of positive events (clicks)
        n: Total observations (impressions)
        z: Z-score for confidence level (1.96 = 95%)

    Returns:
        Lower bound of Wilson score interval
    """
    if n == 0:
        return 0

    phat = pos / n
    # Ensure the value under sqrt is non-negative
    inner = (phat * (1 - phat) + z * z / (4 * n)) / n
    if inner < 0:
        inner = 0
    return (phat + z * z / (2 * n) - z * math.sqrt(inner)) / (1 + z * z / n)


def normalize(values):
    """Min-max normalization to [0, 1] range."""
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.5] * len(values)
    return [(v - min_val) / (max_val - min_val) for v in values]


def log_scale(value, base=10):
    """Log scale with base, handling zeros."""
    return math.log(value + 1, base) / math.log(100, base)  # Normalize to ~1 for 100 clicks


def fetch_d1_data(query):
    """Execute D1 query via wrangler and return results."""
    cmd = [
        'npx', 'wrangler', 'd1', 'execute', 'tech-econ-analytics-db',
        '--remote', '--command', query, '--json'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd='/Users/pranjal/metrics-packages/analytics-worker')

    if result.returncode != 0:
        print(f"Error executing query: {result.stderr}")
        return []

    try:
        data = json.loads(result.stdout)
        return data[0]['results'] if data and data[0].get('results') else []
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"Error parsing response: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description='Rank content by engagement')
    parser.add_argument('--output', '-o', default='data/content_rankings.json',
                        help='Output file path')
    parser.add_argument('--ctr-weight', type=float, default=0.30,
                        help='Weight for CTR (default: 0.30)')
    parser.add_argument('--dwell-weight', type=float, default=0.25,
                        help='Weight for dwell time (default: 0.25)')
    parser.add_argument('--viewability-weight', type=float, default=0.20,
                        help='Weight for viewability (default: 0.20)')
    parser.add_argument('--popularity-weight', type=float, default=0.15,
                        help='Weight for log(clicks) (default: 0.15)')
    parser.add_argument('--confidence-weight', type=float, default=0.10,
                        help='Weight for Wilson score (default: 0.10)')
    args = parser.parse_args()

    print("Fetching analytics data from D1...")

    # Fetch clicks
    clicks_data = fetch_d1_data("SELECT name, section, click_count FROM content_clicks")
    print(f"  Clicks: {len(clicks_data)} items")

    # Fetch impressions
    impressions_data = fetch_d1_data("SELECT name, section, impression_count FROM content_impressions")
    print(f"  Impressions: {len(impressions_data)} items")

    # Fetch dwell times
    dwell_data = fetch_d1_data("SELECT name, section, dwell_ms, viewable_seconds, reading_ratio FROM content_dwell")
    print(f"  Dwell: {len(dwell_data)} items")

    # Build lookup dictionaries
    clicks = {(r['name'], r['section']): r['click_count'] for r in clicks_data}
    impressions = {(r['name'], r['section']): r['impression_count'] for r in impressions_data}
    dwell = {(r['name'], r['section']): r for r in dwell_data}

    # Get all unique items
    all_keys = set(clicks.keys()) | set(impressions.keys()) | set(dwell.keys())
    print(f"\nTotal unique items: {len(all_keys)}")

    # Calculate section averages for cold start
    section_clicks = defaultdict(list)
    section_impressions = defaultdict(list)
    for (name, section), count in clicks.items():
        section_clicks[section].append(count)
    for (name, section), count in impressions.items():
        section_impressions[section].append(count)

    section_avg_ctr = {}
    for section in set(s for _, s in all_keys):
        total_clicks = sum(section_clicks.get(section, [0]))
        total_impr = sum(section_impressions.get(section, [1]))
        section_avg_ctr[section] = total_clicks / max(total_impr, 1)

    # Build item records
    items = []
    for name, section in all_keys:
        click_count = clicks.get((name, section), 0)
        impression_count = impressions.get((name, section), 0)
        dwell_info = dwell.get((name, section), {})

        # Calculate CTR (use section average for cold start)
        if impression_count >= 3:
            ctr = click_count / impression_count
        elif impression_count > 0:
            # Blend with section average
            raw_ctr = click_count / impression_count
            ctr = 0.5 * raw_ctr + 0.5 * section_avg_ctr.get(section, 0)
        else:
            # No impressions = no CTR data (will rely on click count instead)
            ctr = 0

        items.append({
            'name': name,
            'section': section,
            'clicks': click_count,
            'impressions': impression_count,
            'ctr': round(ctr, 4),
            'dwell_ms': dwell_info.get('dwell_ms'),
            'viewable_seconds': dwell_info.get('viewable_seconds'),
            'reading_ratio': dwell_info.get('reading_ratio'),
        })

    # Calculate normalized scores
    ctrs = [item['ctr'] for item in items]
    dwells = [item['dwell_ms'] or 0 for item in items]
    viewables = [item['viewable_seconds'] or 0 for item in items]

    norm_ctrs = normalize(ctrs)
    norm_dwells = normalize(dwells)
    norm_viewables = normalize(viewables)

    # Calculate engagement scores
    for i, item in enumerate(items):
        # Component scores
        ctr_score = norm_ctrs[i]
        dwell_score = norm_dwells[i] if item['dwell_ms'] else 0
        viewability_score = norm_viewables[i] if item['viewable_seconds'] else 0
        popularity_score = log_scale(item['clicks'])
        confidence_score = wilson_lower_bound(item['clicks'], item['impressions'])

        # Adjust weights if no dwell data
        if item['dwell_ms'] is None:
            # Redistribute dwell/viewability weights to CTR and popularity
            adjusted_ctr_weight = args.ctr_weight + args.dwell_weight * 0.5
            adjusted_pop_weight = args.popularity_weight + args.dwell_weight * 0.3 + args.viewability_weight * 0.2
            adjusted_conf_weight = args.confidence_weight + args.viewability_weight * 0.3

            score = (
                adjusted_ctr_weight * ctr_score +
                adjusted_pop_weight * popularity_score +
                adjusted_conf_weight * confidence_score
            )
        else:
            score = (
                args.ctr_weight * ctr_score +
                args.dwell_weight * dwell_score +
                args.viewability_weight * viewability_score +
                args.popularity_weight * popularity_score +
                args.confidence_weight * confidence_score
            )

        item['score'] = round(score, 4)
        item['components'] = {
            'ctr': round(ctr_score, 3),
            'dwell': round(dwell_score, 3),
            'viewability': round(viewability_score, 3),
            'popularity': round(popularity_score, 3),
            'confidence': round(confidence_score, 3),
        }

    # Sort by score
    items.sort(key=lambda x: x['score'], reverse=True)

    # Add ranks
    for i, item in enumerate(items, 1):
        item['rank'] = i

    # Output
    output = {
        'updated': datetime.utcnow().isoformat() + 'Z',
        'weights': {
            'ctr': args.ctr_weight,
            'dwell': args.dwell_weight,
            'viewability': args.viewability_weight,
            'popularity': args.popularity_weight,
            'confidence': args.confidence_weight,
        },
        'total_items': len(items),
        'rankings': items
    }

    # Print top 20
    print("\n" + "=" * 60)
    print("TOP 20 CONTENT BY ENGAGEMENT SCORE")
    print("=" * 60)
    print(f"{'Rank':<5} {'Score':<7} {'Clicks':<7} {'CTR':<7} {'Name'}")
    print("-" * 60)
    for item in items[:20]:
        ctr_str = f"{item['ctr']:.2f}" if item['impressions'] > 0 else "N/A"
        name_display = item['name'][:40] + '...' if len(item['name']) > 40 else item['name']
        print(f"{item['rank']:<5} {item['score']:<7.3f} {item['clicks']:<7} {ctr_str:<7} {name_display}")

    # Print section breakdown
    print("\n" + "=" * 60)
    print("TOP SECTIONS BY AVERAGE SCORE")
    print("=" * 60)
    section_scores = defaultdict(list)
    for item in items:
        section_scores[item['section']].append(item['score'])

    section_avgs = [(s, sum(scores)/len(scores), len(scores)) for s, scores in section_scores.items()]
    section_avgs.sort(key=lambda x: x[1], reverse=True)

    print(f"{'Section':<40} {'Avg Score':<10} {'Items'}")
    print("-" * 60)
    for section, avg, count in section_avgs[:15]:
        section_display = section[:38] + '..' if len(section) > 38 else section
        print(f"{section_display:<40} {avg:<10.3f} {count}")

    # Save to file
    output_path = f"/Users/pranjal/metrics-packages/{args.output}"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nRankings saved to: {args.output}")


if __name__ == '__main__':
    main()
