"""Tests for scripts/scoreboard_status.py.

Pure-function coverage for the format helpers + decision guard. Print
output is exercised end-to-end via main() with synthetic CSVs in
tmp_path; we capture stdout with capsys and assert key phrases. No
network, no filesystem mutation outside tmp_path.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest


# Load the script as a module since scripts/ isn't a package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "scoreboard_status.py"
_spec = importlib.util.spec_from_file_location("scoreboard_status", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
scoreboard_status = importlib.util.module_from_spec(_spec)
sys.modules["scoreboard_status"] = scoreboard_status
_spec.loader.exec_module(scoreboard_status)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


class TestFmtMetric:
    def test_formats_to_4_decimals(self):
        row = {"ndcg_at_10": "0.41912543"}
        assert scoreboard_status.fmt_metric(row, "ndcg_at_10") == "0.4191"

    def test_returns_question_for_missing(self):
        assert scoreboard_status.fmt_metric({}, "ndcg_at_10") == "?"
        assert scoreboard_status.fmt_metric({"ndcg_at_10": ""}, "ndcg_at_10") == "?"
        assert scoreboard_status.fmt_metric({"ndcg_at_10": "  "}, "ndcg_at_10") == "?"

    def test_returns_raw_for_unparseable(self):
        # Non-numeric strings are passed through as-is, not silently "?'d"
        assert scoreboard_status.fmt_metric({"x": "n/a"}, "x") == "n/a"


class TestFmtDelta:
    def test_positive_delta(self):
        curr = {"ndcg_at_10": "0.42"}
        prev = {"ndcg_at_10": "0.40"}
        s = scoreboard_status.fmt_delta(curr, prev, "ndcg_at_10")
        assert "+0.0200" in s
        assert "+5.0%" in s

    def test_negative_delta(self):
        curr = {"ndcg_at_10": "0.38"}
        prev = {"ndcg_at_10": "0.40"}
        s = scoreboard_status.fmt_delta(curr, prev, "ndcg_at_10")
        assert "-0.0200" in s
        assert "-5.0%" in s

    def test_empty_on_unparseable(self):
        assert scoreboard_status.fmt_delta({}, {}, "x") == ""
        assert scoreboard_status.fmt_delta({"x": ""}, {"x": "0.5"}, "x") == ""

    def test_handles_zero_prev_without_div_by_zero(self):
        curr = {"ndcg_at_10": "0.1"}
        prev = {"ndcg_at_10": "0.0"}
        # Should not raise; pct degrades to 0.0 when prev is 0.
        s = scoreboard_status.fmt_delta(curr, prev, "ndcg_at_10")
        assert "+0.1000" in s


class TestFindComparablePrior:
    def test_returns_none_at_index_zero(self):
        rows = [{"holdout_days": "60"}]
        assert scoreboard_status.find_comparable_prior(rows, 0) is None

    def test_returns_immediate_prior_when_match(self):
        rows = [
            {"holdout_days": "60", "tag": "a"},
            {"holdout_days": "60", "tag": "b"},
        ]
        prior = scoreboard_status.find_comparable_prior(rows, 1)
        assert prior is not None
        assert prior["tag"] == "a"

    def test_walks_back_past_mismatched_holdouts(self):
        # We want the prior with same holdout, even if newer-but-different rows sit between.
        rows = [
            {"holdout_days": "60", "tag": "match-old"},
            {"holdout_days": "30", "tag": "skip-me"},
            {"holdout_days": "60", "tag": "current"},
        ]
        prior = scoreboard_status.find_comparable_prior(rows, 2)
        assert prior is not None
        assert prior["tag"] == "match-old"

    def test_returns_none_when_no_prior_matches(self):
        rows = [
            {"holdout_days": "30", "tag": "a"},
            {"holdout_days": "60", "tag": "b"},
        ]
        # Current is holdout=60; no prior row had holdout=60.
        assert scoreboard_status.find_comparable_prior(rows, 1) is None


class TestLoadCsv:
    def test_returns_empty_for_missing_file(self, tmp_path):
        rows = scoreboard_status.load_csv(tmp_path / "nope.csv")
        assert rows == []

    def test_loads_rows(self, tmp_path):
        p = tmp_path / "x.csv"
        with p.open("w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n3,4\n")
        assert scoreboard_status.load_csv(p) == [
            {"a": "1", "b": "2"},
            {"a": "3", "b": "4"},
        ]


# --------------------------------------------------------------------------- #
# main() end-to-end with synthetic CSVs
# --------------------------------------------------------------------------- #


def _write_metrics(path: Path, rows: list[dict[str, str]]) -> None:
    cols = [
        "run_at_utc",
        "git_sha",
        "holdout_days",
        "n_sessions_evaluable",
        "ndcg_at_5",
        "hit_rate_at_5",
        "mean_average_precision",
        "ndcg_at_10",
        "hit_rate_at_10",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_main_empty_metrics_says_empty(tmp_path, capsys):
    metrics = tmp_path / "metrics.csv"
    replays = tmp_path / "replays.csv"
    rc = scoreboard_status.main(
        ["--metrics", str(metrics), "--replays", str(replays)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "scoreboard: empty" in out


def test_main_single_row_red_decision_guard(tmp_path, capsys):
    metrics = tmp_path / "metrics.csv"
    replays = tmp_path / "replays.csv"
    _write_metrics(
        metrics,
        [
            {
                "run_at_utc": "2026-05-03T20:00:00Z",
                "git_sha": "abc1234",
                "holdout_days": "60",
                "n_sessions_evaluable": "15",
                "ndcg_at_10": "0.4191",
                "hit_rate_at_10": "0.8000",
                "ndcg_at_5": "0.3",
                "hit_rate_at_5": "0.5",
                "mean_average_precision": "0.4",
                "notes": "seed",
            }
        ],
    )
    rc = scoreboard_status.main(
        ["--metrics", str(metrics), "--replays", str(replays)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 row(s)" in out
    assert "0.4191" in out
    assert "decision guard: RED" in out


def test_main_three_rows_green_with_delta(tmp_path, capsys):
    metrics = tmp_path / "metrics.csv"
    replays = tmp_path / "replays.csv"
    _write_metrics(
        metrics,
        [
            {
                "run_at_utc": "2026-05-01T00:00:00Z",
                "git_sha": "111",
                "holdout_days": "60",
                "n_sessions_evaluable": "15",
                "ndcg_at_10": "0.40",
                "hit_rate_at_10": "0.75",
                "ndcg_at_5": "0.3",
                "hit_rate_at_5": "0.5",
                "mean_average_precision": "0.35",
            },
            {
                "run_at_utc": "2026-05-02T00:00:00Z",
                "git_sha": "222",
                "holdout_days": "60",
                "n_sessions_evaluable": "16",
                "ndcg_at_10": "0.41",
                "hit_rate_at_10": "0.78",
                "ndcg_at_5": "0.31",
                "hit_rate_at_5": "0.55",
                "mean_average_precision": "0.36",
            },
            {
                "run_at_utc": "2026-05-03T00:00:00Z",
                "git_sha": "333",
                "holdout_days": "60",
                "n_sessions_evaluable": "17",
                "ndcg_at_10": "0.42",
                "hit_rate_at_10": "0.80",
                "ndcg_at_5": "0.32",
                "hit_rate_at_5": "0.60",
                "mean_average_precision": "0.37",
            },
        ],
    )
    rc = scoreboard_status.main(
        ["--metrics", str(metrics), "--replays", str(replays)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "3 row(s)" in out
    assert "decision guard: GREEN" in out
    # Latest 0.42 vs prior 0.41 -> delta +0.01 = +2.4%
    assert "+0.0100" in out


def test_main_warns_on_mixed_holdouts(tmp_path, capsys):
    metrics = tmp_path / "metrics.csv"
    replays = tmp_path / "replays.csv"
    _write_metrics(
        metrics,
        [
            {
                "run_at_utc": "2026-05-01T00:00:00Z",
                "git_sha": "111",
                "holdout_days": "60",
                "n_sessions_evaluable": "15",
                "ndcg_at_10": "0.40",
                "hit_rate_at_10": "0.75",
                "ndcg_at_5": "0",
                "hit_rate_at_5": "0",
                "mean_average_precision": "0",
            },
            {
                "run_at_utc": "2026-05-02T00:00:00Z",
                "git_sha": "222",
                "holdout_days": "30",
                "n_sessions_evaluable": "20",
                "ndcg_at_10": "0.45",
                "hit_rate_at_10": "0.85",
                "ndcg_at_5": "0",
                "hit_rate_at_5": "0",
                "mean_average_precision": "0",
            },
        ],
    )
    rc = scoreboard_status.main(
        ["--metrics", str(metrics), "--replays", str(replays)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "mix 2 holdout windows" in out


def test_main_replays_empty_message(tmp_path, capsys):
    metrics = tmp_path / "metrics.csv"
    replays = tmp_path / "replays.csv"
    _write_metrics(metrics, [])  # header only
    rc = scoreboard_status.main(
        ["--metrics", str(metrics), "--replays", str(replays)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "replays: empty" in out
