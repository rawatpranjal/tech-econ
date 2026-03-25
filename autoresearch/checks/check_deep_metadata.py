#!/usr/bin/env python3
"""Quality checks for deep metadata enrichment."""
import argparse
import json
import sys
from pathlib import Path

VALID_RELATIONSHIP_TYPES = {
    "builds-on", "alternative-to", "implements-paper", "uses-dataset",
    "prerequisite-for", "complements", "fork-of", "successor-to"
}
VALID_MATH_LEVELS = {"none", "basic-stats", "linear-algebra", "calculus", "optimization-theory"}
VALID_CONFIDENCE = {"high", "medium", "low"}
BASELINE_FILE = ".deep_metadata_baseline.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--log-prefix', required=True)
    args = parser.parse_args()

    root = Path(args.project_root)
    data_dir = root / 'data'
    failures = []
    warnings = []

    pkg_file = data_dir / 'packages.json'
    if not pkg_file.exists():
        failures.append("data/packages.json not found")
        print_results(failures, warnings)
        return

    with open(pkg_file) as f:
        packages = json.load(f)

    if not isinstance(packages, list):
        failures.append("data/packages.json is not a list")
        print_results(failures, warnings)
        return

    total = len(packages)
    enriched = [p for p in packages if p.get('deep_metadata')]
    enriched_count = len(enriched)
    pkg_names = {p.get('name', '') for p in packages}

    print(f"Packages: {total} total, {enriched_count} with deep_metadata ({enriched_count/total:.0%})")

    for pkg in enriched:
        name = pkg.get('name', 'unknown')
        dm = pkg['deep_metadata']

        if not dm.get('schema_version'):
            failures.append(f"{name}: missing schema_version")
        if dm.get('math_level') and dm['math_level'] not in VALID_MATH_LEVELS:
            failures.append(f"{name}: invalid math_level '{dm['math_level']}'")
        if dm.get('confidence') and dm['confidence'] not in VALID_CONFIDENCE:
            failures.append(f"{name}: invalid confidence '{dm['confidence']}'")

        for i, m in enumerate(dm.get('methods', [])):
            if not isinstance(m, dict):
                failures.append(f"{name}: methods[{i}] not an object")
            elif not m.get('name') or not m.get('description'):
                failures.append(f"{name}: methods[{i}] missing name or description")

        for i, r in enumerate(dm.get('relationships', [])):
            if not isinstance(r, dict):
                failures.append(f"{name}: relationships[{i}] not an object")
            elif r.get('type', '') not in VALID_RELATIONSHIP_TYPES:
                failures.append(f"{name}: relationships[{i}] invalid type '{r.get('type')}'")
            elif r.get('target') and r['target'] not in pkg_names and r.get('type') not in ('implements-paper', 'uses-dataset'):
                warnings.append(f"{name}: relationship target '{r['target']}' not in packages")

        strengths = dm.get('strengths', [])
        limitations = dm.get('limitations', [])
        if strengths and not limitations:
            warnings.append(f"{name}: has strengths but no limitations")

        comp = dm.get('comparison_notes', {})
        if isinstance(comp, dict):
            for target in comp:
                if target not in pkg_names:
                    warnings.append(f"{name}: comparison target '{target}' not in packages")

        for i, c in enumerate(dm.get('key_concepts', [])):
            if not isinstance(c, dict) or not c.get('name') or not c.get('description'):
                failures.append(f"{name}: key_concepts[{i}] invalid")

    # Regression check
    baseline_file = data_dir / BASELINE_FILE
    if baseline_file.exists():
        with open(baseline_file) as f:
            baseline = json.load(f)
        if enriched_count < baseline.get('packages_enriched', 0):
            failures.append(f"Regression: enriched dropped from {baseline['packages_enriched']} to {enriched_count}")
        if total < baseline.get('packages_total', 0):
            failures.append(f"Regression: total dropped from {baseline['packages_total']} to {total}")

    with open(baseline_file, 'w') as f:
        json.dump({'packages_enriched': enriched_count, 'packages_total': total}, f, indent=2)

    print_results(failures, warnings)


def print_results(failures, warnings):
    for f in failures:
        print(f"FAIL: {f}")
    for w in warnings:
        print(f"WARN: {w}")
    if failures:
        print(f"\nCHECK_RESULT: FAILED ({len(failures)} failures)")
        sys.exit(1)
    else:
        print(f"\nCHECK_RESULT: PASSED ({len(warnings)} warnings)")
        sys.exit(0)


if __name__ == '__main__':
    main()
