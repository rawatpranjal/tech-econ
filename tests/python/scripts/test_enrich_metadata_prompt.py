"""Bullshit tests for enrich_metadata.py get_prompt.

Covers: prompt structure (item fields included, item_type uppercased,
JSON schema present, RULES sections present).
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "enrich_metadata.py"

# Stub anthropic
if "anthropic" not in sys.modules:
    _a = types.ModuleType("anthropic")
    _a.Anthropic = object
    sys.modules["anthropic"] = _a

_spec = importlib.util.spec_from_file_location("enrich_metadata", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_metadata"] = mod
_spec.loader.exec_module(mod)

get_prompt = mod.get_prompt


BASE_ITEM = {
    "name": "DoubleML",
    "description": "Double machine learning for causal inference",
    "category": "Causal",
    "tags": ["causal", "ml"],
}


class TestGetPrompt:
    def test_name_in_prompt(self):
        result = get_prompt(BASE_ITEM, "package")
        assert "DoubleML" in result

    def test_description_in_prompt(self):
        result = get_prompt(BASE_ITEM, "package")
        assert "Double machine learning" in result

    def test_item_type_uppercased(self):
        result = get_prompt(BASE_ITEM, "package")
        assert "PACKAGE" in result

    def test_category_in_prompt(self):
        result = get_prompt(BASE_ITEM, "package")
        assert "Causal" in result

    def test_tags_list_joined(self):
        result = get_prompt({"name": "T", "tags": ["causal", "ml"]}, "paper")
        assert "causal" in result
        assert "ml" in result

    def test_tags_string_passthrough(self):
        result = get_prompt({"name": "T", "tags": "causal, ml"}, "paper")
        assert "causal, ml" in result

    def test_json_schema_present(self):
        result = get_prompt(BASE_ITEM, "package")
        assert '"difficulty"' in result
        assert '"topic_tags"' in result
        assert '"synthetic_questions"' in result

    def test_returns_string(self):
        assert isinstance(get_prompt(BASE_ITEM, "package"), str)

    def test_empty_item_doesnt_crash(self):
        result = get_prompt({}, "resource")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_title_field_fallback(self):
        # Papers use 'title' not 'name'
        result = get_prompt({"title": "My Paper"}, "paper")
        assert "My Paper" in result

    def test_different_item_types_change_prompt(self):
        p1 = get_prompt(BASE_ITEM, "package")
        p2 = get_prompt(BASE_ITEM, "dataset")
        assert "PACKAGE" in p1
        assert "DATASET" in p2
        assert p1 != p2
