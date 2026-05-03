"""Tests for scripts/evaluate_recsys.py."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


@pytest.fixture
def er():
    """Fresh-import evaluate_recsys per test."""
    if "evaluate_recsys" in sys.modules:
        return importlib.reload(sys.modules["evaluate_recsys"])
    return importlib.import_module("evaluate_recsys")


# ---------------------------------------------------------------------------
# load_item_scores
# ---------------------------------------------------------------------------
class TestLoadItemScores:
    def test_loads_from_real_data_dir(self, er):
        # Smoke test against the actual repo. The number of items with
        # a model_score should be > 0 in production.
        repo_root = Path(__file__).resolve().parents[3]
        scores = er.load_item_scores(repo_root / "data")
        assert len(scores) > 100
        for name, score in list(scores.items())[:50]:
            assert isinstance(name, str)
            assert isinstance(score, float)

    def test_handles_missing_data_dir(self, er, tmp_path):
        # No content files → empty scores, no crash
        scores = er.load_item_scores(tmp_path / "nonexistent")
        assert scores == {}

    def test_lowercases_and_strips_names(self, er, tmp_path):
        f = tmp_path / "packages.json"
        f.write_text(json.dumps([
            {"name": "  Mixed Case  ", "model_score": 0.5},
            {"name": "OTHER", "model_score": 0.3},
        ]))
        scores = er.load_item_scores(tmp_path)
        assert "mixed case" in scores
        assert "other" in scores

    def test_skips_items_without_score(self, er, tmp_path):
        f = tmp_path / "packages.json"
        f.write_text(json.dumps([
            {"name": "scored", "model_score": 0.5},
            {"name": "no_score"},
            {"name": "wrong_type", "model_score": "not a number"},
        ]))
        scores = er.load_item_scores(tmp_path)
        assert scores == {"scored": 0.5}

    def test_handles_invalid_json(self, er, tmp_path):
        f = tmp_path / "packages.json"
        f.write_text("not json {{")
        # Should not crash; just skips the file
        scores = er.load_item_scores(tmp_path)
        assert scores == {}


# ---------------------------------------------------------------------------
# session_to_ranking_clicks
# ---------------------------------------------------------------------------
class TestSessionToRankingClicks:
    def test_basic(self, er):
        session = {
            "session_id": "s1",
            "clicks": [
                {"id": "Foo Item", "position": 1},
                {"id": "Bar Item", "position": 5},
            ],
        }
        item_scores = {"foo item": 0.9, "bar item": 0.5, "baz item": 0.3}
        result = er.session_to_ranking_clicks(session, item_scores, top_k=10)
        assert result is not None
        ranking, clicked = result
        # Ranking is sorted by score desc
        assert ranking[0] == "foo item"
        assert ranking[1] == "bar item"
        assert clicked == {"foo item", "bar item"}

    def test_clicks_as_json_string(self, er):
        # D1 stores clicks as a JSON string column
        session = {
            "clicks": json.dumps([{"id": "Foo Item"}]),
        }
        item_scores = {"foo item": 0.5}
        result = er.session_to_ranking_clicks(session, item_scores)
        assert result is not None
        _, clicked = result
        assert "foo item" in clicked

    def test_no_clicks_returns_none(self, er):
        assert er.session_to_ranking_clicks({"clicks": []}, {"a": 0.5}) is None
        assert er.session_to_ranking_clicks({"clicks": None}, {"a": 0.5}) is None
        assert er.session_to_ranking_clicks({}, {"a": 0.5}) is None

    def test_invalid_json_clicks_returns_none(self, er):
        assert (
            er.session_to_ranking_clicks({"clicks": "not json {{"}, {"a": 0.5})
            is None
        )

    def test_empty_clicked_set_returns_none(self, er):
        # Clicks list has entries but none are valid strings/dicts
        session = {"clicks": [42, None, {}]}
        assert er.session_to_ranking_clicks(session, {"a": 0.5}) is None

    def test_top_k_truncates_ranking(self, er):
        item_scores = {f"item-{i}": 1.0 - (i / 100) for i in range(100)}
        session = {"clicks": [{"id": "item-50"}]}
        result = er.session_to_ranking_clicks(session, item_scores, top_k=10)
        assert result is not None
        ranking, _ = result
        assert len(ranking) == 10

    def test_string_clicks_supported(self, er):
        session = {"clicks": ["foo item", "bar item"]}
        item_scores = {"foo item": 0.5, "bar item": 0.4}
        result = er.session_to_ranking_clicks(session, item_scores)
        assert result is not None
        _, clicked = result
        assert clicked == {"foo item", "bar item"}


# ---------------------------------------------------------------------------
# load_fixture_sessions
# ---------------------------------------------------------------------------
class TestLoadFixture:
    def test_bare_list(self, er, tmp_path):
        f = tmp_path / "fix.json"
        f.write_text(json.dumps([{"id": "a"}, {"id": "b"}]))
        out = er.load_fixture_sessions(f)
        assert out == [{"id": "a"}, {"id": "b"}]

    def test_sessions_envelope(self, er, tmp_path):
        f = tmp_path / "fix.json"
        f.write_text(json.dumps({"sessions": [{"id": "a"}]}))
        assert er.load_fixture_sessions(f) == [{"id": "a"}]

    def test_results_envelope(self, er, tmp_path):
        f = tmp_path / "fix.json"
        f.write_text(json.dumps({"results": [{"id": "a"}]}))
        assert er.load_fixture_sessions(f) == [{"id": "a"}]

    def test_invalid_shape_raises(self, er, tmp_path):
        f = tmp_path / "fix.json"
        f.write_text(json.dumps({"foo": "bar"}))
        with pytest.raises(ValueError, match="must be a list"):
            er.load_fixture_sessions(f)


# ---------------------------------------------------------------------------
# write_metrics_row + read_last_row
# ---------------------------------------------------------------------------
class TestCsvIO:
    def test_write_creates_header_on_first_row(self, er, tmp_path):
        path = tmp_path / "metrics.csv"
        er.write_metrics_row(path, {"date": "2026-05-03", "ndcg@10": 0.7})
        text = path.read_text()
        assert text.splitlines()[0] == "date,ndcg@10"
        assert "2026-05-03" in text.splitlines()[1]

    def test_write_creates_parent_dir(self, er, tmp_path):
        path = tmp_path / "deep" / "nested" / "metrics.csv"
        er.write_metrics_row(path, {"date": "2026-05-03"})
        assert path.exists()

    def test_read_last_row_returns_none_when_missing(self, er, tmp_path):
        assert er.read_last_row(tmp_path / "absent.csv") is None

    def test_read_last_row_returns_most_recent(self, er, tmp_path):
        path = tmp_path / "metrics.csv"
        er.write_metrics_row(path, {"date": "2026-05-01", "ndcg@10": 0.6})
        er.write_metrics_row(path, {"date": "2026-05-02", "ndcg@10": 0.7})
        last = er.read_last_row(path)
        assert last is not None
        assert last["date"] == "2026-05-02"


# ---------------------------------------------------------------------------
# detect_regression
# ---------------------------------------------------------------------------
class TestDetectRegression:
    def test_no_baseline_skips(self, er):
        is_reg, msg = er.detect_regression(None, {"ndcg@10": 0.5}, 0.05)
        assert is_reg is False
        assert "no prior baseline" in msg

    def test_no_drop_no_alert(self, er):
        is_reg, msg = er.detect_regression(
            {"ndcg@10": "0.6"}, {"ndcg@10": 0.7}, 0.05
        )
        assert is_reg is False

    def test_small_drop_within_tolerance(self, er):
        # 1% drop with 5% threshold → no alert
        is_reg, msg = er.detect_regression(
            {"ndcg@10": "0.7"}, {"ndcg@10": 0.693}, 0.05
        )
        assert is_reg is False

    def test_large_drop_alerts(self, er):
        # 10% drop with 5% threshold → alert
        is_reg, msg = er.detect_regression(
            {"ndcg@10": "0.7"}, {"ndcg@10": 0.63}, 0.05
        )
        assert is_reg is True
        assert "REGRESSION" in msg

    def test_unparseable_prior_skips(self, er):
        is_reg, msg = er.detect_regression(
            {"ndcg@10": "not a number"}, {"ndcg@10": 0.5}, 0.05
        )
        assert is_reg is False
        assert "unparseable" in msg


# ---------------------------------------------------------------------------
# parse_k_values
# ---------------------------------------------------------------------------
class TestParseKValues:
    def test_uses_default_when_arg_absent(self, er):
        assert er.parse_k_values(None, (5, 10)) == (5, 10)

    def test_parses_comma_separated(self, er):
        assert er.parse_k_values("3,5,10", (1,)) == (3, 5, 10)

    def test_handles_whitespace(self, er):
        assert er.parse_k_values("3, 5 , 10", ()) == (3, 5, 10)

    def test_skips_empty_components(self, er):
        assert er.parse_k_values("3,,5", ()) == (3, 5)


# ---------------------------------------------------------------------------
# main() smoke test (fixture path, dry run)
# ---------------------------------------------------------------------------
class TestMainCli:
    def test_dry_run_with_fixture(self, er, tmp_path, capsys):
        # Build a tiny fixture with a few sessions
        fixture = tmp_path / "fix.json"
        fixture.write_text(json.dumps([
            {
                "session_id": "s1",
                "updated_at": "2026-04-15T12:00:00Z",  # 18 days ago
                "clicks": [{"id": "abracadabra", "position": 1}],
            },
            {
                "session_id": "s2",
                "updated_at": "2026-04-30T12:00:00Z",  # 3 days ago (in test window)
                "clicks": [{"id": "ananke", "position": 2}],
            },
        ]))

        rc = er.main([
            "--source", "fixture",
            "--fixture-path", str(fixture),
            "--holdout-days", "14",
            "--now", "2026-05-03T12:00:00Z",
            "--dry-run",
        ])
        # Should run cleanly even if no items match (live data has many items)
        assert rc in (0, 1)  # 1 acceptable if no test sessions
        out = capsys.readouterr().out
        assert "Loaded" in out

    def test_missing_args_returns_2(self, er):
        # --source fixture with no fixture path
        rc = er.main(["--source", "fixture"])
        assert rc == 2

    def test_invalid_now_returns_2(self, er, tmp_path):
        fixture = tmp_path / "fix.json"
        fixture.write_text("[]")
        rc = er.main([
            "--source", "fixture",
            "--fixture-path", str(fixture),
            "--now", "not a date",
        ])
        assert rc == 2

    def test_unknown_source_via_argparse(self, er):
        # argparse rejects with exit 2 (its default for choice violation)
        with pytest.raises(SystemExit) as exc:
            er.main(["--source", "carrier-pigeon"])
        assert exc.value.code == 2
