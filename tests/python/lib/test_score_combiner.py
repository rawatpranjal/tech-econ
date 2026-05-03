"""Tests for lib.score_combiner."""

from __future__ import annotations

import math

import pytest

from lib.score_combiner import (
    CombinedScores,
    apply_citations_boost,
    apply_freshness_boost,
    blend_engagement_with_predictions,
    combine_scores,
    normalize_scores,
)


# ---------------------------------------------------------------------------
# normalize_scores
# ---------------------------------------------------------------------------
class TestNormalize:
    def test_empty_input(self):
        assert normalize_scores({}) == {}

    def test_simple_min_max(self):
        out = normalize_scores({"a": 0.0, "b": 5.0, "c": 10.0})
        assert math.isclose(out["a"], 0.0)
        assert math.isclose(out["b"], 0.5)
        assert math.isclose(out["c"], 1.0)

    def test_all_equal_returns_unchanged(self):
        # No span — the legacy behaviour passes input through. Document
        # the contract by asserting it.
        out = normalize_scores({"a": 0.7, "b": 0.7, "c": 0.7})
        assert out == {"a": 0.7, "b": 0.7, "c": 0.7}

    def test_negative_values(self):
        out = normalize_scores({"a": -2.0, "b": 0.0, "c": 8.0})
        assert math.isclose(out["a"], 0.0)
        assert math.isclose(out["b"], 0.2)
        assert math.isclose(out["c"], 1.0)


# ---------------------------------------------------------------------------
# blend_engagement_with_predictions
# ---------------------------------------------------------------------------
class TestBlend:
    def test_observed_uses_engagement(self):
        items = [{"name": "a"}, {"name": "b"}]
        eng = {"a": 0.8, "b": 0.5}
        pred = {"a": 0.2, "b": 0.3}
        out = blend_engagement_with_predictions(
            items, eng, pred, cold_start_names=set()
        )
        assert out["a"] == 0.8
        assert out["b"] == 0.5

    def test_cold_uses_discounted_predictions(self):
        items = [{"name": "a"}, {"name": "b"}]
        eng = {"a": 0.8}
        pred = {"a": 0.2, "b": 0.6}
        out = blend_engagement_with_predictions(
            items, eng, pred, cold_start_names={"b"}, cold_start_discount=0.3
        )
        assert out["a"] == 0.8
        assert math.isclose(out["b"], 0.6 * 0.3)

    def test_inferred_cold_when_set_is_none(self):
        # cold_start_names=None → infer "cold = not in engagement"
        items = [{"name": "a"}, {"name": "b"}]
        eng = {"a": 0.8}
        pred = {"a": 0.2, "b": 0.6}
        out = blend_engagement_with_predictions(
            items, eng, pred, cold_start_names=None, cold_start_discount=0.5
        )
        assert out["a"] == 0.8
        assert math.isclose(out["b"], 0.6 * 0.5)

    def test_missing_predicted_score_treated_as_zero(self):
        items = [{"name": "a"}]
        out = blend_engagement_with_predictions(
            items, {}, {}, cold_start_names={"a"}, cold_start_discount=0.5
        )
        assert out["a"] == 0.0

    def test_skips_items_without_string_name(self):
        items = [{"name": "a"}, {"name": None}, {"other_key": "x"}]
        out = blend_engagement_with_predictions(items, {"a": 0.5}, {})
        assert "a" in out
        assert len(out) == 1

    def test_negative_discount_raises(self):
        with pytest.raises(ValueError, match="cold_start_discount must be >= 0"):
            blend_engagement_with_predictions(
                [{"name": "a"}], {}, {}, cold_start_discount=-0.1
            )


# ---------------------------------------------------------------------------
# apply_freshness_boost
# ---------------------------------------------------------------------------
class TestFreshnessBoost:
    def test_basic_boost(self):
        scores = {"a": 0.5, "b": 0.3}
        boosts = {"a": 0.1, "b": 0.05}
        out, n, mx = apply_freshness_boost(scores, boosts)
        assert math.isclose(out["a"], 0.6)
        assert math.isclose(out["b"], 0.35)
        assert n == 2
        assert math.isclose(mx, 0.1)

    def test_caps_at_default_one(self):
        scores = {"a": 0.95}
        boosts = {"a": 0.5}
        out, _, _ = apply_freshness_boost(scores, boosts)
        assert out["a"] == 1.0

    def test_custom_cap(self):
        scores = {"a": 0.5}
        boosts = {"a": 0.5}
        out, _, _ = apply_freshness_boost(scores, boosts, cap=0.8)
        assert out["a"] == 0.8

    def test_items_not_in_boosts_pass_through(self):
        scores = {"a": 0.3, "b": 0.4}
        out, n, _ = apply_freshness_boost(scores, {"a": 0.1})
        assert out["b"] == 0.4
        assert n == 1

    def test_zero_or_negative_boost_skipped(self):
        scores = {"a": 0.3, "b": 0.4, "c": 0.5}
        out, n, _ = apply_freshness_boost(scores, {"a": 0.0, "b": -0.1, "c": 0.05})
        assert out["a"] == 0.3
        assert out["b"] == 0.4
        assert math.isclose(out["c"], 0.55)
        assert n == 1

    def test_empty_scores_or_boosts(self):
        out, n, mx = apply_freshness_boost({}, {"a": 0.1})
        assert out == {}
        assert n == 0
        out, n, mx = apply_freshness_boost({"a": 0.5}, {})
        assert out == {"a": 0.5}
        assert n == 0

    def test_negative_cap_raises(self):
        with pytest.raises(ValueError, match="cap must be >= 0"):
            apply_freshness_boost({"a": 0.5}, {}, cap=-0.1)


# ---------------------------------------------------------------------------
# apply_citations_boost
# ---------------------------------------------------------------------------
class TestCitationsBoost:
    def test_basic_paper_boost(self):
        items = [
            {"name": "p1", "type": "paper", "citations": 100},
            {"name": "p2", "type": "paper", "citations": 10},
            {"name": "pkg1", "type": "package", "citations": 999},  # ignored
        ]
        scores = {"p1": 0.4, "p2": 0.3, "pkg1": 0.5}
        out, n, mx = apply_citations_boost(items, scores, citation_weight=0.3, cap=1.0)
        # Top-cited paper gets the full weight
        # boost(p1) = 0.3 * log(101) / log(101) = 0.3
        assert math.isclose(out["p1"], 0.4 + 0.3, rel_tol=1e-9)
        # boost(p2) = 0.3 * log(11) / log(101) ≈ 0.156
        expected_p2 = 0.3 + 0.3 * math.log(11) / math.log(101)
        assert math.isclose(out["p2"], expected_p2, rel_tol=1e-9)
        # Package untouched
        assert out["pkg1"] == 0.5
        assert n == 2

    def test_no_papers_yields_no_boost(self):
        items = [{"name": "pkg1", "type": "package"}]
        scores = {"pkg1": 0.5}
        out, n, _ = apply_citations_boost(items, scores)
        assert out == scores
        assert n == 0

    def test_zero_citations_skipped(self):
        items = [{"name": "p1", "type": "paper", "citations": 0}]
        scores = {"p1": 0.4}
        out, n, _ = apply_citations_boost(items, scores)
        assert out == {"p1": 0.4}
        assert n == 0

    def test_missing_citations_field_treated_as_zero(self):
        items = [{"name": "p1", "type": "paper"}]
        scores = {"p1": 0.4}
        out, n, _ = apply_citations_boost(items, scores)
        assert out == {"p1": 0.4}
        assert n == 0

    def test_string_citations_robustly_parsed(self):
        items = [
            {"name": "p1", "type": "paper", "citations": "50"},
            {"name": "p2", "type": "paper", "citations": "garbage"},
        ]
        scores = {"p1": 0.4, "p2": 0.3}
        out, n, _ = apply_citations_boost(items, scores)
        assert out["p1"] > 0.4  # parsed to 50, boosted
        assert out["p2"] == 0.3  # garbage → 0, no boost
        assert n == 1

    def test_cap_enforced(self):
        items = [{"name": "p1", "type": "paper", "citations": 1000}]
        scores = {"p1": 0.95}
        out, _, _ = apply_citations_boost(items, scores, citation_weight=0.5, cap=1.0)
        assert out["p1"] == 1.0

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="citation_weight must be >= 0"):
            apply_citations_boost([], {}, citation_weight=-0.1)


# ---------------------------------------------------------------------------
# combine_scores — end-to-end
# ---------------------------------------------------------------------------
class TestCombineScores:
    def test_returns_combined_scores_dataclass(self):
        items = [{"name": "a", "type": "package"}]
        result = combine_scores(items, {"a": 0.5}, {"a": 0.2})
        assert isinstance(result, CombinedScores)
        assert "a" in result.scores

    def test_no_freshness_no_citations(self):
        items = [{"name": "a", "type": "package"}, {"name": "b", "type": "package"}]
        result = combine_scores(
            items,
            engagement_scores={"a": 0.8},
            predicted_scores={"b": 0.4},
            cold_start_names={"b"},
            cold_start_discount=0.5,
        )
        # After blend: a=0.8, b=0.2. Normalized: a=1.0, b=0.0.
        # No freshness, no citations.
        assert math.isclose(result.scores["a"], 1.0)
        assert math.isclose(result.scores["b"], 0.0)
        assert result.n_fresh_boosted == 0
        assert result.n_citation_boosted == 0

    def test_with_freshness(self):
        items = [{"name": "a", "type": "package"}, {"name": "b", "type": "package"}]
        result = combine_scores(
            items,
            engagement_scores={"a": 0.8, "b": 0.4},
            predicted_scores={"a": 0.0, "b": 0.0},
            cold_start_names=set(),
            freshness_boosts={"b": 0.3},  # boost the lower-scored item
        )
        # Freshness pushes b up; after final normalisation both are
        # rescaled into [0, 1] with a re-normalised range.
        assert result.n_fresh_boosted == 1
        assert math.isclose(result.max_freshness_boost, 0.3, rel_tol=1e-9)
        assert 0 <= result.scores["a"] <= 1
        assert 0 <= result.scores["b"] <= 1

    def test_with_citations(self):
        items = [
            {"name": "p1", "type": "paper", "citations": 50},
            {"name": "p2", "type": "paper", "citations": 0},
        ]
        result = combine_scores(
            items,
            engagement_scores={"p1": 0.5, "p2": 0.5},
            predicted_scores={},
            cold_start_names=set(),
            citation_weight=0.3,
        )
        assert result.n_citation_boosted == 1
        # p1 ranks higher than p2 thanks to citations boost
        assert result.scores["p1"] > result.scores["p2"]

    def test_full_pipeline(self):
        items = [
            {"name": "p1", "type": "paper", "citations": 100},
            {"name": "p2", "type": "paper", "citations": 10},
            {"name": "pkg1", "type": "package"},
        ]
        result = combine_scores(
            items,
            engagement_scores={"p1": 0.6, "pkg1": 0.4},
            predicted_scores={"p2": 0.3},
            cold_start_names={"p2"},
            freshness_boosts={"pkg1": 0.2, "p2": 0.1},
            cold_start_discount=0.3,
            citation_weight=0.3,
        )
        # Sanity: every item has a score in [0, 1]
        for name, score in result.scores.items():
            assert 0.0 <= score <= 1.0, f"{name}: {score}"
        # n_observed counts items in engagement_scores that match an item name
        assert result.n_observed == 2
        # n_cold = 1 (p2)
        assert result.n_cold == 1
        # n_fresh_boosted = 2 (pkg1, p2)
        assert result.n_fresh_boosted == 2
        # n_citation_boosted = 2 (both papers have citations > 0)
        assert result.n_citation_boosted == 2

    def test_empty_inputs(self):
        result = combine_scores([], {}, {})
        assert result.scores == {}
        assert result.n_observed == 0
        assert result.n_cold == 0


# ---------------------------------------------------------------------------
# CombinedScores dataclass
# ---------------------------------------------------------------------------
def test_combined_scores_immutable():
    cs = CombinedScores(
        scores={}, n_observed=0, n_cold=0,
        n_fresh_boosted=0, n_citation_boosted=0,
        max_freshness_boost=0.0, max_citation_boost=0.0,
    )
    with pytest.raises(Exception):
        cs.n_observed = 999  # type: ignore[misc]
