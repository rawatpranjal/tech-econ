"""Tests for pure math helpers in scripts/rank_content.py."""

from __future__ import annotations

import importlib.util
import sys
import math
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "rank_content_mod", _REPO_ROOT / "scripts" / "rank_content.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["rank_content_mod"] = mod
_spec.loader.exec_module(mod)

wilson_lower_bound = mod.wilson_lower_bound
normalize = mod.normalize
log_scale = mod.log_scale


# ---------------------------------------------------------------------------
# wilson_lower_bound
# ---------------------------------------------------------------------------
class TestWilsonLowerBound:
    def test_zero_n_returns_zero(self):
        assert wilson_lower_bound(0, 0) == 0

    def test_all_positive_below_phat(self):
        # Lower bound is always ≤ phat
        result = wilson_lower_bound(80, 100)
        assert result <= 0.8

    def test_result_in_unit_interval(self):
        result = wilson_lower_bound(50, 100)
        assert 0.0 <= result <= 1.0

    def test_more_observations_tighter_bound(self):
        # Same CTR, more observations → lower bound closer to phat
        lb_small = wilson_lower_bound(5, 10)
        lb_large = wilson_lower_bound(500, 1000)
        assert lb_large > lb_small

    def test_zero_clicks_returns_zero(self):
        result = wilson_lower_bound(0, 100)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_perfect_ctr_below_one(self):
        # 100/100 CTR — lower bound is < 1 due to uncertainty
        result = wilson_lower_bound(100, 100)
        assert result < 1.0
        assert result > 0.9  # tight bound

    def test_returns_float(self):
        assert isinstance(wilson_lower_bound(50, 100), float)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------
class TestNormalize:
    def test_empty_returns_empty(self):
        assert normalize([]) == []

    def test_all_equal_returns_half(self):
        assert normalize([5, 5, 5]) == [0.5, 0.5, 0.5]

    def test_min_max_range(self):
        result = normalize([0, 50, 100])
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)

    def test_single_value_is_half(self):
        assert normalize([42]) == [0.5]

    def test_output_length_matches_input(self):
        assert len(normalize([1, 2, 3, 4, 5])) == 5

    def test_negative_values_handled(self):
        result = normalize([-10, 0, 10])
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# log_scale
# ---------------------------------------------------------------------------
class TestLogScale:
    def test_zero_returns_zero(self):
        assert log_scale(0) == pytest.approx(0.0)

    def test_100_returns_approximately_one(self):
        # log(101, 10) / log(100, 10) ≈ 1.0
        result = log_scale(100)
        assert result == pytest.approx(1.0, rel=0.01)

    def test_monotonically_increasing(self):
        results = [log_scale(v) for v in [0, 1, 10, 100]]
        for a, b in zip(results, results[1:]):
            assert b > a

    def test_returns_float(self):
        assert isinstance(log_scale(5), float)

    def test_no_zero_division_at_one(self):
        # log(2)/log(100) should not raise
        result = log_scale(1)
        assert result > 0
