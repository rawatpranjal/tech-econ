"""Tests for lib.d1_sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from lib.d1_sessions import (
    Session,
    SessionLoadError,
    parse_events_to_sessions,
)


def _ev(
    *,
    type_="click",
    sid="s1",
    ts_ms=1_700_000_000_000,
    name="Foo Tool",
    extra=None,
):
    """Build a D1-shaped event row for fixtures."""
    data = {"name": name}
    if extra:
        data.update(extra)
    return {
        "id": 1,
        "type": type_,
        "session_id": sid,
        "timestamp": ts_ms,
        "data": json.dumps(data),
    }


# ---------------------------------------------------------------------------
# parse_events_to_sessions
# ---------------------------------------------------------------------------
class TestParseEvents:
    def test_basic_click_groups_by_session(self):
        events = [
            _ev(type_="click", sid="s1", name="Tool A"),
            _ev(type_="click", sid="s1", name="Tool B"),
            _ev(type_="click", sid="s2", name="Tool C"),
        ]
        sessions = parse_events_to_sessions(events)
        assert len(sessions) == 2
        s1 = next(s for s in sessions if s.session_id == "s1")
        assert s1.clicked_names == frozenset({"tool a", "tool b"})

    def test_impression_separated_from_click(self):
        events = [
            _ev(type_="impress", sid="s1", name="Tool A"),
            _ev(type_="click", sid="s1", name="Tool B"),
        ]
        s1 = parse_events_to_sessions(events)[0]
        assert s1.viewed_names == frozenset({"tool a"})
        assert s1.clicked_names == frozenset({"tool b"})

    def test_started_at_is_min_timestamp(self):
        events = [
            _ev(sid="s1", ts_ms=2_000_000_000_000, name="Tool A"),
            _ev(sid="s1", ts_ms=1_000_000_000_000, name="Tool B"),
        ]
        s1 = parse_events_to_sessions(events)[0]
        assert s1.started_at == datetime.fromtimestamp(
            1_000_000_000, tz=timezone.utc
        )

    def test_skips_events_without_session_id(self):
        events = [
            _ev(sid=""),
            _ev(sid="s1"),
        ]
        sessions = parse_events_to_sessions(events)
        assert [s.session_id for s in sessions] == ["s1"]

    def test_skips_non_click_impress_events(self):
        events = [
            {"type": "pageview", "session_id": "s1", "timestamp": 1, "data": "{}"},
            _ev(type_="click", sid="s2", name="Tool A"),
        ]
        sessions = parse_events_to_sessions(events)
        assert [s.session_id for s in sessions] == ["s2"]

    def test_skips_events_with_unparseable_data(self):
        events = [
            {"type": "click", "session_id": "s1", "timestamp": 1, "data": "not json"},
            _ev(type_="click", sid="s2", name="Tool A"),
        ]
        sessions = parse_events_to_sessions(events)
        assert [s.session_id for s in sessions] == ["s2"]

    def test_skips_events_without_name(self):
        events = [
            {"type": "click", "session_id": "s1", "timestamp": 1, "data": "{}"},
            _ev(type_="click", sid="s2", name="Tool A"),
        ]
        sessions = parse_events_to_sessions(events)
        # s1 has no items so it produces no Session at all
        assert [s.session_id for s in sessions] == ["s2"]

    def test_name_lowercased_for_match_with_data_files(self):
        events = [_ev(name="  Foo Tool  ")]
        s1 = parse_events_to_sessions(events)[0]
        assert s1.clicked_names == frozenset({"foo tool"})

    def test_skips_non_numeric_timestamp(self):
        events = [
            {"type": "click", "session_id": "s1", "timestamp": "yesterday",
             "data": json.dumps({"name": "Tool A"})},
            _ev(sid="s2"),
        ]
        sessions = parse_events_to_sessions(events)
        assert [s.session_id for s in sessions] == ["s2"]

    def test_data_field_can_be_a_dict(self):
        # Some loaders deserialise data into a dict before passing it on.
        events = [{
            "type": "click", "session_id": "s1", "timestamp": 1,
            "data": {"name": "Tool A"},
        }]
        s1 = parse_events_to_sessions(events)[0]
        assert s1.clicked_names == frozenset({"tool a"})

    def test_dedup_within_session(self):
        events = [
            _ev(sid="s1", ts_ms=1_000, name="Tool A"),
            _ev(sid="s1", ts_ms=2_000, name="Tool A"),
            _ev(sid="s1", ts_ms=3_000, name="Tool A"),
        ]
        s1 = parse_events_to_sessions(events)[0]
        assert s1.clicked_names == frozenset({"tool a"})

    def test_empty_input(self):
        assert parse_events_to_sessions([]) == []

    def test_sessions_sorted_by_started_at(self):
        events = [
            _ev(sid="s2", ts_ms=2_000, name="A"),
            _ev(sid="s1", ts_ms=1_000, name="B"),
            _ev(sid="s3", ts_ms=3_000, name="C"),
        ]
        sessions = parse_events_to_sessions(events)
        assert [s.session_id for s in sessions] == ["s1", "s2", "s3"]


# ---------------------------------------------------------------------------
# Session.is_evaluable
# ---------------------------------------------------------------------------
class TestSessionEvaluable:
    def test_with_clicks(self):
        s = Session(
            session_id="s1",
            started_at=datetime.now(timezone.utc),
            clicked_names=frozenset({"a"}),
            viewed_names=frozenset(),
        )
        assert s.is_evaluable

    def test_no_clicks(self):
        s = Session(
            session_id="s1",
            started_at=datetime.now(timezone.utc),
            clicked_names=frozenset(),
            viewed_names=frozenset({"a"}),
        )
        assert not s.is_evaluable


# ---------------------------------------------------------------------------
# load_sessions arg validation
# ---------------------------------------------------------------------------
class TestLoadSessionsArgs:
    def test_zero_holdout_days_rejected(self):
        from lib.d1_sessions import load_sessions
        with pytest.raises(ValueError, match="holdout_days"):
            load_sessions(holdout_days=0, source="api", api_url="http://x")

    def test_unknown_source_rejected(self):
        from lib.d1_sessions import load_sessions
        with pytest.raises(ValueError, match="unknown source"):
            load_sessions(holdout_days=14, source="bogus", api_url="http://x")

    def test_api_source_requires_url(self):
        from lib.d1_sessions import load_sessions
        with pytest.raises(ValueError, match="api_url"):
            load_sessions(holdout_days=14, source="api")
