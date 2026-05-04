"""Freshness boost computation for the ranking pipeline.

Why this exists
    Newly-added items have no engagement history, so the LightGBM
    classifier rates them low. The freshness boost is an additive
    bias that decays exponentially with item age — a 1-day-old
    paper gets nearly the full FRESHNESS_BOOST_MAX, a 30-day-old
    paper gets half, a 180-day-old paper gets ~1.6%.

    Formula:
        boost = boost_max * exp(-age_days / half_life_days)

    Per the audit, item-type-specific half-lives are a future
    upgrade (papers slow, talks fast). The shape of this module
    accommodates that without a refactor — pass a dict of
    half-lives keyed by type, or a single global value.

Inputs
    - first_seen_data: list[dict] with `name` + `first_seen`
      (datetime / epoch / ISO 8601 string)
    - boost_max: maximum boost magnitude (default 0.15 from
      legacy)
    - half_life_days: scalar (global) or dict[type -> float]
      keyed by item type
    - now: optional reference timestamp for reproducibility

Outputs
    - dict[str -> float] mapping name (lowercased + stripped) to
      boost in [0, boost_max]

Side effects
    None.

Reproducibility
    - Pure given a fixed `now`
    - Default `now=datetime.now(UTC)` documented; pass an explicit
      value for replays / tests
    - Names are lowercased + stripped to match the dedup convention
      in scripts/rank_all_content.py:load_all_content

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    A3: boost_max + half_life come from the caller, no magic
        constants in this module
    C8: missing/malformed first_seen tolerated (item silently skipped)
    E14: invalid boost_max / half_life raises rather than returning
        garbage
    G18: every public function has a unit test
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, Mapping


__all__ = [
    "compute_freshness_boosts",
    "freshness_boost_for_item",
    "_parse_first_seen",
]


def _parse_first_seen(value) -> datetime | None:
    """Parse a first_seen value to UTC datetime; return None on failure.

    Accepts:
      - datetime (naive treated as UTC)
      - int / float (epoch seconds)
      - str (ISO 8601 with optional Z, or 'YYYY-MM-DD HH:MM:SS')
      - None or '' (returns None)
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            if "T" in s:
                parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                parsed = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def freshness_boost_for_item(
    age_days: float,
    *,
    boost_max: float = 0.15,
    half_life_days: float = 30.0,
) -> float:
    """Compute the boost for a single item given its age in days.

    Future-dated items (age_days < 0) are clamped to 0 days — the
    item is treated as brand-new but not as "more than new", which
    avoids pathological cases where a clock-skewed first_seen yields
    a boost > boost_max.
    """
    if boost_max < 0:
        raise ValueError(f"boost_max must be >= 0, got {boost_max}")
    if half_life_days <= 0:
        raise ValueError(
            f"half_life_days must be > 0, got {half_life_days}. "
            "A non-positive half-life means 'never decay' which is "
            "almost certainly a configuration error."
        )
    age = max(0.0, float(age_days))
    return boost_max * math.exp(-age / half_life_days)


def compute_freshness_boosts(
    first_seen_data: Iterable[Mapping],
    *,
    boost_max: float = 0.15,
    half_life_days: float | Mapping[str, float] = 30.0,
    name_key: str = "name",
    type_key: str = "type",
    first_seen_key: str = "first_seen",
    now: datetime | None = None,
) -> dict[str, float]:
    """Compute freshness boost per item from a list of first_seen rows.

    `half_life_days` may be a scalar (single global half-life) or a
    Mapping keyed by item type (e.g. {'paper': 90, 'talk': 14}).
    Items whose type isn't in the map fall through to the special
    key '__default__' if present, else to a hard 30-day default.

    Names are lowercased + stripped to match the dedup convention in
    rank_all_content.py.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Validate the half_life_days param up front so a bad config
    # doesn't silently produce garbage for thousands of items.
    if isinstance(half_life_days, Mapping):
        if not half_life_days:
            raise ValueError(
                "half_life_days mapping is empty; pass a scalar or a "
                "dict with at least one entry."
            )
        for k, v in half_life_days.items():
            if v <= 0:
                raise ValueError(
                    f"half_life_days[{k!r}] = {v}; all half-lives must be > 0"
                )
    else:
        # Scalar — let freshness_boost_for_item do the validation
        if half_life_days <= 0:
            raise ValueError(f"half_life_days must be > 0, got {half_life_days}")

    boosts: dict[str, float] = {}
    for row in first_seen_data:
        if not isinstance(row, Mapping):
            continue
        name = row.get(name_key)
        if not isinstance(name, str) or not name:
            continue
        first_seen = _parse_first_seen(row.get(first_seen_key))
        if first_seen is None:
            continue

        # Resolve half-life for this item's type
        if isinstance(half_life_days, Mapping):
            item_type = row.get(type_key, "")
            hl = half_life_days.get(item_type)
            if hl is None:
                hl = half_life_days.get("__default__", 30.0)
        else:
            hl = float(half_life_days)

        age_days = (now - first_seen).total_seconds() / 86400.0
        boost = freshness_boost_for_item(
            age_days, boost_max=boost_max, half_life_days=hl
        )
        boosts[name.lower().strip()] = boost

    return boosts
