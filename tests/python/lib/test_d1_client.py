"""Tests for lib.d1_client.

The fetcher is injectable, so we never make real HTTP calls. Each
test passes a fake fetcher that records the URL it was called with
and returns canned (status, body, headers).
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from lib.d1_client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SEC,
    D1Client,
    D1ClientError,
    D1Response,
    _ensure_list,
)


# ---------------------------------------------------------------------------
# Fake fetcher utilities
# ---------------------------------------------------------------------------
class FakeFetcher:
    """Records calls; returns canned responses keyed on URL substring.

    Each `routes` entry is a dict mapping a substring to either:
      - a (status, body_bytes, headers) tuple, or
      - a callable that takes (url, timeout) and returns the same tuple
    """

    def __init__(self, routes: dict[str, Any]):
        self.routes = routes
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float):
        self.calls.append((url, timeout))
        for substring, response in self.routes.items():
            if substring in url:
                return response(url, timeout) if callable(response) else response
        raise AssertionError(f"FakeFetcher: no route matches {url}")


def _json_response(payload: Any, status: int = 200) -> tuple[int, bytes, dict[str, str]]:
    return (status, json.dumps(payload).encode("utf-8"), {"content-type": "application/json"})


# ---------------------------------------------------------------------------
# Construction / config
# ---------------------------------------------------------------------------
class TestConstruction:
    def test_default_base_url(self):
        c = D1Client(http=lambda *a, **kw: _json_response({}))
        assert c.base_url == DEFAULT_BASE_URL

    def test_explicit_base_url_overrides_default(self):
        c = D1Client(base_url="https://example.com", http=lambda *a, **kw: _json_response({}))
        assert c.base_url == "https://example.com"

    def test_trailing_slash_stripped(self):
        c = D1Client(base_url="https://example.com/", http=lambda *a, **kw: _json_response({}))
        assert c.base_url == "https://example.com"

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("ANALYTICS_API", "https://from-env.example.com")
        c = D1Client(http=lambda *a, **kw: _json_response({}))
        assert c.base_url == "https://from-env.example.com"

    def test_explicit_arg_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("ANALYTICS_API", "https://from-env.example.com")
        c = D1Client(base_url="https://from-arg.example.com", http=lambda *a, **kw: _json_response({}))
        assert c.base_url == "https://from-arg.example.com"

    def test_default_timeout_constant(self):
        assert DEFAULT_TIMEOUT_SEC > 0


# ---------------------------------------------------------------------------
# get() — generic
# ---------------------------------------------------------------------------
class TestGet:
    def test_constructs_correct_url_no_params(self):
        fetch = FakeFetcher({"/stats": _json_response({"ok": True})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        c.get("/stats")
        assert fetch.calls[0][0] == "https://w.example.com/stats"

    def test_constructs_correct_url_with_params(self):
        fetch = FakeFetcher({"/clicks": _json_response([])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        c.get("/clicks", params={"limit": 20})
        # urlencoded
        assert "limit=20" in fetch.calls[0][0]

    def test_drops_none_params(self):
        fetch = FakeFetcher({"/clicks": _json_response([])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        c.get("/clicks", params={"limit": None, "country": "US"})
        url = fetch.calls[0][0]
        assert "country=US" in url
        assert "limit" not in url

    def test_path_normalisation_adds_leading_slash(self):
        fetch = FakeFetcher({"/stats": _json_response({})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        c.get("stats")  # no leading /
        assert fetch.calls[0][0] == "https://w.example.com/stats"

    def test_returns_typed_response(self):
        fetch = FakeFetcher({"/stats": _json_response({"x": 1})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        resp = c.get("/stats")
        assert isinstance(resp, D1Response)
        assert resp.status == 200
        assert resp.payload == {"x": 1}
        assert "https://w.example.com/stats" in resp.url
        assert resp.elapsed_ms >= 0

    def test_response_is_immutable(self):
        fetch = FakeFetcher({"/stats": _json_response({})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        resp = c.get("/stats")
        with pytest.raises(Exception):
            resp.status = 999  # type: ignore[misc]

    def test_4xx_raises_d1_client_error(self):
        fetch = FakeFetcher({"/missing": (404, b'{"error":"not found"}', {})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        with pytest.raises(D1ClientError) as exc:
            c.get("/missing")
        assert exc.value.status == 404
        assert "missing" in (exc.value.url or "")

    def test_5xx_raises_d1_client_error(self):
        fetch = FakeFetcher({"/oops": (500, b"server error", {})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        with pytest.raises(D1ClientError) as exc:
            c.get("/oops")
        assert exc.value.status == 500

    def test_invalid_json_raises_d1_client_error(self):
        fetch = FakeFetcher({"/stats": (200, b"not json {{", {})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        with pytest.raises(D1ClientError, match="Invalid JSON"):
            c.get("/stats")


# ---------------------------------------------------------------------------
# Typed endpoints
# ---------------------------------------------------------------------------
class TestTypedEndpoints:
    def test_health(self):
        fetch = FakeFetcher({"/health": _json_response({"ok": True, "lag": 0})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.health()
        assert out == {"ok": True, "lag": 0}
        assert "/health" in fetch.calls[-1][0]

    def test_stats(self):
        fetch = FakeFetcher({"/stats": _json_response({"clicks_today": 10})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        assert c.stats()["clicks_today"] == 10

    def test_clicks_with_limit(self):
        fetch = FakeFetcher({"/clicks": _json_response([{"name": "a"}, {"name": "b"}])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.clicks(limit=2)
        assert out == [{"name": "a"}, {"name": "b"}]
        assert "limit=2" in fetch.calls[-1][0]

    def test_clicks_unwraps_results_envelope(self):
        # Some worker endpoints wrap: {"results": [...]}
        fetch = FakeFetcher({"/clicks": _json_response({"results": [{"name": "wrapped"}]})})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.clicks()
        assert out == [{"name": "wrapped"}]

    def test_searches(self):
        fetch = FakeFetcher({"/searches": _json_response([{"q": "causal", "count": 5}])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.searches(limit=10)
        assert out[0]["q"] == "causal"

    def test_timeseries(self):
        fetch = FakeFetcher({"/timeseries": _json_response([{"day": "2026-05-01", "v": 1}])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.timeseries(days=7)
        assert "days=7" in fetch.calls[-1][0]
        assert out[0]["day"] == "2026-05-01"

    def test_clicks_by_country_global(self):
        fetch = FakeFetcher({"/clicks-by-country": _json_response([{"country": "US"}])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        out = c.clicks_by_country()
        assert out == [{"country": "US"}]
        # No query string at all when country is None
        assert "?" not in fetch.calls[-1][0]

    def test_clicks_by_country_filtered(self):
        fetch = FakeFetcher({"/clicks-by-country": _json_response([{"country": "DE"}])})
        c = D1Client(base_url="https://w.example.com", http=fetch)
        c.clicks_by_country(country="DE")
        assert "country=DE" in fetch.calls[-1][0]


# ---------------------------------------------------------------------------
# _ensure_list
# ---------------------------------------------------------------------------
class TestEnsureList:
    def test_list_passthrough(self):
        assert _ensure_list([1, 2, 3]) == [1, 2, 3]

    def test_results_envelope(self):
        assert _ensure_list({"results": [{"a": 1}]}) == [{"a": 1}]

    def test_data_envelope(self):
        assert _ensure_list({"data": [{"a": 1}]}) == [{"a": 1}]

    def test_rows_envelope(self):
        assert _ensure_list({"rows": [{"a": 1}]}) == [{"a": 1}]

    def test_items_envelope(self):
        assert _ensure_list({"items": [{"a": 1}]}) == [{"a": 1}]

    def test_bare_dict_wrapped(self):
        # Single-row dict response
        assert _ensure_list({"name": "solo"}) == [{"name": "solo"}]

    def test_unsupported_type_raises(self):
        with pytest.raises(D1ClientError, match="Expected list or dict"):
            _ensure_list("not a dict or list")
        with pytest.raises(D1ClientError):
            _ensure_list(None)


# ---------------------------------------------------------------------------
# Timeout plumbing
# ---------------------------------------------------------------------------
class TestTimeout:
    def test_default_timeout_used_when_unspecified(self):
        fetch = FakeFetcher({"/stats": _json_response({})})
        c = D1Client(base_url="https://w.example.com", http=fetch, default_timeout=12.5)
        c.stats()
        assert fetch.calls[-1][1] == 12.5

    def test_per_call_timeout_overrides_default(self):
        fetch = FakeFetcher({"/stats": _json_response({})})
        c = D1Client(base_url="https://w.example.com", http=fetch, default_timeout=30)
        c.stats(timeout=2.0)
        assert fetch.calls[-1][1] == 2.0


# ---------------------------------------------------------------------------
# Network-error path
# ---------------------------------------------------------------------------
class TestNetworkError:
    def test_fetcher_raising_d1_client_error_propagates(self):
        def boom(url, timeout):
            raise D1ClientError("simulated network failure", url=url)

        c = D1Client(base_url="https://w.example.com", http=boom)
        with pytest.raises(D1ClientError, match="simulated network"):
            c.stats()
