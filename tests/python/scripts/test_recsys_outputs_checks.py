"""Bullshit tests for scripts/test_recsys_outputs.py invariant check functions.

Covers: check_model_scores_in_range, check_no_duplicate_ids_in_metadata,
check_related_items_envelope, check_content_files_sorted_by_score,
check_related_items_no_self_reference, check_related_items_ids_resolve.

Monkeypatches DATA_DIR and EMBEDDINGS_DIR so no real repo files are needed.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "test_recsys_outputs.py"

_spec = importlib.util.spec_from_file_location("test_recsys_outputs_mod", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["test_recsys_outputs_mod"] = mod
_spec.loader.exec_module(mod)

Failure = mod.Failure
check_model_scores = mod.check_model_scores_in_range
check_no_dup_ids = mod.check_no_duplicate_ids_in_metadata
check_rel_envelope = mod.check_related_items_envelope
check_sorted = mod.check_content_files_sorted_by_score
check_no_selfref = mod.check_related_items_no_self_reference
check_ids_resolve = mod.check_related_items_ids_resolve


# ─── helpers ──────────────────────────────────────────────────────────────────

def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ─── check_model_scores_in_range ──────────────────────────────────────────────

class TestCheckModelScoresInRange:
    def test_passes_clean_scores(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["packages.json"])
        _write(tmp_path / "data" / "packages.json", [
            {"name": "A", "model_score": 0.8},
            {"name": "B", "model_score": 0.2},
        ])
        result = check_model_scores()
        assert result["seen"] == 2
        assert result["bad"] == []

    def test_raises_on_out_of_range_score(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["packages.json"])
        _write(tmp_path / "data" / "packages.json", [
            {"name": "Bad", "model_score": 1.5},
        ])
        with pytest.raises(Failure) as exc_info:
            check_model_scores()
        assert "model_scores_in_range" in exc_info.value.check

    def test_raises_on_nan_score(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["packages.json"])
        _write(tmp_path / "data" / "packages.json", [
            {"name": "NaNPkg", "model_score": float("nan")},
        ])
        with pytest.raises(Failure):
            check_model_scores()

    def test_items_without_score_not_counted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["packages.json"])
        _write(tmp_path / "data" / "packages.json", [
            {"name": "NoScore"},
        ])
        result = check_model_scores()
        assert result["seen"] == 0

    def test_missing_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["nonexistent.json"])
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        result = check_model_scores()
        assert result["seen"] == 0


# ─── check_no_duplicate_ids_in_metadata ───────────────────────────────────────

class TestCheckNoDuplicateIdsInMetadata:
    def test_passes_unique_ids(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "embeddings")
        _write(tmp_path / "embeddings" / "search-metadata.json", {
            "items": [{"id": "a"}, {"id": "b"}]
        })
        result = check_no_dup_ids()
        assert result["unique_ids"] == 2

    def test_raises_on_duplicate_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "embeddings")
        _write(tmp_path / "embeddings" / "search-metadata.json", {
            "items": [{"id": "x"}, {"id": "x"}]
        })
        with pytest.raises(Failure) as exc_info:
            check_no_dup_ids()
        assert "no_duplicate_ids_in_metadata" in exc_info.value.check

    def test_missing_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "embeddings")
        (tmp_path / "embeddings").mkdir(parents=True, exist_ok=True)
        result = check_no_dup_ids()
        assert "skipped" in result


# ─── check_related_items_envelope ─────────────────────────────────────────────

class TestCheckRelatedItemsEnvelope:
    def _valid_rel(self):
        return {
            "version": 1,
            "items": {
                "item-a": [{"id": "item-b", "score": 0.9}],
            }
        }

    def test_passes_valid_envelope(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", self._valid_rel())
        result = check_rel_envelope()
        assert result["total_items"] == 1

    def test_missing_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        (tmp_path / "emb").mkdir(parents=True, exist_ok=True)
        result = check_rel_envelope()
        assert "skipped" in result

    def test_raises_missing_version_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {"items": {}})
        with pytest.raises(Failure):
            check_rel_envelope()

    def test_raises_items_not_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {"version": 1, "items": []})
        with pytest.raises(Failure):
            check_rel_envelope()

    def test_raises_malformed_neighbour(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {
            "version": 1,
            "items": {"a": ["not-a-dict"]}
        })
        with pytest.raises(Failure):
            check_rel_envelope()


# ─── check_content_files_sorted_by_score ──────────────────────────────────────

class TestCheckContentFilesSortedByScore:
    def test_passes_descending_scores(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["pkgs.json"])
        _write(tmp_path / "data" / "pkgs.json", [
            {"name": "A", "model_score": 0.9},
            {"name": "B", "model_score": 0.5},
            {"name": "C", "model_score": 0.1},
        ])
        result = check_sorted()
        assert result["items_checked"] == 3

    def test_raises_on_ascending_scores(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["pkgs.json"])
        _write(tmp_path / "data" / "pkgs.json", [
            {"name": "A", "model_score": 0.1},
            {"name": "B", "model_score": 0.9},
        ])
        with pytest.raises(Failure) as exc_info:
            check_sorted()
        assert "content_files_sorted_by_score" in exc_info.value.check

    def test_missing_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
        monkeypatch.setattr(mod, "CONTENT_FILES", ["missing.json"])
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        result = check_sorted()
        assert result["items_checked"] == 0


# ─── check_related_items_no_self_reference ────────────────────────────────────

class TestCheckRelatedItemsNoSelfReference:
    def test_passes_no_self_refs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {
            "version": 1,
            "items": {"a": [{"id": "b", "score": 0.9}]}
        })
        result = check_no_selfref()
        assert result["items_checked"] == 1

    def test_raises_on_self_reference(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {
            "version": 1,
            "items": {"a": [{"id": "a", "score": 1.0}]}
        })
        with pytest.raises(Failure) as exc_info:
            check_no_selfref()
        assert "self_reference" in exc_info.value.check

    def test_missing_file_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        (tmp_path / "emb").mkdir(parents=True, exist_ok=True)
        result = check_no_selfref()
        assert "skipped" in result


# ─── check_related_items_ids_resolve ──────────────────────────────────────────

class TestCheckRelatedItemsIdsResolve:
    def test_passes_all_ids_resolve(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {
            "version": 1,
            "items": {"a": [{"id": "b", "score": 0.9}]}
        })
        _write(tmp_path / "emb" / "search-metadata.json", {
            "items": [{"id": "a"}, {"id": "b"}]
        })
        result = check_ids_resolve()
        assert result["valid_ids"] == 2

    def test_raises_when_neighbour_id_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        _write(tmp_path / "emb" / "related-items.json", {
            "version": 1,
            "items": {"a": [{"id": "ghost-id", "score": 0.9}]}
        })
        _write(tmp_path / "emb" / "search-metadata.json", {
            "items": [{"id": "a"}]
        })
        with pytest.raises(Failure) as exc_info:
            check_ids_resolve()
        assert "ids_resolve" in exc_info.value.check

    def test_missing_both_files_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_path / "emb")
        (tmp_path / "emb").mkdir(parents=True, exist_ok=True)
        result = check_ids_resolve()
        assert "skipped" in result
