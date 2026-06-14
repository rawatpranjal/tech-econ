"""Bullshit tests for assign_to_clusters.py :: build_clusters_from_assignments.

Covers:
  - Basic cluster construction from assignments
  - min_cluster_size filtering
  - secondary assignment dedup
  - unknown cluster_id warning (no crash)
  - carousel_items capped at max_carousel
  - items sorted by model_score descending in carousel
  - output schema keys present
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: MagicMock()
    sys.modules[name] = m
    return m


for _dep in ["openai", "anthropic", "requests"]:
    if _dep not in sys.modules:
        _stub(_dep)

_spec = importlib.util.spec_from_file_location(
    "assign_to_clusters", _REPO_ROOT / "scripts" / "assign_to_clusters.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["assign_to_clusters"] = _mod
_spec.loader.exec_module(_mod)

build_clusters_from_assignments = _mod.build_clusters_from_assignments


def _cluster_defs(cluster_ids):
    return {
        "clusters": [
            {"id": cid, "label": f"Label {cid}", "macro_category": "ML"}
            for cid in cluster_ids
        ]
    }


def _items(names_scores):
    return [{"id": n, "name": n, "model_score": s, "category": "ML"} for n, s in names_scores]


def _assignments(items_cluster_pairs):
    return [{"id": n, "primary": c, "secondary": None} for n, c in items_cluster_pairs]


class TestBuildClustersFromAssignments:
    def test_basic_cluster_built(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)])
        assignments = _assignments([("a", "ml"), ("b", "ml"), ("c", "ml"), ("d", "ml")])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        assert result["total_clusters"] == 1
        assert result["clusters"][0]["cluster_id"] == "ml"

    def test_output_schema_keys(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)])
        assignments = _assignments([("a", "ml"), ("b", "ml"), ("c", "ml"), ("d", "ml")])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        c = result["clusters"][0]
        for key in ["id", "label", "cluster_id", "macro_category", "item_count", "items", "carousel_items"]:
            assert key in c, f"Missing key: {key}"

    def test_min_cluster_size_filters_small_clusters(self):
        # resources min_cluster_size = 4; give only 3 items
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7)])
        assignments = _assignments([("a", "ml"), ("b", "ml"), ("c", "ml")])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        assert result["total_clusters"] == 0

    def test_min_cluster_size_talks_is_3(self):
        # talks min_cluster_size = 3
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7)])
        assignments = _assignments([("a", "ml"), ("b", "ml"), ("c", "ml")])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "talks")
        assert result["total_clusters"] == 1

    def test_carousel_capped_at_max_carousel(self):
        # resources max_carousel = 10; give 15 items
        items = _items([(f"item{i}", 1.0 - i * 0.05) for i in range(15)])
        assignments = _assignments([(f"item{i}", "ml") for i in range(15)])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        carousel = result["clusters"][0]["carousel_items"]
        assert len(carousel) <= 10

    def test_carousel_items_sorted_by_score_desc(self):
        items = _items([("low", 0.1), ("high", 0.9), ("mid", 0.5), ("top", 1.0)])
        assignments = _assignments([("low", "ml"), ("high", "ml"), ("mid", "ml"), ("top", "ml")])
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        carousel = result["clusters"][0]["carousel_items"]
        assert carousel[0] == "top"
        assert carousel[-1] == "low"

    def test_secondary_assignment_adds_to_cluster(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6), ("x", 0.5)])
        assignments = [
            {"id": "a", "primary": "ml", "secondary": None},
            {"id": "b", "primary": "ml", "secondary": None},
            {"id": "c", "primary": "ml", "secondary": None},
            {"id": "d", "primary": "ml", "secondary": None},
            {"id": "x", "primary": None, "secondary": "ml"},  # secondary only
        ]
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        assert result["clusters"][0]["item_count"] == 5

    def test_secondary_deduped(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)])
        # "a" is in both primary and secondary for "ml"
        assignments = [
            {"id": "a", "primary": "ml", "secondary": "ml"},
            {"id": "b", "primary": "ml", "secondary": None},
            {"id": "c", "primary": "ml", "secondary": None},
            {"id": "d", "primary": "ml", "secondary": None},
        ]
        cluster_defs = _cluster_defs(["ml"])
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        # "a" should appear only once
        all_items = result["clusters"][0]["items"]
        assert all_items.count("a") == 1

    def test_unknown_cluster_id_skipped_no_crash(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)])
        assignments = _assignments([("a", "unknown_cluster"), ("b", "unknown_cluster"),
                                    ("c", "unknown_cluster"), ("d", "unknown_cluster")])
        cluster_defs = _cluster_defs(["ml"])  # "unknown_cluster" not in defs
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        assert result["total_clusters"] == 0

    def test_none_and_error_primaries_ignored(self):
        items = _items([("a", 0.9), ("b", 0.8), ("c", 0.7), ("d", 0.6)])
        assignments = [
            {"id": "a", "primary": "none", "secondary": None},
            {"id": "b", "primary": "error", "secondary": None},
            {"id": "c", "primary": None, "secondary": None},
            {"id": "d", "primary": "ml", "secondary": None},
        ]
        cluster_defs = _cluster_defs(["ml"])
        # Only "d" goes to "ml" → cluster size 1 < 4 → filtered out
        result = build_clusters_from_assignments(assignments, items, cluster_defs, "resources")
        assert result["total_clusters"] == 0
