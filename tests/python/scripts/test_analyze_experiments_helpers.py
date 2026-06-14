"""Bullshit tests for analyze_experiments.py pure helpers.

Covers: wilson_ci (unit interval, CI width, edge cases),
        two_prop_z (z-stat sign, p-value range, zero-var case),
        _phi (CDF properties), _verdict (threshold logic, sample guard).
"""

import importlib.util
import math
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "analyze_experiments.py"

# stub subprocess (wrangler calls) if needed
if "subprocess" not in sys.modules:
    pass  # stdlib, already available

_spec = importlib.util.spec_from_file_location("analyze_experiments", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["analyze_experiments"] = mod
_spec.loader.exec_module(mod)

wilson_ci = mod.wilson_ci
two_prop_z = mod.two_prop_z
_phi = mod._phi
_verdict = mod._verdict


# ──────────────────────────────────────────────
# _phi (standard normal CDF)
# ──────────────────────────────────────────────

class TestPhi:
    def test_zero_returns_half(self):
        assert _phi(0.0) == pytest.approx(0.5)

    def test_positive_x_above_half(self):
        assert _phi(1.96) > 0.5

    def test_negative_x_below_half(self):
        assert _phi(-1.96) < 0.5

    def test_large_positive_approaches_one(self):
        assert _phi(10.0) > 0.99

    def test_large_negative_approaches_zero(self):
        assert _phi(-10.0) < 0.01

    def test_symmetry(self):
        assert _phi(1.0) + _phi(-1.0) == pytest.approx(1.0)


# ──────────────────────────────────────────────
# wilson_ci
# ──────────────────────────────────────────────

class TestWilsonCI:
    def test_zero_trials_returns_zeros(self):
        assert wilson_ci(0, 0) == (0.0, 0.0)

    def test_ci_in_unit_interval(self):
        lo, hi = wilson_ci(50, 100)
        assert 0 <= lo <= hi <= 1.0

    def test_ci_width_shrinks_with_more_data(self):
        lo1, hi1 = wilson_ci(50, 100)
        lo2, hi2 = wilson_ci(500, 1000)
        assert (hi2 - lo2) < (hi1 - lo1)

    def test_perfect_click_rate(self):
        lo, hi = wilson_ci(100, 100)
        assert lo > 0.9  # CI lower bound well above 0

    def test_zero_clicks(self):
        lo, hi = wilson_ci(0, 100)
        assert lo == pytest.approx(0.0, abs=0.02)  # near 0

    def test_custom_z_widens_interval(self):
        lo95, hi95 = wilson_ci(50, 100, z=1.96)
        lo99, hi99 = wilson_ci(50, 100, z=2.576)
        assert (hi99 - lo99) > (hi95 - lo95)

    def test_midpoint_near_observed_proportion(self):
        lo, hi = wilson_ci(60, 100)
        midpoint = (lo + hi) / 2
        assert abs(midpoint - 0.60) < 0.05


# ──────────────────────────────────────────────
# two_prop_z
# ──────────────────────────────────────────────

class TestTwoPropZ:
    def test_zero_trials_returns_no_effect(self):
        z, p = two_prop_z(0, 0, 0, 0)
        assert z == 0.0
        assert p == 1.0

    def test_equal_proportions_no_effect(self):
        z, p = two_prop_z(50, 100, 50, 100)
        assert z == pytest.approx(0.0, abs=1e-10)
        assert p == pytest.approx(1.0, abs=0.01)

    def test_p_value_in_unit_interval(self):
        _, p = two_prop_z(60, 100, 40, 100)
        assert 0 <= p <= 1.0

    def test_larger_difference_smaller_p(self):
        _, p_small = two_prop_z(51, 100, 50, 100)
        _, p_large = two_prop_z(80, 100, 20, 100)
        assert p_large < p_small

    def test_z_sign_matches_direction(self):
        z_pos, _ = two_prop_z(70, 100, 30, 100)
        z_neg, _ = two_prop_z(30, 100, 70, 100)
        assert z_pos > 0
        assert z_neg < 0

    def test_large_samples_can_be_significant(self):
        _, p = two_prop_z(600, 1000, 500, 1000)
        assert p < 0.05


# ──────────────────────────────────────────────
# _verdict
# ──────────────────────────────────────────────

class TestVerdict:
    def test_insufficient_data_under_100(self):
        result = _verdict(p_value=0.001, delta=0.1, n1=50, n2=200)
        assert "insufficient" in result

    def test_treatment_wins_at_p_001(self):
        result = _verdict(p_value=0.005, delta=0.05, n1=500, n2=500)
        assert result == "treatment-wins"

    def test_control_wins_at_p_001_negative_delta(self):
        result = _verdict(p_value=0.005, delta=-0.05, n1=500, n2=500)
        assert result == "control-wins"

    def test_weak_signal_between_001_and_005(self):
        result = _verdict(p_value=0.03, delta=0.05, n1=500, n2=500)
        assert result == "weak signal"

    def test_no_effect_above_005(self):
        result = _verdict(p_value=0.5, delta=0.01, n1=500, n2=500)
        assert result == "no effect"

    def test_exactly_100_samples_not_insufficient(self):
        result = _verdict(p_value=0.5, delta=0.0, n1=100, n2=100)
        assert "insufficient" not in result
