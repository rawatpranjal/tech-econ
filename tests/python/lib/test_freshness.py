"""Tests for lib.freshness."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from lib.freshness import (
    _parse_first_seen,
    compute_freshness_boosts,
    freshness_boost_for_item,
)


NOW = datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# _parse_first_seen
# ---------------------------------------------------------------------------
class TestParseFirstSeen:
    def test_aware_datetime_passes_through(self):
        assert _parse_first_seen(NOW) == NOW

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 1, 1)
        assert _parse_first_seen(naive) == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_iso_with_z_suffix(self):
        assert _parse_first_seen("2026-05-03T12:00:00Z") == NOW

    def test_iso_with_offset(self):
        assert _parse_first_seen("2026-05-03T12:00:00+00:00") == NOW

    def test_legacy_datetime_format(self):
        # rank_all_content.py:595 supports 'YYYY-MM-DD HH:MM:SS'
        assert _parse_first_seen("2026-05-03 12:00:00") == NOW

    def test_epoch_seconds(self):
        # 2026-05-03T12:00:00Z = 1777809600
        assert _parse_first_seen(1777809600) == NOW

    def test_none_returns_none(self):
        assert _parse_first_seen(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_first_seen("") is None
        assert _parse_first_seen("   ") is None

    def test_garbage_string_returns_none(self):
        # Unparseable but not raising — caller treats as missing
        assert _parse_first_seen("not a date") is None

    def test_unsupported_type_returns_none(self):
        assert _parse_first_seen(["a", "list"]) is None


# ---------------------------------------------------------------------------
# freshness_boost_for_item
# ---------------------------------------------------------------------------
class TestBoostForItem:
    def test_zero_age_yields_max_boost(self):
        # age=0 → exp(0) = 1 → boost = boost_max
        assert math.isclose(
            freshness_boost_for_item(0, boost_max=0.15, half_life_days=30),
            0.15,
            rel_tol=1e-9,
        )

    def test_half_life_yields_half_max(self):
        # age = half_life → exp(-1) (NOT 0.5 — this is "natural" decay)
        # but the documented half-life convention here is "exponential
        # with characteristic time = half_life_days", which gives
        # exp(-1) ≈ 0.368 at age == half_life. That matches the legacy
        # rank_all_content.py implementation.
        out = freshness_boost_for_item(30, boost_max=1.0, half_life_days=30)
        assert math.isclose(out, math.exp(-1), rel_tol=1e-9)

    def test_decay_continues(self):
        # 60 days is two half-lives → exp(-2) ≈ 0.135
        out = freshness_boost_for_item(60, boost_max=1.0, half_life_days=30)
        assert math.isclose(out, math.exp(-2), rel_tol=1e-9)

    def test_large_age_approaches_zero(self):
        out = freshness_boost_for_item(3650, boost_max=0.15, half_life_days=30)
        assert out < 1e-50

    def test_negative_age_clamped_to_zero(self):
        # Future-dated first_seen (clock skew) → still capped at boost_max
        out = freshness_boost_for_item(-30, boost_max=0.15, half_life_days=30)
        assert math.isclose(out, 0.15, rel_tol=1e-9)

    def test_boost_max_zero_yields_zero(self):
        out = freshness_boost_for_item(5, boost_max=0.0, half_life_days=30)
        assert out == 0.0

    def test_negative_boost_max_raises(self):
        with pytest.raises(ValueError, match="boost_max must be >= 0"):
            freshness_boost_for_item(0, boost_max=-0.1)

    def test_zero_half_life_raises(self):
        with pytest.raises(ValueError, match="half_life_days must be > 0"):
            freshness_boost_for_item(0, half_life_days=0)

    def test_negative_half_life_raises(self):
        with pytest.raises(ValueError, match="half_life_days must be > 0"):
            freshness_boost_for_item(0, half_life_days=-1)


# ---------------------------------------------------------------------------
# compute_freshness_boosts
# ---------------------------------------------------------------------------
class TestComputeBoosts:
    def test_basic(self):
        rows = [
            {"name": "Paper A", "first_seen": "2026-05-03T12:00:00Z"},  # 0 days
            {"name": "Paper B", "first_seen": "2026-04-03T12:00:00Z"},  # 30 days
            {"name": "Paper C", "first_seen": "2026-03-04T12:00:00Z"},  # 60 days
        ]
        boosts = compute_freshness_boosts(
            rows, boost_max=1.0, half_life_days=30, now=NOW
        )
        assert math.isclose(boosts["paper a"], 1.0, rel_tol=1e-9)
        assert math.isclose(boosts["paper b"], math.exp(-1), rel_tol=1e-9)
        assert math.isclose(boosts["paper c"], math.exp(-2), rel_tol=1e-9)

    def test_lowercases_and_strips_names(self):
        rows = [{"name": "  Paper Mixed Case  ", "first_seen": "2026-05-03T12:00:00Z"}]
        boosts = compute_freshness_boosts(rows, boost_max=1.0, now=NOW)
        assert "paper mixed case" in boosts
        assert "  Paper Mixed Case  " not in boosts

    def test_skips_rows_without_name(self):
        rows = [{"first_seen": "2026-05-03T12:00:00Z"}]
        boosts = compute_freshness_boosts(rows, now=NOW)
        assert boosts == {}

    def test_skips_rows_with_unparseable_first_seen(self):
        rows = [
            {"name": "Good", "first_seen": "2026-05-03T12:00:00Z"},
            {"name": "Bad", "first_seen": "garbage"},
            {"name": "Also Bad", "first_seen": None},
        ]
        boosts = compute_freshness_boosts(rows, now=NOW)
        assert "good" in boosts
        assert "bad" not in boosts
        assert "also bad" not in boosts

    def test_skips_non_dict_rows(self):
        # Defensive — D1 results are usually dicts but we shouldn't
        # crash if a list / None sneaks in.
        rows = [
            {"name": "Good", "first_seen": "2026-05-03T12:00:00Z"},
            None,
            ["not a dict"],
            "also not",
        ]
        boosts = compute_freshness_boosts(rows, now=NOW)
        assert boosts == {"good": pytest.approx(0.15, rel=1e-9)}

    def test_per_type_half_lives(self):
        rows = [
            {"name": "Paper", "type": "paper", "first_seen": "2026-04-03T12:00:00Z"},
            {"name": "Talk", "type": "talk", "first_seen": "2026-04-03T12:00:00Z"},
        ]
        boosts = compute_freshness_boosts(
            rows,
            boost_max=1.0,
            half_life_days={"paper": 90, "talk": 14},
            now=NOW,
        )
        # Paper at 30 days with 90-day half-life → exp(-30/90) ≈ 0.717
        assert math.isclose(boosts["paper"], math.exp(-30 / 90), rel_tol=1e-9)
        # Talk at 30 days with 14-day half-life → exp(-30/14) ≈ 0.117
        assert math.isclose(boosts["talk"], math.exp(-30 / 14), rel_tol=1e-9)

    def test_per_type_default_fallback(self):
        rows = [
            {"name": "Item", "type": "unknown_type", "first_seen": "2026-05-03T12:00:00Z"},
        ]
        boosts = compute_freshness_boosts(
            rows,
            boost_max=1.0,
            half_life_days={"paper": 90, "__default__": 45},
            now=NOW,
        )
        # Unknown type → __default__ = 45-day half-life. Age 0 → boost_max
        assert math.isclose(boosts["item"], 1.0, rel_tol=1e-9)

    def test_per_type_hard_default_when_no_default_key(self):
        rows = [
            {"name": "Item", "type": "unknown_type", "first_seen": "2026-04-03T12:00:00Z"},
        ]
        # No __default__ provided; hard fallback to 30 days
        boosts = compute_freshness_boosts(
            rows,
            boost_max=1.0,
            half_life_days={"paper": 90},
            now=NOW,
        )
        # 30 days with 30-day default half-life → exp(-1)
        assert math.isclose(boosts["item"], math.exp(-1), rel_tol=1e-9)

    def test_empty_half_lives_dict_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_freshness_boosts([], half_life_days={})

    def test_zero_half_life_in_dict_raises(self):
        with pytest.raises(ValueError, match=r"half_life_days\['paper'\]"):
            compute_freshness_boosts([], half_life_days={"paper": 0})

    def test_now_default_is_documented_to_be_current_time(self):
        # If now is omitted, the function uses datetime.now(UTC).
        # Hard to assert exactly without freezing time, but we can
        # assert the *shape* is sane: a row with first_seen in the
        # very recent past produces a boost close to boost_max.
        rows = [{"name": "Recent", "first_seen": datetime.now(timezone.utc)}]
        boosts = compute_freshness_boosts(rows, boost_max=0.15, half_life_days=30)
        assert math.isclose(boosts["recent"], 0.15, rel_tol=1e-3)

    def test_naive_now_is_treated_as_utc(self):
        rows = [{"name": "Item", "first_seen": "2026-05-03T12:00:00Z"}]
        # Pass naive datetime — should still work, treated as UTC
        naive_now = NOW.replace(tzinfo=None)
        boosts = compute_freshness_boosts(
            rows, boost_max=1.0, half_life_days=30, now=naive_now
        )
        assert math.isclose(boosts["item"], 1.0, rel_tol=1e-9)
