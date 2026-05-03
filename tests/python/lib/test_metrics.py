"""Tests for lib.metrics (Phase 1 evaluation primitives).

We deliberately do NOT depend on scikit-learn for the cross-check —
the whole point of lib/ is light-deps-only. Hand-computed reference
values are inline in each test, with the formula commented above.
"""

from __future__ import annotations

import math

import pytest

from lib.metrics import (
    average_precision,
    dcg_at_k,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


# ---------------------------------------------------------------------------
# precision_at_k
# ---------------------------------------------------------------------------
class TestPrecisionAtK:
    def test_perfect_top_k(self):
        # 3/3 of the top-3 are relevant
        assert precision_at_k([1, 1, 1, 0, 0], 3) == 1.0

    def test_partial(self):
        # 2/3 of the top-3 are relevant
        assert math.isclose(precision_at_k([1, 0, 1, 0, 0], 3), 2.0 / 3.0)

    def test_no_relevant_in_top_k(self):
        assert precision_at_k([0, 0, 0, 1], 3) == 0.0

    def test_k_larger_than_list(self):
        # Per definition, denominator is k regardless of list length.
        # 1 relevant out of k=10 even if the list is shorter.
        assert precision_at_k([1, 0, 0], 10) == 0.1

    def test_empty_list_returns_zero(self):
        assert precision_at_k([], 5) == 0.0

    def test_k_must_be_positive(self):
        with pytest.raises(ValueError, match="k must be positive"):
            precision_at_k([1, 0], 0)
        with pytest.raises(ValueError, match="k must be positive"):
            precision_at_k([1, 0], -1)


# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------
class TestRecallAtK:
    def test_perfect_recall(self):
        # All 3 relevant items are in the top-3
        assert recall_at_k([1, 1, 1, 0, 0], 3) == 1.0

    def test_partial_recall(self):
        # 2 of 4 relevant items in top-3
        assert math.isclose(recall_at_k([1, 0, 1, 0, 1, 1], 3), 2.0 / 4.0)

    def test_zero_relevant_items_returns_zero_not_nan(self):
        # Convention: undefined recall collapses to 0 (documented in lib/metrics.py)
        assert recall_at_k([0, 0, 0], 3) == 0.0


# ---------------------------------------------------------------------------
# hit_rate_at_k
# ---------------------------------------------------------------------------
class TestHitRateAtK:
    def test_hit_in_top_k(self):
        assert hit_rate_at_k([0, 0, 1, 0, 0], 3) == 1.0
        assert hit_rate_at_k([1, 0, 0], 1) == 1.0

    def test_no_hit(self):
        assert hit_rate_at_k([0, 0, 0, 1], 3) == 0.0

    def test_empty(self):
        assert hit_rate_at_k([], 5) == 0.0


# ---------------------------------------------------------------------------
# average_precision
# ---------------------------------------------------------------------------
class TestAveragePrecision:
    def test_perfect_ranking(self):
        # All relevant items at the top of the list
        assert average_precision([1, 1, 1, 0, 0]) == 1.0

    def test_known_example(self):
        # y = [1, 0, 1, 0, 1]
        # precision@1 = 1/1 = 1.0  (relevant)
        # precision@3 = 2/3        (relevant)
        # precision@5 = 3/5        (relevant)
        # AP = (1.0 + 2/3 + 3/5) / 3
        expected = (1.0 + 2.0 / 3.0 + 3.0 / 5.0) / 3.0
        assert math.isclose(average_precision([1, 0, 1, 0, 1]), expected, rel_tol=1e-9)

    def test_zero_relevant_returns_zero(self):
        assert average_precision([0, 0, 0]) == 0.0

    def test_relevant_at_end_only(self):
        # Worst-case ordering — last item is the only relevant one
        # AP = (1/n) / 1
        n = 5
        assert math.isclose(average_precision([0, 0, 0, 0, 1]), 1.0 / n)


# ---------------------------------------------------------------------------
# dcg_at_k
# ---------------------------------------------------------------------------
class TestDCG:
    def test_single_relevant_at_first_position(self):
        # rel = 1 at position 1 → 1 / log2(2) = 1.0
        assert math.isclose(dcg_at_k([1, 0, 0], 3), 1.0)

    def test_single_relevant_at_second_position(self):
        # rel = 1 at position 2 → 1 / log2(3)
        expected = 1.0 / math.log2(3)
        assert math.isclose(dcg_at_k([0, 1, 0], 3), expected, rel_tol=1e-9)

    def test_multiple_relevant_known_values(self):
        # y = [1, 0, 1, 0]
        # DCG = 1/log2(2) + 1/log2(4) = 1.0 + 0.5 = 1.5
        assert math.isclose(dcg_at_k([1, 0, 1, 0], 4), 1.5, rel_tol=1e-9)

    def test_truncates_at_k(self):
        # Position 5 isn't counted in DCG@4
        assert math.isclose(dcg_at_k([0, 0, 0, 0, 1], 4), 0.0)


# ---------------------------------------------------------------------------
# ndcg_at_k
# ---------------------------------------------------------------------------
class TestNDCG:
    def test_perfect_ranking_is_one(self):
        # All relevant items at the top → NDCG = 1.0
        assert math.isclose(ndcg_at_k([1, 1, 1, 0, 0], 3), 1.0)
        assert math.isclose(ndcg_at_k([1, 0, 0], 3), 1.0)

    def test_worst_ranking_is_below_perfect(self):
        # Single relevant item at position k vs position 1
        worst = ndcg_at_k([0, 0, 0, 0, 1], 5)
        best = ndcg_at_k([1, 0, 0, 0, 0], 5)
        assert worst < best
        assert best == 1.0

    def test_ndcg_in_unit_interval(self):
        # Property: NDCG should always be in [0, 1]
        cases = [
            [1, 0, 1, 0, 1],
            [0, 1, 0, 1, 0],
            [1, 1, 0, 0, 0],
            [0, 0, 1, 1, 1],
        ]
        for y in cases:
            score = ndcg_at_k(y, 5)
            assert 0.0 <= score <= 1.0, f"NDCG out of range for y={y}: {score}"

    def test_known_value(self):
        # y = [0, 1, 1, 0, 0], k = 5
        # DCG = 1/log2(3) + 1/log2(4) = 0.6309... + 0.5 = 1.1309...
        # IDCG (best = [1, 1, 0, 0, 0]) = 1/log2(2) + 1/log2(3) = 1 + 0.6309 = 1.6309
        # NDCG = 1.1309 / 1.6309 = 0.6934...
        actual = ndcg_at_k([0, 1, 1, 0, 0], 5)
        expected_dcg = 1.0 / math.log2(3) + 1.0 / math.log2(4)
        expected_idcg = 1.0 + 1.0 / math.log2(3)
        expected = expected_dcg / expected_idcg
        assert math.isclose(actual, expected, rel_tol=1e-9)

    def test_zero_relevant_returns_zero(self):
        assert ndcg_at_k([0, 0, 0], 3) == 0.0

    def test_invalid_labels_raise(self):
        # Non-binary input (rule E14: fail loud)
        with pytest.raises(ValueError, match="binary labels"):
            ndcg_at_k([1, 2, 0], 3)
