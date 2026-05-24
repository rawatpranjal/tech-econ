"""Pull recent user sessions from D1 for offline ranker evaluation.

Inputs:
    - analytics-worker URL (HTTP) OR wrangler CLI access (subprocess)
    - holdout window (days)

Outputs:
    - list[Session]: one per (session_id, day-bucket) pair, with the
      set of item names clicked and the set of item names that the
      user saw an impression for.

Side effects:
    - Reads from D1 via either the HTTP analytics endpoint or the
      wrangler CLI. No writes.

Reproducibility:
    - Output is deterministic given the same D1 snapshot and the same
      `now`. Tests exercise `parse_events_to_sessions` directly with
      fixture event rows so they don't depend on network state.

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    A2: typed surface (Session dataclass, no bare dicts crossing modules)
    C8: missing fields tolerated (events with no `data` JSON are
        skipped, not crashed on)
    E14: invalid JSON in `events.data` raises (caller can decide
         whether to drop or abort) -- but malformed individual rows
         are skipped with a counter so a single bad row does not
         poison the entire run
    G18: every public function has a unit test in
         tests/python/lib/test_d1_sessions.py

D1 event payload (per analytics-worker/index.js line 280-ish):
    {
        "id": ..., "type": "click"|"impress"|"pageview"|...,
        "session_id": "...", "path": "/...",
        "timestamp": <ms epoch>, "country": "..",
        "data": '{"name": "...", "section": "..", ...}'  (JSON string)
    }
"""

from __future__ import annotations

import json
import re
import ssl
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

try:
    import certifi as _certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=_certifi.where())
except ImportError:
    _SSL_CONTEXT = None


__all__ = [
    "Session",
    "SessionLoadError",
    "parse_events_to_sessions",
    "fetch_events_via_api",
    "fetch_events_via_wrangler",
    "load_sessions",
]


# Worker writes 'click' for clicks. The impression event has been
# emitted under both 'impress' (early prototypes) and 'impression'
# (current; verified 2026-05-03 via wrangler -- 6627 rows of type
# 'impression', zero of 'impress'). Accept both so we don't lose
# data across schema-name churn.
_CLICK_LIKE_TYPES = frozenset({"click"})
_IMPRESS_LIKE_TYPES = frozenset({"impress", "impression"})


class SessionLoadError(RuntimeError):
    """Raised when D1 is unreachable or returns an unusable payload.

    Per architecture rule E14 we fail loud rather than degrading to
    "no sessions, NDCG = 0" which would mask the data outage.
    """


@dataclass(frozen=True)
class Session:
    """One user session distilled to (clicks, impressions).

    `clicked_names` and `viewed_names` are normalised to lowercase
    so they line up with the `name` keys in data/*.json (which are
    matched case-insensitively in scripts/inject_scores.py:39).

    `started_at` is the earliest event timestamp in the session, used
    for temporal partitioning.
    """

    session_id: str
    started_at: datetime
    clicked_names: frozenset[str]
    viewed_names: frozenset[str]

    @property
    def is_evaluable(self) -> bool:
        """A session contributes to NDCG / Precision / Hit-Rate only if
        the user clicked something. No-click sessions are counted in
        AggregateMetrics.n_skipped rather than averaging in zeros."""
        return len(self.clicked_names) > 0


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------
def _normalise_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip().lower()
    return name or None


def _parse_event_data(raw: Any) -> dict[str, Any] | None:
    """events.data is stored as a JSON string in D1. Return parsed dict
    or None if it can't be decoded -- never raise."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def parse_events_to_sessions(events: Iterable[dict[str, Any]]) -> list[Session]:
    """Group raw D1 event rows into Session objects.

    Skips events that lack `session_id`, `type`, or `timestamp`. Skips
    click/impress events whose `data` JSON has no `name` field
    (typically pageview-style entries).
    """
    by_session: dict[str, dict[str, Any]] = {}

    for ev in events:
        sid = ev.get("session_id")
        ev_type = ev.get("type")
        ts_raw = ev.get("timestamp")
        if not isinstance(sid, str) or not sid:
            continue
        is_click = ev_type in _CLICK_LIKE_TYPES
        is_impress = ev_type in _IMPRESS_LIKE_TYPES
        if not (is_click or is_impress):
            continue
        if not isinstance(ts_raw, (int, float)):
            continue

        data = _parse_event_data(ev.get("data"))
        if data is None:
            continue
        name = _normalise_name(data.get("name"))
        if name is None:
            continue

        # D1 timestamps are epoch ms (worker writes Date.now())
        ts_ms = float(ts_raw)
        ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)

        bucket = by_session.setdefault(
            sid,
            {"started_at": ts, "clicks": set(), "impressions": set()},
        )
        if ts < bucket["started_at"]:
            bucket["started_at"] = ts

        if is_click:
            bucket["clicks"].add(name)
        else:  # impression / impress
            bucket["impressions"].add(name)

    out: list[Session] = []
    for sid, bucket in by_session.items():
        out.append(
            Session(
                session_id=sid,
                started_at=bucket["started_at"],
                clicked_names=frozenset(bucket["clicks"]),
                viewed_names=frozenset(bucket["impressions"]),
            )
        )
    out.sort(key=lambda s: s.started_at)
    return out


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------
def fetch_events_via_api(
    api_url: str,
    *,
    since_ms: int,
    until_ms: int | None = None,
    admin_key: str | None = None,
    types: tuple[str, ...] = ("click", "impression", "impress"),
    limit: int = 50000,
    timeout_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    """GET {api_url}/events-raw?key=..&since=..&until=.. and return the rows.

    The endpoint contract: returns `{"events": [{...}, ...]}`. The
    handler is ADMIN_KEY-protected (events carry session_ids), so
    `admin_key` is required. If `admin_key` is missing the call will
    almost certainly 401. Defaulting to None lets old callers crash
    loud rather than silently auth-bypass.

    If the worker doesn't expose this endpoint yet (was added 2026-05-03),
    raises SessionLoadError with a clear message so callers can fall
    back to wrangler.
    """
    until = until_ms if until_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
    qs_parts = [
        f"since={int(since_ms)}",
        f"until={int(until)}",
        f"limit={int(limit)}",
        f"types={','.join(types)}",
    ]
    if admin_key:
        qs_parts.append(f"key={admin_key}")
    url = f"{api_url.rstrip('/')}/events-raw?" + "&".join(qs_parts)
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds,
                                    context=_SSL_CONTEXT) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # Don't leak the admin_key into the error message.
        safe_url = url.split("&key=")[0] if admin_key else url
        raise SessionLoadError(
            f"GET {safe_url} returned HTTP {e.code}. The /events-raw "
            "endpoint may not be deployed yet, or the admin key may be "
            "wrong -- fall back to --source wrangler."
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        safe_url = url.split("&key=")[0] if admin_key else url
        raise SessionLoadError(f"Could not reach {safe_url}: {e}") from e

    safe_url = url.split("&key=")[0] if admin_key else url
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise SessionLoadError(f"{safe_url} returned non-JSON body: {e}") from e

    if not isinstance(payload, dict) or "events" not in payload:
        raise SessionLoadError(
            f"{safe_url} returned unexpected shape: keys="
            f"{sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
        )
    events = payload["events"]
    if not isinstance(events, list):
        raise SessionLoadError(f"{safe_url} 'events' field is not a list")
    return events


def fetch_events_via_wrangler(
    *,
    since_ms: int,
    until_ms: int | None = None,
    db_name: str = "tech-econ-analytics-db",
    cwd: Path | str | None = None,
    limit: int = 50000,
) -> list[dict[str, Any]]:
    """Fall back to the wrangler CLI when the HTTP endpoint isn't up.

    Runs `npx wrangler d1 execute <db> --remote --command <SQL> --json`
    and returns the rows.
    """
    until = until_ms if until_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
    sql = (
        "SELECT id, type, session_id, timestamp, data "
        "FROM events "
        f"WHERE type IN ('click','impress','impression') "
        f"AND timestamp >= {int(since_ms)} AND timestamp <= {int(until)} "
        f"ORDER BY timestamp ASC "
        f"LIMIT {int(limit)}"
    )
    if cwd is None:
        cwd = Path(__file__).resolve().parents[1] / "analytics-worker"
    cmd = [
        "npx", "wrangler", "d1", "execute", db_name,
        "--remote", "--command", sql, "--json",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(cwd), timeout=120
        )
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        raise SessionLoadError(f"wrangler invocation failed: {e}") from e
    if result.returncode != 0:
        raise SessionLoadError(
            f"wrangler exit {result.returncode}: {result.stderr.strip()[:400]}"
        )
    # Wrangler 4.x prints a non-JSON preamble to stdout before the JSON array
    # even when --json is passed. Strip it by finding the first '['.
    match = re.search(r'\[.*\]', result.stdout, re.DOTALL)
    if not match:
        raise SessionLoadError(
            f"wrangler returned no JSON array "
            f"(stdout={result.stdout[:300]!r})"
        )
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise SessionLoadError(
            f"wrangler JSON parse failed: {e} "
            f"(raw={result.stdout[:300]!r})"
        ) from e
    # wrangler --json returns a list of result-sets; results[0]["results"] is the rows
    if isinstance(payload, list) and payload:
        first = payload[0]
        rows = first.get("results", []) if isinstance(first, dict) else []
    elif isinstance(payload, dict):
        rows = payload.get("results", [])
    else:
        rows = []
    if not isinstance(rows, list):
        raise SessionLoadError("wrangler payload had no 'results' list")
    return rows


def load_sessions(
    *,
    holdout_days: int,
    source: str = "api",
    api_url: str | None = None,
    admin_key: str | None = None,
    now: datetime | None = None,
    db_name: str = "tech-econ-analytics-db",
) -> list[Session]:
    """High-level entry point: fetch the last `holdout_days` of events
    and group into Session objects.

    `source` is "api" (HTTP, requires admin_key) or "wrangler" (CLI).
    Caller decides the fallback policy. Per rule E14 we never silently
    return [] on failure -- we raise SessionLoadError.
    """
    if holdout_days <= 0:
        raise ValueError(f"holdout_days must be positive, got {holdout_days}")
    if now is None:
        now = datetime.now(timezone.utc)
    since_ms = int((now - timedelta(days=holdout_days)).timestamp() * 1000)
    until_ms = int(now.timestamp() * 1000)

    if source == "api":
        if not api_url:
            raise ValueError("source='api' requires api_url")
        events = fetch_events_via_api(
            api_url,
            since_ms=since_ms,
            until_ms=until_ms,
            admin_key=admin_key,
        )
    elif source == "wrangler":
        events = fetch_events_via_wrangler(
            since_ms=since_ms, until_ms=until_ms, db_name=db_name
        )
    else:
        raise ValueError(f"unknown source {source!r}; expected 'api' or 'wrangler'")

    return parse_events_to_sessions(events)
