"""Tests for lib.model_cache (Ra7).

We don't import lightgbm here — the module is duck-typed against any
object with .save_model(path). The fake below covers the contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.model_cache import (
    CachedModel,
    ModelCacheError,
    _resolve_version,
    default_cache_dir,
    latest_version,
    list_versions,
    load_model,
    save_model,
)


# ---------------------------------------------------------------------------
# Test doubles — minimal interface that lib.model_cache duck-types against.
# ---------------------------------------------------------------------------
class FakeBooster:
    """Stand-in for lightgbm.Booster. .save_model(path) writes a stable
    line so round-trip tests can assert content equality."""

    def __init__(self, payload: str = "fake-booster-content"):
        self.payload = payload

    def save_model(self, path: str) -> None:
        Path(path).write_text(self.payload, encoding="utf-8")


def fake_loader(path: str) -> FakeBooster:
    text = Path(path).read_text(encoding="utf-8")
    return FakeBooster(payload=text)


# ---------------------------------------------------------------------------
# default_cache_dir
# ---------------------------------------------------------------------------
class TestDefaultCacheDir:
    def test_resolves_relative_to_repo_root(self):
        d = default_cache_dir()
        assert d.name == ".model_cache"
        assert d.parent.name == "data"

    def test_accepts_explicit_repo_root(self, tmp_path):
        d = default_cache_dir(tmp_path)
        assert d == tmp_path / "data" / ".model_cache"


# ---------------------------------------------------------------------------
# list_versions / latest_version
# ---------------------------------------------------------------------------
class TestListVersions:
    def test_empty_dir_returns_empty(self, tmp_path):
        assert list_versions(tmp_path) == []
        assert latest_version(tmp_path) is None

    def test_missing_dir_returns_empty(self, tmp_path):
        assert list_versions(tmp_path / "does-not-exist") == []
        assert latest_version(tmp_path / "does-not-exist") is None

    def test_lists_only_matching_files(self, tmp_path):
        (tmp_path / "lightgbm_v1.txt").write_text("a")
        (tmp_path / "lightgbm_v3.txt").write_text("b")
        (tmp_path / "lightgbm_v2.txt").write_text("c")
        # Distractors that should be ignored
        (tmp_path / "README.md").write_text("hi")
        (tmp_path / "lightgbm_v1.json").write_text("{}")  # sidecar, not a booster
        (tmp_path / "old_lightgbm.txt").write_text("nope")

        assert list_versions(tmp_path) == [1, 2, 3]
        assert latest_version(tmp_path) == 3


# ---------------------------------------------------------------------------
# save_model
# ---------------------------------------------------------------------------
class TestSaveModel:
    def test_saves_booster_and_sidecar(self, tmp_path):
        result = save_model(
            FakeBooster("payload-v1"),
            version=1,
            metadata={"git_sha": "deadbeef", "n_features": 7},
            cache_dir=tmp_path,
        )
        assert isinstance(result, CachedModel)
        assert result.version == 1
        assert result.booster_path == tmp_path / "lightgbm_v1.txt"
        assert result.sidecar_path == tmp_path / "lightgbm_v1.json"
        assert result.booster_path.exists()
        assert result.sidecar_path.exists()
        assert result.booster_path.read_text() == "payload-v1"

        sidecar = json.loads(result.sidecar_path.read_text())
        assert sidecar["_meta"]["version"] == 1
        assert sidecar["_meta"]["schema"] == "model-cache-sidecar@v1"
        assert sidecar["user_metadata"]["git_sha"] == "deadbeef"

    def test_creates_cache_dir_if_missing(self, tmp_path):
        cache = tmp_path / "freshly-created"
        save_model(FakeBooster(), version=1, cache_dir=cache)
        assert cache.exists()

    def test_writes_latest_pointer(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        save_model(FakeBooster(), version=3, cache_dir=tmp_path)

        pointer = json.loads((tmp_path / "latest.json").read_text())
        assert pointer["latest_version"] == 3

    def test_refuses_to_overwrite(self, tmp_path):
        save_model(FakeBooster("first"), version=1, cache_dir=tmp_path)
        with pytest.raises(ModelCacheError, match="Refusing to overwrite"):
            save_model(FakeBooster("second"), version=1, cache_dir=tmp_path)
        # First payload survives
        assert (tmp_path / "lightgbm_v1.txt").read_text() == "first"

    def test_metadata_optional(self, tmp_path):
        result = save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        assert result.meta["user_metadata"] == {}

    def test_rejects_non_booster_objects(self, tmp_path):
        with pytest.raises(TypeError, match="save_model expected"):
            save_model({"not": "a booster"}, version=1, cache_dir=tmp_path)


# ---------------------------------------------------------------------------
# _resolve_version
# ---------------------------------------------------------------------------
class TestResolveVersion:
    def test_none_means_latest(self, tmp_path):
        save_model(FakeBooster(), version=2, cache_dir=tmp_path)
        save_model(FakeBooster(), version=5, cache_dir=tmp_path)
        assert _resolve_version(None, tmp_path) == 5

    def test_string_latest(self, tmp_path):
        save_model(FakeBooster(), version=2, cache_dir=tmp_path)
        assert _resolve_version("latest", tmp_path) == 2

    def test_explicit_int(self, tmp_path):
        save_model(FakeBooster(), version=2, cache_dir=tmp_path)
        save_model(FakeBooster(), version=3, cache_dir=tmp_path)
        assert _resolve_version(2, tmp_path) == 2

    def test_missing_int_raises(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        with pytest.raises(ModelCacheError, match="version 99 not found"):
            _resolve_version(99, tmp_path)

    def test_empty_cache_with_no_request_raises(self, tmp_path):
        with pytest.raises(ModelCacheError, match="No cached models found"):
            _resolve_version(None, tmp_path)

    def test_invalid_type_raises(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        with pytest.raises(TypeError, match="version must be int"):
            _resolve_version(1.5, tmp_path)


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------
class TestLoadModel:
    def test_round_trip_with_loader(self, tmp_path):
        save_model(
            FakeBooster("trained-payload"),
            version=1,
            metadata={"n_features": 42},
            cache_dir=tmp_path,
        )
        loaded = load_model(1, cache_dir=tmp_path, booster_loader=fake_loader)
        assert loaded.version == 1
        assert loaded.booster is not None
        assert loaded.booster.payload == "trained-payload"
        assert loaded.meta["user_metadata"]["n_features"] == 42

    def test_metadata_only_load(self, tmp_path):
        # Useful when an evaluator only needs to know "what model was
        # this?" without dragging in lightgbm.
        save_model(FakeBooster(), version=1, metadata={"x": 1}, cache_dir=tmp_path)
        loaded = load_model(1, cache_dir=tmp_path)  # no loader
        assert loaded.booster is None
        assert loaded.meta["user_metadata"]["x"] == 1

    def test_load_latest_by_default(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        save_model(FakeBooster(), version=4, cache_dir=tmp_path)
        loaded = load_model(cache_dir=tmp_path)
        assert loaded.version == 4

    def test_load_latest_string(self, tmp_path):
        save_model(FakeBooster(), version=2, cache_dir=tmp_path)
        loaded = load_model("latest", cache_dir=tmp_path)
        assert loaded.version == 2

    def test_missing_version_raises(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        with pytest.raises(ModelCacheError):
            load_model(99, cache_dir=tmp_path)

    def test_corrupt_sidecar_raises_loud(self, tmp_path):
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        # Corrupt the sidecar
        (tmp_path / "lightgbm_v1.json").write_text("{not valid json")
        with pytest.raises(ModelCacheError, match="not valid JSON"):
            load_model(1, cache_dir=tmp_path)

    def test_missing_sidecar_tolerated(self, tmp_path):
        # If the sidecar is missing, loading still works (rule C8 —
        # tolerant readers). Returns empty meta dict.
        save_model(FakeBooster(), version=1, cache_dir=tmp_path)
        (tmp_path / "lightgbm_v1.json").unlink()
        loaded = load_model(1, cache_dir=tmp_path)
        assert loaded.meta == {}


# ---------------------------------------------------------------------------
# CachedModel dataclass
# ---------------------------------------------------------------------------
def test_cached_model_is_immutable(tmp_path):
    saved = save_model(FakeBooster(), version=1, cache_dir=tmp_path)
    with pytest.raises(Exception):
        saved.version = 999  # type: ignore[misc]
