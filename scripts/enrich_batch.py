#!/usr/bin/env python3
"""
OpenAI Batch API for LLM Metadata Enrichment.

50% cheaper than real-time API, with higher rate limits.

Usage:
    # All-in-one (prepare → submit → poll → apply)
    OPENAI_API_KEY=sk-... python3 scripts/enrich_batch.py run

    # Step-by-step
    python3 scripts/enrich_batch.py prepare --output batch_requests.jsonl
    OPENAI_API_KEY=sk-... python3 scripts/enrich_batch.py submit --input batch_requests.jsonl
    OPENAI_API_KEY=sk-... python3 scripts/enrich_batch.py status --batch-id batch_abc123
    OPENAI_API_KEY=sk-... python3 scripts/enrich_batch.py apply --batch-id batch_abc123

    # List all batches
    OPENAI_API_KEY=sk-... python3 scripts/enrich_batch.py list
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed")
    print("Install with: pip install openai")
    sys.exit(1)

try:
    from pydantic import ValidationError
except ImportError:
    print("Error: pydantic package not installed")
    print("Install with: pip install pydantic")
    sys.exit(1)

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import from existing enrichment script
from enrich_metadata_v2 import (
    DATA_DIR, DATA_FILES, PAPERS_FILE, MODEL_VERSION, SCHEMA_VERSION,
    PROMPT_MAP, EMBEDDING_TEXT_MAP, EMBEDDING_TEXT_BASE, ANTI_HALLUCINATION,
    CLUSTERING_FIELDS_INSTRUCTION,
    load_state, save_state, needs_enrichment, get_item_id, compute_hash,
    apply_enrichment, update_state, calculate_confidence,
    BaseEnrichment, SCHEMA_MAP
)

# =============================================================================
# Configuration
# =============================================================================

BATCH_STATE_FILE = DATA_DIR / ".enrichment_batch.json"
BATCH_REQUESTS_FILE = DATA_DIR / "batch_requests.jsonl"
BATCH_RESULTS_FILE = DATA_DIR / "batch_results.jsonl"

POLL_INTERVAL = 30  # seconds between status checks


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
    return re.sub(r'^-|-$', '', slug)[:80]


# =============================================================================
# Batch State Management
# =============================================================================

def load_batch_state() -> dict:
    """Load batch processing state."""
    if BATCH_STATE_FILE.exists():
        with open(BATCH_STATE_FILE) as f:
            return json.load(f)
    return {"batches": [], "item_map": {}}


def save_batch_state(state: dict) -> None:
    """Save batch processing state."""
    with open(BATCH_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


# =============================================================================
# Prepare Command
# =============================================================================

def format_prompt_for_batch(item: dict, content_type: str) -> list:
    """Format messages for batch API request."""
    template = PROMPT_MAP.get(content_type, PROMPT_MAP["resource"])

    # Build format dict
    format_dict = {
        "name": item.get("name", item.get("title", "")),
        "title": item.get("title", item.get("name", "")),
        "description": item.get("description", ""),
        "category": item.get("category", ""),
        "type": item.get("type", ""),
        "language": item.get("language", ""),
        "location": item.get("location", ""),
        "authors": item.get("authors", ""),
        "year": item.get("year", ""),
        "citations": item.get("citations", 0),
        "tags": ", ".join(item.get("tags", [])) if isinstance(item.get("tags"), list) else item.get("tags", ""),
        "anti_hallucination": ANTI_HALLUCINATION,
        "embedding_text_instruction": EMBEDDING_TEXT_MAP.get(content_type, EMBEDDING_TEXT_BASE),
        "clustering_fields_instruction": CLUSTERING_FIELDS_INSTRUCTION,
    }

    prompt = template.format(**format_dict)

    return [
        {
            "role": "system",
            "content": "You are a metadata enrichment assistant. Return only valid JSON. Never fabricate information - use null or empty arrays when data is not available."
        },
        {"role": "user", "content": prompt}
    ]


def prepare_batch_file(output_path: Path, force: bool = False, limit: int | None = None) -> tuple[int, dict]:
    """Generate .jsonl file with all enrichment requests."""
    state = load_state()
    batch_state = load_batch_state()
    item_map = {}  # custom_id -> (file_key, item_index, item_name)

    requests = []

    # Process flat files
    for filename in DATA_FILES:
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue

        with open(filepath) as f:
            data = json.load(f)

        if not isinstance(data, list):
            continue

        content_type = filepath.stem.rstrip("s")
        file_key = filepath.name

        for idx, item in enumerate(data):
            if not needs_enrichment(item, state, file_key, force):
                continue

            item_name = get_item_id(item)
            custom_id = f"{content_type}:{idx}:{slugify(item_name)}"

            # Store mapping for later
            item_map[custom_id] = {
                "file": file_key,
                "index": idx,
                "name": item_name,
                "content_type": content_type
            }

            requests.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL_VERSION,
                    "messages": format_prompt_for_batch(item, content_type),
                    "max_tokens": 2000,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            })

    # Process papers file (nested structure)
    papers_path = DATA_DIR / PAPERS_FILE
    if papers_path.exists():
        with open(papers_path) as f:
            papers_data = json.load(f)

        if "topics" in papers_data:
            paper_idx = 0
            for topic in papers_data["topics"]:
                for subtopic in topic.get("subtopics", []):
                    for paper in subtopic.get("papers", []):
                        if not needs_enrichment(paper, state, PAPERS_FILE, force):
                            continue

                        paper_title = paper.get("title", "unknown")
                        custom_id = f"paper:{topic['id']}:{subtopic['id']}:{paper_idx}:{slugify(paper_title)}"

                        item_map[custom_id] = {
                            "file": PAPERS_FILE,
                            "topic_id": topic["id"],
                            "subtopic_id": subtopic["id"],
                            "paper_idx": paper_idx,
                            "name": paper_title,
                            "content_type": "paper"
                        }

                        requests.append({
                            "custom_id": custom_id,
                            "method": "POST",
                            "url": "/v1/chat/completions",
                            "body": {
                                "model": MODEL_VERSION,
                                "messages": format_prompt_for_batch(paper, "paper"),
                                "max_tokens": 2000,
                                "temperature": 0.3,
                                "response_format": {"type": "json_object"}
                            }
                        })
                        paper_idx += 1

    # Apply limit
    if limit:
        requests = requests[:limit]
        # Filter item_map to only include limited items
        limited_ids = {r["custom_id"] for r in requests}
        item_map = {k: v for k, v in item_map.items() if k in limited_ids}

    # Write requests to .jsonl
    with open(output_path, "w") as f:
        for req in requests:
            f.write(json.dumps(req) + "\n")

    # Save item map for later
    batch_state["item_map"] = item_map
    save_batch_state(batch_state)

    print(f"Prepared {len(requests)} requests → {output_path}")
    return len(requests), item_map


# =============================================================================
# Submit Command
# =============================================================================

def submit_batch(client: OpenAI, input_path: Path) -> str:
    """Upload file and create batch job."""
    print(f"Uploading {input_path}...")

    with open(input_path, "rb") as f:
        file = client.files.create(file=f, purpose="batch")

    print(f"File uploaded: {file.id}")

    batch = client.batches.create(
        input_file_id=file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": f"tech-econ enrichment v{SCHEMA_VERSION}"}
    )

    print(f"Batch created: {batch.id}")
    print(f"Status: {batch.status}")

    # Save batch ID
    batch_state = load_batch_state()
    batch_state["batches"].append({
        "id": batch.id,
        "input_file_id": file.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": batch.status
    })
    save_batch_state(batch_state)

    return batch.id


# =============================================================================
# Status Command
# =============================================================================

def check_status(client: OpenAI, batch_id: str) -> dict:
    """Check batch status."""
    batch = client.batches.retrieve(batch_id)

    print(f"\nBatch: {batch.id}")
    print(f"Status: {batch.status}")
    print(f"Requests: {batch.request_counts.completed}/{batch.request_counts.total} completed, {batch.request_counts.failed} failed")

    if batch.created_at:
        print(f"Created: {datetime.fromtimestamp(batch.created_at)}")
    if batch.completed_at:
        print(f"Completed: {datetime.fromtimestamp(batch.completed_at)}")
    if batch.output_file_id:
        print(f"Output file: {batch.output_file_id}")
    if batch.error_file_id:
        print(f"Error file: {batch.error_file_id}")

    return batch


def poll_until_complete(client: OpenAI, batch_id: str, interval: int = POLL_INTERVAL) -> dict:
    """Poll batch status until complete."""
    print(f"Polling batch {batch_id} every {interval}s...")

    while True:
        batch = client.batches.retrieve(batch_id)
        status = batch.status
        counts = batch.request_counts

        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {status}: {counts.completed}/{counts.total} done, {counts.failed} failed")

        if status in ["completed", "failed", "expired", "cancelled"]:
            return batch

        time.sleep(interval)


# =============================================================================
# Apply Command
# =============================================================================

def apply_results(client: OpenAI, batch_id: str) -> tuple[int, int]:
    """Download results and apply enrichments."""
    batch = client.batches.retrieve(batch_id)

    if batch.status != "completed":
        print(f"Batch is not complete (status: {batch.status})")
        return 0, 0

    if not batch.output_file_id:
        print("No output file available")
        return 0, 0

    # Download output
    print(f"Downloading output file {batch.output_file_id}...")
    response = client.files.content(batch.output_file_id)
    output = response.text if hasattr(response, 'text') else response.read().decode('utf-8')

    # Save locally for debugging
    with open(BATCH_RESULTS_FILE, "w") as f:
        f.write(output)
    print(f"Saved results to {BATCH_RESULTS_FILE}")

    # Load item map and state
    batch_state = load_batch_state()
    item_map = batch_state.get("item_map", {})
    enrichment_state = load_state()

    # Load all data files into memory
    data_cache = {}
    for filename in DATA_FILES:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath) as f:
                data_cache[filename] = json.load(f)

    # Load papers
    papers_path = DATA_DIR / PAPERS_FILE
    if papers_path.exists():
        with open(papers_path) as f:
            data_cache[PAPERS_FILE] = json.load(f)

    # Process results
    success_count = 0
    fail_count = 0

    for line in output.strip().split("\n"):
        if not line:
            continue

        result = json.loads(line)
        custom_id = result["custom_id"]
        response = result.get("response", {})
        error = result.get("error")

        if error:
            print(f"  [ERROR] {custom_id}: {error}")
            fail_count += 1
            continue

        if response.get("status_code") != 200:
            print(f"  [ERROR] {custom_id}: HTTP {response.get('status_code')}")
            fail_count += 1
            continue

        # Parse enrichment from response
        try:
            body = response.get("body", {})
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            enrichment = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"  [ERROR] {custom_id}: JSON parse error - {e}")
            fail_count += 1
            continue

        # Get item info from map
        info = item_map.get(custom_id)
        if not info:
            print(f"  [WARN] {custom_id}: not found in item map")
            fail_count += 1
            continue

        file_key = info["file"]
        content_type = info["content_type"]

        # Validate with Pydantic
        schema_class = SCHEMA_MAP.get(content_type, BaseEnrichment)
        try:
            validated = schema_class(**enrichment)
            enrichment = validated.model_dump()
        except ValidationError:
            pass  # Use raw if validation fails

        # Calculate confidence
        confidence = calculate_confidence(enrichment, {}, content_type)

        # Apply enrichment to the right item
        if file_key == PAPERS_FILE:
            # Navigate nested structure
            topic_id = info["topic_id"]
            subtopic_id = info["subtopic_id"]

            for topic in data_cache[PAPERS_FILE]["topics"]:
                if topic["id"] == topic_id:
                    for subtopic in topic.get("subtopics", []):
                        if subtopic["id"] == subtopic_id:
                            for paper in subtopic.get("papers", []):
                                if paper.get("title") == info["name"]:
                                    apply_enrichment(paper, enrichment, content_type)
                                    update_state(enrichment_state, file_key, paper, confidence)
                                    break
        else:
            # Flat file - use index
            idx = info["index"]
            if file_key in data_cache and idx < len(data_cache[file_key]):
                item = data_cache[file_key][idx]
                apply_enrichment(item, enrichment, content_type)
                update_state(enrichment_state, file_key, item, confidence)

        success_count += 1

    # Save all updated data files
    for filename, data in data_cache.items():
        filepath = DATA_DIR / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    # Save state
    save_state(enrichment_state)

    print(f"\nApplied: {success_count} success, {fail_count} failed")
    return success_count, fail_count


# =============================================================================
# List Command
# =============================================================================

def list_batches(client: OpenAI, limit: int = 10):
    """List recent batches."""
    batches = client.batches.list(limit=limit)

    print(f"Recent batches:")
    for batch in batches:
        created = datetime.fromtimestamp(batch.created_at).strftime("%Y-%m-%d %H:%M")
        print(f"  {batch.id} | {batch.status:12} | {batch.request_counts.completed}/{batch.request_counts.total} | {created}")


# =============================================================================
# Run Command (All-in-one)
# =============================================================================

def run_all(client: OpenAI, force: bool = False, limit: int | None = None):
    """Run complete batch workflow: prepare → submit → poll → apply."""
    print("=" * 60)
    print("STEP 1: Prepare batch file")
    print("=" * 60)
    count, _ = prepare_batch_file(BATCH_REQUESTS_FILE, force=force, limit=limit)

    if count == 0:
        print("No items to enrich!")
        return

    print("\n" + "=" * 60)
    print("STEP 2: Submit batch")
    print("=" * 60)
    batch_id = submit_batch(client, BATCH_REQUESTS_FILE)

    print("\n" + "=" * 60)
    print("STEP 3: Poll until complete")
    print("=" * 60)
    batch = poll_until_complete(client, batch_id)

    if batch.status != "completed":
        print(f"\nBatch did not complete successfully: {batch.status}")
        return

    print("\n" + "=" * 60)
    print("STEP 4: Apply results")
    print("=" * 60)
    success, failed = apply_results(client, batch_id)

    print("\n" + "=" * 60)
    print(f"DONE: {success} enriched, {failed} failed")
    print("=" * 60)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OpenAI Batch API for metadata enrichment (50% cheaper)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # prepare
    p_prepare = subparsers.add_parser("prepare", help="Generate batch requests .jsonl")
    p_prepare.add_argument("--output", type=Path, default=BATCH_REQUESTS_FILE)
    p_prepare.add_argument("--force", action="store_true", help="Re-enrich all items")
    p_prepare.add_argument("--limit", type=int, help="Limit number of requests")

    # submit
    p_submit = subparsers.add_parser("submit", help="Upload and create batch job")
    p_submit.add_argument("--input", type=Path, default=BATCH_REQUESTS_FILE)

    # status
    p_status = subparsers.add_parser("status", help="Check batch status")
    p_status.add_argument("--batch-id", required=True)

    # apply
    p_apply = subparsers.add_parser("apply", help="Download and apply results")
    p_apply.add_argument("--batch-id", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List recent batches")
    p_list.add_argument("--limit", type=int, default=10)

    # run (all-in-one)
    p_run = subparsers.add_parser("run", help="Full workflow: prepare → submit → poll → apply")
    p_run.add_argument("--force", action="store_true", help="Re-enrich all items")
    p_run.add_argument("--limit", type=int, help="Limit number of requests")

    args = parser.parse_args()

    # Commands that need API key
    needs_api = ["submit", "status", "apply", "list", "run"]

    if args.command in needs_api:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set")
            print("Set with: export OPENAI_API_KEY=sk-...")
            sys.exit(1)
        client = OpenAI(api_key=api_key)
    else:
        client = None

    # Execute command
    if args.command == "prepare":
        prepare_batch_file(args.output, force=args.force, limit=args.limit)

    elif args.command == "submit":
        submit_batch(client, args.input)

    elif args.command == "status":
        check_status(client, args.batch_id)

    elif args.command == "apply":
        apply_results(client, args.batch_id)

    elif args.command == "list":
        list_batches(client, args.limit)

    elif args.command == "run":
        run_all(client, force=args.force, limit=args.limit)


if __name__ == "__main__":
    main()
