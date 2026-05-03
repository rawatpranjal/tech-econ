"""Central config loader for the recsys / search stack.

Inputs:
    - data/recsys_config.json (optional — defaults are used if missing)

Outputs:
    - Config dataclass with typed sub-configs

Side effects:
    None. Pure read.

Reproducibility:
    - Loading is deterministic
    - load() is safe to call repeatedly; returns a fresh Config each
      time so callers can't mutate one another
    - random_seed is exposed via Config.ranking.random_seed so any
      script that calls load() can seed numpy/random/lightgbm/etc.

Architecture rules enforced
    - A3: no magic constants in scripts/. Read them from here.
    - C7: schema migrations live in scripts/migrate_data.py — this
      module just consumes whatever shape the JSON arrives in
    - C8: missing fields tolerated (use default)
    - C9: unknown fields ignored (forward compat)
    - E14: explicit invalid types raise rather than silently coerce

Usage
    from lib.recsys_config import load
    config = load()
    half_life = config.ranking.freshness_half_life_days
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Default config path. Overridable via load(path=...) for tests.
# ---------------------------------------------------------------------------
_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "recsys_config.json"


# ---------------------------------------------------------------------------
# Sub-configs. Add fields here as we migrate magic constants out of
# scripts/. Each field has a documented default; bumping the default is
# a behavior change and needs an explicit decision-log entry in
# master_recsys_planner.md.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RankingConfig:
    # Engagement signals — match the existing constants in
    # scripts/rank_all_content.py:62-90 so flipping to config-driven
    # is a no-op for v1.
    click_weight: float = 5.0
    impression_weight: float = 0.5
    viewable_weight: float = 0.1
    dwell_weight: float = 1.0
    scroll_90_weight: float = 2.0
    scroll_75_weight: float = 1.0
    scroll_50_weight: float = 0.5
    search_click_weight: float = 3.0
    deep_session_weight: float = 1.5
    coview_weight: float = 0.1
    coclick_weight: float = 0.3
    reading_ratio_weight: float = 0.5
    rage_click_weight: float = -2.0
    quick_bounce_weight: float = -1.0
    high_imp_no_click_weight: float = -1.0
    citations_weight: float = 0.3

    # Freshness boost decay (exponential half-life, in days)
    freshness_half_life_days: float = 30.0
    freshness_boost_max: float = 0.15

    # Cold-start scoring
    cold_start_discount: float = 0.3
    cold_start_k_neighbors: int = 5

    # Reproducibility
    random_seed: int = 42


@dataclass(frozen=True)
class SurfacesConfig:
    # Each homepage / item-page row can be flipped without code change.
    # Today most surfaces are always-on; this future-proofs the per-
    # surface kill switch for the eventual A/B harness.
    related_items_enabled: bool = True
    because_you_viewed_enabled: bool = True
    continue_reading_enabled: bool = True


@dataclass(frozen=True)
class EvaluationConfig:
    # For Phase 1 of the audit (offline NDCG / Precision / Hit-Rate
    # measurement). Currently unused but the config slot exists so
    # Phase 1 doesn't have to change two files.
    holdout_days: int = 14
    k_values: tuple[int, ...] = (5, 10)
    ndcg_drop_alert_threshold: float = 0.05  # alert if NDCG@10 drops > 5%


@dataclass(frozen=True)
class Config:
    ranking: RankingConfig = field(default_factory=RankingConfig)
    surfaces: SurfacesConfig = field(default_factory=SurfacesConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def _build_dataclass(cls: type, raw: dict[str, Any] | None) -> Any:
    """Construct a dataclass from a (possibly partial) dict.

    - Missing fields → defaults (rule C8)
    - Unknown fields → ignored (rule C9)
    - Wrong type for a known field → raise (rule E14)
    """
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    raw = raw or {}
    if not isinstance(raw, dict):
        raise TypeError(
            f"Expected dict for {cls.__name__}, got {type(raw).__name__}"
        )
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in raw:
            continue  # default kicks in
        value = raw[f.name]
        # Tuples in JSON come back as lists — convert per-field if the
        # default is a tuple so equality checks stay sane.
        if f.type is tuple or (
            hasattr(f.type, "__origin__") and f.type.__origin__ is tuple
        ) or isinstance(f.default, tuple) or (
            f.default_factory is not field
            and callable(f.default_factory)
            and isinstance(f.default_factory(), tuple)
        ):
            value = tuple(value) if isinstance(value, list) else value
        kwargs[f.name] = value
    return cls(**kwargs)


def load(path: str | Path | None = None) -> Config:
    """Read the recsys config and return a typed Config.

    If `path` is None, defaults to data/recsys_config.json at the repo
    root. If the file does not exist, returns Config() with all defaults
    (this is what new clones / fresh CI runs see).
    """
    p = Path(path) if path is not None else _DEFAULT_PATH
    if not p.exists():
        return Config()

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"recsys_config.json at {p} is not valid JSON: {e}"
        ) from e

    if not isinstance(raw, dict):
        raise TypeError(
            f"recsys_config.json at {p} must be a JSON object, got "
            f"{type(raw).__name__}"
        )

    return Config(
        ranking=_build_dataclass(RankingConfig, raw.get("ranking")),
        surfaces=_build_dataclass(SurfacesConfig, raw.get("surfaces")),
        evaluation=_build_dataclass(EvaluationConfig, raw.get("evaluation")),
    )


__all__ = [
    "Config",
    "RankingConfig",
    "SurfacesConfig",
    "EvaluationConfig",
    "load",
]
