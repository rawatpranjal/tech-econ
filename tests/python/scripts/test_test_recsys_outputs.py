"""Tests for pure check functions in scripts/test_recsys_outputs.py.

Monkeypatches DATA_DIR and EMBEDDINGS_DIR (module-level constants) to
tmp_path subdirs so no real repo files are needed.

Note: the source script is named test_recsys_outputs.py which confuses
pytest auto-discovery, so we register it under the alias
``test_recsys_outputs_mod`` in sys.modules.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "test_recsys_outputs.py"
_spec = importlib.util.spec_from_file_location("test_recsys_outputs_mod", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["test_recsys_outputs_mod"] = mod
_spec.loader.exec_module(mod)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ─── check_model_scores_in_range ──────────────────────────────────────────────

class TestCheckModelScoresInRange:
    def test_happy_path_all_scores_in_range(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "A", "model_score": 0.9},
            {"name": "B", "model_score": 0.0},
            {"name": "C", "model_score": 1.0},
        ])
        result = mod.check_model_scores_in_range()
        assert result["seen"] == 3
        assert result["bad"] == []

    def test_out_of_range_score_raises_failure(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "Bad", "model_score": 1.5},
        ])
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_model_scores_in_range()
        assert exc_info.value.check == "model_scores_in_range"

    def test_nan_score_raises_failure(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "NaN", "model_score": float("nan")},
        ])
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_model_scores_in_range()
        assert exc_info.value.check == "model_scores_in_range"

    def test_items_without_score_are_skipped(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "NoScore"},
            {"name": "AlsoNoScore", "tags": ["x"]},
        ])
        result = mod.check_model_scores_in_range()
        assert result["seen"] == 0
        assert result["bad"] == []

    def test_missing_file_is_skipped(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        tmp_data.mkdir(parents=True, exist_ok=True)
        # fixture.json does not exist — should not raise
        result = mod.check_model_scores_in_range()
        assert result["seen"] == 0


# ─── check_no_duplicate_ids_in_metadata ───────────────────────────────────────

class TestCheckNoDuplicateIdsInMetadata:
    def test_missing_file_returns_skipped(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        tmp_emb.mkdir(parents=True, exist_ok=True)
        result = mod.check_no_duplicate_ids_in_metadata()
        assert "skipped" in result

    def test_unique_ids_returns_count(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "search-metadata.json", {
            "items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        })
        result = mod.check_no_duplicate_ids_in_metadata()
        assert result["unique_ids"] == 3

    def test_duplicate_ids_raises_failure(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "search-metadata.json", {
            "items": [{"id": "dup"}, {"id": "unique"}, {"id": "dup"}]
        })
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_no_duplicate_ids_in_metadata()
        assert exc_info.value.check == "no_duplicate_ids_in_metadata"


# ─── check_related_items_envelope ─────────────────────────────────────────────

class TestCheckRelatedItemsEnvelope:
    def test_missing_file_returns_skipped(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        tmp_emb.mkdir(parents=True, exist_ok=True)
        result = mod.check_related_items_envelope()
        assert "skipped" in result

    def test_correct_envelope_passes(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": {"a": [{"id": "b", "score": 0.9}]},
        })
        result = mod.check_related_items_envelope()
        assert result["total_items"] == 1

    def test_missing_version_key_raises_failure(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "items": {"a": [{"id": "b", "score": 0.9}]},
        })
        with pytest.raises(mod.Failure):
            mod.check_related_items_envelope()

    def test_items_as_list_raises_failure(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": [{"id": "b", "score": 0.9}],
        })
        with pytest.raises(mod.Failure):
            mod.check_related_items_envelope()


# ─── check_content_files_sorted_by_score ──────────────────────────────────────

class TestCheckContentFilesSortedByScore:
    def test_sorted_descending_passes(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "A", "model_score": 0.9},
            {"name": "B", "model_score": 0.5},
            {"name": "C", "model_score": 0.1},
        ])
        result = mod.check_content_files_sorted_by_score()
        assert result["items_checked"] == 3

    def test_unsorted_raises_failure(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        _write(tmp_data / "fixture.json", [
            {"name": "A", "model_score": 0.1},
            {"name": "B", "model_score": 0.9},
        ])
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_content_files_sorted_by_score()
        assert exc_info.value.check == "content_files_sorted_by_score"

    def test_items_without_score_treated_as_zero(self, tmp_path, monkeypatch):
        tmp_data = tmp_path / "data"
        monkeypatch.setattr(mod, "DATA_DIR", tmp_data)
        monkeypatch.setattr(mod, "CONTENT_FILES", ["fixture.json"])
        # No model_score keys — all treated as 0; all equal, no sort violation
        _write(tmp_data / "fixture.json", [
            {"name": "X"},
            {"name": "Y"},
        ])
        # Should not raise
        result = mod.check_content_files_sorted_by_score()
        assert result["items_checked"] == 2


# ─── check_related_items_no_self_reference ────────────────────────────────────

class TestCheckRelatedItemsNoSelfReference:
    def test_no_self_ref_passes(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": {"a": [{"id": "b", "score": 0.9}]},
        })
        result = mod.check_related_items_no_self_reference()
        assert result["items_checked"] == 1

    def test_self_reference_raises_failure(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": {"a": [{"id": "a", "score": 1.0}]},
        })
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_related_items_no_self_reference()
        assert "self_reference" in exc_info.value.check


# ─── check_related_items_ids_resolve ──────────────────────────────────────────

class TestCheckRelatedItemsIdsResolve:
    def test_both_files_missing_returns_skipped(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        tmp_emb.mkdir(parents=True, exist_ok=True)
        result = mod.check_related_items_ids_resolve()
        assert "skipped" in result

    def test_all_neighbour_ids_in_metadata_passes(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": {"a": [{"id": "b", "score": 0.9}]},
        })
        _write(tmp_emb / "search-metadata.json", {
            "items": [{"id": "a"}, {"id": "b"}]
        })
        result = mod.check_related_items_ids_resolve()
        assert result["valid_ids"] == 2

    def test_missing_neighbour_id_raises_failure(self, tmp_path, monkeypatch):
        tmp_emb = tmp_path / "embeddings"
        monkeypatch.setattr(mod, "EMBEDDINGS_DIR", tmp_emb)
        _write(tmp_emb / "related-items.json", {
            "version": "1",
            "items": {"a": [{"id": "ghost", "score": 0.9}]},
        })
        _write(tmp_emb / "search-metadata.json", {
            "items": [{"id": "a"}]
        })
        with pytest.raises(mod.Failure) as exc_info:
            mod.check_related_items_ids_resolve()
        assert "ids_resolve" in exc_info.value.check
