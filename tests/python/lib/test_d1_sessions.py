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

    def test_full_word_impression_event_type(self):
        # Regression: 2026-05-03 the worker writes type='impression'
        # (full word) but we were filtering for 'impress'. 6627
        # impression rows in production were silently dropped from
        # the eval gate. Both spellings must be accepted.
        events = [
            _ev(type_="impression", sid="s1", name="Tool A"),
            _ev(type_="impress", sid="s2", name="Tool B"),  # legacy short form
            _ev(type_="click", sid="s1", name="Tool A"),
        ]
        sessions = parse_events_to_sessions(events)
        s1 = next(s for s in sessions if s.session_id == "s1")
        s2 = next(s for s in sessions if s.session_id == "s2")
        assert "tool a" in s1.viewed_names
        assert "tool a" in s1.clicked_names
        assert "tool b" in s2.viewed_names

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
# fetch_events_via_api -- URL building, key handling, error mapping
# ---------------------------------------------------------------------------
class TestFetchEventsViaApi:
    """Unit tests for the HTTP fetcher. Patches urllib.request.urlopen
    so the suite remains offline."""

    def _stub_urlopen(self, body: bytes, *, http_status: int = 200,
                      raise_kind: type | None = None):
        from contextlib import contextmanager
        import urllib.error

        @contextmanager
        def fake_open(url, timeout, context=None):
            self._called_url = url  # capture for assertion
            if raise_kind is urllib.error.HTTPError:
                raise urllib.error.HTTPError(url, http_status, "boom", {}, None)
            if raise_kind is urllib.error.URLError:
                raise urllib.error.URLError("network down")
            class _Resp:
                def __init__(self, b): self.b = b
                def read(self): return self.b
            yield _Resp(body)
        return fake_open

    def test_passes_admin_key_in_query(self, monkeypatch):
        from lib import d1_sessions
        body = json.dumps({"events": [_ev()]}).encode("utf-8")
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(body))
        d1_sessions.fetch_events_via_api(
            "http://w/", since_ms=1000, until_ms=2000, admin_key="SECRET",
        )
        assert "key=SECRET" in self._called_url
        assert "since=1000" in self._called_url
        assert "until=2000" in self._called_url

    def test_includes_types_and_limit(self, monkeypatch):
        from lib import d1_sessions
        body = json.dumps({"events": []}).encode("utf-8")
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(body))
        d1_sessions.fetch_events_via_api(
            "http://w/", since_ms=0, until_ms=1, admin_key="K",
            types=("click", "impression"), limit=12345,
        )
        assert "types=click,impression" in self._called_url
        assert "limit=12345" in self._called_url

    def test_404_raises_session_load_error_without_leaking_key(
        self, monkeypatch
    ):
        from lib import d1_sessions
        import urllib.error
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(
                                b"", http_status=404,
                                raise_kind=urllib.error.HTTPError))
        with pytest.raises(d1_sessions.SessionLoadError) as exc:
            d1_sessions.fetch_events_via_api(
                "http://w/", since_ms=0, until_ms=1, admin_key="SECRET",
            )
        assert "SECRET" not in str(exc.value)

    def test_url_error_raises_with_clean_url(self, monkeypatch):
        from lib import d1_sessions
        import urllib.error
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(
                                b"", raise_kind=urllib.error.URLError))
        with pytest.raises(d1_sessions.SessionLoadError) as exc:
            d1_sessions.fetch_events_via_api(
                "http://w/", since_ms=0, until_ms=1, admin_key="SECRET",
            )
        assert "SECRET" not in str(exc.value)

    def test_non_json_body_raises(self, monkeypatch):
        from lib import d1_sessions
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(b"not json"))
        with pytest.raises(d1_sessions.SessionLoadError, match="non-JSON"):
            d1_sessions.fetch_events_via_api(
                "http://w/", since_ms=0, until_ms=1, admin_key="K",
            )

    def test_unexpected_shape_raises(self, monkeypatch):
        from lib import d1_sessions
        body = json.dumps({"data": []}).encode("utf-8")  # no 'events' key
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(body))
        with pytest.raises(d1_sessions.SessionLoadError, match="unexpected shape"):
            d1_sessions.fetch_events_via_api(
                "http://w/", since_ms=0, until_ms=1, admin_key="K",
            )

    def test_admin_key_optional_for_legacy_callers(self, monkeypatch):
        from lib import d1_sessions
        body = json.dumps({"events": []}).encode("utf-8")
        monkeypatch.setattr(d1_sessions.urllib.request, "urlopen",
                            self._stub_urlopen(body))
        # No admin_key -> URL should NOT contain key=
        d1_sessions.fetch_events_via_api(
            "http://w/", since_ms=0, until_ms=1,
        )
        assert "key=" not in self._called_url


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
