"""Tests for lib.replay (Phase 1 follow-up)."""

from __future__ import annotations

import math

import pytest

from lib.replay import (
    AggregateMetrics,
    SessionMetrics,
    aggregate_sessions,
    build_relevance_vector,
    evaluate_session,
)


# ---------------------------------------------------------------------------
# build_relevance_vector
# ---------------------------------------------------------------------------
class TestBuildRelevance:
    def test_basic(self):
        rv = build_relevance_vector(["a", "b", "c"], {"b"})
        assert rv == [0, 1, 0]

    def test_all_relevant(self):
        rv = build_relevance_vector(["a", "b"], {"a", "b"})
        assert rv == [1, 1]

    def test_none_relevant(self):
        rv = build_relevance_vector(["x", "y"], {"a"})
        assert rv == [0, 0]

    def test_empty_ranking(self):
        rv = build_relevance_vector([], {"a", "b"})
        assert rv == []

    def test_empty_clicked(self):
        rv = build_relevance_vector(["a", "b", "c"], set())
        assert rv == [0, 0, 0]

    def test_iterable_clicked_coerced_to_set(self):
        # List input still works (we coerce internally)
        rv = build_relevance_vector(["a", "b", "c"], ["a", "c"])
        assert rv == [1, 0, 1]

    def test_duplicate_ids_kept(self):
        # Some rankers (RRF) can have the same id from two sources;
        # we don't dedup for the caller.
        rv = build_relevance_vector(["a", "a", "b"], {"a"})
        assert rv == [1, 1, 0]


# ---------------------------------------------------------------------------
# evaluate_session
# ---------------------------------------------------------------------------
class TestEvaluateSession:
    def test_perfect_session(self):
        # All clicks are at the very top
        ranking = ["a", "b", "c", "d", "e"]
        clicked = {"a", "b"}
        sm = evaluate_session(ranking, clicked, k_values=(5, 10))
        assert isinstance(sm, SessionMetrics)
        assert sm.n_ranked == 5
        assert sm.n_clicked == 2
        assert sm.n_clicked_in_ranking == 2
        assert sm.hit_rate_at_k[5] == 1.0
        assert sm.ndcg_at_k[5] == 1.0
        assert sm.precision_at_k[5] == 2.0 / 5.0

    def test_no_clicks_returns_zero_metrics(self):
        sm = evaluate_session(["a", "b", "c"], set(), k_values=(5,))
        assert sm.n_clicked == 0
        assert sm.n_clicked_in_ranking == 0
        assert sm.hit_rate_at_k[5] == 0.0
        assert sm.ndcg_at_k[5] == 0.0
        assert sm.average_precision == 0.0

    def test_clicks_not_in_ranking_dont_count_toward_recall(self):
        # The ranker offered 3 items; user clicked one of those + one
        # *not* in the ranking. Only the in-ranking click contributes.
        ranking = ["a", "b", "c"]
        clicked = {"a", "external-link-not-in-ranking"}
        sm = evaluate_session(ranking, clicked, k_values=(3,))
        # Ranker found 1 of the 2 clicked items in top-3
        assert sm.n_clicked == 2
        assert sm.n_clicked_in_ranking == 1
        # recall@3 = 1 / 2 (clicked items found / total clicks)
        # NOTE: lib.metrics.recall_at_k computes against the relevance
        # vector, where total relevant = sum(rel). So total relevant = 1
        # (only "a" is in the ranking). recall@3 = 1/1 = 1.0.
        # This is a known caveat: clicks outside the ranking are not
        # part of the metric's denominator. Document it in the report.
        assert sm.recall_at_k[3] == 1.0

    def test_session_metrics_is_immutable(self):
        sm = evaluate_session(["a", "b"], {"a"}, k_values=(2,))
        with pytest.raises(Exception):
            sm.n_ranked = 999  # type: ignore[misc]

    def test_known_ndcg_value(self):
        # Ranking: [a, b, c, d, e]
        # Clicks: {b, d}
        # Relevance: [0, 1, 0, 1, 0]
        # DCG@5 = 1/log2(3) + 1/log2(5)
        # IDCG@5 = 1/log2(2) + 1/log2(3)  (best = both at the top)
        # NDCG@5 = DCG / IDCG
        sm = evaluate_session(["a", "b", "c", "d", "e"], {"b", "d"}, k_values=(5,))
        expected_dcg = 1.0 / math.log2(3) + 1.0 / math.log2(5)
        expected_idcg = 1.0 + 1.0 / math.log2(3)
        expected = expected_dcg / expected_idcg
        assert math.isclose(sm.ndcg_at_k[5], expected, rel_tol=1e-9)

    def test_default_k_values(self):
        sm = evaluate_session(["a"] * 20, {"a"})
        # Default k_values is (5, 10) per signature
        assert set(sm.precision_at_k.keys()) == {5, 10}


# ---------------------------------------------------------------------------
# aggregate_sessions
# ---------------------------------------------------------------------------
class TestAggregateSessions:
    def test_three_sessions(self):
        sessions = [
            (["a", "b", "c"], {"a"}),     # ndcg@3 = 1.0
            (["a", "b", "c"], {"c"}),     # ndcg@3 < 1.0
            (["a", "b", "c"], {"b"}),     # ndcg@3 between
        ]
        agg = aggregate_sessions(sessions, k_values=(3,))
        assert isinstance(agg, AggregateMetrics)
        assert agg.n_sessions == 3
        assert agg.n_skipped == 0
        # Average NDCG should be in (0, 1) — not 0, not 1
        assert 0 < agg.ndcg_at_k[3] < 1.0
        # Mean of three known precisions:
        # session 1: P@3 = 1/3
        # session 2: P@3 = 1/3
        # session 3: P@3 = 1/3
        # mean = 1/3
        assert math.isclose(agg.precision_at_k[3], 1.0 / 3.0, rel_tol=1e-9)

    def test_skips_sessions_with_no_clicks(self):
        sessions = [
            (["a"], {"a"}),
            (["a"], set()),    # skip
            (["a"], frozenset()),  # skip
        ]
        agg = aggregate_sessions(sessions, k_values=(1,))
        assert agg.n_sessions == 3
        assert agg.n_skipped == 2
        # Single contributing session has hit@1 = 1.0
        assert agg.hit_rate_at_k[1] == 1.0

    def test_all_skipped_returns_zero_metrics_no_raise(self):
        sessions = [(["a"], set()), (["b"], set())]
        agg = aggregate_sessions(sessions, k_values=(5,))
        assert agg.n_sessions == 2
        assert agg.n_skipped == 2
        # All zeros, but the dataclass is well-formed
        assert agg.hit_rate_at_k[5] == 0.0
        assert agg.precision_at_k[5] == 0.0
        assert agg.mean_average_precision == 0.0

    def test_empty_input_returns_zero_metrics(self):
        agg = aggregate_sessions([], k_values=(5, 10))
        assert agg.n_sessions == 0
        assert agg.n_skipped == 0

    def test_propagates_k_values_to_output(self):
        agg = aggregate_sessions(
            [(["a", "b"], {"a"})],
            k_values=(1, 3, 5),
        )
        assert set(agg.precision_at_k.keys()) == {1, 3, 5}
        assert set(agg.ndcg_at_k.keys()) == {1, 3, 5}

    def test_aggregate_metrics_is_immutable(self):
        agg = aggregate_sessions([(["a"], {"a"})], k_values=(1,))
        with pytest.raises(Exception):
            agg.n_sessions = 999  # type: ignore[misc]
