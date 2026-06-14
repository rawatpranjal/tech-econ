"""Bullshit tests for rank_all_content.py pure helpers.

Covers: extract_item_name_from_path, extract_url_domain, safe_join
These are pure functions with no network/filesystem/ML dependencies.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "rank_all_content.py"

# Stub every heavy dep before the module loads
_heavy = [
    "lightgbm", "sklearn", "sklearn.preprocessing",
    "sklearn.model_selection", "sklearn.metrics",
    "sklearn.feature_extraction", "sklearn.feature_extraction.text",
    "sentence_transformers", "torch",
    "scipy", "scipy.sparse", "scipy.stats",
]
for _name in _heavy:
    if _name not in sys.modules:
        _s = types.ModuleType(_name)
        _s.__getattr__ = lambda attr, n=_name: MagicMock()
        sys.modules[_name] = _s

# numpy: real is available; if not, stub it
try:
    import numpy as np  # noqa: F401
except ImportError:
    _np = types.ModuleType("numpy")
    _np.array = list
    _np.zeros = lambda *a, **k: []
    sys.modules["numpy"] = _np

_spec = importlib.util.spec_from_file_location("rank_all_content", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["rank_all_content"] = mod
_spec.loader.exec_module(mod)

extract_item_name = mod.extract_item_name_from_path
extract_url_domain = mod.extract_url_domain
safe_join = mod.safe_join
normalize_scores = mod.normalize_scores
apply_citations_boost = mod.apply_citations_boost
CITATION_WEIGHT = mod.CITATION_WEIGHT


# ──────────────────────────────────────────────
# extract_item_name_from_path
# ──────────────────────────────────────────────

class TestExtractItemNameFromPath:
    def test_standard_path(self):
        assert extract_item_name("/packages/double-ml") == "double ml"

    def test_trailing_slash_ignored(self):
        assert extract_item_name("/packages/double-ml/") == "double ml"

    def test_underscore_becomes_space(self):
        result = extract_item_name("/resources/causal_forest")
        assert "causal forest" in result

    def test_lowercased(self):
        assert extract_item_name("/packages/EconML") == "econml"

    def test_hyphens_become_spaces(self):
        result = extract_item_name("/talks/causal-inference-101")
        assert "-" not in result

    def test_single_segment_returns_none(self):
        # Only one segment (no /section/name form)
        assert extract_item_name("/packages") is None

    def test_empty_returns_none(self):
        assert extract_item_name("") is None

    def test_none_returns_none(self):
        assert extract_item_name(None) is None

    def test_deep_path_uses_last_segment(self):
        result = extract_item_name("/packages/causal/double-ml")
        assert result == "double ml"


# ──────────────────────────────────────────────
# extract_url_domain
# ──────────────────────────────────────────────

class TestExtractUrlDomain:
    def test_github_url(self):
        assert extract_url_domain("https://github.com/microsoft/EconML") == "github"

    def test_arxiv_url(self):
        assert extract_url_domain("https://arxiv.org/abs/1234.5678") == "arxiv"

    def test_youtube_url(self):
        assert extract_url_domain("https://www.youtube.com/watch?v=xyz") == "youtube"

    def test_kaggle_url(self):
        assert extract_url_domain("https://kaggle.com/datasets/foo") == "kaggle"

    def test_medium_url(self):
        assert extract_url_domain("https://medium.com/@user/post") == "medium"

    def test_substack_url(self):
        assert extract_url_domain("https://user.substack.com/p/article") == "substack"

    def test_other_domain_returns_other(self):
        assert extract_url_domain("https://econometrics.org/paper") == "other"

    def test_empty_returns_none(self):
        assert extract_url_domain("") == "none"

    def test_none_returns_none(self):
        assert extract_url_domain(None) == "none"

    def test_returns_lowercase(self):
        result = extract_url_domain("https://GITHUB.COM/foo/bar")
        assert result == result.lower()


# ──────────────────────────────────────────────
# safe_join
# ──────────────────────────────────────────────

class TestSafeJoin:
    def test_list_joined_with_spaces(self):
        assert safe_join(["causal", "ml", "econ"]) == "causal ml econ"

    def test_string_returned_unchanged(self):
        assert safe_join("already a string") == "already a string"

    def test_none_returns_empty(self):
        assert safe_join(None) == ""

    def test_empty_list_returns_empty(self):
        assert safe_join([]) == ""

    def test_none_values_in_list_skipped(self):
        result = safe_join([None, "causal", None, "ml"])
        assert "causal" in result
        assert "ml" in result

    def test_number_coerced_to_string(self):
        result = safe_join([1, 2, 3])
        assert "1" in result and "2" in result

    def test_non_string_non_list_coerced(self):
        result = safe_join(42)
        assert result == "42"


# ──────────────────────────────────────────────
# normalize_scores
# ──────────────────────────────────────────────

class TestNormalizeScores:
    def test_empty_returns_empty(self):
        assert normalize_scores({}) == {}

    def test_all_equal_returns_half(self):
        scores = {"a": 5.0, "b": 5.0, "c": 5.0}
        result = normalize_scores(scores)
        assert all(v == 0.5 for v in result.values())

    def test_normalizes_to_zero_one_range(self):
        scores = {"a": 0.0, "b": 0.5, "c": 1.0}
        result = normalize_scores(scores)
        assert result["a"] == 0.0
        assert result["c"] == 1.0

    def test_middle_value_is_proportional(self):
        scores = {"low": 10.0, "mid": 15.0, "high": 20.0}
        result = normalize_scores(scores)
        assert abs(result["mid"] - 0.5) < 1e-9

    def test_preserves_all_keys(self):
        scores = {"x": 1, "y": 2, "z": 3}
        result = normalize_scores(scores)
        assert set(result.keys()) == {"x", "y", "z"}

    def test_single_item_returns_half(self):
        result = normalize_scores({"only": 7.0})
        assert result["only"] == 0.5

    def test_negative_scores_handled(self):
        scores = {"a": -10.0, "b": 0.0, "c": 10.0}
        result = normalize_scores(scores)
        assert result["a"] == 0.0
        assert result["c"] == 1.0


# ──────────────────────────────────────────────
# apply_citations_boost
# ──────────────────────────────────────────────

import math as _math

class TestApplyCitationsBoost:

    def _paper(self, name, citations):
        return {"type": "paper", "name": name, "citations": citations}

    def _non_paper(self, name):
        return {"type": "package", "name": name, "citations": 100}

    def test_non_paper_items_not_boosted(self):
        items = [self._non_paper("SomeTool")]
        scores = {}
        result = apply_citations_boost(items, scores)
        assert "SomeTool" not in result

    def test_paper_with_citations_gets_score(self):
        items = [self._paper("Great Paper", 500)]
        scores = {}
        result = apply_citations_boost(items, scores)
        assert "Great Paper" in result
        assert result["Great Paper"] > 0

    def test_paper_with_zero_citations_not_added(self):
        items = [self._paper("No Cites", 0)]
        scores = {}
        result = apply_citations_boost(items, scores)
        assert "No Cites" not in result

    def test_existing_score_boosted(self):
        items = [self._paper("Paper A", 100)]
        scores = {"Paper A": 0.2}
        result = apply_citations_boost(items, scores)
        assert result["Paper A"] > 0.2

    def test_score_capped_at_1(self):
        items = [self._paper("Hot Paper", 99999)]
        scores = {"Hot Paper": 0.95}
        result = apply_citations_boost(items, scores)
        assert result["Hot Paper"] <= 1.0

    def test_max_citations_paper_gets_full_weight(self):
        # With only one paper, it IS the max — boost = CITATION_WEIGHT
        items = [self._paper("Top Paper", 1000)]
        scores = {"Top Paper": 0.0}
        result = apply_citations_boost(items, scores)
        expected = min(1.0, CITATION_WEIGHT)
        assert abs(result["Top Paper"] - expected) < 1e-9

    def test_returns_same_dict_object(self):
        items = [self._paper("P1", 50)]
        scores = {"P1": 0.1}
        returned = apply_citations_boost(items, scores)
        assert returned is scores

    def test_empty_items_returns_scores_unchanged(self):
        scores = {"existing": 0.5}
        result = apply_citations_boost([], scores)
        assert result == {"existing": 0.5}

    def test_none_citations_treated_as_zero(self):
        items = [{"type": "paper", "name": "P", "citations": None}]
        scores = {}
        result = apply_citations_boost(items, scores)
        assert "P" not in result
