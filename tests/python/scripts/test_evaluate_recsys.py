"""Output-shape tests for scripts/evaluate_recsys.py.

We exercise the script at the function level (load_scores, main()
with mocked D1 + frozen now) so the test runs offline in 100ms. The
real CLI smoke test would require D1, which we keep out of CI.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# load_scores
# ---------------------------------------------------------------------------
class TestLoadScores:
    def test_loads_global_rankings_shape(self, tmp_path: Path):
        from scripts.evaluate_recsys import load_scores
        path = tmp_path / "global_rankings.json"
        path.write_text(json.dumps({
            "rankings": [
                {"name": "Tool A", "score": 0.7, "type": "package"},
                {"name": "Tool B", "score": 0.3, "type": "package"},
            ],
        }))
        scores = load_scores(path)
        # Names lowercased to align with data/*.json case-insensitive lookup
        assert scores == {"tool a": 0.7, "tool b": 0.3}

    def test_loads_plain_dict_shape(self, tmp_path: Path):
        from scripts.evaluate_recsys import load_scores
        path = tmp_path / "scores.json"
        path.write_text(json.dumps({"Tool A": 0.7, "Tool B": 0.3}))
        scores = load_scores(path)
        assert scores == {"tool a": 0.7, "tool b": 0.3}

    def test_missing_file_raises_clearly(self, tmp_path: Path):
        from scripts.evaluate_recsys import load_scores
        with pytest.raises(FileNotFoundError, match="rank_all_content"):
            load_scores(tmp_path / "missing.json")

    def test_rejects_empty_rankings(self, tmp_path: Path):
        from scripts.evaluate_recsys import load_scores
        path = tmp_path / "global_rankings.json"
        path.write_text(json.dumps({"rankings": []}))
        with pytest.raises(ValueError, match="no usable"):
            load_scores(path)


# ---------------------------------------------------------------------------
# main() integration: mock D1, frozen now, real CSV write
# ---------------------------------------------------------------------------
def _mock_sessions():
    from lib.d1_sessions import Session
    return [
        Session(
            session_id="s1",
            started_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            clicked_names=frozenset({"tool a"}),
            viewed_names=frozenset({"tool b"}),
        ),
        Session(
            session_id="s2",
            started_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
            clicked_names=frozenset({"tool b"}),
            viewed_names=frozenset({"tool a"}),
        ),
    ]


def _write_scores(tmp_path: Path, name: str = "global_rankings.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({
        "rankings": [
            {"name": "Tool A", "score": 0.9, "type": "package"},
            {"name": "Tool B", "score": 0.1, "type": "package"},
        ],
    }))
    return p


class TestMain:
    def _run_main(self, argv: list[str]) -> int:
        import sys
        from scripts import evaluate_recsys
        old = sys.argv
        sys.argv = ["evaluate_recsys"] + argv
        try:
            return evaluate_recsys.main()
        finally:
            sys.argv = old

    def test_writes_metrics_row(self, tmp_path: Path):
        scores_path = _write_scores(tmp_path)
        metrics_csv = tmp_path / "reports" / "metrics.csv"

        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=_mock_sessions()):
            rc = self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(metrics_csv),
                "--source", "api",
                "--api-url", "http://stub",
                "--git-sha", "test1234",
                "--now", "2026-05-03T12:00:00Z",
            ])
        assert rc == 0
        assert metrics_csv.exists()
        with metrics_csv.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        row = rows[0]
        assert row["run_at_utc"] == "2026-05-03T12:00:00Z"
        assert row["git_sha"] == "test1234"
        assert row["holdout_days"] == "14"
        assert row["n_sessions_total"] == "2"
        # Tool A is at score 0.9 (top); s1 clicked it -> Hit-Rate@10 = 1
        # for that session. Tool B at 0.1; s2 clicked it -> ranks #2 of 2,
        # Hit-Rate@10 = 1. Average = 1.0.
        assert float(row["hit_rate_at_10"]) == pytest.approx(1.0)

    def test_dry_run_does_not_write(self, tmp_path: Path):
        scores_path = _write_scores(tmp_path)
        metrics_csv = tmp_path / "reports" / "metrics.csv"
        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=_mock_sessions()):
            rc = self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(metrics_csv),
                "--api-url", "http://stub",
                "--git-sha", "test1234",
                "--now", "2026-05-03T12:00:00Z",
                "--dry-run",
            ])
        assert rc == 0
        assert not metrics_csv.exists()

    def test_d1_unreachable_returns_3(self, tmp_path: Path):
        from lib.d1_sessions import SessionLoadError
        scores_path = _write_scores(tmp_path)
        with patch("scripts.evaluate_recsys.load_sessions",
                   side_effect=SessionLoadError("simulated outage")):
            rc = self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(tmp_path / "metrics.csv"),
                "--api-url", "http://stub",
                "--now", "2026-05-03T12:00:00Z",
            ])
        assert rc == 3

    def test_zero_sessions_returns_4(self, tmp_path: Path):
        scores_path = _write_scores(tmp_path)
        with patch("scripts.evaluate_recsys.load_sessions", return_value=[]):
            rc = self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(tmp_path / "metrics.csv"),
                "--api-url", "http://stub",
                "--now", "2026-05-03T12:00:00Z",
            ])
        assert rc == 4

    def test_regression_returns_5(self, tmp_path: Path):
        scores_path = _write_scores(tmp_path)
        metrics_csv = tmp_path / "metrics.csv"
        # Seed the CSV with a high baseline so the new run drops below.
        baseline_sessions = _mock_sessions()
        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=baseline_sessions):
            self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(metrics_csv),
                "--api-url", "http://stub",
                "--git-sha", "old1234",
                "--now", "2026-05-03T12:00:00Z",
            ])

        # New run with bad scores: rank Tool A LAST so clicked items
        # land at the bottom -> NDCG drops.
        bad_path = tmp_path / "bad.json"
        bad_path.write_text(json.dumps({
            "rankings": [
                {"name": "Tool A", "score": 0.0, "type": "package"},
                {"name": "Tool B", "score": 0.0, "type": "package"},
                # Add a high-scoring decoy that wasn't seen
                {"name": "Decoy", "score": 1.0, "type": "package"},
            ],
        }))
        decoy_sessions = baseline_sessions
        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=decoy_sessions):
            rc = self._run_main([
                "--scores-file", str(bad_path),
                "--metrics-csv", str(metrics_csv),
                "--api-url", "http://stub",
                "--git-sha", "new1234",
                "--now", "2026-05-04T12:00:00Z",
                "--fill-with-global-top", "1",
            ])
        # Decoy ranks first because its score is 1.0; clicked items
        # rank below -> NDCG@10 drops vs baseline.
        # However if drop happens to be within 5%, this could pass --
        # we craft the scenario above to definitely exceed it.
        assert rc == 5

    def test_skip_regression_check(self, tmp_path: Path):
        scores_path = _write_scores(tmp_path)
        metrics_csv = tmp_path / "metrics.csv"
        # Same setup as the previous test, but with --skip-regression-check.
        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=_mock_sessions()):
            self._run_main([
                "--scores-file", str(scores_path),
                "--metrics-csv", str(metrics_csv),
                "--api-url", "http://stub",
                "--git-sha", "old1234",
                "--now", "2026-05-03T12:00:00Z",
            ])

        bad_path = tmp_path / "bad.json"
        bad_path.write_text(json.dumps({
            "rankings": [
                {"name": "Decoy", "score": 1.0, "type": "package"},
                {"name": "Tool A", "score": 0.0, "type": "package"},
                {"name": "Tool B", "score": 0.0, "type": "package"},
            ],
        }))
        with patch("scripts.evaluate_recsys.load_sessions",
                   return_value=_mock_sessions()):
            rc = self._run_main([
                "--scores-file", str(bad_path),
                "--metrics-csv", str(metrics_csv),
                "--api-url", "http://stub",
                "--git-sha", "new1234",
                "--now", "2026-05-04T12:00:00Z",
                "--fill-with-global-top", "1",
                "--skip-regression-check",
            ])
        assert rc == 0
        with metrics_csv.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
