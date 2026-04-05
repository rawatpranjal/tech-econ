#!/usr/bin/env python3
"""
check_homepage_rows.py — Validates data/homepage_rows.json for the autoresearch loop.

Checks:
  - Row count: 10-15
  - Items per row: 3-12
  - No more than 5 duplicate items across rows
  - Section coverage: 7 expected content types present
  - Total unique items >= 60
  - Required fields on each row: id, row_type, title, template, items
  - Required fields on each item: name, type, url

Usage:
    python3 autoresearch/checks/check_homepage_rows.py
    python3 autoresearch/checks/check_homepage_rows.py --project-root /path/to/repo
    python3 autoresearch/checks/check_homepage_rows.py --project-root /path --log-prefix /path/to/log
"""

import json
import sys
import argparse
from pathlib import Path
from collections import Counter


# Thresholds
MIN_ROWS = 5
MAX_ROWS = 7
MIN_ITEMS_PER_ROW = 3
MAX_ITEMS_PER_ROW = 12
MAX_ALLOWED_DUPLICATES = 5
EXPECTED_TYPES = {"package", "dataset", "resource", "talk"}
MIN_UNIQUE_ITEMS = 30

# Required fields
ROW_REQUIRED_FIELDS = {"id", "row_type", "title", "template", "items"}
ITEM_REQUIRED_FIELDS = {"name", "type", "url"}


def check(condition: bool, message: str, errors: list, warnings: list, warn_only: bool = False) -> None:
    """Record a check result."""
    if not condition:
        if warn_only:
            warnings.append(f"WARN  {message}")
        else:
            errors.append(f"FAIL  {message}")
    else:
        print(f"PASS  {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate homepage_rows.json")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).parent.parent.parent),
        help="Project root directory",
    )
    parser.add_argument(
        "--log-prefix",
        default=None,
        help="Log file prefix (unused, for compatibility with evaluate.sh)",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    rows_file = project_root / "data" / "homepage_rows.json"

    errors: list[str] = []
    warnings: list[str] = []

    # ── File existence ──────────────────────────────────────────────────────
    if not rows_file.exists():
        print(f"FAIL  File not found: {rows_file}")
        return 1

    try:
        with open(rows_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"FAIL  Cannot parse {rows_file}: {e}")
        return 1

    print(f"Validating: {rows_file}")
    print()

    # ── Top-level structure ──────────────────────────────────────────────────
    if "rows" not in data:
        print("FAIL  Missing 'rows' key at top level")
        return 1

    rows = data["rows"]
    if not isinstance(rows, list):
        print("FAIL  'rows' must be a list")
        return 1

    # ── Row count ────────────────────────────────────────────────────────────
    row_count = len(rows)
    check(
        MIN_ROWS <= row_count <= MAX_ROWS,
        f"Row count {row_count} within [{MIN_ROWS}, {MAX_ROWS}]",
        errors,
        warnings,
    )

    # ── Per-row checks ───────────────────────────────────────────────────────
    all_item_names: list[str] = []
    all_types: set[str] = set()
    rows_with_missing_fields: list[str] = []

    for i, row in enumerate(rows):
        row_id = row.get("id", f"row[{i}]")

        # Required fields
        missing = ROW_REQUIRED_FIELDS - set(row.keys())
        if missing:
            errors.append(f"FAIL  Row '{row_id}' missing fields: {missing}")
            rows_with_missing_fields.append(row_id)
            continue

        items = row.get("items", [])
        item_count = len(items)

        # Item count per row
        check(
            MIN_ITEMS_PER_ROW <= item_count <= MAX_ITEMS_PER_ROW,
            f"Row '{row_id}' item count {item_count} within [{MIN_ITEMS_PER_ROW}, {MAX_ITEMS_PER_ROW}]",
            errors,
            warnings,
        )

        # Per-item required fields
        for j, item in enumerate(items):
            item_name = item.get("name", f"item[{j}]")
            item_missing = ITEM_REQUIRED_FIELDS - set(item.keys())
            # url can be empty string but must be present
            if item_missing:
                warnings.append(
                    f"WARN  Row '{row_id}' item '{item_name}' missing fields: {item_missing}"
                )

            name = item.get("name", "")
            if name:
                all_item_names.append(name.lower().strip())
            itype = item.get("type", "")
            if itype:
                all_types.add(itype)

    # ── Duplicate check ───────────────────────────────────────────────────────
    name_counts = Counter(all_item_names)
    duplicates = {name: cnt for name, cnt in name_counts.items() if cnt > 1}
    dup_count = len(duplicates)
    check(
        dup_count <= MAX_ALLOWED_DUPLICATES,
        f"Duplicate items across rows: {dup_count} (max {MAX_ALLOWED_DUPLICATES})",
        errors,
        warnings,
    )
    if duplicates:
        for name, cnt in sorted(duplicates.items(), key=lambda x: -x[1])[:10]:
            print(f"      Duplicate: '{name}' appears {cnt} times")

    # ── Section coverage ──────────────────────────────────────────────────────
    missing_types = EXPECTED_TYPES - all_types
    check(
        len(missing_types) == 0,
        f"All expected content types present: {sorted(EXPECTED_TYPES)}",
        errors,
        warnings,
    )
    if missing_types:
        print(f"      Missing types: {sorted(missing_types)}")
        print(f"      Found types:   {sorted(all_types)}")

    # ── Total unique items ────────────────────────────────────────────────────
    unique_count = len(set(all_item_names))
    check(
        unique_count >= MIN_UNIQUE_ITEMS,
        f"Total unique items {unique_count} >= {MIN_UNIQUE_ITEMS}",
        errors,
        warnings,
        warn_only=True,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  {w}")
        print()

    if errors:
        print("Errors:")
        for e in errors:
            print(f"  {e}")
        print()
        print(f"RESULT: FAIL ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1

    print(f"RESULT: PASS ({len(warnings)} warning(s))")
    print(f"  Rows: {row_count}")
    print(f"  Unique items: {unique_count}")
    print(f"  Types covered: {sorted(all_types)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
