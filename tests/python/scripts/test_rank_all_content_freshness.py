"""Side-by-side comparison: scripts/rank_all_content.py:calculate_freshness_scores
(now a thin wrapper around lib.freshness.compute_freshness_boosts) vs the
original inline implementation.

The migration shifts two things deliberately:
  1. fractional days instead of integer days (sub-day precision)
  2. future-dated rows (clock skew) clamp to age=0 instead of producing
     boost > FRESHNESS_WEIGHT

This test pins both implementations against the same fixtures and asserts:
  - identical keys (same items get a boost)
  - boosts are within a tiny epsilon (well below scoring noise)
  - rank order over the items is identical

If a future change accidentally diverges these, the suite fails loudly.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# Load rank_all_content as a module without running its main() side effects.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "rank_all_content.py"
_spec = importlib.util.spec_from_file_location("rank_all_content", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
rank_module = importlib.util.module_from_spec(_spec)
sys.modules["rank_all_content"] = rank_module
_spec.loader.exec_module(rank_module)


# --------------------------------------------------------------------------- #
# Reference: the pre-migration inline implementation, frozen here so future
# refactors can never quietly drop behaviour. If the lib version produces
# different results, this test is the canary.
# --------------------------------------------------------------------------- #


def legacy_calculate_freshness_scores(first_seen_data, weight, half_life):
    """Verbatim copy of the pre-migration inline impl from
    scripts/rank_all_content.py (the version with integer days and no
    future-clamp). Kept here as a fixture, NOT for production use."""
    now = datetime.now(timezone.utc)
    freshness_scores = {}

    for row in first_seen_data:
        name = row["name"].lower().strip()
        first_seen_str = row.get("first_seen")

        if not first_seen_str:
            continue

        try:
            if "T" in first_seen_str:
                first_seen = datetime.fromisoformat(
                    first_seen_str.replace("Z", "+00:00")
                )
            else:
                first_seen = datetime.strptime(first_seen_str, "%Y-%m-%d %H:%M:%S")
                first_seen = first_seen.replace(tzinfo=timezone.utc)

            days_since = (now - first_seen).days
            decay = math.exp(-days_since / half_life)
            freshness_scores[name] = weight * decay
        except (ValueError, TypeError):
            continue

    return freshness_scores


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _iso(days_ago: float) -> str:
    """Return an ISO 8601 timestamp `days_ago` days before now (UTC)."""
    return (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _legacy_format(days_ago: float) -> str:
    """Return a 'YYYY-MM-DD HH:MM:SS' timestamp `days_ago` days before now."""
    return (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Equivalence tests
# --------------------------------------------------------------------------- #


class TestEquivalence:
    """Assert lib version produces equivalent results to legacy on integer-day
    inputs (no fractional drift to worry about)."""

    def test_empty_input(self):
        assert rank_module.calculate_freshness_scores([]) == {}

    def test_integer_day_inputs_match_legacy(self):
        """When ages are exact integer days, fractional vs integer has no
        impact -- so the lib version must produce identical boosts."""
        rows = [
            {"name": "A", "first_seen": _iso(1)},
            {"name": "B", "first_seen": _iso(7)},
            {"name": "C", "first_seen": _iso(30)},
            {"name": "D", "first_seen": _iso(180)},
        ]
        new = rank_module.calculate_freshness_scores(rows)
        legacy = legacy_calculate_freshness_scores(
            rows,
            rank_module.FRESHNESS_WEIGHT,
            rank_module.FRESHNESS_HALF_LIFE_DAYS,
        )
        assert set(new.keys()) == set(legacy.keys())
        for k in new:
            # Allow tiny float drift from the now-difference between the
            # two function calls (a few microseconds apart).
            assert new[k] == pytest.approx(legacy[k], rel=1e-3, abs=1e-4)

    def test_legacy_format_input_also_supported(self):
        """The pre-migration impl accepted 'YYYY-MM-DD HH:MM:SS'; the lib
        version preserves that path."""
        rows = [
            {"name": "X", "first_seen": _legacy_format(5)},
            {"name": "Y", "first_seen": _legacy_format(60)},
        ]
        new = rank_module.calculate_freshness_scores(rows)
        legacy = legacy_calculate_freshness_scores(
            rows,
            rank_module.FRESHNESS_WEIGHT,
            rank_module.FRESHNESS_HALF_LIFE_DAYS,
        )
        for k in new:
            assert new[k] == pytest.approx(legacy[k], rel=1e-3, abs=1e-4)

    def test_rank_order_preserved(self):
        """Even with the fractional-vs-integer-day change, the relative
        ranking of items must be identical -- monotone decay is preserved."""
        rows = [
            {"name": "fresh", "first_seen": _iso(0.5)},   # 12 hours old
            {"name": "week", "first_seen": _iso(7.3)},
            {"name": "month", "first_seen": _iso(31.7)},
            {"name": "old", "first_seen": _iso(120.0)},
        ]
        new = rank_module.calculate_freshness_scores(rows)
        ordered_new = sorted(new, key=lambda k: -new[k])
        # Newer items must always rank higher (max boost) than older.
        assert ordered_new == ["fresh", "week", "month", "old"]


class TestDeliberateDivergences:
    """The lib version intentionally fixes two edge cases. These tests pin
    that behaviour so a future refactor can't silently revert them."""

    def test_future_dated_rows_clamp_to_max_boost(self):
        """Clock-skewed first_seen in the future used to produce boost
        > FRESHNESS_WEIGHT under the legacy impl (negative days_since,
        exp positive). Lib version clamps to age=0 -> boost = WEIGHT exactly."""
        rows = [{"name": "future", "first_seen": _iso(-10)}]
        new = rank_module.calculate_freshness_scores(rows)
        # Maximum possible boost under the new impl
        assert new["future"] == pytest.approx(rank_module.FRESHNESS_WEIGHT, abs=1e-9)
        # Legacy would have over-shot
        legacy = legacy_calculate_freshness_scores(
            rows,
            rank_module.FRESHNESS_WEIGHT,
            rank_module.FRESHNESS_HALF_LIFE_DAYS,
        )
        assert legacy["future"] > rank_module.FRESHNESS_WEIGHT  # the bug we fixed

    def test_fractional_days_resolve_more_precisely(self):
        """A 1.7-day-old item under legacy had days_since=1 (truncated);
        lib uses 1.7. Boosts differ by exp(-1.7/30) - exp(-1/30) ≈ 0.022
        of FRESHNESS_WEIGHT (~0.0033 absolute at WEIGHT=0.15).
        Below scoring noise; test pins the direction of the change."""
        rows = [{"name": "p", "first_seen": _iso(1.7)}]
        new = rank_module.calculate_freshness_scores(rows)
        legacy = legacy_calculate_freshness_scores(
            rows,
            rank_module.FRESHNESS_WEIGHT,
            rank_module.FRESHNESS_HALF_LIFE_DAYS,
        )
        # New (uses 1.7 days) decays more than legacy (uses 1 day, less decay).
        assert new["p"] < legacy["p"]
        # But the difference is bounded.
        assert abs(new["p"] - legacy["p"]) < 0.01


class TestErrorHandling:
    """The lib version preserves the legacy behaviour of silently dropping
    unparseable / missing rows."""

    def test_missing_first_seen_skipped(self):
        rows = [
            {"name": "valid", "first_seen": _iso(5)},
            {"name": "no_field"},
            {"name": "empty_field", "first_seen": ""},
            {"name": "null_field", "first_seen": None},
        ]
        out = rank_module.calculate_freshness_scores(rows)
        assert "valid" in out
        assert "no_field" not in out
        assert "empty_field" not in out
        assert "null_field" not in out

    def test_unparseable_first_seen_skipped(self):
        rows = [
            {"name": "valid", "first_seen": _iso(5)},
            {"name": "garbage", "first_seen": "not a date"},
        ]
        out = rank_module.calculate_freshness_scores(rows)
        assert "valid" in out
        assert "garbage" not in out
