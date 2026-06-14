"""Tests for scripts/build_site_scoreboard.py.

Coverage:
    - Parses metrics.csv rows correctly (field names, float parsing, date slicing)
    - Handles missing replays.csv gracefully (returns empty history, no crash)
    - Parses per-variant counts + CTR from an experiment markdown report
    - Writes valid JSON to disk atomically via .tmp rename

No network, no subprocess, no filesystem mutation outside tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


# ── load script as module ────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "build_site_scoreboard.py"
_spec = importlib.util.spec_from_file_location("build_site_scoreboard", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
bss = importlib.util.module_from_spec(_spec)
sys.modules["build_site_scoreboard"] = bss
_spec.loader.exec_module(bss)


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_metrics_csv(path: Path, rows: list[dict]) -> None:
    """Write a minimal metrics.csv to path."""
    headers = [
        "run_at_utc", "git_sha", "holdout_days",
        "n_sessions_total", "n_sessions_evaluable", "n_sessions_skipped",
        "mean_average_precision", "notes",
        "ndcg_at_5", "precision_at_5", "recall_at_5", "hit_rate_at_5",
        "ndcg_at_10", "precision_at_10", "recall_at_10", "hit_rate_at_10",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(headers) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(h, "")) for h in headers) + "\n")


def _write_experiment_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── Test: parses metrics.csv correctly ──────────────────────────────────────


class TestParseMetricsRow:
    def test_field_names_and_float_parsing(self):
        row = {
            "run_at_utc": "2026-05-03T20:37:56Z",
            "git_sha": "3a5ba9b",
            "holdout_days": "60",
            "n_sessions_total": "139",
            "n_sessions_evaluable": "15",
            "n_sessions_skipped": "124",
            "mean_average_precision": "0.414948",
            "notes": "rerank source=api",
            "ndcg_at_5": "0.386307",
            "ndcg_at_10": "0.419125",
            "hit_rate_at_5": "0.666667",
            "hit_rate_at_10": "0.8",
            "precision_at_10": "0.126667",
        }
        parsed = bss._parse_metrics_row(row)
        assert parsed["date"] == "2026-05-03"
        assert parsed["ndcg_at_10"] == pytest.approx(0.419125)
        assert parsed["hit_rate_at_10"] == pytest.approx(0.8)
        assert parsed["map_at_10"] == pytest.approx(0.414948)
        assert parsed["holdout_days"] == 60
        assert parsed["n_evaluable_sessions"] == 15
        assert parsed["notes"] == "rerank source=api"

    def test_git_sha_truncated_to_7(self):
        row = {"git_sha": "3a5ba9b1234abc", "run_at_utc": "", "holdout_days": ""}
        parsed = bss._parse_metrics_row(row)
        assert parsed["git_sha"] == "3a5ba9b"

    def test_missing_optional_fields_return_none(self):
        parsed = bss._parse_metrics_row({})
        assert parsed["ndcg_at_10"] is None
        assert parsed["hit_rate_at_10"] is None
        assert parsed["holdout_days"] is None


class TestBuildMetrics:
    def test_parses_real_metrics_csv(self, tmp_path):
        csv_path = tmp_path / "metrics.csv"
        _write_metrics_csv(
            csv_path,
            [
                {
                    "run_at_utc": "2026-05-03T20:37:56Z",
                    "git_sha": "3a5ba9b",
                    "holdout_days": "60",
                    "n_sessions_total": "139",
                    "n_sessions_evaluable": "15",
                    "n_sessions_skipped": "124",
                    "mean_average_precision": "0.414948",
                    "notes": "rerank source=api",
                    "ndcg_at_5": "0.386307",
                    "ndcg_at_10": "0.419125",
                    "hit_rate_at_5": "0.666667",
                    "hit_rate_at_10": "0.8",
                }
            ],
        )
        result = bss.build_metrics(csv_path)
        assert result["latest"] is not None
        assert result["latest"]["ndcg_at_10"] == pytest.approx(0.419125)
        assert len(result["history"]) == 1
        assert result["history"][0]["date"] == "2026-05-03"

    def test_multiple_rows_latest_is_last(self, tmp_path):
        csv_path = tmp_path / "metrics.csv"
        _write_metrics_csv(
            csv_path,
            [
                {"run_at_utc": "2026-05-01T00:00:00Z", "ndcg_at_10": "0.40"},
                {"run_at_utc": "2026-05-10T00:00:00Z", "ndcg_at_10": "0.45"},
            ],
        )
        result = bss.build_metrics(csv_path)
        assert result["latest"]["ndcg_at_10"] == pytest.approx(0.45)
        assert len(result["history"]) == 2


# ── Test: handles missing replays.csv gracefully ─────────────────────────────


class TestBuildReplaysGraceful:
    def test_missing_file_returns_empty_history(self, tmp_path):
        result = bss.build_replays(tmp_path / "replays.csv")
        assert result["latest"] is None
        assert result["history"] == []

    def test_header_only_csv_returns_empty_history(self, tmp_path):
        p = tmp_path / "replays.csv"
        p.write_text(
            "run_at_utc,git_sha,baseline_path,candidate_path,n_sessions,"
            "n_evaluable,verdict,notes,baseline_ndcg_at_10,candidate_ndcg_at_10,"
            "delta_ndcg_at_10,baseline_hit_rate_at_10,candidate_hit_rate_at_10,"
            "delta_hit_rate_at_10\n",
            encoding="utf-8",
        )
        result = bss.build_replays(p)
        assert result["latest"] is None
        assert result["history"] == []

    def test_parses_real_replay_row(self, tmp_path):
        p = tmp_path / "replays.csv"
        p.write_text(
            "run_at_utc,git_sha,baseline_path,candidate_path,n_sessions,"
            "n_evaluable,verdict,notes,baseline_ndcg_at_10,candidate_ndcg_at_10,"
            "delta_ndcg_at_10,baseline_hit_rate_at_10,candidate_hit_rate_at_10,"
            "delta_hit_rate_at_10\n"
            "2026-05-24T03:35:46Z,2bb7722,/data/global_rankings.json,"
            "data/global_rankings.json,145,39,ok,,0.2275,0.2275,0.0,0.59,0.59,0.0\n",
            encoding="utf-8",
        )
        result = bss.build_replays(p)
        assert result["latest"] is not None
        assert result["latest"]["n_evaluable"] == 39
        assert result["latest"]["baseline_ndcg_at_10"] == pytest.approx(0.2275)
        assert result["latest"]["verdict"] == "ok"


# ── Test: parses experiment markdown report ───────────────────────────────────


class TestParseExperimentReport:
    _SAMPLE_MD = """\
# Experiment report: `harness_aa_v1`

- **status:** `active`
- **primary metric:** `ctr`

## Per-variant counts + CTR

| variant | impressions | clicks | CTR | 95% CI |
|---|---:|---:|---:|---|
| `control_a` | 8,071 | 322 | 0.0399 | [0.0358, 0.0444] |
| `control_b` | 10,205 | 237 | 0.0232 | [0.0205, 0.0263] |
"""

    def test_parses_both_variants(self, tmp_path):
        p = tmp_path / "harness_aa_v1-2026-05-24.md"
        p.write_text(self._SAMPLE_MD, encoding="utf-8")
        results = bss._parse_experiment_report(p)
        assert results is not None
        assert "control_a" in results
        assert "control_b" in results

    def test_parses_impressions_clicks_ctr_ci(self, tmp_path):
        p = tmp_path / "harness_aa_v1-2026-05-24.md"
        p.write_text(self._SAMPLE_MD, encoding="utf-8")
        results = bss._parse_experiment_report(p)
        a = results["control_a"]
        assert a["impressions"] == 8071
        assert a["clicks"] == 322
        assert a["ctr"] == pytest.approx(0.0399)
        assert a["ci_low"] == pytest.approx(0.0358)
        assert a["ci_high"] == pytest.approx(0.0444)

    def test_returns_none_for_missing_file(self, tmp_path):
        result = bss._parse_experiment_report(tmp_path / "nope.md")
        assert result is None

    def test_returns_none_for_file_with_no_table(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("# No table here\nJust prose.\n", encoding="utf-8")
        result = bss._parse_experiment_report(p)
        assert result is None


# ── Test: writes valid JSON to disk ──────────────────────────────────────────


class TestWriteScoreboard:
    def test_writes_valid_json(self, tmp_path):
        scoreboard = {
            "generated_at": "2026-05-24T00:00:00+00:00",
            "metrics": {"latest": None, "history": []},
            "replays": {"latest": None, "history": []},
            "experiments": [],
        }
        out = tmp_path / "site_scoreboard.json"
        bss.write_scoreboard(scoreboard, out)
        assert out.exists()
        with out.open(encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["generated_at"] == "2026-05-24T00:00:00+00:00"
        assert loaded["experiments"] == []

    def test_atomic_write_no_partial_file_on_success(self, tmp_path):
        out = tmp_path / "site_scoreboard.json"
        scoreboard = {"generated_at": "x", "metrics": {}, "replays": {}, "experiments": []}
        bss.write_scoreboard(scoreboard, out)
        # .tmp file should be cleaned up
        assert not (tmp_path / "site_scoreboard.tmp").exists()
        assert out.exists()

    def test_output_ends_with_newline(self, tmp_path):
        out = tmp_path / "site_scoreboard.json"
        bss.write_scoreboard({"a": 1}, out)
        raw = out.read_bytes()
        assert raw.endswith(b"\n")


# ── Test: end-to-end main() ───────────────────────────────────────────────────


def test_main_produces_valid_json(tmp_path, capsys):
    # Set up minimal directory structure
    (tmp_path / "reports" / "experiments").mkdir(parents=True)
    (tmp_path / "data").mkdir()

    _write_metrics_csv(
        tmp_path / "reports" / "metrics.csv",
        [
            {
                "run_at_utc": "2026-05-03T20:37:56Z",
                "git_sha": "3a5ba9b",
                "holdout_days": "60",
                "n_sessions_evaluable": "15",
                "ndcg_at_10": "0.4191",
                "hit_rate_at_10": "0.80",
                "mean_average_precision": "0.415",
                "notes": "seed",
            }
        ],
    )
    # No replays.csv -- should be handled gracefully
    exp_json = tmp_path / "data" / "experiments.json"
    exp_json.write_text(
        json.dumps(
            {
                "_meta": {},
                "experiments": [
                    {
                        "id": "my_aa_v1",
                        "status": "paused",
                        "started_at": "2026-05-04",
                        "ended_at": "2026-05-20",
                        "primary_metric": "ctr",
                        "variants": [
                            {"id": "control_a", "traffic": 50},
                            {"id": "control_b", "traffic": 50},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "data" / "site_scoreboard.json"
    rc = bss.main(["--repo-root", str(tmp_path), "--output", str(out)])
    assert rc == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "generated_at" in data
    assert data["metrics"]["latest"]["ndcg_at_10"] == pytest.approx(0.4191)
    assert data["replays"]["history"] == []
    assert len(data["experiments"]) == 1


# ── _try_float / _try_int / _shorten_path ─────────────────────────────────────


class TestTryFloat:
    def test_valid_float(self):
        assert bss._try_float("3.14") == pytest.approx(3.14)

    def test_int_string_parses_to_float(self):
        assert bss._try_float("42") == pytest.approx(42.0)

    def test_empty_string_returns_default(self):
        assert bss._try_float("") is None
        assert bss._try_float("", 0.0) == 0.0

    def test_whitespace_only_returns_default(self):
        assert bss._try_float("   ") is None

    def test_none_input_returns_default(self):
        assert bss._try_float(None) is None
        assert bss._try_float(None, -1.0) == -1.0

    def test_non_numeric_returns_default(self):
        assert bss._try_float("abc") is None
        assert bss._try_float("abc", 0.5) == pytest.approx(0.5)

    def test_strips_whitespace_before_parse(self):
        assert bss._try_float("  2.718  ") == pytest.approx(2.718)


class TestTryInt:
    def test_valid_int(self):
        assert bss._try_int("7") == 7

    def test_empty_string_returns_default(self):
        assert bss._try_int("") is None
        assert bss._try_int("", 0) == 0

    def test_none_input_returns_default(self):
        assert bss._try_int(None) is None

    def test_float_string_returns_default(self):
        # "3.14" is not a valid int
        assert bss._try_int("3.14") is None

    def test_non_numeric_returns_default(self):
        assert bss._try_int("foo", 99) == 99

    def test_strips_whitespace(self):
        assert bss._try_int("  15  ") == 15


class TestShortenPath:
    def test_returns_stem_of_path(self):
        assert bss._shorten_path("reports/metrics_v2.csv") == "metrics_v2"

    def test_no_directory_just_filename(self):
        assert bss._shorten_path("model.pkl") == "model"

    def test_empty_string_returns_empty(self):
        assert bss._shorten_path("") == ""

    def test_no_extension_returns_full_stem(self):
        assert bss._shorten_path("reports/myfile") == "myfile"

    def test_absolute_path(self):
        assert bss._shorten_path("/tmp/output/rankings_2026.json") == "rankings_2026"


# ── _find_latest_experiment_report ───────────────────────────────────────────


class TestFindLatestExperimentReport:
    def test_returns_none_when_dir_missing(self, tmp_path):
        result = bss._find_latest_experiment_report(tmp_path / "nonexistent", "exp_aa_v1")
        assert result is None

    def test_returns_none_when_no_matching_files(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        result = bss._find_latest_experiment_report(reports, "exp_aa_v1")
        assert result is None

    def test_returns_single_matching_file(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        f = reports / "exp_aa_v1-2026-05-10.md"
        f.write_text("# report")
        result = bss._find_latest_experiment_report(reports, "exp_aa_v1")
        assert result == f

    def test_returns_lexicographically_latest_date(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        for date in ["2026-04-01", "2026-05-10", "2026-05-09"]:
            (reports / f"exp_aa_v1-{date}.md").write_text("")
        result = bss._find_latest_experiment_report(reports, "exp_aa_v1")
        assert result.name == "exp_aa_v1-2026-05-10.md"

    def test_ignores_different_experiment_id(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "exp_bb_v1-2026-05-10.md").write_text("")
        result = bss._find_latest_experiment_report(reports, "exp_aa_v1")
        assert result is None

    def test_ignores_files_without_date_pattern(self, tmp_path):
        reports = tmp_path / "reports"
        reports.mkdir()
        (reports / "exp_aa_v1-latest.md").write_text("")
        result = bss._find_latest_experiment_report(reports, "exp_aa_v1")
        assert result is None
