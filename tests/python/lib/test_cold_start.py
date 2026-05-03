"""Tests for lib.cold_start."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lib.cold_start import (
    ColdStartResult,
    make_dense_similarity_fn,
    propagate_cold_start_scores,
)


# ---------------------------------------------------------------------------
# Basic propagation
# ---------------------------------------------------------------------------
class TestPropagation:
    def test_perfect_neighbour_match(self):
        # Two observed items + one cold item that is identical to one
        # of the observed items in embedding space. Expected: cold item
        # gets the matching observed score (times the discount).
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "obs2", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.8, "obs2": 0.4}
        embeddings = np.array(
            [
                [1.0, 0.0],   # obs1
                [0.0, 1.0],   # obs2
                [1.0, 0.0],   # cold1 — identical to obs1
            ],
            dtype=np.float64,
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(
            items, observed, sim_fn, k=1, discount=0.3
        )
        assert isinstance(result, ColdStartResult)
        assert result.n_observed == 2
        assert result.n_cold == 1
        assert result.fallback is False
        # cold1 perfectly aligned with obs1 → propagated = 0.8, then discounted
        assert math.isclose(result.scores["cold1"], 0.8 * 0.3, rel_tol=1e-9)

    def test_weighted_average_of_top_k(self):
        # Cold item that is 50/50 between obs1 (score 0.8) and
        # obs2 (score 0.4) → with k=2 we expect (0.8 + 0.4) / 2 = 0.6,
        # then discount.
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "obs2", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.8, "obs2": 0.4}
        # Cold sits at 45° between obs1 and obs2 axes
        embeddings = np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 1.0],
            ],
            dtype=np.float64,
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=2, discount=1.0)
        # Equal weights ⇒ simple mean
        assert math.isclose(result.scores["cold1"], 0.6, rel_tol=1e-9)

    def test_discount_applied(self):
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 1.0}
        embeddings = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=1, discount=0.25)
        assert math.isclose(result.scores["cold1"], 0.25, rel_tol=1e-9)

    def test_discount_zero_yields_zero_scores(self):
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.5}
        embeddings = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=1, discount=0.0)
        assert result.scores["cold1"] == 0.0

    def test_k_larger_than_observed(self):
        # k=10 with only 2 observed items — should use all of them
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "obs2", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.8, "obs2": 0.4}
        embeddings = np.array(
            [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float64
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=10, discount=1.0)
        # Same as the k=2 weighted-average case
        assert math.isclose(result.scores["cold1"], 0.6, rel_tol=1e-9)

    def test_no_cold_items_returns_empty_dict(self):
        items = [{"name": "obs1", "type": "package"}]
        observed = {"obs1": 0.5}
        embeddings = np.array([[1.0, 0.0]], dtype=np.float64)
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn)
        assert result.scores == {}
        assert result.n_cold == 0
        assert result.fallback is False

    def test_negative_similarities_handled_gracefully(self):
        # Cold item that is anti-aligned with both observed items
        # (cosine ≈ -1). All-negative weights should fall back to
        # global average rather than returning NaN.
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "obs2", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.8, "obs2": 0.4}
        embeddings = np.array(
            [
                [1.0, 0.0],
                [1.0, 0.0],
                [-1.0, 0.0],  # opposite direction
            ],
            dtype=np.float64,
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=2, discount=1.0)
        # Falls back to global mean = (0.8 + 0.4) / 2 = 0.6
        assert math.isclose(result.scores["cold1"], 0.6, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Fallback path (no observed items / no similarity)
# ---------------------------------------------------------------------------
class TestFallback:
    def test_no_observed_uses_zero_then_discount(self):
        items = [
            {"name": "cold1", "type": "package"},
            {"name": "cold2", "type": "paper"},
        ]
        observed = {}  # nothing engaged yet
        embeddings = np.zeros((2, 2))
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, discount=0.3)
        assert result.fallback is True
        # No observed → global average is 0 → all scores 0
        assert result.scores["cold1"] == 0.0
        assert result.scores["cold2"] == 0.0

    def test_no_similarity_fn_uses_type_average(self):
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "obs2", "type": "package"},
            {"name": "obs3", "type": "paper"},
            {"name": "cold_pkg", "type": "package"},
            {"name": "cold_paper", "type": "paper"},
            {"name": "cold_career", "type": "career"},
        ]
        observed = {"obs1": 0.6, "obs2": 0.8, "obs3": 0.4}
        # similarity_fn=None forces fallback
        result = propagate_cold_start_scores(
            items, observed, similarity_fn=None, discount=1.0
        )
        assert result.fallback is True
        # Type averages: package = 0.7, paper = 0.4, career falls back
        # to global = (0.6 + 0.8 + 0.4) / 3 = 0.6
        assert math.isclose(result.scores["cold_pkg"], 0.7, rel_tol=1e-9)
        assert math.isclose(result.scores["cold_paper"], 0.4, rel_tol=1e-9)
        assert math.isclose(result.scores["cold_career"], 0.6, rel_tol=1e-9)

    def test_items_without_name_skipped(self):
        items = [
            {"name": "obs1", "type": "package"},
            {"type": "package"},  # no name → skip
        ]
        observed = {"obs1": 0.5}
        embeddings = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        sim_fn = make_dense_similarity_fn(embeddings)
        result = propagate_cold_start_scores(items, observed, sim_fn, k=1, discount=1.0)
        # The unnamed item shouldn't appear in scores
        assert "obs1" not in result.scores
        assert result.scores == {}


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------
class TestErrors:
    def test_invalid_k_raises(self):
        items = [{"name": "obs1", "type": "package"}]
        with pytest.raises(ValueError, match="k must be >= 1"):
            propagate_cold_start_scores(items, {}, similarity_fn=None, k=0)

    def test_negative_discount_raises(self):
        items = [{"name": "obs1", "type": "package"}]
        with pytest.raises(ValueError, match="discount must be >= 0"):
            propagate_cold_start_scores(items, {}, similarity_fn=None, discount=-0.1)

    def test_wrong_shape_similarity_matrix_raises(self):
        items = [
            {"name": "obs1", "type": "package"},
            {"name": "cold1", "type": "package"},
        ]
        observed = {"obs1": 0.5}

        def bad_sim(_observed_idx, _cold_idx):
            return np.zeros((42, 42))  # nonsense shape

        with pytest.raises(ValueError, match="returned shape"):
            propagate_cold_start_scores(items, observed, bad_sim)


# ---------------------------------------------------------------------------
# make_dense_similarity_fn
# ---------------------------------------------------------------------------
class TestDenseSimilarityFn:
    def test_correct_cosine_values(self):
        embeddings = np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 1.0],
            ],
            dtype=np.float64,
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        # cold = item 2, observed = items 0 and 1
        sim_matrix = sim_fn([0, 1], [2])
        assert sim_matrix.shape == (1, 2)
        # cos(item2, item0) = 1/sqrt(2), cos(item2, item1) = 1/sqrt(2)
        expected = 1.0 / math.sqrt(2)
        assert math.isclose(sim_matrix[0, 0], expected, rel_tol=1e-9)
        assert math.isclose(sim_matrix[0, 1], expected, rel_tol=1e-9)

    def test_zero_norm_rows_dont_produce_nan(self):
        embeddings = np.array(
            [[1.0, 0.0], [0.0, 0.0]],  # second row is zero
            dtype=np.float64,
        )
        sim_fn = make_dense_similarity_fn(embeddings)
        sim = sim_fn([0], [1])
        assert sim.shape == (1, 1)
        assert sim[0, 0] == 0.0  # not NaN

    def test_empty_input_returns_zero_matrix(self):
        embeddings = np.array([[1.0, 0.0]], dtype=np.float64)
        sim_fn = make_dense_similarity_fn(embeddings)
        assert sim_fn([], [0]).shape == (1, 0)
        assert sim_fn([0], []).shape == (0, 1)

    def test_rejects_non_2d_input(self):
        with pytest.raises(ValueError, match="2-D embeddings"):
            make_dense_similarity_fn(np.array([1.0, 2.0, 3.0]))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
def test_result_is_immutable():
    r = ColdStartResult(scores={}, n_observed=0, n_cold=0, fallback=False)
    with pytest.raises(Exception):
        r.n_cold = 99  # type: ignore[misc]
