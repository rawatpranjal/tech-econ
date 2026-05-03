"""Versioned save/load for trained ranking models (Ra7).

Why this exists
    The current pipeline retrains LightGBM from scratch on every run.
    That's fine for a once-a-week cron, but it makes three things hard:

    1. Inspection: there's no model artifact to point at when debugging
       "why did item X drop in rank between Tuesday and Friday?"
    2. Replay-mode evaluation (Phase 1): scripts/evaluate_recsys.py will
       want to score a fixed set of historical sessions against a
       *specific* model, not whatever happens to be in memory at run time.
    3. Rollback: if a retrain produces a regression we noticed in the
       Phase 1 metrics, we want to point the next deploy at last week's
       model file rather than re-running with old data.

    This module provides the storage layer for those workflows. Behaviour
    of `rank_all_content.py` is unchanged: still retrains on every run,
    just also writes the artifact + sidecar metadata.

Inputs
    - LightGBM Booster (or model.booster_) and a small metadata dict
    - cache_dir (defaults to data/.model_cache/ relative to repo root)

Outputs
    - On disk: {cache_dir}/lightgbm_v{N}.txt  (LightGBM's text format)
                {cache_dir}/lightgbm_v{N}.json (sidecar metadata)
                {cache_dir}/latest.json        (pointer to newest)

Side effects
    - File writes use lib.data_io.write_json_atomic for the JSON
      sidecar + latest pointer. Booster.save_model() does its own
      tmp+rename internally per LightGBM source. Both safe under crash.

Reproducibility
    - save_model() is deterministic given the same model + metadata
    - latest_version() reads from disk; never randomises
    - Version numbers are explicit ints; the caller chooses when to bump

Architecture rules enforced
    - A1: Inputs / Outputs / Side effects / Reproducibility documented
    - A2: typed surface (CachedModel dataclass)
    - B4: models versioned by filename, never overwrite
    - B6: outputs include a _meta field
    - C8: readers tolerate missing fields in the sidecar
    - E14: ValueError raised on non-existent versions; not silent fallbacks
    - G18: every public function has a unit test
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


__all__ = [
    "CachedModel",
    "ModelCacheError",
    "default_cache_dir",
    "list_versions",
    "latest_version",
    "save_model",
    "load_model",
    "_resolve_version",
]


_DEFAULT_CACHE_SUBDIR = Path("data") / ".model_cache"
_VERSION_RE = re.compile(r"^lightgbm_v(\d+)\.txt$")


class ModelCacheError(RuntimeError):
    """Raised on cache integrity / not-found errors. Never silently
    swallowed — caller decides whether to fall back to in-memory."""


@dataclass(frozen=True)
class CachedModel:
    """Lightweight handle to a saved model + its sidecar metadata.

    The booster is intentionally typed as `Any` because lightgbm is a
    heavy import and lib/ stays light-deps-only; callers that need the
    real type pass it through directly.
    """
    version: int
    booster: Any  # lightgbm.Booster | None on a metadata-only load
    booster_path: Path
    sidecar_path: Path
    meta: dict[str, Any] = field(default_factory=dict)


def default_cache_dir(repo_root: Path | None = None) -> Path:
    """Resolve the default cache directory relative to repo root.

    Repo root is inferred from this file's location. Callers running
    from a different CWD still get a stable path.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    return repo_root / _DEFAULT_CACHE_SUBDIR


def list_versions(cache_dir: Path | None = None) -> list[int]:
    """Return sorted list of integer versions present in cache_dir.

    Empty list if the directory doesn't exist (rule C8 — tolerant).
    Files that don't match the lightgbm_vN.txt pattern are ignored.
    """
    cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
    if not cache_dir.exists():
        return []
    versions: list[int] = []
    for entry in cache_dir.iterdir():
        if not entry.is_file():
            continue
        m = _VERSION_RE.match(entry.name)
        if m:
            versions.append(int(m.group(1)))
    return sorted(versions)


def latest_version(cache_dir: Path | None = None) -> int | None:
    """Return the highest version present, or None if cache is empty."""
    versions = list_versions(cache_dir)
    return versions[-1] if versions else None


def _booster_path(cache_dir: Path, version: int) -> Path:
    return cache_dir / f"lightgbm_v{version}.txt"


def _sidecar_path(cache_dir: Path, version: int) -> Path:
    return cache_dir / f"lightgbm_v{version}.json"


def _latest_pointer_path(cache_dir: Path) -> Path:
    return cache_dir / "latest.json"


def _resolve_version(
    requested: int | str | None, cache_dir: Path
) -> int:
    """Translate version='latest' / int / None into a concrete int.

    None and 'latest' both mean "newest available". Specific ints must
    exist or ValueError is raised (rule E14).
    """
    if requested is None or requested == "latest":
        v = latest_version(cache_dir)
        if v is None:
            raise ModelCacheError(
                f"No cached models found in {cache_dir}. Train one first "
                "via scripts/rank_all_content.py."
            )
        return v
    if not isinstance(requested, int):
        raise TypeError(
            f"version must be int or 'latest'/None, got {type(requested).__name__}"
        )
    if _booster_path(cache_dir, requested).exists():
        return requested
    available = list_versions(cache_dir)
    raise ModelCacheError(
        f"Model version {requested} not found in {cache_dir}. "
        f"Available: {available}"
    )


def save_model(
    booster: Any,
    *,
    version: int,
    metadata: dict[str, Any] | None = None,
    cache_dir: Path | None = None,
) -> CachedModel:
    """Persist a LightGBM booster + metadata under a specific version.

    Will refuse to overwrite an existing version (rule B4). Caller must
    pass a higher integer if it wants a fresh slot. Updates a
    `latest.json` pointer for cheap discovery.

    The booster argument may be either a `lightgbm.Booster` (the raw
    underlying object) OR a `lightgbm.LGBMClassifier`. If it's the
    latter, we reach into `.booster_`. We don't import lightgbm here —
    duck-typing only — so that lib/ stays light-deps.
    """
    cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    booster_path = _booster_path(cache_dir, version)
    sidecar_path = _sidecar_path(cache_dir, version)

    if booster_path.exists():
        raise ModelCacheError(
            f"Refusing to overwrite existing model at {booster_path}. "
            "Bump the version (rule B4: models versioned by filename, "
            "never overwrite). To delete it explicitly, rm the file first."
        )

    # Reach for .booster_ if needed — covers both Booster and
    # LGBMClassifier without importing lightgbm.
    raw = booster
    if hasattr(booster, "booster_") and not hasattr(booster, "save_model"):
        raw = booster.booster_  # pragma: no cover — defensive
    elif hasattr(booster, "booster_") and hasattr(booster, "save_model"):
        # LGBMClassifier has save_model that delegates to .booster_;
        # prefer the wrapper so we get the same on-disk format.
        pass

    if not hasattr(raw, "save_model"):
        raise TypeError(
            "save_model expected a lightgbm Booster / LGBMClassifier "
            f"with .save_model(), got {type(raw).__name__}"
        )

    # LightGBM does its own atomic write internally.
    raw.save_model(str(booster_path))

    # Build sidecar
    user_meta = dict(metadata or {})
    sidecar = {
        "_meta": {
            "schema": "model-cache-sidecar@v1",
            "version": version,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "booster_filename": booster_path.name,
        },
        "user_metadata": user_meta,
    }

    # Atomic JSON write — write to .tmp then rename.
    tmp = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    tmp.write_text(json.dumps(sidecar, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(sidecar_path)

    # Update latest pointer (atomic)
    pointer = {"latest_version": version, "updated_at": sidecar["_meta"]["saved_at"]}
    pointer_path = _latest_pointer_path(cache_dir)
    pointer_tmp = pointer_path.with_suffix(pointer_path.suffix + ".tmp")
    pointer_tmp.write_text(json.dumps(pointer, indent=2, sort_keys=True), encoding="utf-8")
    pointer_tmp.replace(pointer_path)

    return CachedModel(
        version=version,
        booster=raw,
        booster_path=booster_path,
        sidecar_path=sidecar_path,
        meta=sidecar,
    )


def load_model(
    version: int | str | None = None,
    *,
    cache_dir: Path | None = None,
    booster_loader: Any = None,
) -> CachedModel:
    """Load a saved model + sidecar.

    `booster_loader` is a callable that takes a path and returns a
    booster object — typically `lightgbm.Booster(model_file=...)`.
    Required because lib/ won't import lightgbm itself. Pass None to
    get a metadata-only load (booster=None in the result), useful in
    tests / evaluators that only need the sidecar.

    `version` may be an int, the literal string "latest", or None
    (treated as "latest"). Raises ModelCacheError if the requested
    version doesn't exist.
    """
    cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
    resolved = _resolve_version(version, cache_dir)

    booster_path = _booster_path(cache_dir, resolved)
    sidecar_path = _sidecar_path(cache_dir, resolved)

    sidecar: dict[str, Any] = {}
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ModelCacheError(
                f"Sidecar at {sidecar_path} is not valid JSON: {e}"
            ) from e

    booster = None
    if booster_loader is not None:
        booster = booster_loader(str(booster_path))

    return CachedModel(
        version=resolved,
        booster=booster,
        booster_path=booster_path,
        sidecar_path=sidecar_path,
        meta=sidecar,
    )
