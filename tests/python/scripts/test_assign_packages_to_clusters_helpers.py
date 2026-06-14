"""Bullshit tests for assign_packages_to_clusters.py pure helpers.

Covers: build_clusters_from_assignments, save_csv_for_review, load_reviewed_csv.
Stubs: openai (heavy import at module top).
"""

import csv
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "assign_packages_to_clusters.py"

# Stub openai and asyncio-heavy deps
for _name in ["openai"]:
    if _name not in sys.modules:
        _s = types.ModuleType(_name)
        _s.__getattr__ = lambda attr: MagicMock()
        sys.modules[_name] = _s

_spec = importlib.util.spec_from_file_location("assign_packages_to_clusters", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["assign_packages_to_clusters"] = mod
_spec.loader.exec_module(mod)

build_clusters = mod.build_clusters_from_assignments
save_csv = mod.save_csv_for_review
load_csv = mod.load_reviewed_csv


# ── helpers ──────────────────────────────────────────────────────────────────

def _cluster_defs(*cluster_ids):
    return {
        "clusters": [
            {"id": c, "label": f"Label for {c}", "macro_category": "ML"}
            for c in cluster_ids
        ]
    }


def _packages(*names, score=0.5, category="ML", language="Python"):
    return [{"name": n, "model_score": score, "category": category, "language": language}
            for n in names]


def _assignments(items):
    """items = list of (name, primary) or (name, primary, secondary)."""
    result = []
    for item in items:
        name = item[0]; primary = item[1]
        secondary = item[2] if len(item) > 2 else None
        result.append({"id": name.lower(), "name": name, "primary": primary, "secondary": secondary, "confidence": "high", "status": "ok"})
    return result


# ── build_clusters_from_assignments ─────────────────────────────────────────

def _clusters(result):
    """Extract the clusters list from the return value."""
    return result["clusters"]


class TestBuildClustersFromAssignments:
    def test_returns_dict_with_clusters_key(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("ml-causal")
        assigns = _assignments([("A", "ml-causal"), ("B", "ml-causal"),
                                 ("C", "ml-causal"), ("D", "ml-causal")])
        result = build_clusters(assigns, pkgs, defs)
        assert isinstance(result, dict)
        assert "clusters" in result

    def test_basic_cluster_built(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("ml-causal")
        assigns = _assignments([("A", "ml-causal"), ("B", "ml-causal"),
                                 ("C", "ml-causal"), ("D", "ml-causal")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 1
        assert clusters[0]["cluster_id"] == "ml-causal"

    def test_min_4_items_enforced(self):
        pkgs = _packages("A", "B", "C")
        defs = _cluster_defs("ml-causal")
        assigns = _assignments([("A", "ml-causal"), ("B", "ml-causal"), ("C", "ml-causal")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 0  # only 3 items → skipped

    def test_unknown_cluster_skipped(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("known-cluster")
        assigns = _assignments([("A", "unknown-id"), ("B", "unknown-id"),
                                 ("C", "unknown-id"), ("D", "unknown-id")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 0

    def test_none_primary_filtered(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("ml-causal")
        assigns = _assignments([("A", "none"), ("B", "none"), ("C", "none"), ("D", "none")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 0

    def test_error_primary_filtered(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("ml-causal")
        assigns = _assignments([("A", "error"), ("B", "error"), ("C", "error"), ("D", "error")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 0

    def test_secondary_adds_to_cluster(self):
        pkgs = _packages("A", "B", "C", "D", "E")
        defs = _cluster_defs("causal", "ml")
        assigns = _assignments([
            ("A", "causal"), ("B", "causal"), ("C", "causal"), ("D", "causal"),
            ("E", "ml", "causal"),  # E has secondary=causal
        ])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        causal_cluster = next((c for c in clusters if c["cluster_id"] == "causal"), None)
        assert causal_cluster is not None
        assert "E" in causal_cluster["items"]

    def test_carousel_items_capped_at_10(self):
        pkgs = _packages(*[f"pkg{i}" for i in range(15)])
        defs = _cluster_defs("big-cluster")
        assigns = _assignments([(f"pkg{i}", "big-cluster") for i in range(15)])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        assert len(clusters) == 1
        assert len(clusters[0]["carousel_items"]) <= 10

    def test_items_sorted_by_model_score(self):
        pkgs = [
            {"name": "Low", "model_score": 0.1, "category": "ML", "language": "Python"},
            {"name": "High", "model_score": 0.9, "category": "ML", "language": "Python"},
            {"name": "Med", "model_score": 0.5, "category": "ML", "language": "Python"},
            {"name": "Med2", "model_score": 0.5, "category": "ML", "language": "Python"},
        ]
        defs = _cluster_defs("sorted")
        assigns = _assignments([("Low", "sorted"), ("High", "sorted"), ("Med", "sorted"), ("Med2", "sorted")])
        clusters = _clusters(build_clusters(assigns, pkgs, defs))
        carousel = clusters[0]["carousel_items"]
        assert carousel[0] == "High"

    def test_total_clusters_in_metadata(self):
        pkgs = _packages("A", "B", "C", "D")
        defs = _cluster_defs("cl1")
        assigns = _assignments([("A", "cl1"), ("B", "cl1"), ("C", "cl1"), ("D", "cl1")])
        result = build_clusters(assigns, pkgs, defs)
        assert result["total_clusters"] == 1


# ── save_csv_for_review and load_reviewed_csv ───────────────────────────────

class TestCsvRoundtrip:
    def test_save_then_load_roundtrip(self, tmp_path):
        data = [
            {"id": "a", "name": "ToolA", "category": "ML", "language": "Python",
             "primary": "ml-causal", "secondary": "none", "confidence": "high", "status": "ok"},
            {"id": "b", "name": "ToolB", "category": "Stats", "language": "R",
             "primary": "stats-methods", "secondary": "none", "confidence": "medium", "status": "ok"},
        ]
        path = tmp_path / "review.csv"
        save_csv(data, path)
        loaded = load_csv(path)
        assert len(loaded) == 2
        assert loaded[0]["name"] == "ToolA"
        assert loaded[1]["name"] == "ToolB"

    def test_loaded_items_are_dicts(self, tmp_path):
        data = [{"id": "x", "name": "X", "category": "C", "language": "L",
                 "primary": "p", "secondary": "s", "confidence": "h", "status": "ok"}]
        path = tmp_path / "review.csv"
        save_csv(data, path)
        loaded = load_csv(path)
        assert isinstance(loaded[0], dict)
