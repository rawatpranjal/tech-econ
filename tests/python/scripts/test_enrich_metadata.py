"""Tests for pure helpers in scripts/enrich_metadata.py.

anthropic is stubbed so the module loads cleanly without the SDK installed.
Only the pure get_prompt() helper is tested.
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("anthropic", MagicMock())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "enrich_metadata_mod", _REPO_ROOT / "scripts" / "enrich_metadata.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_metadata_mod"] = mod

_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _spec.loader.exec_module(mod)

get_prompt = mod.get_prompt


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------
class TestGetPrompt:
    def test_includes_item_name(self):
        prompt = get_prompt({"name": "DiD Package"}, "package")
        assert "DiD Package" in prompt

    def test_uses_title_when_name_missing(self):
        prompt = get_prompt({"title": "My Paper"}, "paper")
        assert "My Paper" in prompt

    def test_item_type_uppercased_in_prompt(self):
        prompt = get_prompt({"name": "X"}, "dataset")
        assert "DATASET" in prompt

    def test_includes_description(self):
        prompt = get_prompt({"name": "X", "description": "Causal forest estimator"}, "package")
        assert "Causal forest estimator" in prompt

    def test_includes_category(self):
        prompt = get_prompt({"name": "X", "category": "Causal Inference"}, "resource")
        assert "Causal Inference" in prompt

    def test_list_tags_joined(self):
        prompt = get_prompt({"name": "X", "tags": ["python", "causal", "ml"]}, "package")
        assert "python" in prompt
        assert "causal" in prompt

    def test_string_tags_passthrough(self):
        prompt = get_prompt({"name": "X", "tags": "python, ml"}, "package")
        assert "python, ml" in prompt

    def test_returns_json_only_instruction(self):
        prompt = get_prompt({"name": "X"}, "package")
        assert "JSON only" in prompt

    def test_returns_string(self):
        assert isinstance(get_prompt({"name": "X"}, "resource"), str)

    def test_empty_item_no_crash(self):
        prompt = get_prompt({}, "resource")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_response_format_keys_present(self):
        # The prompt should request these fields
        prompt = get_prompt({"name": "X"}, "resource")
        for key in ("difficulty", "prerequisites", "topic_tags", "summary", "use_cases", "audience"):
            assert key in prompt
