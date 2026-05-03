"""Temporal train / test split for offline ranker evaluation.

Why temporal not random: clicks today depend on yesterday's catalog,
yesterday's recommendations, and yesterday's seasonal context. A
random shuffle leaks future information into training. Per the audit
(Phase 1, Ch7 from the book), evaluation MUST use a temporal split.

Inputs:
    - events: iterable of dicts (or any object with a `timestamp`
      attribute / key). The function copes with both dict-style and
      attribute-style access.
    - holdout_days: int — train events older than `now - holdout_days`,
      test events from the last `holdout_days`.
    - now (optional): override the reference timestamp for
      reproducibility. Tests pass a frozen value so they don't depend
      on wall-clock time.

Outputs:
    - tuple (train_events, test_events) — same types as input, just
      partitioned by timestamp.

Side effects:
    None. Pure function.

Reproducibility:
    - Deterministic given a fixed `now`.
    - Default `now = datetime.now(timezone.utc)` is documented; pass
      an explicit value for reproducible tests / replays.

Architecture rules enforced
    - A2: typed I/O. Returns tuple[list, list] not Tuple[Any, Any].
    - E14: invalid timestamp parses raise rather than silently dropping.

Timestamp handling
    The function accepts these timestamp formats per event:
      * datetime.datetime (with or without tzinfo — naive treated as UTC)
      * int / float (epoch seconds)
      * str (ISO 8601 — parsed via datetime.fromisoformat)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


__all__ = [
    "temporal_split",
    "to_utc_datetime",
]


def to_utc_datetime(value: Any) -> datetime:
    """Normalize a timestamp value to a UTC-aware datetime.

    Raises ValueError on un-parseable input (rule E14).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            # fromisoformat in 3.11+ accepts a "Z" suffix
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(
                f"Could not parse {value!r} as ISO 8601 datetime: {e}"
            ) from e
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(
        f"Cannot convert {type(value).__name__} {value!r} to datetime"
    )


def _extract_timestamp(event: Any, key: str) -> datetime:
    """Pull the timestamp from a Mapping (event[key]) or object
    (event.<key>), whichever shape the caller passed."""
    if isinstance(event, Mapping):
        if key not in event:
            raise KeyError(
                f"Event has no '{key}' field; got keys "
                f"{sorted(event.keys())[:10]}"
            )
        return to_utc_datetime(event[key])
    # Attribute access (dataclass, namedtuple, plain object)
    if not hasattr(event, key):
        raise AttributeError(
            f"Event has no '{key}' attribute; type {type(event).__name__}"
        )
    return to_utc_datetime(getattr(event, key))


@dataclass(frozen=True)
class TemporalSplitStats:
    """Lightweight summary of a split for logging / metrics output."""
    n_train: int
    n_test: int
    train_window_start: datetime | None
    train_window_end: datetime | None
    test_window_start: datetime | None
    test_window_end: datetime | None
    cutoff: datetime


def temporal_split(
    events: Iterable[Any],
    holdout_days: int,
    *,
    timestamp_key: str = "timestamp",
    now: datetime | None = None,
) -> tuple[list[Any], list[Any], TemporalSplitStats]:
    """Split events into (train, test, stats) by timestamp.

    Items with timestamp < (now - holdout_days) → train.
    Items with timestamp >= cutoff → test.
    Stats summarises the resulting windows for downstream reporting.

    `now` defaults to datetime.now(timezone.utc) — pass an explicit
    value for deterministic tests.
    """
    if holdout_days <= 0:
        raise ValueError(
            f"holdout_days must be positive, got {holdout_days}. "
            "If you want zero-holdout (everything in train), call "
            "temporal_split with holdout_days=1 and treat empty test "
            "as a special case in your evaluator."
        )

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=holdout_days)

    train: list[Any] = []
    test: list[Any] = []
    train_min: datetime | None = None
    train_max: datetime | None = None
    test_min: datetime | None = None
    test_max: datetime | None = None

    for event in events:
        ts = _extract_timestamp(event, timestamp_key)
        if ts < cutoff:
            train.append(event)
            if train_min is None or ts < train_min:
                train_min = ts
            if train_max is None or ts > train_max:
                train_max = ts
        else:
            test.append(event)
            if test_min is None or ts < test_min:
                test_min = ts
            if test_max is None or ts > test_max:
                test_max = ts

    stats = TemporalSplitStats(
        n_train=len(train),
        n_test=len(test),
        train_window_start=train_min,
        train_window_end=train_max,
        test_window_start=test_min,
        test_window_end=test_max,
        cutoff=cutoff,
    )
    return train, test, stats
