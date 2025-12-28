#!/usr/bin/env python3
"""
Generate vector embeddings and MiniSearch index for semantic search.

Uses sentence-transformers to create embeddings for all items in the data files.
Outputs:
  - search-metadata.json: Item data + IDs (for client-side use)
  - search-embeddings.bin: Binary Float32 embeddings (~1MB vs 2.5MB JSON)
  - search-index.json: Pre-built MiniSearch index for fast keyword search
  - search-embeddings.json: Legacy JSON format (for backwards compatibility)
"""

import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def get_model():
    """Load the sentence-transformers model."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer('all-MiniLM-L6-v2')
    except ImportError:
        print("Error: sentence-transformers not installed")
        print("Install with: pip install sentence-transformers")
        sys.exit(1)


# Data files to process
DATA_FILES = [
    "packages.json",
    "datasets.json",
    "resources.json",
    "talks.json",
    "career.json",
    "community.json",
    "roadmaps.json"
]

# Map file to type
FILE_TO_TYPE = {
    "packages.json": "package",
    "datasets.json": "dataset",
    "resources.json": "resource",
    "talks.json": "talk",
    "career.json": "career",
    "community.json": "community",
    "roadmaps.json": "roadmap"
}


def compute_content_hash(data_dir: Path) -> str:
    """Compute SHA256 hash of all data files for change detection."""
    hasher = hashlib.sha256()
    for filename in sorted(DATA_FILES):
        filepath = data_dir / filename
        if filepath.exists():
            hasher.update(filepath.read_bytes())
    return hasher.hexdigest()[:16]


def should_regenerate(output_dir: Path, data_dir: Path, force: bool) -> bool:
    """Check if embeddings need regeneration based on content hash."""
    if force:
        return True

    metadata_file = output_dir / "search-metadata.json"
    if not metadata_file.exists():
        return True

    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
        current_hash = compute_content_hash(data_dir)
        return metadata.get("contentHash") != current_hash
    except Exception:
        return True


def combine_text_for_embedding(item: Dict[str, Any]) -> str:
    """
    Combine relevant fields into a single text for embedding.

    Strategy: Name first (most important), then description, then metadata.
    This matches how users think about items and search for them.
    """
    parts = []

    # Name is most important - always first
    name = item.get("name", "").strip()
    if name:
        parts.append(name)

    # Description provides semantic richness
    description = item.get("description", "").strip()
    if description:
        parts.append(description)

    # Category provides domain context
    category = item.get("category", "").strip()
    if category:
        parts.append(f"Category: {category}")

    # Tags are valuable keywords
    tags = item.get("tags", [])
    if tags and isinstance(tags, list) and len(tags) > 0:
        tags_text = ", ".join(str(t) for t in tags)
        parts.append(f"Tags: {tags_text}")

    # best_for is highly descriptive
    best_for = item.get("best_for", "").strip()
    if best_for:
        parts.append(f"Best for: {best_for}")

    return ". ".join(parts)


def load_all_items(data_dir: Path) -> List[Dict[str, Any]]:
    """Load all items from data files with their types."""
    all_items = []

    for filename in DATA_FILES:
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"Warning: {filename} not found, skipping")
            continue

        with open(filepath) as f:
            items = json.load(f)

        item_type = FILE_TO_TYPE.get(filename, "unknown")

        for item in items:
            # Create a unique ID for each item
            item_id = f"{item_type}-{item.get('name', 'unknown')}".lower()
            item_id = item_id.replace(" ", "-").replace("/", "-")[:100]

            # Get tags as string for MiniSearch
            tags = item.get("tags", [])
            tags_str = ", ".join(str(t) for t in tags) if isinstance(tags, list) else ""

            all_items.append({
                "id": item_id,
                "type": item_type,
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "url": item.get("url", ""),
                "tags": tags_str,
                "best_for": item.get("best_for", ""),
                "text_for_embedding": combine_text_for_embedding(item)
            })

    return all_items


def generate_minisearch_index(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a MiniSearch-compatible index structure.

    MiniSearch's JSON serialization format stores:
    - documentIds: mapping of internal IDs to document IDs
    - fieldIds: mapping of field names to internal IDs
    - fieldLength: document field lengths
    - averageFieldLength: average lengths per field
    - storedFields: stored document fields
    - index: the inverted index structure
    """
    # Build documents for MiniSearch indexing
    documents = []
    for i, item in enumerate(items):
        documents.append({
            "id": item["id"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "tags": item["tags"],
            "best_for": item["best_for"],
            "url": item["url"],
            "type": item["type"]
        })

    # Return the documents array - MiniSearch will index them on the client side
    # This is simpler and more reliable than trying to replicate MiniSearch's internal format
    return {
        "version": 1,
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "documents": documents,
        "config": {
            "fields": ["name", "description", "category", "tags", "best_for"],
            "storeFields": ["name", "description", "category", "url", "type", "tags", "best_for"],
            "searchOptions": {
                "boost": {"name": 3, "tags": 1.5, "best_for": 1.2, "description": 1, "category": 0.8},
                "fuzzy": 0.2,
                "prefix": True
            }
        }
    }


def write_binary_embeddings(embeddings, output_file: Path):
    """Write embeddings as raw Float32 binary (much smaller than JSON)."""
    flat = embeddings.flatten().astype('float32')
    with open(output_file, 'wb') as f:
        f.write(flat.tobytes())


def generate_all_outputs(items: List[Dict[str, Any]], model, output_dir: Path, content_hash: str):
    """Generate all output files: metadata, binary embeddings, MiniSearch index, and legacy JSON."""
    texts = [item["text_for_embedding"] for item in items]

    print(f"Generating embeddings for {len(texts)} items...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    # 1. Generate MiniSearch index
    print("Generating MiniSearch index...")
    minisearch_index = generate_minisearch_index(items)
    index_file = output_dir / "search-index.json"
    with open(index_file, 'w') as f:
        json.dump(minisearch_index, f, separators=(',', ':'))
    print(f"  MiniSearch index: {index_file.stat().st_size / 1024:.1f} KB")

    # 2. Build metadata (items without embeddings, for client-side matching)
    metadata = {
        "version": 2,
        "model": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "count": len(items),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "contentHash": content_hash,
        "items": [{
            "id": item["id"],
            "type": item["type"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "url": item["url"]
        } for item in items]
    }

    # Write metadata JSON
    metadata_file = output_dir / "search-metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, separators=(',', ':'))
    print(f"  Metadata: {metadata_file.stat().st_size / 1024:.1f} KB")

    # 3. Write binary embeddings
    binary_file = output_dir / "search-embeddings.bin"
    write_binary_embeddings(embeddings, binary_file)
    print(f"  Binary embeddings: {binary_file.stat().st_size / 1024:.1f} KB")

    # 4. Legacy JSON format (for backwards compatibility during migration)
    legacy_output = {
        "model": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "count": len(items),
        "items": []
    }

    for i, item in enumerate(items):
        # Round embeddings to reduce file size (6 decimal places)
        embedding_list = [round(float(x), 6) for x in embeddings[i]]

        legacy_output["items"].append({
            "id": item["id"],
            "type": item["type"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "url": item["url"],
            "embedding": embedding_list
        })

    legacy_file = output_dir / "search-embeddings.json"
    with open(legacy_file, 'w') as f:
        json.dump(legacy_output, f, separators=(',', ':'))
    print(f"  Legacy JSON: {legacy_file.stat().st_size / 1024:.1f} KB")

    # Total size report
    total_new = metadata_file.stat().st_size + binary_file.stat().st_size + index_file.stat().st_size
    total_legacy = legacy_file.stat().st_size
    print(f"\nNew format total: {total_new / 1024:.1f} KB")
    print(f"Legacy JSON: {total_legacy / 1024:.1f} KB")
    print(f"Savings: {(1 - total_new / total_legacy) * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='Generate search embeddings and indices')
    parser.add_argument('--force', action='store_true', help='Force regeneration even if content unchanged')
    parser.add_argument('--skip-cache-check', action='store_true', help='Skip content hash check')
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    output_dir = script_dir.parent / "static" / "embeddings"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if regeneration is needed
    if not args.skip_cache_check and not should_regenerate(output_dir, data_dir, args.force):
        print("Content unchanged, embeddings are up to date. Use --force to regenerate.")
        return

    # Load items
    print(f"Loading items from {data_dir}...")
    items = load_all_items(data_dir)
    print(f"Loaded {len(items)} items")

    # Compute content hash
    content_hash = compute_content_hash(data_dir)
    print(f"Content hash: {content_hash}")

    # Load model and generate all outputs
    print("Loading sentence-transformers model...")
    model = get_model()

    generate_all_outputs(items, model, output_dir, content_hash)

    print("\nDone! All search files generated successfully.")


if __name__ == "__main__":
    main()
