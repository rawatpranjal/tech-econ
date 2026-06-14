"""Tests for pure helpers in scripts/human_metrics.py.

Only the computation helpers (clicks_per_session, return_rate, build_json_report)
are tested — all use injected fakes, no real network calls.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "human_metrics_mod", _REPO_ROOT / "scripts" / "human_metrics.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["human_metrics_mod"] = mod
_spec.loader.exec_module(mod)

clicks_per_session = mod.clicks_per_session
return_rate = mod.return_rate
build_json_report = mod.build_json_report
top_content = mod.top_content


# ---------------------------------------------------------------------------
# helpers / fakes
# ---------------------------------------------------------------------------

def _make_client(timeseries=None, users_payload=None, clicks_payload=None):
    """Build a minimal fake D1Client."""
    client = MagicMock()
    if timeseries is not None:
        client.timeseries.return_value = timeseries
    else:
        client.timeseries.side_effect = mod.D1ClientError("no data")

    if users_payload is not None:
        resp = MagicMock()
        resp.payload = users_payload
        client.get.return_value = resp
    else:
        client.get.side_effect = mod.D1ClientError("no data")

    if clicks_payload is not None:
        client.clicks.return_value = clicks_payload
    else:
        client.clicks.return_value = []

    return client


# ---------------------------------------------------------------------------
# clicks_per_session
# ---------------------------------------------------------------------------
class TestClicksPerSession:
    def test_basic_computation(self):
        client = _make_client(timeseries=[
            {"clicks": 10, "sessions": 5},
            {"clicks": 20, "sessions": 5},
        ])
        result = clicks_per_session(client, days=7)
        assert result == pytest.approx(3.0)  # 30 / 10

    def test_single_day(self):
        client = _make_client(timeseries=[{"clicks": 3, "sessions": 2}])
        assert clicks_per_session(client, days=7) == pytest.approx(1.5)

    def test_zero_sessions_returns_none(self):
        client = _make_client(timeseries=[{"clicks": 10, "sessions": 0}])
        assert clicks_per_session(client, days=7) is None

    def test_empty_timeseries_returns_none(self):
        client = _make_client(timeseries=[])
        assert clicks_per_session(client, days=7) is None

    def test_d1_error_returns_none(self):
        client = _make_client()  # timeseries raises
        assert clicks_per_session(client, days=7) is None

    def test_missing_keys_treated_as_zero(self):
        # sessions key absent → treated as 0 → returns None (div-by-zero guard)
        client = _make_client(timeseries=[{"clicks": 5}])
        assert clicks_per_session(client, days=7) is None

    def test_string_values_coerced(self):
        client = _make_client(timeseries=[{"clicks": "8", "sessions": "4"}])
        assert clicks_per_session(client, days=7) == pytest.approx(2.0)

    def test_days_passed_to_client(self):
        client = _make_client(timeseries=[{"clicks": 5, "sessions": 5}])
        clicks_per_session(client, days=14)
        client.timeseries.assert_called_once_with(days=14)


# ---------------------------------------------------------------------------
# return_rate
# ---------------------------------------------------------------------------
class TestReturnRate:
    def test_basic(self):
        client = _make_client(users_payload={"returning_rate": 0.42})
        assert return_rate(client) == pytest.approx(0.42)

    def test_zero_rate(self):
        client = _make_client(users_payload={"returning_rate": 0.0})
        assert return_rate(client) == pytest.approx(0.0)

    def test_missing_key_returns_none(self):
        client = _make_client(users_payload={"total_users": 100})
        assert return_rate(client) is None

    def test_d1_error_returns_none(self):
        client = _make_client()  # users raises
        assert return_rate(client) is None

    def test_string_value_coerced(self):
        client = _make_client(users_payload={"returning_rate": "0.35"})
        assert return_rate(client) == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# top_content
# ---------------------------------------------------------------------------
class TestTopContent:
    def test_returns_up_to_limit(self):
        items = [{"name": f"item{i}", "count": 10 - i} for i in range(15)]
        client = _make_client(clicks_payload=items)
        result = top_content(client, limit=10)
        assert len(result) == 10

    def test_returns_all_when_fewer_than_limit(self):
        items = [{"name": "a"}, {"name": "b"}]
        client = _make_client(clicks_payload=items)
        result = top_content(client, limit=10)
        assert len(result) == 2

    def test_d1_error_returns_empty(self):
        client = MagicMock()
        client.clicks.side_effect = mod.D1ClientError("fail")
        result = top_content(client, limit=10)
        assert result == []

    def test_limit_passed_to_client(self):
        client = _make_client(clicks_payload=[])
        top_content(client, limit=5)
        client.clicks.assert_called_once_with(limit=5)


# ---------------------------------------------------------------------------
# build_json_report
# ---------------------------------------------------------------------------
class TestBuildJsonReport:
    def test_structure(self):
        top = [{"name": "foo", "count": 5}]
        result = build_json_report(cps=1.8, rr=0.35, top=top, days=7)
        assert "clicks_per_session" in result
        assert "return_rate" in result
        assert "top_10" in result

    def test_cps_value_and_days(self):
        result = build_json_report(cps=2.1, rr=0.3, top=[], days=14)
        assert result["clicks_per_session"]["value"] == pytest.approx(2.1)
        assert result["clicks_per_session"]["days"] == 14
        assert result["clicks_per_session"]["target"] == mod.CLICKS_PER_SESSION_TARGET

    def test_none_values_serialise(self):
        result = build_json_report(cps=None, rr=None, top=[], days=7)
        s = json.dumps(result)
        assert "null" in s

    def test_top_10_preserved(self):
        top = [{"name": "bar", "count": 3}]
        result = build_json_report(cps=1.0, rr=0.2, top=top, days=7)
        assert result["top_10"] == top
