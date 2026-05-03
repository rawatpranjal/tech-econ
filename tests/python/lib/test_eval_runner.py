"""Tests for lib.eval_runner: orchestration + CSV append + regression check."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lib.d1_sessions import Session
from lib.eval_runner import (
    EvalResult,
    RegressionAlert,
    build_session_pairs,
    check_regression,
    format_metrics_row,
    format_replay_row,
    header_columns,
    read_last_metrics_row,
    run_evaluation,
    write_metrics_row,
    write_replay_row,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sess(sid, clicked, viewed=(), ts=None) -> Session:
    return Session(
        session_id=sid,
        started_at=ts or datetime(2026, 5, 1, tzinfo=timezone.utc),
        clicked_names=frozenset(clicked),
        viewed_names=frozenset(viewed),
    )


# ---------------------------------------------------------------------------
# build_session_pairs
# ---------------------------------------------------------------------------
class TestBuildSessionPairs:
    def test_ranking_sorted_by_score_desc(self):
        scores = {"a": 0.1, "b": 0.9, "c": 0.5}
        sessions = [_sess("s1", clicked={"a"}, viewed={"b", "c"})]
        pairs = build_session_pairs(sessions, scores)
        ranking, clicked = pairs[0]
        assert ranking == ["b", "c", "a"]
        assert clicked == frozenset({"a"})

    def test_missing_score_treated_as_zero(self):
        scores = {"a": 0.5}
        sessions = [_sess("s1", clicked={"a"}, viewed={"b"})]
        ranking, _ = build_session_pairs(sessions, scores)[0]
        # b has no score so its implicit score is 0 -> ranks below a
        assert ranking == ["a", "b"]

    def test_fill_with_global_top(self):
        scores = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.1}
        sessions = [_sess("s1", clicked={"d"})]
        pairs = build_session_pairs(sessions, scores, fill_with_global_top=2)
        ranking, clicked = pairs[0]
        # Global top 2 = a, b. Plus clicked d. Sorted by score: a, b, d.
        assert ranking == ["a", "b", "d"]
        assert clicked == frozenset({"d"})

    def test_empty_session_clicks_and_views(self):
        scores = {"a": 1.0}
        sessions = [_sess("s1", clicked=set(), viewed=set())]
        pairs = build_session_pairs(sessions, scores)
        ranking, clicked = pairs[0]
        assert ranking == []
        assert clicked == frozenset()

    def test_rejects_non_dict_scores(self):
        with pytest.raises(TypeError):
            build_session_pairs([], scores="not a dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# run_evaluation
# ---------------------------------------------------------------------------
class TestRunEvaluation:
    def test_perfect_ranker_gets_max_metrics(self):
        # Click is always at the top of the ranking
        scores = {"a": 1.0, "b": 0.5, "c": 0.1}
        sessions = [
            _sess("s1", clicked={"a"}, viewed={"b", "c"}),
            _sess("s2", clicked={"a"}, viewed={"b", "c"}),
        ]
        result = run_evaluation(
            scores=scores, sessions=sessions,
            holdout_days=14, k_values=(5, 10),
            git_sha="abc1234",
            now=datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
        )
        assert result.run_at_utc == "2026-05-03T12:00:00Z"
        assert result.git_sha == "abc1234"
        assert result.holdout_days == 14
        assert result.n_sessions_total == 2
        assert result.n_sessions_evaluable == 2
        assert result.n_sessions_skipped == 0
        assert result.aggregate.ndcg_at_k[10] == pytest.approx(1.0)
        assert result.aggregate.hit_rate_at_k[5] == pytest.approx(1.0)

    def test_no_click_session_counted_as_skipped(self):
        scores = {"a": 1.0}
        sessions = [
            _sess("s1", clicked=set(), viewed={"a"}),  # no click -> skipped
            _sess("s2", clicked={"a"}),
        ]
        result = run_evaluation(
            scores=scores, sessions=sessions, holdout_days=14, k_values=(10,)
        )
        assert result.n_sessions_total == 2
        assert result.n_sessions_skipped == 1
        assert result.n_sessions_evaluable == 1

    def test_empty_k_values_rejected(self):
        with pytest.raises(ValueError, match="k_values"):
            run_evaluation(scores={}, sessions=[], holdout_days=14, k_values=())


# ---------------------------------------------------------------------------
# CSV write / read
# ---------------------------------------------------------------------------
class TestMetricsCSV:
    def _result(self, k_values=(5, 10), ndcg_10=0.7, run_at="2026-05-03T12:00:00Z",
                notes="") -> EvalResult:
        # Build a fake AggregateMetrics by running through the real path
        scores = {"a": 1.0, "b": 0.5}
        sessions = [_sess("s1", clicked={"a"}, viewed={"b"})]
        result = run_evaluation(
            scores=scores, sessions=sessions,
            holdout_days=14, k_values=k_values,
            git_sha="abc1234",
            now=datetime.fromisoformat(run_at.replace("Z", "+00:00")),
            notes=notes,
        )
        return result

    def test_writes_header_on_first_call(self, tmp_path: Path):
        path = tmp_path / "metrics.csv"
        write_metrics_row(path, self._result())
        text = path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        for col in ("run_at_utc", "git_sha", "ndcg_at_10", "precision_at_5"):
            assert col in first_line

    def test_appends_subsequent_rows(self, tmp_path: Path):
        path = tmp_path / "metrics.csv"
        write_metrics_row(path, self._result(run_at="2026-05-03T12:00:00Z"))
        write_metrics_row(path, self._result(run_at="2026-05-04T12:00:00Z"))
        with path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["run_at_utc"] == "2026-05-03T12:00:00Z"
        assert rows[1]["run_at_utc"] == "2026-05-04T12:00:00Z"

    def test_rejects_header_drift(self, tmp_path: Path):
        path = tmp_path / "metrics.csv"
        write_metrics_row(path, self._result(k_values=(5, 10)))
        # Now try to write with different k_values -- should raise.
        with pytest.raises(ValueError, match="header mismatch"):
            write_metrics_row(path, self._result(k_values=(3, 7)))

    def test_atomic_write_no_partial_on_error(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "metrics.csv"
        write_metrics_row(path, self._result(run_at="2026-05-03T12:00:00Z"))
        original = path.read_text()

        # Force os.replace to raise; the tmp file should be cleaned up
        # and the original should be untouched.
        import os
        real_replace = os.replace

        def boom(*a, **k):
            raise OSError("simulated crash")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError, match="simulated crash"):
            write_metrics_row(path, self._result(run_at="2026-05-04T12:00:00Z"))
        # original intact
        assert path.read_text() == original
        # tmp cleaned
        assert not (path.with_suffix(".csv.tmp")).exists()
        monkeypatch.setattr(os, "replace", real_replace)

    def test_read_last_returns_none_for_missing_file(self, tmp_path: Path):
        assert read_last_metrics_row(tmp_path / "nope.csv") is None

    def test_read_last_returns_none_for_empty_history(self, tmp_path: Path):
        path = tmp_path / "metrics.csv"
        cols = header_columns((5, 10))
        path.write_text(",".join(cols) + "\n", encoding="utf-8")
        assert read_last_metrics_row(path) is None

    def test_read_last_returns_last_row(self, tmp_path: Path):
        path = tmp_path / "metrics.csv"
        write_metrics_row(path, self._result(run_at="2026-05-03T12:00:00Z"))
        write_metrics_row(path, self._result(run_at="2026-05-04T12:00:00Z"))
        last = read_last_metrics_row(path)
        assert last is not None
        assert last["run_at_utc"] == "2026-05-04T12:00:00Z"

    def test_format_row_rounds_floats(self):
        result = self._result()
        row = format_metrics_row(result)
        # Round to 6 decimals
        assert isinstance(row["ndcg_at_10"], float)
        assert row["holdout_days"] == 14


# ---------------------------------------------------------------------------
# check_regression
# ---------------------------------------------------------------------------
class TestRegressionCheck:
    def _result_with_ndcg(self, ndcg_10: float) -> EvalResult:
        # Build a result whose ndcg_at_10 we control by choosing the
        # session ranking.
        scores = {"good": 1.0, "bad": 0.0}
        if ndcg_10 >= 0.99:
            sessions = [_sess("s1", clicked={"good"})]
        else:
            sessions = [_sess("s1", clicked={"bad"}, viewed={"good"})]
        return run_evaluation(
            scores=scores, sessions=sessions, holdout_days=14, k_values=(10,),
        )

    def test_no_previous_row_is_noop(self):
        check_regression(self._result_with_ndcg(0.0), None, threshold=0.05)

    def test_within_threshold_passes(self):
        prev = {"ndcg_at_10": "1.0"}
        new = self._result_with_ndcg(0.99)  # actually 1.0 (perfect)
        check_regression(new, prev, threshold=0.05)  # no raise

    def test_drop_beyond_threshold_raises(self):
        prev = {"ndcg_at_10": "1.0"}
        # ndcg_at_10 will be 0 in this scenario (clicked item is at
        # the bottom of a 2-item ranking)
        new = self._result_with_ndcg(0.0)
        with pytest.raises(RegressionAlert, match="regressed"):
            check_regression(new, prev, threshold=0.05)

    def test_zero_previous_value_skips(self):
        prev = {"ndcg_at_10": "0"}
        new = self._result_with_ndcg(0.0)
        check_regression(new, prev, threshold=0.05)  # no raise

    def test_missing_metric_in_prev_skips(self):
        prev = {"some_other_column": "0.5"}
        new = self._result_with_ndcg(0.99)
        check_regression(new, prev, threshold=0.05)

    def test_unsupported_metric_raises_value_error(self):
        new = self._result_with_ndcg(0.99)
        with pytest.raises(ValueError, match="unsupported metric"):
            check_regression(new, {"weird": "0.5"}, threshold=0.05, metric="weird")

    def test_supports_mean_average_precision(self):
        prev = {"mean_average_precision": "1.0"}
        new = self._result_with_ndcg(0.0)
        with pytest.raises(RegressionAlert):
            check_regression(new, prev, threshold=0.05,
                             metric="mean_average_precision")


# ---------------------------------------------------------------------------
# Replay history CSV
# ---------------------------------------------------------------------------
class TestReplayCSV:
    def _pair(self):
        # Build a baseline + candidate via the real pipeline so the
        # results carry honest k_values and metric values.
        scores_a = {"good": 1.0, "bad": 0.0}
        scores_b = {"good": 0.0, "bad": 1.0}
        sessions = [_sess("s1", clicked={"good"}, viewed={"bad"})]
        baseline = run_evaluation(
            scores=scores_a, sessions=sessions, holdout_days=14,
            k_values=(5, 10), git_sha="base1234",
            now=datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
        )
        candidate = run_evaluation(
            scores=scores_b, sessions=sessions, holdout_days=14,
            k_values=(5, 10), git_sha="cand5678",
            now=datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
        )
        return baseline, candidate

    def test_format_row_includes_deltas(self):
        b, c = self._pair()
        row = format_replay_row(
            baseline=b, candidate=c,
            baseline_path="data/baseline.json",
            candidate_path="data/candidate.json",
            regression_metric="ndcg_at_10",
            regression_threshold=0.05,
            verdict="regressed",
            notes="ra2 test",
        )
        assert row["baseline_path"] == "data/baseline.json"
        assert row["candidate_path"] == "data/candidate.json"
        assert row["regression_metric"] == "ndcg_at_10"
        assert row["verdict"] == "regressed"
        assert row["notes"] == "ra2 test"
        # delta = candidate - baseline; baseline ranks "good" first (perfect),
        # candidate ranks "bad" first (zero) -> delta should be negative.
        assert row["delta_ndcg_at_10"] < 0

    def test_writes_header_on_first_call(self, tmp_path: Path):
        b, c = self._pair()
        path = tmp_path / "replays.csv"
        write_replay_row(
            path, baseline=b, candidate=c,
            baseline_path="data/baseline.json",
            candidate_path="data/candidate.json",
            regression_metric="ndcg_at_10",
            regression_threshold=0.05,
            verdict="ok",
        )
        text = path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0]
        for col in ("run_at_utc", "git_sha", "baseline_path",
                    "delta_ndcg_at_10", "verdict", "notes"):
            assert col in first_line

    def test_appends_subsequent_rows(self, tmp_path: Path):
        b, c = self._pair()
        path = tmp_path / "replays.csv"
        for i in range(3):
            write_replay_row(
                path, baseline=b, candidate=c,
                baseline_path=f"a{i}.json", candidate_path=f"b{i}.json",
                regression_metric="ndcg_at_10", regression_threshold=0.05,
                verdict="ok",
            )
        with path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_rejects_header_drift(self, tmp_path: Path):
        b, c = self._pair()
        path = tmp_path / "replays.csv"
        write_replay_row(
            path, baseline=b, candidate=c,
            baseline_path="a", candidate_path="b",
            regression_metric="ndcg_at_10", regression_threshold=0.05,
            verdict="ok",
        )
        # Force a different k_values via a re-run, then try writing
        b2 = run_evaluation(
            scores={"x": 1.0}, sessions=[_sess("s1", clicked={"x"})],
            holdout_days=14, k_values=(3, 7),
            now=datetime(2026, 5, 3, 12, tzinfo=timezone.utc),
        )
        c2 = b2  # same shape; the point is k_values mismatch with file
        with pytest.raises(ValueError, match="header mismatch"):
            write_replay_row(
                path, baseline=b2, candidate=c2,
                baseline_path="a", candidate_path="b",
                regression_metric="ndcg_at_3", regression_threshold=0.05,
                verdict="ok",
            )

    def test_baseline_candidate_kvalues_must_match(self):
        b = run_evaluation(
            scores={"x": 1.0}, sessions=[_sess("s1", clicked={"x"})],
            holdout_days=14, k_values=(5, 10),
        )
        c = run_evaluation(
            scores={"x": 1.0}, sessions=[_sess("s1", clicked={"x"})],
            holdout_days=14, k_values=(3, 7),
        )
        with pytest.raises(ValueError, match="k_values mismatch"):
            format_replay_row(
                baseline=b, candidate=c,
                baseline_path="a", candidate_path="b",
                regression_metric="ndcg_at_10", regression_threshold=0.05,
                verdict="ok",
            )
