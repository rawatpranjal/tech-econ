"""HTTP client for the tech-econ analytics worker (D1-backed).

Why this exists
    The audit treats D1 access as infrastructure: scripts/rank_all_content.py
    currently shells out to `wrangler d1 execute`, but that's hard to
    mock and hard to call from anything other than a script with the
    wrangler CLI installed (notably: scripts/evaluate_recsys.py running
    in CI / from a different working directory).

    This module wraps the analytics worker's HTTP API. Every read
    endpoint (/stats, /clicks, /searches, /clicks-by-country,
    /timeseries, /health, /users) becomes a typed method that returns
    plain-Python data ready for downstream metrics work.

Inputs
    - base_url:  the worker URL (default
                 https://tech-econ-analytics-v2.pp712.workers.dev,
                 overridable via the ANALYTICS_API env var or the
                 D1Client(base_url=...) constructor)
    - http:      a callable (url, *, timeout) -> Response. Defaults
                 to urllib; tests inject a fake.

Outputs
    - dicts/lists matching the worker's JSON schema. Errors raise
      D1ClientError instead of returning empty (rule E14).

Side effects
    - Network access (one HTTP GET per call, no caching here — the
      caller decides if it wants memoisation)

Reproducibility
    - Pure aside from the HTTP layer; the same base_url + endpoint +
      query string always hit the same worker route
    - All public methods accept an optional `timeout` argument so
      tests / scripts can pin behaviour deterministically

Architecture rules enforced
    - A1: docstring with Inputs/Outputs/Side effects/Reproducibility
    - A2: typed result (D1Response dataclass) — payload still a dict
      because worker responses are heterogeneous, but provenance
      (status, url, elapsed_ms) is structured
    - C8: tolerant readers — methods like `clicks(limit=...)` use
      kwargs with documented defaults
    - E14: D1ClientError on HTTP errors / parse failures, never
      silent empty
    - F: no D1 schema-write paths here. Reads only. Writes go through
      the worker's POST /events path which has its own schema-code
      agreement test in Phase 2.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable


__all__ = [
    "D1Client",
    "D1ClientError",
    "D1Response",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SEC",
]


DEFAULT_BASE_URL = "https://tech-econ-analytics-v2.pp712.workers.dev"
DEFAULT_TIMEOUT_SEC = 30.0


class D1ClientError(RuntimeError):
    """Raised on HTTP errors, JSON parse failures, or unexpected
    response shapes. Carries status code + URL when available so
    callers can decide whether to retry."""

    def __init__(self, message: str, *, status: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status = status
        self.url = url


@dataclass(frozen=True)
class D1Response:
    """Wrapped response with provenance metadata."""

    payload: Any
    status: int
    url: str
    elapsed_ms: float
    headers: dict[str, str] = field(default_factory=dict)


# A "fetcher" is anything that takes (url, *, timeout) and returns
# (status, body_bytes, headers). Lets tests inject a fake without
# monkey-patching urllib at the module level.
HttpFetcher = Callable[[str, float], tuple[int, bytes, dict[str, str]]]


def _default_fetcher(url: str, timeout: float) -> tuple[int, bytes, dict[str, str]]:
    """Default fetcher backed by urllib. No external HTTP library —
    keeps lib/ light-deps."""
    req = urllib.request.Request(url, headers={"User-Agent": "tech-econ-d1-client/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return (resp.status, body, headers)
    except urllib.error.HTTPError as e:
        # HTTPError IS a Response (it has .read(), .status). We treat
        # 4xx/5xx as a real response for the caller to interpret rather
        # than swallowing into a generic exception.
        body = e.read() if hasattr(e, "read") else b""
        headers = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        return (e.code, body, headers)
    except urllib.error.URLError as e:
        # Network-level error (DNS, connection refused, TLS, etc.).
        # Surface as D1ClientError with a synthetic status of -1 so the
        # caller can distinguish from HTTP-level problems.
        raise D1ClientError(
            f"Network error fetching {url}: {e.reason}",
            status=None,
            url=url,
        ) from e


class D1Client:
    """Read-only client for the tech-econ analytics worker.

    Usage:
        client = D1Client()
        clicks = client.clicks(limit=20)        # → list[dict]
        searches = client.searches(limit=10)
        stats = client.stats()
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        http: HttpFetcher | None = None,
        default_timeout: float = DEFAULT_TIMEOUT_SEC,
    ):
        self.base_url = (
            base_url
            or os.environ.get("ANALYTICS_API")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self._http: HttpFetcher = http if http is not None else _default_fetcher
        self.default_timeout = default_timeout

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------
    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> D1Response:
        """Generic GET. Most callers want one of the typed helpers below."""
        url = self._build_url(path, params)
        t = timeout if timeout is not None else self.default_timeout

        start = time.monotonic()
        status, body, headers = self._http(url, t)
        elapsed_ms = (time.monotonic() - start) * 1000.0

        if status >= 400:
            raise D1ClientError(
                f"HTTP {status} from {url}: {body[:200].decode('utf-8', errors='replace')}",
                status=status,
                url=url,
            )

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise D1ClientError(
                f"Invalid JSON from {url}: {e}",
                status=status,
                url=url,
            ) from e

        return D1Response(
            payload=payload,
            status=status,
            url=url,
            elapsed_ms=elapsed_ms,
            headers=headers,
        )

    def _build_url(self, path: str, params: dict[str, Any] | None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.base_url}{path}"
        if params:
            # Only include params with non-None values; allow callers
            # to pass {limit: None} to mean "use server default"
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url += "?" + urllib.parse.urlencode(cleaned)
        return url

    # ------------------------------------------------------------------
    # Typed endpoints
    # ------------------------------------------------------------------
    def health(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Worker /health endpoint — surfaces D1 binding + write freshness."""
        return self.get("/health", timeout=timeout).payload

    def stats(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Worker /stats — dashboard summary."""
        return self.get("/stats", timeout=timeout).payload

    def clicks(
        self,
        *,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Worker /clicks — top clicked content. Returns the bare list
        (worker may wrap in {results: [...]} or return list directly;
        we normalise so callers always get a list)."""
        return _ensure_list(
            self.get("/clicks", params={"limit": limit}, timeout=timeout).payload
        )

    def searches(
        self,
        *,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Worker /searches — top searches."""
        return _ensure_list(
            self.get("/searches", params={"limit": limit}, timeout=timeout).payload
        )

    def timeseries(
        self,
        *,
        days: int | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Worker /timeseries — daily aggregates."""
        return _ensure_list(
            self.get("/timeseries", params={"days": days}, timeout=timeout).payload
        )

    def clicks_by_country(
        self,
        *,
        country: str | None = None,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Worker /clicks-by-country — geo breakdown."""
        return _ensure_list(
            self.get(
                "/clicks-by-country",
                params={"country": country},
                timeout=timeout,
            ).payload
        )


def _ensure_list(payload: Any) -> list[dict[str, Any]]:
    """Worker endpoints sometimes return {results: [...]}, sometimes
    bare lists. Normalise so callers don't have to branch."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "data", "rows", "items"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        # Single-row response — wrap it
        return [payload]
    raise D1ClientError(
        f"Expected list or dict from worker, got {type(payload).__name__}"
    )
