#!/usr/bin/env python3
"""
Generate creative Netflix-style names for topic clusters using GPT-4o-mini.

Usage:
    OPENAI_API_KEY=sk-... python3 scripts/generate_creative_names.py

Features:
- Generates creative 2-6 word names for each cluster
- Avoids generic terms like "Topics", "Resources", "Collection"
- Batch processing for cost efficiency
- Preserves original labels as fallback
"""

import json
import os
import time
from pathlib import Path

# Optional OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CLUSTERS_FILE = PROJECT_ROOT / "data" / "topic_clusters_all.json"

# Blacklist for creative names - these terms make names too generic
NAME_BLACKLIST = [
    'topics', 'resources', 'collection', 'papers on', 'overview of',
    'guide to', 'introduction to', 'fundamentals of', 'basics of',
    'methods', 'techniques', 'approaches', 'strategies', 'insights'
]

# Creative naming prompt template
CREATIVE_NAMING_PROMPT = '''You are a Netflix content curator creating compelling category names.

Generate ONE creative name (2-6 words) for this content cluster.

AVOID:
- "Topics", "Resources", "Collection", "Papers on X"
- Generic terms: "Overview", "Introduction", "Guide", "Methods"
- Boring academic phrasing

GOOD EXAMPLES:
- "The Transformer Revolution"
- "Taming Your Data Jungle"
- "When Experiments Go Wrong"
- "Beyond A/B Testing"
- "The Prediction Game"
- "Causal Magic"

Cluster Label: {label}
Sample Items: {items}
Tags: {tags}

Generate exactly one creative name (no quotes, no explanation):'''


def load_clusters():
    """Load existing clusters."""
    with open(CLUSTERS_FILE) as f:
        return json.load(f)


def save_clusters(data):
    """Save clusters back to file."""
    with open(CLUSTERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def is_valid_creative_name(name):
    """Check if name passes quality filters."""
    if not name or len(name) < 3:
        return False

    name_lower = name.lower()

    # Check blacklist
    for term in NAME_BLACKLIST:
        if term in name_lower:
            return False

    # Check length (2-6 words)
    words = name.split()
    if len(words) < 2 or len(words) > 6:
        return False

    return True


def generate_creative_name(cluster, client):
    """Generate a creative name for a single cluster."""
    label = cluster.get('label', 'Unknown')
    sample_items = cluster.get('sample_items', [])[:5]
    top_tags = cluster.get('top_tags', [])[:5]

    # Format items - just use IDs for now since we don't have full item data
    items_str = ', '.join(sample_items[:5]) if sample_items else label
    tags_str = ', '.join(top_tags) if top_tags else 'general'

    prompt = CREATIVE_NAMING_PROMPT.format(
        label=label,
        items=items_str,
        tags=tags_str
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.7  # Slightly higher for creativity
        )

        name = response.choices[0].message.content.strip()
        name = name.strip('"\'').rstrip('.')

        # Validate the name
        if is_valid_creative_name(name):
            return name
        else:
            return None

    except Exception as e:
        print(f"    [LLM error: {e}]")
        return None


def main():
    print("="*60)
    print("CREATIVE NAME GENERATION")
    print("="*60)

    if not OPENAI_AVAILABLE:
        print("\nError: OPENAI_API_KEY not set. Exiting.")
        return

    client = OpenAI()

    # Load clusters
    print("\nLoading clusters...")
    data = load_clusters()
    clusters = data['clusters']
    print(f"  Loaded {len(clusters)} clusters")

    # Count clusters needing names
    needs_name = [c for c in clusters if not c.get('creative_name')]
    print(f"  Clusters needing creative names: {len(needs_name)}")

    if not needs_name:
        print("\nAll clusters already have creative names. Done!")
        return

    # Generate names
    print("\n" + "="*60)
    print("GENERATING CREATIVE NAMES")
    print("="*60)

    generated = 0
    failed = 0

    for i, cluster in enumerate(clusters):
        if cluster.get('creative_name'):
            continue

        label = cluster.get('label', 'Unknown')
        print(f"\n[{i+1}/{len(clusters)}] {label}")

        creative_name = generate_creative_name(cluster, client)

        if creative_name:
            cluster['creative_name'] = creative_name
            print(f"  -> {creative_name}")
            generated += 1
        else:
            # Fall back to cleaned-up original label
            cluster['creative_name'] = label
            print(f"  -> (fallback) {label}")
            failed += 1

        # Rate limiting
        time.sleep(0.1)

        # Save periodically
        if (i + 1) % 50 == 0:
            print(f"\n  [Saving progress: {generated} generated, {failed} fallbacks]")
            save_clusters(data)

    # Final save
    print("\n" + "="*60)
    print("SAVING RESULTS")
    print("="*60)

    save_clusters(data)

    print(f"\n  Generated: {generated} creative names")
    print(f"  Fallbacks: {failed}")
    print(f"  Total: {len(clusters)}")

    # Show some examples
    print("\n" + "="*60)
    print("SAMPLE CREATIVE NAMES")
    print("="*60)

    for cluster in clusters[:10]:
        label = cluster.get('label', '')
        creative = cluster.get('creative_name', '')
        if creative and creative != label:
            print(f"  '{label}' -> '{creative}'")


if __name__ == "__main__":
    main()
