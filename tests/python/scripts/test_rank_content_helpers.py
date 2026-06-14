"""Bullshit tests for rank_content.py pure helpers.

Covers: wilson_lower_bound, normalize, log_scale
All three are pure math functions — no network, no filesystem.
"""

import importlib.util
import math
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "rank_content.py"
_spec = importlib.util.spec_from_file_location("rank_content", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["rank_content"] = mod
_spec.loader.exec_module(mod)

wilson_lower_bound = mod.wilson_lower_bound
normalize = mod.normalize
log_scale = mod.log_scale


# ──────────────────────────────────────────────
# wilson_lower_bound
# ──────────────────────────────────────────────

class TestWilsonLowerBound:
    def test_zero_impressions_returns_zero(self):
        assert wilson_lower_bound(0, 0) == 0

    def test_perfect_click_rate_positive(self):
        result = wilson_lower_bound(100, 100)
        assert 0 < result <= 1.0

    def test_zero_clicks_returns_nonnegative(self):
        result = wilson_lower_bound(0, 100)
        assert result >= 0

    def test_result_in_unit_interval(self):
        for pos, n in [(10, 100), (50, 100), (1, 1000), (999, 1000)]:
            result = wilson_lower_bound(pos, n)
            assert 0 <= result <= 1.0, f"Out of bounds for pos={pos}, n={n}"

    def test_higher_click_rate_higher_bound(self):
        low = wilson_lower_bound(5, 100)
        high = wilson_lower_bound(50, 100)
        assert high > low

    def test_larger_sample_tighter_bound(self):
        # Same CTR (50%) but 1000 vs 100 samples
        small = wilson_lower_bound(50, 100)
        large = wilson_lower_bound(500, 1000)
        # Larger sample → lower bound is higher (more confident)
        assert large > small

    def test_custom_z_score(self):
        r99 = wilson_lower_bound(50, 100, z=2.58)  # 99% CI
        r95 = wilson_lower_bound(50, 100, z=1.96)  # 95% CI
        # Higher z → wider interval → lower bound is lower
        assert r99 < r95

    def test_symmetry_around_half(self):
        # 10/100 vs 90/100: lower bound of 90/100 should be much higher
        low = wilson_lower_bound(10, 100)
        high = wilson_lower_bound(90, 100)
        assert high > 0.7  # well above 0.5
        assert low < 0.2   # well below 0.5


# ──────────────────────────────────────────────
# normalize
# ──────────────────────────────────────────────

class TestNormalize:
    def test_empty_input_returns_empty(self):
        assert normalize([]) == []

    def test_single_value_returns_half(self):
        # All equal → constant 0.5
        assert normalize([7]) == [0.5]

    def test_two_values_min_max(self):
        result = normalize([0, 10])
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0)

    def test_all_equal_returns_half_list(self):
        result = normalize([5, 5, 5])
        assert all(v == 0.5 for v in result)

    def test_result_bounded_to_unit_interval(self):
        values = [1, 5, 3, 9, 2, 7]
        result = normalize(values)
        assert min(result) == pytest.approx(0.0)
        assert max(result) == pytest.approx(1.0)

    def test_preserves_order(self):
        values = [10, 20, 30]
        result = normalize(values)
        assert result[0] < result[1] < result[2]

    def test_length_unchanged(self):
        values = list(range(10))
        assert len(normalize(values)) == len(values)

    def test_negative_values_handled(self):
        result = normalize([-5, 0, 5])
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)


# ──────────────────────────────────────────────
# log_scale
# ──────────────────────────────────────────────

class TestLogScale:
    def test_zero_returns_zero(self):
        # log(0+1, 10) / log(100, 10) = 0/2 = 0
        assert log_scale(0) == pytest.approx(0.0)

    def test_100_clicks_returns_approx_one(self):
        # log(101, 10) / log(100, 10) ≈ 1.002 / 2 ≈ 1.001... effectively ~1
        result = log_scale(100)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_monotonically_increasing(self):
        values = [0, 1, 10, 50, 100, 500]
        results = [log_scale(v) for v in values]
        for i in range(len(results) - 1):
            assert results[i] < results[i + 1], f"Not monotone at index {i}"

    def test_returns_nonnegative(self):
        for v in [0, 1, 5, 10, 100, 1000]:
            assert log_scale(v) >= 0

    def test_custom_base_changes_result(self):
        r10 = log_scale(10, base=10)
        r2  = log_scale(10, base=2)
        # Different bases → different scale normalization
        assert r10 != r2
