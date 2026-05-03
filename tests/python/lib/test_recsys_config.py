"""Tests for lib.recsys_config (Job 0.2 seed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.recsys_config import (
    Config,
    EvaluationConfig,
    RankingConfig,
    SurfacesConfig,
    load,
)


# ---------------------------------------------------------------------------
# Default behaviour
# ---------------------------------------------------------------------------
def test_load_with_no_file_returns_defaults(tmp_path):
    cfg = load(tmp_path / "does-not-exist.json")
    assert isinstance(cfg, Config)
    assert isinstance(cfg.ranking, RankingConfig)
    assert isinstance(cfg.surfaces, SurfacesConfig)
    assert isinstance(cfg.evaluation, EvaluationConfig)
    # Spot-check known defaults
    assert cfg.ranking.click_weight == 5.0
    assert cfg.ranking.random_seed == 42
    assert cfg.surfaces.related_items_enabled is True
    assert cfg.evaluation.holdout_days == 14


def test_dataclass_frozen_means_assignment_raises():
    """Architecture rule: configs are immutable. Mutating after load
    would defeat the "single source of truth" guarantee."""
    cfg = RankingConfig()
    with pytest.raises(Exception):
        cfg.click_weight = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Repo-root config file (data/recsys_config.json)
# ---------------------------------------------------------------------------
def test_repo_root_config_loads_without_error():
    """The actual data/recsys_config.json shipped in the repo must parse.
    This is essentially a smoke test that catches typos in the file."""
    cfg = load()  # uses default path
    assert isinstance(cfg, Config)
    # The shipped file matches the documented defaults — any mismatch
    # is something we want to know about.
    assert cfg.ranking.click_weight == 5.0
    assert cfg.ranking.dwell_weight == 1.0
    assert cfg.ranking.freshness_half_life_days == 30.0


# ---------------------------------------------------------------------------
# Forward / backward compat
# ---------------------------------------------------------------------------
def test_unknown_top_level_key_is_ignored(tmp_path):
    """Forward compat: future versions may add sections."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "ranking": {"click_weight": 7.0},
        "future_section": {"new_thing": True},
    }))
    cfg = load(p)
    assert cfg.ranking.click_weight == 7.0
    # Other sections still get defaults
    assert cfg.surfaces.related_items_enabled is True


def test_unknown_field_inside_section_is_ignored(tmp_path):
    """Forward compat: future versions may add fields to existing sections."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "ranking": {
            "click_weight": 7.0,
            "experimental_new_signal": 0.99,
        }
    }))
    cfg = load(p)
    assert cfg.ranking.click_weight == 7.0
    # Doesn't crash on the unknown field
    assert not hasattr(cfg.ranking, "experimental_new_signal")


def test_missing_field_in_section_uses_default(tmp_path):
    """Backward compat: old configs without new fields still work."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ranking": {"click_weight": 7.0}}))
    cfg = load(p)
    assert cfg.ranking.click_weight == 7.0
    # Other ranking fields default
    assert cfg.ranking.dwell_weight == 1.0
    assert cfg.ranking.random_seed == 42


def test_missing_section_uses_all_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ranking": {"click_weight": 99.0}}))
    cfg = load(p)
    # Surfaces section was absent → all defaults
    assert cfg.surfaces.related_items_enabled is True
    assert cfg.surfaces.because_you_viewed_enabled is True


# ---------------------------------------------------------------------------
# Type handling
# ---------------------------------------------------------------------------
def test_k_values_list_in_json_becomes_tuple(tmp_path):
    """JSON has no tuples — list input should be converted so equality
    against (5, 10) works."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"evaluation": {"k_values": [3, 5, 10]}}))
    cfg = load(p)
    assert cfg.evaluation.k_values == (3, 5, 10)


def test_overriding_one_field_does_not_affect_others(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "ranking": {"random_seed": 12345},
    }))
    cfg = load(p)
    assert cfg.ranking.random_seed == 12345
    # Everything else still default
    assert cfg.ranking.click_weight == 5.0
    assert cfg.ranking.freshness_half_life_days == 30.0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------
def test_invalid_json_raises_loud_error(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("not valid json {{")
    with pytest.raises(ValueError, match="not valid JSON"):
        load(p)


def test_top_level_must_be_object(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps([1, 2, 3]))  # JSON array, not object
    with pytest.raises(TypeError, match="must be a JSON object"):
        load(p)


def test_section_must_be_object(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ranking": "not an object"}))
    with pytest.raises(TypeError, match="Expected dict"):
        load(p)


# ---------------------------------------------------------------------------
# Independence
# ---------------------------------------------------------------------------
def test_load_returns_fresh_config_each_call(tmp_path):
    """Architecture rule A1 corollary — callers shouldn't be able to
    mutate one another's config."""
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ranking": {"click_weight": 7.0}}))
    a = load(p)
    b = load(p)
    assert a is not b  # different objects
    # Frozen dataclass — can't mutate, but can verify equality
    assert a == b
    assert a.ranking == b.ranking
