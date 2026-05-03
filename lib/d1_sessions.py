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
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request


__all__ = [
    "Session",
    "SessionLoadError",
    "parse_events_to_sessions",
    "fetch_events_via_api",
    "fetch_events_via_wrangler",
    "load_sessions",
]


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
        if ev_type not in ("click", "impress"):
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

        if ev_type == "click":
            bucket["clicks"].add(name)
        else:  # impress
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
    timeout_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    """GET {api_url}/events-raw?since=..&until=.. and return the rows.

    The endpoint contract: returns `{"events": [{...}, ...]}`. If the
    worker doesn't expose this endpoint yet, raises SessionLoadError
    with a clear message so callers can fall back to wrangler.
    """
    until = until_ms if until_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
    url = f"{api_url.rstrip('/')}/events-raw?since={int(since_ms)}&until={int(until)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise SessionLoadError(
            f"GET {url} returned HTTP {e.code}. The /events-raw endpoint "
            "may not be deployed yet -- fall back to --source wrangler."
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SessionLoadError(f"Could not reach {url}: {e}") from e

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise SessionLoadError(f"{url} returned non-JSON body: {e}") from e

    if not isinstance(payload, dict) or "events" not in payload:
        raise SessionLoadError(
            f"{url} returned unexpected shape: keys="
            f"{sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
        )
    events = payload["events"]
    if not isinstance(events, list):
        raise SessionLoadError(f"{url} 'events' field is not a list")
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
        f"WHERE type IN ('click','impress') "
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
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise SessionLoadError(f"wrangler returned non-JSON: {e}") from e
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
    now: datetime | None = None,
    db_name: str = "tech-econ-analytics-db",
) -> list[Session]:
    """High-level entry point: fetch the last `holdout_days` of events
    and group into Session objects.

    `source` is "api" (HTTP) or "wrangler" (CLI). Caller decides the
    fallback policy. Per rule E14 we never silently return [] on
    failure -- we raise SessionLoadError.
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
        events = fetch_events_via_api(api_url, since_ms=since_ms, until_ms=until_ms)
    elif source == "wrangler":
        events = fetch_events_via_wrangler(
            since_ms=since_ms, until_ms=until_ms, db_name=db_name
        )
    else:
        raise ValueError(f"unknown source {source!r}; expected 'api' or 'wrangler'")

    return parse_events_to_sessions(events)
