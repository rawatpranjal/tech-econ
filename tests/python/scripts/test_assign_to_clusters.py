"""Tests for scripts/assign_to_clusters.py :: build_clusters_from_assignments.

Covers all 10 scenarios specified in the task brief, using only stdlib
fixtures (no openai calls). The openai package is stubbed before module load.
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Stub openai before the module tries to import it
if "openai" not in sys.modules:
    _openai_stub = types.ModuleType("openai")
    _openai_stub.AsyncOpenAI = MagicMock()
    sys.modules["openai"] = _openai_stub


def _load(script_name, alias):
    path = _REPO_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(m)
    return m


_mod = _load("assign_to_clusters.py", "assign_to_clusters_mod")
build_clusters_from_assignments = _mod.build_clusters_from_assignments

# content_type "resources" → min_cluster_size=4, max_carousel=10
CONTENT_TYPE = "resources"

CLUSTER_DEFS = {
    "clusters": [
        {"id": "c1", "label": "Causal Inference", "macro_category": "Causal Methods"},
        {"id": "c2", "label": "ML", "macro_category": "Machine Learning"},
    ]
}


def _items(n: int):
    """Return n items with id='item{i}' and model_score=i*0.1."""
    return [{"id": f"item{i}", "name": f"Item {i}", "model_score": i * 0.1, "category": "Test"} for i in range(n)]


def _primary_assignments(cluster_id: str, item_ids: list[str]):
    return [{"id": iid, "primary": cluster_id, "secondary": None} for iid in item_ids]


# ---------------------------------------------------------------------------
# 1. Empty assignments → empty clusters list
# ---------------------------------------------------------------------------

def test_empty_assignments_returns_empty_clusters():
    result = build_clusters_from_assignments([], _items(5), CLUSTER_DEFS, CONTENT_TYPE)
    assert result["clusters"] == []
    assert result["total_clusters"] == 0


# ---------------------------------------------------------------------------
# 2. Cluster with >= min_cluster_size (4) items → appears in output
# ---------------------------------------------------------------------------

def test_cluster_at_min_size_appears():
    items = _items(4)
    assignments = _primary_assignments("c1", [f"item{i}" for i in range(4)])
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    assert result["total_clusters"] == 1
    assert result["clusters"][0]["cluster_id"] == "c1"


# ---------------------------------------------------------------------------
# 3. Cluster with < min_cluster_size items → NOT in output
# ---------------------------------------------------------------------------

def test_cluster_below_min_size_excluded():
    items = _items(3)
    assignments = _primary_assignments("c1", ["item0", "item1", "item2"])
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    assert result["total_clusters"] == 0
    assert result["clusters"] == []


# ---------------------------------------------------------------------------
# 4. Secondary assignment deduplicated
# ---------------------------------------------------------------------------

def test_secondary_assignment_not_duplicated():
    items = _items(5)
    # item0 is primary AND secondary for c1; should appear only once
    assignments = [
        {"id": "item0", "primary": "c1", "secondary": "c1"},
        {"id": "item1", "primary": "c1", "secondary": None},
        {"id": "item2", "primary": "c1", "secondary": None},
        {"id": "item3", "primary": "c1", "secondary": None},
    ]
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    assert result["total_clusters"] == 1
    cluster_items = result["clusters"][0]["items"]
    assert cluster_items.count("item0") == 1


# ---------------------------------------------------------------------------
# 5. Items sorted by model_score descending within carousel
# ---------------------------------------------------------------------------

def test_carousel_items_sorted_by_model_score_desc():
    # Deliberately shuffle scores; expect carousel order is highest-first
    items = [
        {"id": "low",  "name": "Low",  "model_score": 0.1, "category": "Test"},
        {"id": "high", "name": "High", "model_score": 0.9, "category": "Test"},
        {"id": "mid",  "name": "Mid",  "model_score": 0.5, "category": "Test"},
        {"id": "top",  "name": "Top",  "model_score": 1.0, "category": "Test"},
    ]
    assignments = [{"id": i["id"], "primary": "c1", "secondary": None} for i in items]
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    carousel = result["clusters"][0]["carousel_items"]
    assert carousel[0] == "top"
    assert carousel[-1] == "low"


# ---------------------------------------------------------------------------
# 6. max_carousel cap: only 10 items in carousel_items even if 15 assigned
# ---------------------------------------------------------------------------

def test_carousel_capped_at_max_carousel():
    items = _items(15)
    assignments = _primary_assignments("c1", [f"item{i}" for i in range(15)])
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    carousel = result["clusters"][0]["carousel_items"]
    assert len(carousel) == 10  # max_carousel for "resources"


# ---------------------------------------------------------------------------
# 7. item_count matches total items assigned (not just carousel)
# ---------------------------------------------------------------------------

def test_item_count_reflects_all_assigned_not_just_carousel():
    items = _items(15)
    assignments = _primary_assignments("c1", [f"item{i}" for i in range(15)])
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    cluster = result["clusters"][0]
    assert cluster["item_count"] == 15
    assert len(cluster["carousel_items"]) == 10  # capped
    assert len(cluster["items"]) == 15            # full list


# ---------------------------------------------------------------------------
# 8. Unknown cluster_id in assignment → skipped (warning printed, no crash)
# ---------------------------------------------------------------------------

def test_unknown_cluster_id_skipped(capsys):
    items = _items(4)
    assignments = _primary_assignments("nonexistent", [f"item{i}" for i in range(4)])
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    assert result["total_clusters"] == 0
    captured = capsys.readouterr()
    assert "nonexistent" in captured.out or "Warning" in captured.out


# ---------------------------------------------------------------------------
# 9. primary == "error" or "none" → item not added to that cluster
# ---------------------------------------------------------------------------

def test_error_and_none_primaries_not_added():
    items = _items(4)
    assignments = [
        {"id": "item0", "primary": "error", "secondary": None},
        {"id": "item1", "primary": "none",  "secondary": None},
        {"id": "item2", "primary": None,    "secondary": None},
        # Only item3 goes to c1 — cluster size 1 < 4 → also filtered out
        {"id": "item3", "primary": "c1",    "secondary": None},
    ]
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    assert result["total_clusters"] == 0


# ---------------------------------------------------------------------------
# 10. secondary == "null" (string) → not added as secondary
# ---------------------------------------------------------------------------

def test_string_null_secondary_not_added():
    # Give c1 exactly 4 primary items; a "null" secondary should not inflate count
    items = _items(5)
    assignments = [
        {"id": "item0", "primary": "c1", "secondary": "null"},
        {"id": "item1", "primary": "c1", "secondary": "null"},
        {"id": "item2", "primary": "c1", "secondary": "null"},
        {"id": "item3", "primary": "c1", "secondary": "null"},
        # item4 has a valid secondary to a second cluster that exists but stays < min_size
        {"id": "item4", "primary": None, "secondary": "c2"},
    ]
    result = build_clusters_from_assignments(assignments, items, CLUSTER_DEFS, CONTENT_TYPE)
    # c1 should have exactly 4 items (the "null" secondaries are skipped)
    assert result["total_clusters"] == 1
    c1 = result["clusters"][0]
    assert c1["cluster_id"] == "c1"
    assert c1["item_count"] == 4
