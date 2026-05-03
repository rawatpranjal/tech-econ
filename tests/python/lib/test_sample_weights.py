"""Tests for lib.sample_weights (Ra1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lib.sample_weights import compute_sample_weights


def test_empty_input_returns_empty_array():
    out = compute_sample_weights(np.array([]))
    assert out.shape == (0,)
    assert out.dtype == np.float64


def test_negatives_get_unit_weight():
    # All-zero engagement → all-1.0 weights (preserves negative class)
    out = compute_sample_weights(np.array([0.0, 0.0, 0.0]))
    np.testing.assert_array_equal(out, np.array([1.0, 1.0, 1.0]))


def test_positive_engagement_gets_above_unit_weight():
    out = compute_sample_weights(np.array([1.0]))
    assert out[0] > 1.0
    # 1 + log1p(1) = 1 + ln(2) ≈ 1.6931
    assert math.isclose(out[0], 1.0 + math.log1p(1.0), rel_tol=1e-9)


def test_weights_are_monotonic_in_engagement():
    y = np.array([0, 0.5, 1, 5, 10, 50, 100], dtype=float)
    out = compute_sample_weights(y)
    # Strictly increasing for y > 0; equal for y == 0
    assert out[0] == 1.0
    for i in range(1, len(out)):
        if y[i] > y[i - 1]:
            assert out[i] > out[i - 1], (
                f"weights[{i}]={out[i]} should exceed weights[{i-1}]={out[i-1]} "
                f"for y[{i-1}]={y[i-1]}, y[{i}]={y[i]}"
            )


def test_log_dampening_caps_runaway_weights():
    # Weight grows logarithmically — a 100x bigger engagement should NOT
    # produce a 100x bigger weight.
    out = compute_sample_weights(np.array([1.0, 100.0]))
    assert out[1] / out[0] < 4.0, (
        f"Expected log-dampened ratio < 4x, got {out[1]/out[0]:.2f}x. "
        "If this fails, the dampening function changed."
    )


def test_mixed_zero_and_positive_preserved_in_place():
    y = np.array([0.0, 5.0, 0.0, 20.0])
    out = compute_sample_weights(y)
    assert out[0] == 1.0
    assert out[2] == 1.0
    assert out[1] > 1.0
    assert out[3] > out[1]


def test_negative_input_raises_loud_error():
    # Architecture rule E14 — no silent failure. Negative engagement
    # is upstream-violation territory.
    with pytest.raises(ValueError, match="negative engagement"):
        compute_sample_weights(np.array([-0.1, 1.0, 2.0]))


def test_input_dtype_promoted_to_float64():
    # Integer input should still work (no division-by-zero / overflow).
    out = compute_sample_weights(np.array([0, 1, 100], dtype=np.int32))
    assert out.dtype == np.float64
    assert out[0] == 1.0
    assert out[1] > 1.0


def test_pandas_series_compatible():
    # The ranker uses both numpy arrays and pandas Series in places.
    # asarray should just-work with anything array-like.
    pd = pytest.importorskip("pandas")
    s = pd.Series([0.0, 1.0, 10.0])
    out = compute_sample_weights(s)
    assert out.shape == (3,)
    assert out[0] == 1.0
    assert out[2] > out[1] > out[0]


def test_returns_new_array_does_not_mutate_input():
    y = np.array([0.0, 1.0, 5.0])
    y_copy = y.copy()
    _ = compute_sample_weights(y)
    np.testing.assert_array_equal(y, y_copy)
