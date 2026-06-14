"""Tests for pure helpers in scripts/generate_embeddings.py.

sentence_transformers is guarded with try/except at module level,
so the module loads cleanly without any ML deps.
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_embeddings.py"
_spec = importlib.util.spec_from_file_location("generate_embeddings_mod", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_embeddings_mod"] = mod

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _spec.loader.exec_module(mod)

combine_text = mod.combine_text_for_embedding
slugify = mod.slugify


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------
class TestSlugify:
    def test_lowercases(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_become_hyphens(self):
        assert slugify("C++ / Python!") == "c-python"

    def test_consecutive_non_alnum_collapsed(self):
        assert slugify("foo  --  bar") == "foo-bar"

    def test_no_leading_trailing_hyphens(self):
        result = slugify("  causal inference  ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_digits_preserved(self):
        assert slugify("gpt-4 v2") == "gpt-4-v2"

    def test_truncated_to_100_chars(self):
        result = slugify("a" * 200)
        assert len(result) <= 100

    def test_empty_string(self):
        assert slugify("") == ""


# ---------------------------------------------------------------------------
# combine_text_for_embedding
# ---------------------------------------------------------------------------
class TestCombineTextForEmbedding:
    def test_uses_embedding_text_when_long(self):
        item = {
            "name": "DiD Estimator",
            "embedding_text": "x" * 300,  # > 200 chars
        }
        result = combine_text(item)
        assert "DiD Estimator" in result
        assert "x" * 100 in result  # big chunk of embedding_text present

    def test_name_always_first(self):
        item = {
            "name": "My Package",
            "description": "A description",
        }
        result = combine_text(item)
        assert result.startswith("My Package")

    def test_short_embedding_text_falls_through_to_legacy(self):
        # embedding_text < 200 chars → uses legacy fallback
        item = {
            "name": "Pkg",
            "embedding_text": "short",
            "description": "A useful description",
        }
        result = combine_text(item)
        assert "A useful description" in result

    def test_legacy_includes_description(self):
        item = {"name": "X", "description": "Informative desc"}
        assert "Informative desc" in combine_text(item)

    def test_legacy_includes_category(self):
        item = {"name": "X", "category": "Causal Inference"}
        assert "Causal Inference" in combine_text(item)

    def test_legacy_includes_tags(self):
        item = {"name": "X", "tags": ["python", "ml"]}
        result = combine_text(item)
        assert "python" in result

    def test_legacy_includes_topic_tags(self):
        item = {"name": "X", "topic_tags": ["regression", "IV"]}
        result = combine_text(item)
        assert "regression" in result

    def test_legacy_includes_best_for(self):
        item = {"name": "X", "best_for": "Researchers"}
        assert "Researchers" in combine_text(item)

    def test_legacy_includes_synthetic_questions(self):
        item = {"name": "X", "synthetic_questions": ["How to use RD?", "What is IV?"]}
        result = combine_text(item)
        assert "How to use RD?" in result

    def test_empty_item_returns_empty_string(self):
        assert combine_text({}) == ""

    def test_missing_name_no_crash(self):
        result = combine_text({"description": "desc only"})
        assert "desc only" in result

    def test_embedding_text_appends_synthetic_questions(self):
        item = {
            "name": "Pkg",
            "embedding_text": "e" * 300,
            "synthetic_questions": ["Q1?", "Q2?"],
        }
        result = combine_text(item)
        assert "Q1?" in result

    def test_non_list_tags_no_crash(self):
        # Tags may be missing or not a list — should not throw
        item = {"name": "X", "tags": "not-a-list"}
        result = combine_text(item)
        assert isinstance(result, str)
