"""Tests for pure helpers in scripts/cluster_topics.py.

Covers: generate_clean_label, dedupe_labels.
No network, no embeddings, no LLM calls.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "cluster_topics.py"
_spec = importlib.util.spec_from_file_location("cluster_topics", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["cluster_topics"] = mod
_spec.loader.exec_module(mod)

generate_clean_label = mod.generate_clean_label
dedupe_labels = mod.dedupe_labels


# ---------------------------------------------------------------------------
# generate_clean_label
# ---------------------------------------------------------------------------

class TestGenerateCleanLabel:

    def test_two_good_tags_joined(self):
        label = generate_clean_label(["causal-inference", "machine-learning"], ["ML"])
        assert "Causal Inference" in label
        assert "Machine Learning" in label
        assert "&" in label

    def test_hyphens_replaced_by_spaces(self):
        label = generate_clean_label(["deep-learning"], ["DL"])
        assert "Deep Learning" in label
        assert "-" not in label

    def test_title_case_applied(self):
        label = generate_clean_label(["time-series"], ["Stats"])
        assert label[0].isupper()

    def test_no_tags_falls_back_to_category(self):
        label = generate_clean_label([], ["Econometrics"])
        assert label == "Econometrics"

    def test_no_tags_no_categories_returns_miscellaneous(self):
        label = generate_clean_label([], [])
        assert label == "Miscellaneous"

    def test_skip_career_tags(self):
        label = generate_clean_label(["career-portal", "causal-inference"], ["ML"])
        assert "Career Portal" not in label
        assert "Causal Inference" in label

    def test_skip_job_search_tags(self):
        label = generate_clean_label(["job-search", "regression"], ["ML"])
        assert "Job Search" not in label
        assert "Regression" in label

    def test_dedupe_similar_tags(self):
        # "causal" and "causal-inference" are very similar; only one should appear
        label = generate_clean_label(["causal", "causal-inference", "bayesian"], ["ML"])
        # Should not have "Causal & Causal Inference"
        assert label.count("Causal") <= 1 or "Bayesian" in label

    def test_category_with_hierarchy_stripped(self):
        # Category "ML > Supervised Learning" → takes last part "Supervised Learning"
        label = generate_clean_label([], ["ML > Supervised Learning"])
        assert "Supervised Learning" in label
        assert ">" not in label

    def test_all_skip_tags_falls_back_to_category(self):
        label = generate_clean_label(["career-portal", "job-board", "hiring"], ["Statistics"])
        assert label == "Statistics"

    def test_max_two_tags(self):
        # Even with many good tags, max 2 used
        tags = ["causal", "inference", "bayesian", "machine-learning", "econometrics"]
        label = generate_clean_label(tags, ["ML"])
        # Should have at most 2 tags separated by " & "
        parts = label.split(" & ")
        assert len(parts) <= 2


# ---------------------------------------------------------------------------
# dedupe_labels
# ---------------------------------------------------------------------------

class TestDedupeLabels:

    def _make_cluster(self, label, top_categories=None, top_tags=None):
        return {
            "label": label,
            "top_categories": top_categories or [],
            "top_tags": top_tags or [],
        }

    def test_unique_labels_unchanged(self):
        clusters = [
            self._make_cluster("Causal Inference"),
            self._make_cluster("Machine Learning"),
        ]
        dedupe_labels(clusters)
        assert clusters[0]["label"] == "Causal Inference"
        assert clusters[1]["label"] == "Machine Learning"

    def test_duplicate_labels_differentiated(self):
        clusters = [
            self._make_cluster("Econometrics", top_categories=["IV Methods"]),
            self._make_cluster("Econometrics", top_categories=["Panel Data"]),
        ]
        dedupe_labels(clusters)
        labels = {c["label"] for c in clusters}
        assert len(labels) == 2  # Both unique after dedup

    def test_uses_category_as_differentiator(self):
        clusters = [
            self._make_cluster("ML Methods", top_categories=["Tree Models"]),
            self._make_cluster("ML Methods", top_categories=["Neural Networks"]),
        ]
        dedupe_labels(clusters)
        labels = [c["label"] for c in clusters]
        assert any("Tree" in l or "Neural" in l for l in labels)

    def test_numeric_suffix_as_last_resort(self):
        clusters = [
            self._make_cluster("Generic"),
            self._make_cluster("Generic"),
            self._make_cluster("Generic"),
        ]
        dedupe_labels(clusters)
        labels = [c["label"] for c in clusters]
        # All must be unique
        assert len(set(labels)) == 3

    def test_single_cluster_unchanged(self):
        clusters = [self._make_cluster("Unique Label")]
        dedupe_labels(clusters)
        assert clusters[0]["label"] == "Unique Label"

    def test_empty_list_no_error(self):
        dedupe_labels([])
