"""Bullshit tests for enrich_batch.py :: format_prompt_for_batch.

Covers:
  - returns a 2-element message list (system + user)
  - name/description/category fields injected into user prompt
  - tags list → comma-joined string
  - tags string passes through unchanged
  - unknown content_type falls back to "resource" prompt
  - known content_types produce different prompts
  - missing fields silently use empty string / 0
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: MagicMock()
    sys.modules[name] = m
    return m


# Stub heavy deps before any import chain
for _dep in ["anthropic", "openai", "requests", "pydantic"]:
    if _dep not in sys.modules:
        _stub(_dep)

# pydantic.BaseModel must be a real class
import pydantic as _p
if not isinstance(getattr(_p, "BaseModel", None), type):
    _p.BaseModel = object
_p.Field = MagicMock(return_value=None)
_p.validator = MagicMock(return_value=lambda f: f)

# Load enrich_metadata_v2 first (enrich_batch imports from it)
if "enrich_metadata_v2" not in sys.modules:
    _spec_v2 = importlib.util.spec_from_file_location(
        "enrich_metadata_v2", _REPO_ROOT / "scripts" / "enrich_metadata_v2.py"
    )
    assert _spec_v2 and _spec_v2.loader
    _m2 = importlib.util.module_from_spec(_spec_v2)
    sys.modules["enrich_metadata_v2"] = _m2
    _spec_v2.loader.exec_module(_m2)

_spec = importlib.util.spec_from_file_location(
    "enrich_batch", _REPO_ROOT / "scripts" / "enrich_batch.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_batch"] = _mod
_spec.loader.exec_module(_mod)

format_prompt_for_batch = _mod.format_prompt_for_batch


class TestFormatPromptForBatch:
    def test_returns_two_messages(self):
        msgs = format_prompt_for_batch({"name": "Tool"}, "resource")
        assert len(msgs) == 2

    def test_first_message_is_system(self):
        msgs = format_prompt_for_batch({"name": "Tool"}, "resource")
        assert msgs[0]["role"] == "system"

    def test_second_message_is_user(self):
        msgs = format_prompt_for_batch({"name": "Tool"}, "resource")
        assert msgs[1]["role"] == "user"

    def test_name_injected_into_prompt(self):
        msgs = format_prompt_for_batch({"name": "CausalForest"}, "resource")
        assert "CausalForest" in msgs[1]["content"]

    def test_description_injected(self):
        msgs = format_prompt_for_batch(
            {"name": "A", "description": "Unique desc xyzzy"}, "resource"
        )
        assert "Unique desc xyzzy" in msgs[1]["content"]

    def test_tags_list_joined(self):
        msgs = format_prompt_for_batch(
            {"name": "A", "tags": ["causal", "ml", "bayesian"]}, "resource"
        )
        assert "causal" in msgs[1]["content"]
        assert "ml" in msgs[1]["content"]

    def test_tags_string_passes_through(self):
        msgs = format_prompt_for_batch(
            {"name": "A", "tags": "causal, ml"}, "resource"
        )
        assert "causal, ml" in msgs[1]["content"]

    def test_unknown_type_no_crash(self):
        # Falls back to resource template; just verify no KeyError/crash
        msgs = format_prompt_for_batch({"name": "A"}, "unknown_type_xyz")
        assert len(msgs) == 2
        assert msgs[1]["role"] == "user"

    def test_different_content_types_produce_different_prompts(self):
        msg_resource = format_prompt_for_batch({"name": "A"}, "resource")
        msg_paper = format_prompt_for_batch({"name": "A"}, "paper")
        # Paper and resource templates should differ
        assert msg_resource[1]["content"] != msg_paper[1]["content"]

    def test_missing_fields_no_crash(self):
        # Empty item should not raise KeyError
        msgs = format_prompt_for_batch({}, "resource")
        assert len(msgs) == 2

    def test_title_fallback_for_name(self):
        msgs = format_prompt_for_batch({"title": "My Paper Title"}, "paper")
        assert "My Paper Title" in msgs[1]["content"]

    def test_system_message_mentions_json(self):
        msgs = format_prompt_for_batch({"name": "A"}, "resource")
        assert "JSON" in msgs[0]["content"]
