"""Tests for scripts/analyze_experiments.py.

Pure-function coverage for stats helpers + the report renderer + the
CLI verdict heuristic. The wrangler-subprocess query path is mocked in
the integration tests; we never spawn an actual subprocess in CI.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "analyze_experiments.py"
_spec = importlib.util.spec_from_file_location("analyze_experiments", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["analyze_experiments"] = mod
_spec.loader.exec_module(mod)


# --------------------------------------------------------------------------- #
# Stats helpers
# --------------------------------------------------------------------------- #


class TestWilsonCi:
    def test_zero_trials_returns_zeros(self):
        assert mod.wilson_ci(0, 0) == (0.0, 0.0)

    def test_centred_proportion(self):
        # 50/100 -> CI symmetric around 0.5
        lo, hi = mod.wilson_ci(50, 100)
        assert lo < 0.5 < hi
        assert pytest.approx(0.5 - lo, abs=1e-3) == pytest.approx(hi - 0.5, abs=1e-3)

    def test_extreme_proportion_clamped_to_unit_interval(self):
        # 100/100 should give a CI strictly within [0, 1]
        lo, hi = mod.wilson_ci(100, 100)
        assert 0.0 <= lo <= 1.0
        assert 0.0 <= hi <= 1.0
        assert lo < 1.0  # has uncertainty; not exactly 1

    def test_narrows_with_sample_size(self):
        lo10, hi10 = mod.wilson_ci(5, 10)
        lo1k, hi1k = mod.wilson_ci(500, 1000)
        # Both centred at 0.5 but the 1000-sample CI is much tighter.
        assert (hi1k - lo1k) < (hi10 - lo10)


class TestTwoPropZ:
    def test_zero_n_returns_neutral(self):
        z, p = mod.two_prop_z(0, 0, 0, 0)
        assert z == 0.0 and p == 1.0

    def test_identical_proportions_gives_zero_z(self):
        z, p = mod.two_prop_z(50, 100, 50, 100)
        assert z == pytest.approx(0.0, abs=1e-9)
        assert p == pytest.approx(1.0, abs=1e-9)

    def test_clear_difference_is_significant(self):
        # 80/100 vs 20/100 — should be a strong z-stat with tiny p
        z, p = mod.two_prop_z(80, 100, 20, 100)
        assert z > 5  # treatment >> control
        assert p < 0.001

    def test_reverse_direction_yields_negative_z(self):
        z, _ = mod.two_prop_z(20, 100, 80, 100)
        assert z < 0


# --------------------------------------------------------------------------- #
# VariantRow + verdict
# --------------------------------------------------------------------------- #


class TestVariantRow:
    def test_ctr_basic(self):
        r = mod.VariantRow(variant="control", impressions=1000, clicks=50)
        assert r.ctr == 0.05

    def test_ctr_zero_impressions(self):
        r = mod.VariantRow(variant="control", impressions=0, clicks=0)
        assert r.ctr == 0.0


class TestVerdict:
    def test_insufficient_when_under_100_per_arm(self):
        out = mod._verdict(p_value=0.001, delta=0.5, n1=50, n2=200)
        assert "insufficient" in out

    def test_treatment_wins_on_strong_positive(self):
        out = mod._verdict(p_value=0.001, delta=0.05, n1=500, n2=500)
        assert out == "treatment-wins"

    def test_control_wins_on_strong_negative(self):
        out = mod._verdict(p_value=0.001, delta=-0.05, n1=500, n2=500)
        assert out == "control-wins"

    def test_weak_signal_threshold(self):
        out = mod._verdict(p_value=0.03, delta=0.01, n1=500, n2=500)
        assert out == "weak signal"

    def test_no_effect_default(self):
        out = mod._verdict(p_value=0.5, delta=0.001, n1=500, n2=500)
        assert out == "no effect"


# --------------------------------------------------------------------------- #
# load_experiments
# --------------------------------------------------------------------------- #


class TestLoadExperiments:
    def test_returns_empty_when_file_missing(self, tmp_path):
        assert mod.load_experiments(tmp_path / "nope.json") == []

    def test_filters_to_active_and_paused(self, tmp_path):
        p = tmp_path / "experiments.json"
        p.write_text(json.dumps({
            "experiments": [
                {"id": "active_one", "status": "active"},
                {"id": "paused_one", "status": "paused"},
                {"id": "draft_one", "status": "draft"},
                {"id": "missing_status"},
                {"id": 42, "status": "active"},  # non-string id, drop
                "not-a-dict",
            ]
        }), encoding="utf-8")
        out = mod.load_experiments(p)
        ids = sorted(e["id"] for e in out)
        assert ids == ["active_one", "paused_one"]


# --------------------------------------------------------------------------- #
# fetch_variant_counts (mocked subprocess)
# --------------------------------------------------------------------------- #


def _mock_wrangler(payload):
    """Patch _wrangler_query to return a fixed list of result dicts."""
    return patch.object(mod, "_wrangler_query", return_value=payload)


class TestFetchVariantCounts:
    def test_parses_typical_response(self):
        with _mock_wrangler([
            {"variant": "control", "impressions": "200", "clicks": "10"},
            {"variant": "treatment", "impressions": "210", "clicks": "20"},
        ]):
            rows = mod.fetch_variant_counts("homepage_row_mmr")
        assert len(rows) == 2
        rows = sorted(rows, key=lambda r: r.variant)
        assert rows[0].variant == "control"
        assert rows[0].impressions == 200
        assert rows[0].clicks == 10
        assert rows[1].variant == "treatment"

    def test_drops_rows_with_non_string_variant(self):
        with _mock_wrangler([
            {"variant": None, "impressions": 1, "clicks": 0},  # SQL NULL
            {"variant": "control", "impressions": 1, "clicks": 0},
        ]):
            rows = mod.fetch_variant_counts("e1")
        assert [r.variant for r in rows] == ["control"]

    def test_empty_response(self):
        with _mock_wrangler([]):
            assert mod.fetch_variant_counts("e1") == []

    def test_missing_count_fields_default_to_zero(self):
        with _mock_wrangler([{"variant": "control"}]):
            rows = mod.fetch_variant_counts("e1")
        assert rows[0].impressions == 0
        assert rows[0].clicks == 0


# --------------------------------------------------------------------------- #
# render_report
# --------------------------------------------------------------------------- #


class TestRenderReport:
    def _exp(self, **kw):
        return {
            "id": kw.get("id", "homepage_row_mmr"),
            "status": kw.get("status", "active"),
            "primary_metric": kw.get("primary_metric", "ctr_top10"),
            "started_at": kw.get("started_at", "2026-05-04"),
        }

    def test_no_data_message(self):
        report = mod.render_report(self._exp(), [])
        assert "No data yet" in report
        assert "homepage_row_mmr" in report

    def test_includes_per_variant_table(self):
        rows = [
            mod.VariantRow("control", 1000, 50),
            mod.VariantRow("treatment", 1000, 80),
        ]
        report = mod.render_report(self._exp(), rows)
        assert "Per-variant counts" in report
        assert "1,000" in report  # commafied impressions
        assert "0.0500" in report  # control CTR
        assert "0.0800" in report  # treatment CTR

    def test_pairwise_table_when_control_present(self):
        rows = [
            mod.VariantRow("control", 1000, 50),
            mod.VariantRow("treatment", 1000, 80),
        ]
        report = mod.render_report(self._exp(), rows)
        assert "vs `control`" in report
        # Treatment has clear positive delta -> verdict should reflect that
        assert "treatment-wins" in report or "weak signal" in report

    def test_skips_pairwise_when_no_control(self):
        rows = [
            mod.VariantRow("alpha", 1000, 50),
            mod.VariantRow("beta", 1000, 60),
        ]
        report = mod.render_report(self._exp(), rows)
        assert "skipping pairwise" in report.lower()

    def test_includes_reproducibility_sql(self):
        rows = [mod.VariantRow("control", 100, 5)]
        report = mod.render_report(self._exp(), rows)
        assert "json_extract(experiments" in report
        assert "GROUP BY variant" in report

    def test_insufficient_n_verdict_when_low_traffic(self):
        rows = [
            mod.VariantRow("control", 30, 1),
            mod.VariantRow("treatment", 30, 5),
        ]
        report = mod.render_report(self._exp(), rows)
        assert "insufficient" in report.lower()


# --------------------------------------------------------------------------- #
# _coerce_ms
# --------------------------------------------------------------------------- #


class TestCoerceMs:
    def test_unix_seconds(self):
        assert mod._coerce_ms("1700000000") == 1_700_000_000_000

    def test_unix_millis(self):
        assert mod._coerce_ms("1700000000000") == 1_700_000_000_000

    def test_iso_date(self):
        # Round-trip: convert to ms then back, the date should match.
        from datetime import datetime, timezone
        out = mod._coerce_ms("2026-05-04")
        round_trip = datetime.fromtimestamp(out / 1000, tz=timezone.utc).isoformat()
        assert round_trip.startswith("2026-05-04T00:00:00")

    def test_iso_datetime_with_z(self):
        from datetime import datetime, timezone
        out = mod._coerce_ms("2026-05-04T10:00:00Z")
        assert datetime.fromtimestamp(out / 1000, tz=timezone.utc).isoformat().startswith("2026-05-04T10:00")


# ---------------------------------------------------------------------------
# _wrangler_query — preamble stripping + error paths (mocked subprocess)
# ---------------------------------------------------------------------------

import subprocess
from types import SimpleNamespace


def _proc(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)


class TestWranglerQuery:
    """Tests for _wrangler_query's Wrangler 4.x preamble stripping."""

    def _patch(self, result):
        return patch("analyze_experiments.subprocess.run", return_value=result)

    def test_clean_json_array_parsed(self):
        rows = [{"variant": "control", "clicks": 10}]
        payload = [{"results": rows}]
        with self._patch(_proc(stdout=json.dumps(payload))):
            out = mod._wrangler_query("SELECT 1")
        assert out == rows

    def test_wrangler_4x_preamble_stripped(self):
        rows = [{"variant": "treatment", "clicks": 5}]
        payload = [{"results": rows}]
        preamble = "Cloudflare agent skills are available...\nSome other line\n"
        with self._patch(_proc(stdout=preamble + json.dumps(payload))):
            out = mod._wrangler_query("SELECT 1")
        assert out == rows

    def test_no_json_array_raises_value_error(self):
        with self._patch(_proc(stdout="no brackets here")):
            with pytest.raises(ValueError, match="no JSON array"):
                mod._wrangler_query("SELECT 1")

    def test_invalid_json_raises_value_error(self):
        with self._patch(_proc(stdout="[not valid json]")):
            with pytest.raises(ValueError, match="JSON parse failed"):
                mod._wrangler_query("SELECT 1")

    def test_empty_results_list_returns_empty(self):
        payload = [{"results": []}]
        with self._patch(_proc(stdout=json.dumps(payload))):
            out = mod._wrangler_query("SELECT 1")
        assert out == []

    def test_empty_payload_list_returns_empty(self):
        with self._patch(_proc(stdout="[]")):
            out = mod._wrangler_query("SELECT 1")
        assert out == []
