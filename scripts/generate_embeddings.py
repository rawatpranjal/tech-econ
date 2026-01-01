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
        return SentenceTransformer('thenlper/gte-small')
    except ImportError:
        print("Error: sentence-transformers not installed")
        print("Install with: pip install sentence-transformers")
        sys.exit(1)


# Data files to process (flat structure)
DATA_FILES = [
    "packages.json",
    "datasets.json",
    "resources.json",
    "talks.json",
    "career.json",
    "community.json",
    "roadmaps.json",
    "books.json",
    "domains.json"
]

# Map file to type
FILE_TO_TYPE = {
    "packages.json": "package",
    "datasets.json": "dataset",
    "resources.json": "resource",
    "talks.json": "talk",
    "career.json": "career",
    "community.json": "community",
    "roadmaps.json": "roadmap",
    "books.json": "book",
    "domains.json": "domain"
}

# Files with nested structure (require special handling)
NESTED_FILES = ["papers.json"]


def compute_content_hash(data_dir: Path) -> str:
    """Compute SHA256 hash of all data files for change detection."""
    hasher = hashlib.sha256()
    all_files = sorted(DATA_FILES + NESTED_FILES)
    for filename in all_files:
        filepath = data_dir / filename
        if filepath.exists():
            hasher.update(filepath.read_bytes())
    return hasher.hexdigest()[:16]


def load_papers(data_dir: Path) -> List[Dict[str, Any]]:
    """Load papers from nested papers.json structure (topics -> subtopics -> papers)."""
    filepath = data_dir / "papers.json"
    if not filepath.exists():
        print(f"Warning: papers.json not found, skipping")
        return []

    with open(filepath) as f:
        data = json.load(f)

    items = []
    for topic in data.get('topics', []):
        topic_name = topic.get('name', '')
        for subtopic in topic.get('subtopics', []):
            subtopic_name = subtopic.get('name', '')
            for paper in subtopic.get('papers', []):
                # Parse year as integer for filtering
                year_raw = paper.get('year', '')
                year_int = None
                if year_raw:
                    try:
                        year_int = int(str(year_raw).strip())
                    except (ValueError, TypeError):
                        pass

                items.append({
                    'name': paper.get('title', ''),
                    'description': paper.get('description', ''),
                    'category': f"{topic_name} > {subtopic_name}",
                    'topic': topic_name,
                    'subtopic': subtopic_name,
                    'url': paper.get('url', ''),
                    'authors': paper.get('authors', ''),
                    'year': year_int,
                    'tags': '',
                    'best_for': ''
                })

    return items


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

    Strategy: Name first (most important), then description, then enriched metadata.
    Enriched fields from LLM (summary, use_cases, synthetic_questions) boost semantic matching.
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

    # LLM-generated summary adds alternative phrasing
    summary = item.get("summary", "").strip()
    if summary:
        parts.append(summary)

    # Use cases describe concrete scenarios (great for matching intent)
    use_cases = item.get("use_cases", [])
    if use_cases and isinstance(use_cases, list) and len(use_cases) > 0:
        use_cases_text = " ".join(str(u) for u in use_cases)
        parts.append(use_cases_text)

    # Category provides domain context
    category = item.get("category", "").strip()
    if category:
        parts.append(f"Category: {category}")

    # Topic tags from LLM enrichment (searchable keywords)
    topic_tags = item.get("topic_tags", [])
    if topic_tags and isinstance(topic_tags, list) and len(topic_tags) > 0:
        topic_tags_text = ", ".join(str(t) for t in topic_tags)
        parts.append(f"Topics: {topic_tags_text}")

    # Original tags
    tags = item.get("tags", [])
    if tags and isinstance(tags, list) and len(tags) > 0:
        tags_text = ", ".join(str(t) for t in tags)
        parts.append(f"Tags: {tags_text}")

    # best_for is highly descriptive
    best_for = item.get("best_for", "").strip()
    if best_for:
        parts.append(f"Best for: {best_for}")

    # Synthetic questions help match user queries
    synthetic_questions = item.get("synthetic_questions", [])
    if synthetic_questions and isinstance(synthetic_questions, list) and len(synthetic_questions) > 0:
        questions_text = " ".join(str(q) for q in synthetic_questions)
        parts.append(questions_text)

    return ". ".join(parts)


def slugify(text: str) -> str:
    """Convert text to URL-safe slug (matches JS slugify exactly)."""
    import re
    # Lowercase, replace non-alphanumeric with hyphens, strip leading/trailing hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
    return re.sub(r'^-|-$', '', slug)[:100]


def load_all_items(data_dir: Path) -> List[Dict[str, Any]]:
    """Load all items from data files with their types."""
    all_items = []
    seen_ids = {}  # Track seen IDs to handle duplicates

    for filename in DATA_FILES:
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"Warning: {filename} not found, skipping")
            continue

        with open(filepath) as f:
            items = json.load(f)

        item_type = FILE_TO_TYPE.get(filename, "unknown")

        for item in items:
            # Create a unique ID for each item (using slugify to match JS)
            name = item.get('name', 'unknown')
            base_id = f"{item_type}-{slugify(name)}"

            # Handle duplicate IDs by appending a counter
            item_id = base_id
            if base_id in seen_ids:
                seen_ids[base_id] += 1
                item_id = f"{base_id}-{seen_ids[base_id]}"
            else:
                seen_ids[base_id] = 0

            # Get tags as string for MiniSearch
            tags = item.get("tags", [])
            tags_str = ", ".join(str(t) for t in tags) if isinstance(tags, list) else ""

            # Get enriched fields (if available from LLM enrichment)
            difficulty = item.get("difficulty", "")
            prerequisites = item.get("prerequisites", [])
            prerequisites_str = ", ".join(str(p) for p in prerequisites) if isinstance(prerequisites, list) else ""
            topic_tags = item.get("topic_tags", [])
            topic_tags_str = ", ".join(str(t) for t in topic_tags) if isinstance(topic_tags, list) else ""
            summary = item.get("summary", "")
            use_cases = item.get("use_cases", [])
            use_cases_str = ", ".join(str(u) for u in use_cases) if isinstance(use_cases, list) else ""
            audience = item.get("audience", [])
            audience_str = ", ".join(str(a) for a in audience) if isinstance(audience, list) else ""
            synthetic_questions = item.get("synthetic_questions", [])

            all_items.append({
                "id": item_id,
                "type": item_type,
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "url": item.get("url", ""),
                "tags": tags_str,
                "best_for": item.get("best_for", ""),
                # Enriched fields from LLM
                "difficulty": difficulty,
                "prerequisites": prerequisites_str,
                "topic_tags": topic_tags_str,
                "summary": summary,
                "use_cases": use_cases_str,
                "audience": audience_str,
                "synthetic_questions": synthetic_questions,
                "text_for_embedding": combine_text_for_embedding(item)
            })

    # Load papers (nested structure)
    papers = load_papers(data_dir)
    for paper in papers:
        # Create a unique ID for each paper (using slugify to match JS)
        paper_name = paper.get('name', 'unknown')
        base_id = f"paper-{slugify(paper_name)}"

        # Handle duplicate IDs by appending a counter
        item_id = base_id
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            item_id = f"{base_id}-{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 0

        # Build tags from authors and year
        tags_parts = ["paper"]
        authors = paper.get("authors")
        if authors:
            # Handle both string and list formats
            if isinstance(authors, list):
                tags_parts.append(", ".join(authors))
            else:
                tags_parts.append(authors)
        if paper.get("year"):
            tags_parts.append(str(paper["year"]))
        tags_str = ", ".join(tags_parts)

        all_items.append({
            "id": item_id,
            "type": "paper",
            "name": paper.get("name", ""),
            "description": paper.get("description", ""),
            "category": paper.get("category", ""),
            "topic": paper.get("topic", ""),
            "subtopic": paper.get("subtopic", ""),
            "url": paper.get("url", ""),
            "tags": tags_str,
            "authors": ", ".join(authors) if isinstance(authors, list) else (authors or ""),
            "year": paper.get("year"),  # Integer or None
            "best_for": "",
            "text_for_embedding": combine_text_for_embedding(paper)
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
        doc = {
            "id": item["id"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "tags": item["tags"],
            "best_for": item.get("best_for", ""),
            "url": item["url"],
            "type": item["type"]
        }
        # Add optional fields for filtering (papers have these)
        if item.get("topic"):
            doc["topic"] = item["topic"]
        if item.get("subtopic"):
            doc["subtopic"] = item["subtopic"]
        if item.get("authors"):
            doc["authors"] = item["authors"]
        if item.get("year") is not None:
            doc["year"] = item["year"]

        # Add enriched fields (if available from LLM enrichment)
        if item.get("difficulty"):
            doc["difficulty"] = item["difficulty"]
        if item.get("prerequisites"):
            doc["prerequisites"] = item["prerequisites"]
        if item.get("topic_tags"):
            doc["topic_tags"] = item["topic_tags"]
        if item.get("summary"):
            doc["summary"] = item["summary"]
        if item.get("use_cases"):
            doc["use_cases"] = item["use_cases"]
        if item.get("audience"):
            doc["audience"] = item["audience"]
        # Synthetic questions are searchable text
        if item.get("synthetic_questions"):
            synthetic_q = item["synthetic_questions"]
            if isinstance(synthetic_q, list) and len(synthetic_q) > 0:
                doc["synthetic_questions"] = " ".join(str(q) for q in synthetic_q)

        documents.append(doc)

    # Return the documents array - MiniSearch will index them on the client side
    return {
        "version": 4,  # Bumped for new enriched fields
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "documents": documents,
        "config": {
            "fields": ["name", "description", "category", "tags", "best_for", "authors", "summary", "use_cases", "topic_tags", "synthetic_questions"],
            "storeFields": ["name", "description", "category", "url", "type", "tags", "best_for", "topic", "subtopic", "authors", "year", "difficulty", "prerequisites", "topic_tags", "summary", "use_cases", "audience"],
            "searchOptions": {
                "boost": {"name": 3, "tags": 2, "topic_tags": 2, "authors": 1.5, "use_cases": 1.3, "best_for": 1.2, "synthetic_questions": 1.2, "summary": 1.1, "description": 1, "category": 0.8},
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


def write_quantized_embeddings(embeddings, output_file: Path):
    """
    Write quantized embeddings (Int8 with per-vector scale factors).

    Format:
    - 4 bytes: count (uint32)
    - 4 bytes: dimensions (uint32)
    - count * 4 bytes: min values per vector (float32)
    - count * 4 bytes: max values per vector (float32)
    - count * dim bytes: quantized values (uint8)

    This reduces size by ~75% (4 bytes -> 1 byte per value).
    """
    import numpy as np

    count, dim = embeddings.shape

    # Compute per-vector min/max for better precision
    mins = embeddings.min(axis=1).astype('float32')
    maxs = embeddings.max(axis=1).astype('float32')

    # Avoid division by zero
    ranges = maxs - mins
    ranges[ranges == 0] = 1

    # Quantize to 0-255 range
    normalized = (embeddings - mins[:, np.newaxis]) / ranges[:, np.newaxis]
    quantized = (normalized * 255).astype('uint8')

    with open(output_file, 'wb') as f:
        # Header: count, dimensions
        f.write(struct.pack('<II', count, dim))
        # Scale factors: min and max for each vector
        f.write(mins.tobytes())
        f.write(maxs.tobytes())
        # Quantized embeddings
        f.write(quantized.tobytes())

    return count * dim  # Return original float count for size comparison


def compute_related_items(items: List[Dict[str, Any]], embeddings, top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compute top-k related items for each item using cosine similarity.

    Args:
        items: List of item dictionaries with 'id' field
        embeddings: numpy array of shape (n_items, embedding_dim)
        top_k: Number of related items to compute per item

    Returns:
        Dictionary mapping item ID to list of {id, score} dicts
    """
    import numpy as np

    print(f"Computing related items (top {top_k} neighbors per item)...")

    # Embeddings are already normalized, so cosine similarity = dot product
    # Compute all pairwise similarities at once
    similarity_matrix = np.dot(embeddings, embeddings.T)

    related = {}
    n_items = len(items)

    for i in range(n_items):
        # Get similarities to all other items
        sims = similarity_matrix[i]

        # Set self-similarity to -1 to exclude it
        sims[i] = -1

        # Get indices of top-k most similar items
        top_indices = np.argsort(sims)[-top_k:][::-1]

        # Build related items list with scores
        neighbors = []
        for idx in top_indices:
            score = float(sims[idx])
            if score > 0.3:  # Only include if similarity is meaningful
                neighbors.append({
                    "id": items[idx]["id"],
                    "score": round(score, 3)
                })

        related[items[i]["id"]] = neighbors

    return related


def write_related_items(related: Dict[str, List[Dict[str, Any]]], output_file: Path):
    """Write related items to JSON file."""
    output = {
        "version": 1,
        "generatedAt": datetime.utcnow().isoformat() + "Z",
        "topK": 5,
        "items": related
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, separators=(',', ':'))

    print(f"  Related items: {output_file.stat().st_size / 1024:.1f} KB")


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
        "version": 4,  # Bumped for all enriched fields
        "model": "gte-small",
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
            "url": item["url"],
            # Include enriched fields if available
            **({"difficulty": item["difficulty"]} if item.get("difficulty") else {}),
            **({"prerequisites": item["prerequisites"]} if item.get("prerequisites") else {}),
            **({"topic_tags": item["topic_tags"]} if item.get("topic_tags") else {}),
            **({"summary": item["summary"]} if item.get("summary") else {}),
            **({"use_cases": item["use_cases"]} if item.get("use_cases") else {}),
            **({"audience": item["audience"]} if item.get("audience") else {}),
            **({"synthetic_questions": item["synthetic_questions"]} if item.get("synthetic_questions") else {}),
        } for item in items]
    }

    # Write metadata JSON
    metadata_file = output_dir / "search-metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, separators=(',', ':'))
    print(f"  Metadata: {metadata_file.stat().st_size / 1024:.1f} KB")

    # 3. Write binary embeddings (Float32)
    binary_file = output_dir / "search-embeddings.bin"
    write_binary_embeddings(embeddings, binary_file)
    print(f"  Binary embeddings: {binary_file.stat().st_size / 1024:.1f} KB")

    # 4. Write quantized embeddings (Int8 with scale factors)
    quantized_file = output_dir / "search-embeddings-q8.bin"
    write_quantized_embeddings(embeddings, quantized_file)
    print(f"  Quantized embeddings: {quantized_file.stat().st_size / 1024:.1f} KB")

    # 4. Legacy JSON format (for backwards compatibility during migration)
    legacy_output = {
        "model": "gte-small",
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

    # 5. Compute and write related items (semantic neighbors)
    related = compute_related_items(items, embeddings, top_k=5)
    related_file = output_dir / "related-items.json"
    write_related_items(related, related_file)

    # Total size report
    total_new = metadata_file.stat().st_size + binary_file.stat().st_size + index_file.stat().st_size + related_file.stat().st_size
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
