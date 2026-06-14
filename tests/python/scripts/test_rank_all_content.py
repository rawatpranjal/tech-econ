"""Tests for pure helper functions in scripts/rank_all_content.py.

Heavy ML dependencies (lightgbm, SentenceTransformer) are stubbed out
before loading so the module can be imported without network calls or GPU
time. Only pure utility functions are tested here; the ML training path
is not exercised.
"""

from __future__ import annotations

import importlib.util
import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

# --- stub heavy deps before module load ------------------------------------
sys.modules.setdefault("lightgbm", MagicMock())
# Patch SentenceTransformer before sentence_transformers is imported by the module
_st_mock = MagicMock()
_st_mock.encode = MagicMock(return_value=[])
import sentence_transformers as _st_pkg
_orig_sbert = getattr(_st_pkg, "SentenceTransformer", None)
_st_pkg.SentenceTransformer = MagicMock(return_value=_st_mock)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "rank_all_content.py"

_spec = importlib.util.spec_from_file_location("rank_all_content_mod", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["rank_all_content_mod"] = mod

import io
import contextlib

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _spec.loader.exec_module(mod)

extract_item_name_from_path = mod.extract_item_name_from_path
safe_join = mod.safe_join
build_engagement_scores = mod.build_engagement_scores

CLICK_W = mod.CLICK_WEIGHT
IMPRESSION_W = mod.IMPRESSION_WEIGHT
DWELL_W = mod.DWELL_WEIGHT
RAGE_CLICK_W = mod.RAGE_CLICK_WEIGHT
READING_RATIO_W = mod.READING_RATIO_WEIGHT
COVIEW_W = mod.COVIEW_WEIGHT
COCLICK_W = mod.COCLICK_WEIGHT


# ---------------------------------------------------------------------------
# extract_item_name_from_path
# ---------------------------------------------------------------------------
class TestExtractItemNameFromPath:
    def test_standard_two_segment_path(self):
        assert extract_item_name_from_path("/packages/causal-inference") == "causal inference"

    def test_hyphens_and_underscores_to_spaces(self):
        assert extract_item_name_from_path("/talks/my_cool_talk") == "my cool talk"

    def test_result_is_lowercased(self):
        assert extract_item_name_from_path("/resources/My-Package") == "my package"

    def test_three_segment_path_uses_last(self):
        assert extract_item_name_from_path("/papers/causal/diff-in-diff") == "diff in diff"

    def test_single_segment_returns_none(self):
        # Only one segment after stripping slash
        assert extract_item_name_from_path("/packages") is None

    def test_empty_string_returns_none(self):
        assert extract_item_name_from_path("") is None

    def test_none_returns_none(self):
        assert extract_item_name_from_path(None) is None

    def test_no_leading_slash(self):
        # Parts still split correctly
        assert extract_item_name_from_path("packages/foo") == "foo"


# ---------------------------------------------------------------------------
# safe_join
# ---------------------------------------------------------------------------
class TestSafeJoin:
    def test_none_returns_empty(self):
        assert safe_join(None) == ""

    def test_string_passthrough(self):
        assert safe_join("hello world") == "hello world"

    def test_list_joined_by_space(self):
        assert safe_join(["foo", "bar", "baz"]) == "foo bar baz"

    def test_list_with_none_entries_skipped(self):
        assert safe_join(["a", None, "b"]) == "a b"

    def test_list_with_empty_strings_skipped(self):
        assert safe_join(["a", "", "b"]) == "a b"

    def test_empty_list_returns_empty(self):
        assert safe_join([]) == ""

    def test_integer_converted_to_str(self):
        assert safe_join(42) == "42"

    def test_list_of_ints_joined(self):
        assert safe_join([1, 2, 3]) == "1 2 3"


# ---------------------------------------------------------------------------
# build_engagement_scores
# ---------------------------------------------------------------------------
class TestBuildEngagementScores:
    def _run(self, **kwargs):
        """Call with keyword-named engagement buckets."""
        return build_engagement_scores(kwargs)

    def test_empty_input_returns_empty_dicts(self):
        scores, signals, _ = self._run()
        assert scores == {}
        assert signals == {}

    def test_clicks_weighted(self):
        scores, signals, _ = self._run(
            clicks=[{"name": "foo pkg", "click_count": 10}]
        )
        assert scores["foo pkg"] == pytest.approx(10 * CLICK_W)
        assert signals["foo pkg"]["clicks"] == 10

    def test_impressions_weighted(self):
        # 100 impressions: impression bonus = 100 × 0.5 = 50.0
        # But 100 ≥ HIGH_IMP_NO_CLICK_THRESHOLD(10) with 0 clicks → penalty = -1.0 × (100/10) = -10
        # Net = max(0, 50 - 10) = 40.0
        threshold = mod.HIGH_IMP_NO_CLICK_THRESHOLD
        penalty = mod.HIGH_IMP_NO_CLICK_WEIGHT * (100 / threshold)
        expected = max(0.0, 100 * IMPRESSION_W + penalty)
        scores, signals, _ = self._run(
            impressions=[{"name": "bar", "impression_count": 100}]
        )
        assert scores["bar"] == pytest.approx(expected)

    def test_name_lowercased(self):
        scores, _, _ = self._run(
            clicks=[{"name": "MyPkg", "click_count": 1}]
        )
        assert "mypkg" in scores
        assert "MyPkg" not in scores

    def test_dwell_minutes_weighted(self):
        # 60000 ms = 1 minute
        scores, signals, _ = self._run(
            dwell=[{"name": "pkg", "total_dwell": 60000, "total_viewable": 0}]
        )
        assert scores["pkg"] == pytest.approx(1.0 * DWELL_W)
        assert signals["pkg"]["dwell_ms"] == 60000

    def test_rage_clicks_negative_then_floored(self):
        # rage click adds RAGE_CLICK_WEIGHT (negative) to score
        # The function floors scores at 0 at the end
        scores, signals, _ = self._run(
            frustration=[{"path": "/packages/my-item", "event_type": "rage_click", "count": 5}]
        )
        # Score should be floored at 0 (never negative)
        assert scores.get("my item", 0.0) >= 0.0
        assert signals["my item"]["rage_clicks"] == 5

    def test_reading_ratio_capped_at_2(self):
        scores, signals, _ = self._run(
            reading_ratio=[{"name": "item", "avg_reading_ratio": 99.0}]
        )
        # Capped at 2.0 × weight
        assert scores["item"] == pytest.approx(2.0 * READING_RATIO_W)
        assert signals["item"]["reading_ratio"] == 2.0

    def test_cooccurrence_boosts_both_items(self):
        scores, signals, _ = self._run(
            cooccurrence=[{"item_a": "alpha", "item_b": "beta",
                           "coview_count": 10, "coclick_count": 5}]
        )
        expected = 10 * COVIEW_W + 5 * COCLICK_W
        assert scores["alpha"] == pytest.approx(expected)
        assert scores["beta"] == pytest.approx(expected)
        assert signals["alpha"]["coviews"] == 10
        assert signals["beta"]["coviews"] == 10

    def test_high_imp_no_click_penalty(self):
        threshold = mod.HIGH_IMP_NO_CLICK_THRESHOLD
        penalty_w = mod.HIGH_IMP_NO_CLICK_WEIGHT
        # threshold impressions → bonus = threshold × 0.5; penalty = -1.0 × 1.0 = -1.0
        # Net = max(0, threshold × 0.5 - 1.0)
        expected = max(0.0, threshold * IMPRESSION_W + penalty_w * (threshold / threshold))
        scores_before, signals, _ = self._run(
            impressions=[{"name": "ghost", "impression_count": threshold}],
            clicks=[]
        )
        assert scores_before.get("ghost", 0.0) == pytest.approx(expected)
        assert signals["ghost"]["high_imp_no_click"] is True

    def test_multiple_signals_accumulate(self):
        scores, _, _ = self._run(
            clicks=[{"name": "item", "click_count": 2}],
            impressions=[{"name": "item", "impression_count": 50}],
        )
        expected = 2 * CLICK_W + 50 * IMPRESSION_W
        assert scores["item"] == pytest.approx(expected)
