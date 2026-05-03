#!/usr/bin/env python3
"""Output-invariant checks for the recsys / search pipeline.

Designed to run in CI on every PR alongside validate_data.py. Exits
non-zero with a structured report if any invariant fails. The
invariants are intentionally narrow: they catch the obvious classes
of regression (NaN scores, score range drift, embeddings file shape
change, related-items pointing at non-existent ids) without
duplicating the per-module unit tests in tests/python/lib/.

Inputs
    - Repo on disk:
        data/{papers_flat, packages, datasets, talks, resources,
              books, career, community}.json
        static/embeddings/related-items.json
        static/embeddings/search-metadata.json

Outputs
    - stdout: structured per-check report
    - exit code 0 on success, 1 on any failure

Side effects
    - Reads only. Never writes.

Reproducibility
    - Pure read of files on disk. Same disk state -> same result.

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    E14: invariant failures fail loud (non-zero exit)
    G19: every shipped JSON output has at least one invariant test
         here (even if the production unit tests cover it too;
         redundancy is cheap when the cost is one CI step)

Why this is a script not a pytest test
    These checks scan the actual on-disk JSON files, not fixtures.
    Pytest could do that, but a standalone script is friendlier to
    invoke from CI without the full test environment, and easier to
    point a future debugger at when an invariant fails on a deploy.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
EMBEDDINGS_DIR = REPO_ROOT / "static" / "embeddings"


# ---------------------------------------------------------------------------
# Tunables — tighten over time as we accumulate confidence in the pipeline.
# ---------------------------------------------------------------------------
SCORE_MIN = 0.0
SCORE_MAX = 1.0
RELATED_TOP_K_EXPECTED = 5
# How many top-K items per content file we require to have model_score.
# 0 (off) until the pipeline is wired more tightly; we just check that
# every model_score that EXISTS is in range.
MIN_SCORED_FRACTION = 0.0


CONTENT_FILES = [
    "papers_flat.json",
    "packages.json",
    "datasets.json",
    "talks.json",
    "resources.json",
    "books.json",
    "career.json",
    "community.json",
]


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------
class Failure(Exception):
    """Marker for invariant failure. Carries the check name + reason."""

    def __init__(self, check: str, reason: str):
        super().__init__(f"[{check}] {reason}")
        self.check = check
        self.reason = reason


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------
def check_model_scores_in_range() -> dict[str, Any]:
    """Every model_score across all content JSON must be in [0, 1] and
    not NaN. Items without a score are allowed (cold-start path)."""
    out: dict[str, Any] = {}
    bad: list[str] = []
    seen = 0
    for filename in CONTENT_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        data = _load_json(path)
        items = data if isinstance(data, list) else data.get("items", [])
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            score = item.get("model_score")
            if score is None:
                continue
            seen += 1
            if not isinstance(score, (int, float)):
                bad.append(f"{filename}#{i}: type={type(score).__name__}")
                continue
            if isinstance(score, float) and math.isnan(score):
                bad.append(f"{filename}#{i}: NaN")
                continue
            if score < SCORE_MIN or score > SCORE_MAX:
                name = item.get("name", item.get("title", f"item {i}"))
                bad.append(f"{filename}: {name!r} -> {score}")
    out["seen"] = seen
    out["bad"] = bad
    if bad:
        raise Failure(
            "model_scores_in_range",
            f"{len(bad)} out-of-range / NaN scores; first 5: {bad[:5]}",
        )
    return out


def check_no_duplicate_ids_in_metadata() -> dict[str, Any]:
    """search-metadata.json must have unique ids — duplicates would
    silently bias every downstream lookup (related-items, MMR, etc.)."""
    path = EMBEDDINGS_DIR / "search-metadata.json"
    if not path.exists():
        return {"skipped": "search-metadata.json not present"}
    data = _load_json(path)
    items = data.get("items", [])
    ids: dict[str, int] = {}
    dups: list[str] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        item_id = it.get("id")
        if item_id is None:
            continue
        if item_id in ids:
            dups.append(item_id)
        else:
            ids[item_id] = i
    if dups:
        raise Failure(
            "no_duplicate_ids_in_metadata",
            f"{len(dups)} duplicate ids; first 5: {dups[:5]}",
        )
    return {"unique_ids": len(ids)}


def check_related_items_envelope() -> dict[str, Any]:
    """related-items.json must have the documented envelope and the
    expected per-item neighbour count. Catches accidental schema
    changes from generate_embeddings.py rewrites."""
    path = EMBEDDINGS_DIR / "related-items.json"
    if not path.exists():
        return {"skipped": "related-items.json not present"}
    data = _load_json(path)
    if not isinstance(data, dict):
        raise Failure("related_items_envelope", "top-level is not an object")
    for required in ("version", "items"):
        if required not in data:
            raise Failure(
                "related_items_envelope",
                f"missing top-level field: {required!r}",
            )
    items = data["items"]
    if not isinstance(items, dict):
        raise Failure(
            "related_items_envelope",
            f"items is {type(items).__name__}, expected dict",
        )
    # Sample 25 items; assert each has a list of (id, score) entries
    # capped at the documented topK.
    sample_ids = list(items.keys())[:25]
    bad: list[str] = []
    for sid in sample_ids:
        neighbours = items[sid]
        if not isinstance(neighbours, list):
            bad.append(f"{sid}: value is {type(neighbours).__name__}")
            continue
        if len(neighbours) > RELATED_TOP_K_EXPECTED:
            bad.append(f"{sid}: {len(neighbours)} neighbours, expected ≤ {RELATED_TOP_K_EXPECTED}")
        for j, n in enumerate(neighbours):
            if not isinstance(n, dict) or "id" not in n or "score" not in n:
                bad.append(f"{sid}[{j}]: malformed neighbour {n!r}")
                break
    if bad:
        raise Failure("related_items_envelope", f"{len(bad)} issues: {bad[:3]}")
    return {"sample_size": len(sample_ids), "total_items": len(items)}


def check_related_items_no_self_reference() -> dict[str, Any]:
    """No item should appear as its own related-item. A self-reference
    is a real-world bug we've shipped before; cheap to assert."""
    path = EMBEDDINGS_DIR / "related-items.json"
    if not path.exists():
        return {"skipped": "related-items.json not present"}
    data = _load_json(path)
    items = data.get("items", {})
    self_refs: list[str] = []
    for source_id, neighbours in items.items():
        if not isinstance(neighbours, list):
            continue
        for n in neighbours:
            if isinstance(n, dict) and n.get("id") == source_id:
                self_refs.append(source_id)
                break
    if self_refs:
        raise Failure(
            "related_items_no_self_reference",
            f"{len(self_refs)} items reference themselves; first 5: {self_refs[:5]}",
        )
    return {"items_checked": len(items)}


def check_related_items_ids_resolve() -> dict[str, Any]:
    """Every id mentioned as a neighbour in related-items.json must
    exist in search-metadata.json. Catches the case where one rebuild
    refreshed embeddings but not metadata (or vice versa)."""
    rel_path = EMBEDDINGS_DIR / "related-items.json"
    meta_path = EMBEDDINGS_DIR / "search-metadata.json"
    if not (rel_path.exists() and meta_path.exists()):
        return {"skipped": "related-items.json or search-metadata.json missing"}
    rel = _load_json(rel_path)
    meta = _load_json(meta_path)
    valid_ids: set[str] = set()
    for it in meta.get("items", []):
        if isinstance(it, dict) and it.get("id"):
            valid_ids.add(it["id"])
    missing: list[str] = []
    items = rel.get("items", {})
    for source_id, neighbours in items.items():
        if not isinstance(neighbours, list):
            continue
        for n in neighbours:
            nid = n.get("id") if isinstance(n, dict) else None
            if nid and nid not in valid_ids:
                missing.append(nid)
    if missing:
        # Cap the list — a stale generation could produce thousands
        unique_missing = sorted(set(missing))[:10]
        raise Failure(
            "related_items_ids_resolve",
            f"{len(set(missing))} unique neighbour ids missing from "
            f"search-metadata.json; first 10: {unique_missing}",
        )
    return {"valid_ids": len(valid_ids)}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
CHECKS = [
    ("model_scores_in_range", check_model_scores_in_range),
    ("no_duplicate_ids_in_metadata", check_no_duplicate_ids_in_metadata),
    ("related_items_envelope", check_related_items_envelope),
    ("related_items_no_self_reference", check_related_items_no_self_reference),
    ("related_items_ids_resolve", check_related_items_ids_resolve),
]


def main(argv: list[str] | None = None) -> int:
    print("Running recsys output invariants...\n")
    failures: list[Failure] = []
    for name, fn in CHECKS:
        try:
            result = fn()
            if "skipped" in result:
                print(f"  ⊘  {name}: {result['skipped']}")
            else:
                summary = ", ".join(f"{k}={v}" for k, v in result.items() if k != "bad")
                print(f"  ✓  {name}: {summary}")
        except Failure as f:
            print(f"  ✗  {name}: {f.reason}")
            failures.append(f)
        except Exception as e:  # noqa: BLE001 -- surface anything unexpected
            print(f"  !  {name}: unexpected error -> {type(e).__name__}: {e}")
            failures.append(Failure(name, f"unexpected error: {e}"))

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} of {len(CHECKS)} invariants violated.")
        return 1
    print(f"PASSED: all {len(CHECKS)} invariants satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
