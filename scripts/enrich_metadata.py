#!/usr/bin/env python3
"""
Enrich data files with LLM-generated metadata using Anthropic Claude Sonnet.
Adds: difficulty, prerequisites, topic_tags, summary, use_cases, audience, synthetic_questions

Usage:
    ANTHROPIC_API_KEY=sk-... python3 scripts/enrich_metadata.py [--file packages.json]

Parallel usage (run each file independently):
    ANTHROPIC_API_KEY=sk-... python3 scripts/enrich_metadata.py --file packages.json &
    ANTHROPIC_API_KEY=sk-... python3 scripts/enrich_metadata.py --file datasets.json &

Resume: Script automatically skips items that already have 'difficulty' field.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Error: anthropic package not installed")
    print("Install with: pip install anthropic")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"

# Files to enrich
DATA_FILES = [
    "packages.json",
    "datasets.json",
    "resources.json",
    "talks.json",
    "career.json",
    "community.json",
    "books.json",
]

# Rate limiting - 8 req/min per process allows 6 parallel processes under 50 req/min limit
REQUESTS_PER_MINUTE = 8
REQUEST_DELAY = 60.0 / REQUESTS_PER_MINUTE

# Batch save frequency
SAVE_EVERY_N = 5


def get_prompt(item, item_type):
    """Generate the enrichment prompt for an item."""
    name = item.get("name", item.get("title", ""))
    description = item.get("description", "")
    category = item.get("category", "")
    tags = item.get("tags", "")
    if isinstance(tags, list):
        tags = ", ".join(str(t) for t in tags)

    return f"""You're enriching search metadata for tech-econ.org - the largest curated library for tech economists.

TARGET USERS:
- Early PhDs: Learning foundational methods, reading classic papers
- Junior DS: First tech job, implementing packages, learning best practices
- Mid DS: Running experiments, owning analysis, evaluating tools
- Senior DS/Researchers: Publishing, cutting-edge methods, deep expertise
- Curious browsers: Exploring new areas, following interests
- Specific seekers: "I need X to solve Y problem"

CONTENT: {item_type.upper()}
NAME: {name}
DESCRIPTION: {description}
CATEGORY: {category}
TAGS: {tags}

Return JSON:
{{
  "difficulty": "beginner|intermediate|advanced",
  "prerequisites": ["specific-skill-1", "specific-skill-2"],
  "topic_tags": ["tag1", "tag2", "tag3"],
  "summary": "2-3 sentences",
  "use_cases": ["concrete-scenario-1", "concrete-scenario-2"],
  "audience": ["persona-1", "persona-2"],
  "synthetic_questions": ["query1", "query2", "query3", "query4"]
}}

RULES:
- DIFFICULTY: beginner (accessible), intermediate (1-2 yrs exp), advanced (PhD/senior)
- PREREQUISITES: 2-3 ACTUAL tools/methods/concepts. Use hyphens not underscores.
  Examples: "python-pandas", "difference-in-differences", "SQL-window-functions"
  NEVER use vague terms like "statistics", "programming", "machine-learning"
- TOPIC_TAGS: 3-5 searchable keywords with hyphens (method + domain + format tags)
- SUMMARY: 2-3 sentences. What is it? Who uses it? What can you do with it?
- USE_CASES: 2 concrete scenarios where someone would use this
- AUDIENCE: 1-2 primary personas from: Early-PhD, Junior-DS, Mid-DS, Senior-DS, Curious-browser
- SYNTHETIC_QUESTIONS: 4 natural queries someone would type to find this

JSON only, no explanation."""


def enrich_item(client, item, item_type):
    """Use Claude to enrich a single item with metadata."""
    prompt = get_prompt(item, item_type)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        print(f"    JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"    API error: {e}")
        return None


def save_file(filepath, data):
    """Save data to JSON file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def enrich_file(client, filename, dry_run=False, limit=None):
    """Enrich all items in a data file."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Skipping {filename} (not found)")
        return 0

    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Skipping {filename} (not a list)")
        return 0

    item_type = filename.replace(".json", "").rstrip("s")
    enriched_count = 0
    skipped_count = 0
    pending_save = 0

    already_enriched = sum(1 for item in data if "difficulty" in item)
    to_enrich = len(data) - already_enriched

    print(f"\n{'='*60}")
    print(f"Processing {filename}: {already_enriched}/{len(data)} done, {to_enrich} remaining")
    print(f"{'='*60}")

    for i, item in enumerate(data):
        if "difficulty" in item:
            skipped_count += 1
            continue

        if limit is not None and enriched_count >= limit:
            print(f"  Reached limit of {limit} items")
            break

        name = item.get("name", item.get("title", "unknown"))
        print(f"  [{enriched_count + 1}/{to_enrich}] {name[:50]}...")

        if dry_run:
            enriched_count += 1
            continue

        enriched = enrich_item(client, item, item_type)

        if enriched:
            item["difficulty"] = enriched.get("difficulty", "intermediate")
            item["prerequisites"] = enriched.get("prerequisites", [])
            item["topic_tags"] = enriched.get("topic_tags", [])
            item["summary"] = enriched.get("summary", "")
            item["use_cases"] = enriched.get("use_cases", [])
            item["audience"] = enriched.get("audience", [])
            item["synthetic_questions"] = enriched.get("synthetic_questions", [])
            enriched_count += 1
            pending_save += 1

            if pending_save >= SAVE_EVERY_N:
                save_file(filepath, data)
                print(f"    [Saved {enriched_count} items]")
                pending_save = 0
        else:
            print(f"    [FAILED - skipping]")

        time.sleep(REQUEST_DELAY)

    if not dry_run and pending_save > 0:
        save_file(filepath, data)
        print(f"  Final save: {enriched_count} items")

    print(f"  Done: {enriched_count} enriched, {skipped_count} skipped")
    return enriched_count


def main():
    parser = argparse.ArgumentParser(description="Enrich data files with LLM metadata")
    parser.add_argument("--dry-run", action="store_true", help="Don't make API calls")
    parser.add_argument("--file", type=str, help="Only process specific file")
    parser.add_argument("--limit", type=int, help="Limit items to enrich")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key) if api_key else None

    files_to_process = [args.file] if args.file else DATA_FILES
    total_enriched = 0

    print(f"Enriching with Claude Sonnet (high quality)")
    if args.limit:
        print(f"Limit: {args.limit} items per file")

    for filename in files_to_process:
        total_enriched += enrich_file(client, filename, args.dry_run, args.limit)

    print(f"\n{'='*60}")
    print(f"Total enriched: {total_enriched} items")
    if args.dry_run:
        print("[DRY RUN]")


if __name__ == "__main__":
    main()
