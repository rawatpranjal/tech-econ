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

Import strategy: scripts/rank_all_content.py imports sklearn at module load,
which isn't in requirements-dev.txt (CI installs only dev deps). To test the
wrapper without pulling in the full ML stack, we stub the heavy imports
in sys.modules before loading the module — same code path under test, just
without forcing pytest to need sklearn/lightgbm/sentence_transformers.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Stub heavy ML deps that rank_all_content.py imports at module load.
# Only the modules — and only the names we know it imports — need to exist;
# we don't actually call any sklearn / lightgbm / sentence_transformers
# functions in the freshness path under test. Each stub uses a real
# ModuleType (not just MagicMock) so submodule lookups via dotted-path
# import work — `from sklearn.preprocessing import StandardScaler`
# needs `sklearn.preprocessing` to be a module.
import types as _types

def _stub_module(name: str) -> None:
    if name not in sys.modules:
        m = _types.ModuleType(name)
        # MagicMock backstop so any attribute access (e.g. SentenceTransformer)
        # still returns *something* rather than AttributeError.
        m.__getattr__ = lambda attr: MagicMock()  # type: ignore[assignment]
        sys.modules[name] = m

for _mod in (
    "sklearn",
    "sklearn.preprocessing",
    "sklearn.model_selection",
    "sklearn.feature_extraction",
    "sklearn.feature_extraction.text",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
    "lightgbm",
    "sentence_transformers",
):
    _stub_module(_mod)


# Load rank_all_content as a module without running its main() side effects.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "rank_all_content.py"
_spec = importlib.util.spec_from_file_location("rank_all_content", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
rank_module = importlib.util.module_from_spec(_spec)
sys.modules["rank_all_content"] = rank_module
_spec.loader.exec_module(rank_module)

# Read the canonical freshness tunables from data/recsys_config.json (the same
# place rank_all_content.calculate_freshness_scores reads them). Used as the
# "weight" and "half_life" args to the frozen legacy reference impl below so
# both sides of the equivalence test see identical inputs.
from lib.recsys_config import load as _load_recsys_config  # noqa: E402

_CFG = _load_recsys_config()
FRESH_WEIGHT = _CFG.ranking.freshness_boost_max
FRESH_HALF_LIFE = _CFG.ranking.freshness_half_life_days


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
            FRESH_WEIGHT,
            FRESH_HALF_LIFE,
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
            FRESH_WEIGHT,
            FRESH_HALF_LIFE,
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
        assert new["future"] == pytest.approx(FRESH_WEIGHT, abs=1e-9)
        # Legacy would have over-shot
        legacy = legacy_calculate_freshness_scores(
            rows,
            FRESH_WEIGHT,
            FRESH_HALF_LIFE,
        )
        assert legacy["future"] > FRESH_WEIGHT  # the bug we fixed

    def test_fractional_days_resolve_more_precisely(self):
        """A 1.7-day-old item under legacy had days_since=1 (truncated);
        lib uses 1.7. Boosts differ by exp(-1.7/30) - exp(-1/30) ≈ 0.022
        of FRESHNESS_WEIGHT (~0.0033 absolute at WEIGHT=0.15).
        Below scoring noise; test pins the direction of the change."""
        rows = [{"name": "p", "first_seen": _iso(1.7)}]
        new = rank_module.calculate_freshness_scores(rows)
        legacy = legacy_calculate_freshness_scores(
            rows,
            FRESH_WEIGHT,
            FRESH_HALF_LIFE,
        )
        # New (uses 1.7 days) decays more than legacy (uses 1 day, less decay).
        assert new["p"] < legacy["p"]
        # But the difference is bounded.
        assert abs(new["p"] - legacy["p"]) < 0.01


class TestConfigOverride:
    """The new wrapper accepts an optional `config` kwarg so tests / replays
    can pin behaviour without depending on disk state. This is also the
    forward-compat path for per-type half-lives once the audit's "papers
    slow / talks fast" plan lands -- pass a Mapping in the config."""

    def test_explicit_config_overrides_default(self):
        """Build a config with double the boost and assert the output reflects
        it. Verifies the new `config=` kwarg is wired all the way through."""
        from dataclasses import replace
        rows = [{"name": "x", "first_seen": _iso(0)}]
        # Halve the half-life and double the boost from defaults.
        custom = replace(
            _CFG.ranking,
            freshness_boost_max=FRESH_WEIGHT * 2,
            freshness_half_life_days=FRESH_HALF_LIFE / 2,
        )
        custom_cfg = replace(_CFG, ranking=custom)
        out = rank_module.calculate_freshness_scores(rows, config=custom_cfg)
        # At age≈0 the boost should equal the configured max (within the
        # microsecond drift between _iso(0) and the function call below).
        assert out["x"] == pytest.approx(FRESH_WEIGHT * 2, abs=1e-5)

    def test_default_config_used_when_kwarg_omitted(self):
        """No-kwargs call should match an explicit-default-config call."""
        rows = [
            {"name": "a", "first_seen": _iso(3)},
            {"name": "b", "first_seen": _iso(15)},
        ]
        no_kw = rank_module.calculate_freshness_scores(rows)
        with_kw = rank_module.calculate_freshness_scores(rows, config=_CFG)
        assert set(no_kw.keys()) == set(with_kw.keys())
        for k in no_kw:
            assert no_kw[k] == pytest.approx(with_kw[k], abs=1e-9)


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


# --------------------------------------------------------------------------- #
# extract_item_name_from_path
# --------------------------------------------------------------------------- #

class TestExtractItemNameFromPath:
    _fn = staticmethod(rank_module.extract_item_name_from_path)

    def test_basic_two_segment_path(self):
        assert self._fn("/packages/doubleml") == "doubleml"

    def test_hyphens_become_spaces(self):
        assert self._fn("/papers/causal-inference") == "causal inference"

    def test_underscores_become_spaces(self):
        assert self._fn("/resources/synthetic_control") == "synthetic control"

    def test_lowercases_result(self):
        assert self._fn("/packages/DoubleML") == "doubleml"

    def test_none_returns_none(self):
        assert self._fn(None) is None

    def test_empty_string_returns_none(self):
        assert self._fn("") is None

    def test_single_segment_returns_none(self):
        # Only one segment → not enough parts
        assert self._fn("/packages") is None

    def test_three_segments_returns_last(self):
        assert self._fn("/section/category/item") == "item"


# --------------------------------------------------------------------------- #
# extract_url_domain
# --------------------------------------------------------------------------- #

class TestExtractUrlDomain:
    _fn = staticmethod(rank_module.extract_url_domain)

    def test_github_url(self):
        assert self._fn("https://github.com/org/repo") == "github"

    def test_arxiv_url(self):
        assert self._fn("https://arxiv.org/abs/1234.5678") == "arxiv"

    def test_youtube_url(self):
        assert self._fn("https://youtube.com/watch?v=x") == "youtube"

    def test_kaggle_url(self):
        assert self._fn("https://kaggle.com/datasets/foo") == "kaggle"

    def test_medium_url(self):
        assert self._fn("https://medium.com/@author/post") == "medium"

    def test_substack_url(self):
        assert self._fn("https://author.substack.com/p/post") == "substack"

    def test_other_url(self):
        assert self._fn("https://some-other-site.io/doc") == "other"

    def test_empty_string_returns_none_domain(self):
        assert self._fn("") == "none"

    def test_none_returns_none_domain(self):
        assert self._fn(None) == "none"

    def test_malformed_url_returns_none_domain(self):
        # urlparse is lenient but domain would be empty
        result = self._fn("not-a-url")
        assert result in ("none", "other")


# --------------------------------------------------------------------------- #
# normalize_scores
# --------------------------------------------------------------------------- #

class TestNormalizeScores:
    _fn = staticmethod(rank_module.normalize_scores)

    def test_empty_dict_returns_empty(self):
        assert self._fn({}) == {}

    def test_all_equal_returns_half(self):
        result = self._fn({"a": 5.0, "b": 5.0, "c": 5.0})
        assert all(v == 0.5 for v in result.values())

    def test_min_zero_max_one(self):
        result = self._fn({"a": 0.0, "b": 1.0})
        assert result["a"] == pytest.approx(0.0)
        assert result["b"] == pytest.approx(1.0)

    def test_result_in_unit_interval(self):
        scores = {"x": 10, "y": 3, "z": 7, "w": 1}
        result = self._fn(scores)
        for v in result.values():
            assert 0.0 <= v <= 1.0

    def test_preserves_relative_order(self):
        scores = {"high": 100, "mid": 50, "low": 10}
        result = self._fn(scores)
        assert result["high"] > result["mid"] > result["low"]

    def test_keys_preserved(self):
        scores = {"alpha": 1.0, "beta": 2.0}
        assert set(self._fn(scores).keys()) == {"alpha", "beta"}


# --------------------------------------------------------------------------- #
# safe_join
# --------------------------------------------------------------------------- #

class TestSafeJoin:
    _fn = staticmethod(rank_module.safe_join)

    def test_none_returns_empty(self):
        assert self._fn(None) == ""

    def test_string_returned_as_is(self):
        assert self._fn("causal inference") == "causal inference"

    def test_list_joined_with_spaces(self):
        assert self._fn(["causal", "inference"]) == "causal inference"

    def test_list_with_none_items_filtered(self):
        assert self._fn(["a", None, "b"]) == "a b"

    def test_empty_list_returns_empty(self):
        assert self._fn([]) == ""

    def test_non_string_list_items_converted(self):
        assert self._fn([1, 2, 3]) == "1 2 3"

    def test_integer_converted_to_string(self):
        assert self._fn(42) == "42"


# --------------------------------------------------------------------------- #
# apply_citations_boost
# --------------------------------------------------------------------------- #

class TestApplyCitationsBoost:
    _fn = staticmethod(rank_module.apply_citations_boost)

    def test_paper_with_citations_boosted(self, capsys):
        items = [{"name": "high_cite", "type": "paper", "citations": 1000}]
        scores = {"high_cite": 0.3}
        result = self._fn(items, scores)
        assert result["high_cite"] > 0.3

    def test_paper_without_citations_unchanged(self, capsys):
        items = [{"name": "nocite", "type": "paper", "citations": 0}]
        scores = {"nocite": 0.3}
        result = self._fn(items, scores)
        assert result["nocite"] == pytest.approx(0.3)

    def test_non_paper_type_not_boosted(self, capsys):
        items = [{"name": "pkg", "type": "package", "citations": 999}]
        scores = {"pkg": 0.3}
        result = self._fn(items, scores)
        assert result["pkg"] == pytest.approx(0.3)

    def test_score_capped_at_one(self, capsys):
        items = [{"name": "viral", "type": "paper", "citations": 1000000}]
        scores = {"viral": 0.99}
        result = self._fn(items, scores)
        assert result["viral"] <= 1.0

    def test_paper_not_in_scores_gets_baseline(self, capsys):
        items = [{"name": "newpaper", "type": "paper", "citations": 50}]
        scores = {}
        result = self._fn(items, scores)
        assert "newpaper" in result
        assert result["newpaper"] > 0.0

    def test_empty_items_returns_scores_unchanged(self, capsys):
        scores = {"a": 0.5}
        result = self._fn([], scores)
        assert result == {"a": 0.5}


# --------------------------------------------------------------------------- #
# build_engagement_scores
# --------------------------------------------------------------------------- #

class TestBuildEngagementScores:
    _fn = staticmethod(rank_module.build_engagement_scores)

    def test_empty_data_returns_empty_scores(self):
        scores, signals, _ = self._fn({})
        assert len(scores) == 0

    def test_click_adds_to_score(self):
        data = {"clicks": [{"name": "DoubleML", "click_count": 10}]}
        scores, signals, _ = self._fn(data)
        assert "doubleml" in scores
        assert scores["doubleml"] > 0

    def test_click_count_proportional(self):
        data1 = {"clicks": [{"name": "A", "click_count": 10}]}
        data2 = {"clicks": [{"name": "A", "click_count": 20}]}
        s1, _, _ = self._fn(data1)
        s2, _, _ = self._fn(data2)
        assert s2["a"] > s1["a"]

    def test_name_lowercased(self):
        data = {"clicks": [{"name": "MyTool", "click_count": 5}]}
        scores, _, _ = self._fn(data)
        assert "mytool" in scores
        assert "MyTool" not in scores

    def test_search_clicks_contribute_to_score(self):
        import json
        scores_imp_only, _, _ = self._fn({"impressions": [{"name": "item", "impression_count": 100}]})
        # search_clicks rows use a nested clicks JSON array with {id, position} objects
        scores_search_only, _, _ = self._fn({
            "search_clicks": [{"clicks": json.dumps([{"id": "item", "position": 1}])}]
        })
        assert scores_imp_only.get("item", 0) > 0
        assert scores_search_only.get("item", 0) > 0

    def test_null_count_treated_as_zero(self):
        data = {"clicks": [{"name": "A", "click_count": None}]}
        scores, _, _ = self._fn(data)
        assert scores.get("a", 0) == 0

    def test_signals_track_raw_counts(self):
        data = {"clicks": [{"name": "tool", "click_count": 7}]}
        _, signals, _ = self._fn(data)
        assert signals["tool"]["clicks"] == 7
