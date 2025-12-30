#!/usr/bin/env python3
"""
Leading Lights - Main Pipeline
==============================
Discover, collect, validate, and format tech economist trailblazers.

Usage:
    python main.py discover    # Run Perplexity queries
    python main.py collect     # Generate collection sheet
    python main.py validate    # Validate collected data
    python main.py format      # Format for site
    python main.py all         # Run full pipeline
"""

import os
import sys
import json
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.discovery import PerplexityDiscovery, extract_names_from_results
from src.linkedin_collector import (
    create_collection_sheet,
    load_completed_sheet,
    validate_sheet,
    filter_eligible
)
from src.validator import Validator, validate_batch
from src.formatter import format_for_site, save_for_site, preview_entries


def load_config(filepath: str = "config/seeds.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(filepath) as f:
        return yaml.safe_load(f)


def run_discovery():
    """Phase 1: Discover candidates using Perplexity API."""
    print("\n" + "=" * 60)
    print("PHASE 1: DISCOVERY")
    print("=" * 60)

    config = load_config()

    try:
        discovery = PerplexityDiscovery()
    except ValueError as e:
        print(f"Error: {e}")
        print("Set PERPLEXITY_API_KEY environment variable")
        return None

    results = discovery.run_full_discovery(
        seed_people=config['seed_people'],
        target_companies=config['target_companies'],
        output_path="data/raw/discovery_results.json",
        delay=1.0  # Be nice to the API
    )

    # Extract names
    names = extract_names_from_results(results)
    print(f"\nExtracted {len(names)} unique candidate names")

    # Save candidate names
    with open("data/candidates.json", "w") as f:
        json.dump(names, f, indent=2)

    return names


def run_collection(candidates: list = None):
    """Phase 2: Generate collection sheet for manual data entry."""
    print("\n" + "=" * 60)
    print("PHASE 2: COLLECTION SHEET")
    print("=" * 60)

    if candidates is None:
        # Load from previous discovery
        try:
            with open("data/candidates.json") as f:
                candidates = json.load(f)
        except FileNotFoundError:
            print("Error: Run 'discover' first or provide candidates")
            return None

    sheet = create_collection_sheet(candidates)
    sheet.to_csv("data/collection_sheet.csv", index=False)

    print(f"Created collection sheet with {len(candidates)} candidates")
    print("Location: data/collection_sheet.csv")
    print("\nNext steps:")
    print("1. Open data/collection_sheet.csv")
    print("2. Use linkedin_search and google_search columns to find profiles")
    print("3. Fill in the data columns")
    print("4. Set verified=True for completed entries")
    print("5. Run 'python main.py validate' when done")

    return sheet


def run_validation():
    """Phase 3: Validate collected data."""
    print("\n" + "=" * 60)
    print("PHASE 3: VALIDATION")
    print("=" * 60)

    try:
        sheet = load_completed_sheet("data/collection_sheet.csv")
    except FileNotFoundError:
        print("Error: data/collection_sheet.csv not found")
        print("Run 'collect' first")
        return None

    # Show stats
    stats = validate_sheet(sheet)
    print(f"\nCollection stats:")
    print(f"  Total candidates: {stats['total']}")
    print(f"  Verified: {stats['verified']}")
    print(f"  With LinkedIn: {stats['with_linkedin']}")
    print(f"  With PhD info: {stats['with_phd']}")
    print(f"  Senior level: {stats['is_senior']}")
    print(f"  Professors: {stats['is_professor']}")
    print(f"  Completion rate: {stats['completion_rate']:.1%}")

    # Filter eligible
    eligible = filter_eligible(sheet)
    print(f"\nEligible candidates: {len(eligible)}")

    if len(eligible) == 0:
        print("\nNo eligible candidates found.")
        print("Ensure entries have:")
        print("  - phd_institution filled")
        print("  - is_senior=True OR is_professor=True")
        print("  - verified=True")
        return None

    # Optionally validate with Perplexity
    try:
        discovery = PerplexityDiscovery()
        validator = Validator(discovery)

        print("\nValidating with Perplexity API...")
        verified_list = []
        for _, row in eligible.iterrows():
            person = row.to_dict()
            if validator.is_eligible(person):
                verified_list.append(person)

    except ValueError:
        print("\nPerplexity API not available, using local validation only")
        validator = Validator()
        verified_list = eligible.to_dict('records')

    # Save verified
    with open("data/verified.json", "w") as f:
        json.dump(verified_list, f, indent=2, default=str)

    print(f"\nSaved {len(verified_list)} verified entries to data/verified.json")
    return verified_list


def run_format():
    """Phase 4: Format for site."""
    print("\n" + "=" * 60)
    print("PHASE 4: FORMAT FOR SITE")
    print("=" * 60)

    try:
        with open("data/verified.json") as f:
            verified = json.load(f)
    except FileNotFoundError:
        print("Error: data/verified.json not found")
        print("Run 'validate' first")
        return None

    formatted = format_for_site(verified)
    save_for_site(formatted, "data/for_site.json")

    # Preview
    preview_entries(formatted)

    print("\nNext steps:")
    print("1. Review data/for_site.json")
    print("2. Copy entries to data/community.json in site root")
    print("3. Run 'hugo server' to preview")

    return formatted


def run_all():
    """Run full pipeline."""
    print("\n" + "=" * 60)
    print("LEADING LIGHTS - FULL PIPELINE")
    print("=" * 60)

    # Discovery
    candidates = run_discovery()
    if not candidates:
        print("\nDiscovery failed. Check API key.")
        return

    # Collection
    run_collection(candidates)
    print("\n" + "-" * 60)
    print("MANUAL STEP REQUIRED")
    print("-" * 60)
    print("Fill in data/collection_sheet.csv with LinkedIn data")
    print("Then run: python main.py validate")


def main():
    """Main entry point."""
    # Ensure we're in the right directory
    os.chdir(Path(__file__).parent)

    # Create data directories if needed
    Path("data/raw").mkdir(parents=True, exist_ok=True)

    # Parse command
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'discover':
        run_discovery()
    elif cmd == 'collect':
        run_collection()
    elif cmd == 'validate':
        run_validation()
    elif cmd == 'format':
        run_format()
    elif cmd == 'all':
        run_all()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
