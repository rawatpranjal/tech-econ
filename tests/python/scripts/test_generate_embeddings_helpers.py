"""Bullshit tests for generate_embeddings.py pure helpers.

Covers: combine_text_for_embedding, slugify
Heavy deps (torch, sentence_transformers) are stubbed at sys.modules level.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_embeddings.py"

# Stub heavy ML deps
for _name in ["torch", "sentence_transformers", "FlagEmbedding"]:
    if _name not in sys.modules:
        _stub = types.ModuleType(_name)
        _stub.__getattr__ = lambda attr, n=_name: types.ModuleType(f"{n}.{attr}")
        sys.modules[_name] = _stub
# Minimal numpy stub
if "numpy" not in sys.modules:
    _np = types.ModuleType("numpy")
    _np.array = list
    sys.modules["numpy"] = _np

_spec = importlib.util.spec_from_file_location("generate_embeddings", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_embeddings"] = mod
_spec.loader.exec_module(mod)

combine_text = mod.combine_text_for_embedding
slugify = mod.slugify


# ──────────────────────────────────────────────
# slugify
# ──────────────────────────────────────────────

class TestSlugify:
    def test_lowercases(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_become_hyphens(self):
        result = slugify("Causal & ML")
        assert result == "causal-ml"

    def test_no_leading_or_trailing_hyphen(self):
        result = slugify("!hello!")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_consecutive_specials_collapse(self):
        result = slugify("a -- b")
        assert "--" not in result

    def test_max_100_chars(self):
        result = slugify("word " * 30)
        assert len(result) <= 100

    def test_digits_preserved(self):
        assert "2" in slugify("version 2 release")

    def test_empty_string(self):
        # Produces empty string (no fallback in this version)
        assert slugify("") == ""


# ──────────────────────────────────────────────
# combine_text_for_embedding
# ──────────────────────────────────────────────

class TestCombineTextForEmbedding:
    def test_name_always_first(self):
        result = combine_text({"name": "MyTool", "description": "Does stuff"})
        assert result.startswith("MyTool")

    def test_includes_description(self):
        result = combine_text({"name": "T", "description": "A great library"})
        assert "A great library" in result

    def test_tags_appended(self):
        result = combine_text({"name": "T", "tags": ["causal", "ml"]})
        assert "causal" in result
        assert "ml" in result

    def test_rich_embedding_text_used_as_primary(self):
        rich = "x" * 250
        result = combine_text({"name": "T", "embedding_text": rich})
        assert rich in result

    def test_short_embedding_text_ignored(self):
        # < 200 chars → falls back to legacy field assembly
        result = combine_text({"name": "T", "embedding_text": "short", "description": "legacydesc"})
        assert "legacydesc" in result

    def test_synthetic_questions_included(self):
        result = combine_text({
            "name": "T",
            "synthetic_questions": ["How does it work?", "When to use it?"]
        })
        assert "How does it work?" in result

    def test_best_for_included(self):
        result = combine_text({"name": "T", "best_for": "beginners learning ML"})
        assert "beginners learning ML" in result

    def test_empty_item_returns_empty(self):
        result = combine_text({})
        assert result == ""

    def test_none_list_fields_not_crash(self):
        result = combine_text({"name": "T", "tags": None, "use_cases": None})
        assert "T" in result

    def test_category_labeled(self):
        result = combine_text({"name": "T", "category": "Econometrics"})
        assert "Category: Econometrics" in result


# ──────────────────────────────────────────────
# compute_content_hash
# ──────────────────────────────────────────────

import hashlib
import json

compute_content_hash = mod.compute_content_hash
should_regenerate = mod.should_regenerate


class TestComputeContentHash:
    def test_returns_16_char_string(self, tmp_path):
        h = compute_content_hash(tmp_path)
        assert isinstance(h, str)
        assert len(h) == 16

    def test_empty_dir_returns_stable_hash(self, tmp_path):
        h1 = compute_content_hash(tmp_path)
        h2 = compute_content_hash(tmp_path)
        assert h1 == h2

    def test_adding_file_changes_hash(self, tmp_path):
        h1 = compute_content_hash(tmp_path)
        (tmp_path / "packages.json").write_text('[]')
        h2 = compute_content_hash(tmp_path)
        assert h1 != h2

    def test_changing_file_content_changes_hash(self, tmp_path):
        f = tmp_path / "packages.json"
        f.write_text('[]')
        h1 = compute_content_hash(tmp_path)
        f.write_text('[{"name": "X"}]')
        h2 = compute_content_hash(tmp_path)
        assert h1 != h2

    def test_result_is_hex(self, tmp_path):
        h = compute_content_hash(tmp_path)
        int(h, 16)  # raises if not valid hex


# ──────────────────────────────────────────────
# should_regenerate
# ──────────────────────────────────────────────

class TestShouldRegenerate:
    def test_force_always_true(self, tmp_path):
        assert should_regenerate(tmp_path, tmp_path, force=True) is True

    def test_missing_metadata_returns_true(self, tmp_path):
        assert should_regenerate(tmp_path, tmp_path, force=False) is True

    def test_matching_hash_returns_false(self, tmp_path):
        (tmp_path / "packages.json").write_text('[]')
        current_hash = compute_content_hash(tmp_path)
        metadata = {"contentHash": current_hash, "items": []}
        (tmp_path / "search-metadata.json").write_text(json.dumps(metadata))
        assert should_regenerate(tmp_path, tmp_path, force=False) is False

    def test_stale_hash_returns_true(self, tmp_path):
        metadata = {"contentHash": "deadbeefdeadbeef", "items": []}
        (tmp_path / "search-metadata.json").write_text(json.dumps(metadata))
        assert should_regenerate(tmp_path, tmp_path, force=False) is True

    def test_corrupt_metadata_returns_true(self, tmp_path):
        (tmp_path / "search-metadata.json").write_text("not json{{{")
        assert should_regenerate(tmp_path, tmp_path, force=False) is True


# ──────────────────────────────────────────────
# generate_minisearch_index
# ──────────────────────────────────────────────

generate_minisearch_index = mod.generate_minisearch_index


def _item(**kwargs):
    base = {"id": "pkg-test", "name": "TestPkg", "description": "A test package",
            "category": "ML", "tags": ["causal", "ml"], "url": "https://test.com", "type": "package"}
    base.update(kwargs)
    return base


class TestGenerateMiniSearchIndex:
    def test_returns_dict_with_documents(self):
        result = generate_minisearch_index([_item()])
        assert isinstance(result, dict)
        assert "documents" in result

    def test_document_count_matches_input(self):
        items = [_item(id=f"pkg-{i}", name=f"Pkg{i}") for i in range(5)]
        result = generate_minisearch_index(items)
        assert len(result["documents"]) == 5

    def test_required_fields_present(self):
        doc = generate_minisearch_index([_item()])["documents"][0]
        for field in ("id", "name", "description", "category", "url", "type"):
            assert field in doc

    def test_optional_fields_included_when_present(self):
        item = _item(difficulty="intermediate", summary="Great tool", model_score=0.75)
        doc = generate_minisearch_index([item])["documents"][0]
        assert doc["difficulty"] == "intermediate"
        assert doc["summary"] == "Great tool"
        assert doc["model_score"] == pytest.approx(0.75)

    def test_optional_fields_excluded_when_absent(self):
        doc = generate_minisearch_index([_item()])["documents"][0]
        assert "difficulty" not in doc
        assert "summary" not in doc

    def test_synthetic_questions_list_joined(self):
        item = _item(synthetic_questions=["How to use?", "When to apply?"])
        doc = generate_minisearch_index([item])["documents"][0]
        assert "synthetic_questions" in doc
        assert "How to use?" in doc["synthetic_questions"]

    def test_empty_synthetic_questions_excluded(self):
        item = _item(synthetic_questions=[])
        doc = generate_minisearch_index([item])["documents"][0]
        assert "synthetic_questions" not in doc

    def test_version_field_present(self):
        result = generate_minisearch_index([_item()])
        assert "version" in result
        assert isinstance(result["version"], int)

    def test_config_has_fields_list(self):
        result = generate_minisearch_index([_item()])
        assert "fields" in result["config"]
        assert "name" in result["config"]["fields"]

    def test_empty_items_returns_empty_documents(self):
        result = generate_minisearch_index([])
        assert result["documents"] == []
