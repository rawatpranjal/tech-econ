"""Tests for the pure helpers in scripts/generate_hero_images.py.

Stubs PIL and requests before loading the module so no real I/O happens.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# --- stub heavy deps before module load ----------------------------------
for _mod in ("PIL", "PIL.Image", "requests", "dotenv"):
    sys.modules.setdefault(_mod, MagicMock())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_hero_images.py"
_spec = importlib.util.spec_from_file_location("generate_hero_images_mod", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_hero_images_mod"] = mod
_spec.loader.exec_module(mod)

slugify = mod.slugify
build_prompt = mod.build_prompt
_decode_image = mod._decode_image


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------
class TestSlugify:
    def test_basic_ascii(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_removed(self):
        assert slugify("C++ / Python!") == "c-python"

    def test_unicode_normalised(self):
        result = slugify("Ångström")
        # Non-ASCII stripped after NFKD → ASCII
        assert result == "angstrom"

    def test_multiple_spaces_and_hyphens_collapsed(self):
        assert slugify("foo  --  bar") == "foo-bar"

    def test_empty_returns_untitled(self):
        assert slugify("") == "untitled"
        assert slugify("   ") == "untitled"

    def test_truncated_to_80_chars(self):
        result = slugify("a" * 100)
        assert len(result) == 80

    def test_numbers_preserved(self):
        assert slugify("Top 10 Papers 2024") == "top-10-papers-2024"

    def test_no_trailing_hyphen(self):
        result = slugify("hello!")
        assert not result.endswith("-")


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------
class TestBuildPrompt:
    def test_includes_item_name(self):
        prompt = build_prompt({"name": "DiD Estimator", "type": "package"})
        assert "DiD Estimator" in prompt

    def test_includes_category_when_present(self):
        prompt = build_prompt({"name": "x", "category": "Causal Inference", "type": "resource"})
        assert "Causal Inference" in prompt

    def test_falls_back_to_semantic_cluster(self):
        prompt = build_prompt({"name": "x", "semantic_cluster": "ML Theory", "type": "package"})
        assert "ML Theory" in prompt

    def test_no_text_in_prompt_phrase(self):
        prompt = build_prompt({"name": "y", "type": "talk"})
        assert "No text" in prompt

    def test_wide_composition_phrase(self):
        prompt = build_prompt({"name": "z"})
        assert "16:9" in prompt

    def test_empty_name_handled(self):
        # Should not crash; name may be empty string
        prompt = build_prompt({"name": "", "type": "book"})
        assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# _decode_image
# ---------------------------------------------------------------------------
class TestDecodeImage:
    def test_b64_json_path(self):
        import base64
        raw = b"fake png bytes"
        payload = {"data": [{"b64_json": base64.b64encode(raw).decode()}]}
        result = _decode_image(payload)
        assert result == raw

    def test_empty_data_returns_none(self):
        assert _decode_image({"data": []}) is None

    def test_no_data_key_returns_none(self):
        assert _decode_image({}) is None

    def test_url_path_returns_content_on_200(self, monkeypatch):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"image bytes"
        monkeypatch.setattr(mod.requests, "get", lambda *a, **kw: fake_resp)
        result = _decode_image({"data": [{"url": "https://example.com/img.png"}]})
        assert result == b"image bytes"

    def test_url_path_non_200_returns_none(self, monkeypatch):
        fake_resp = MagicMock()
        fake_resp.status_code = 404
        monkeypatch.setattr(mod.requests, "get", lambda *a, **kw: fake_resp)
        result = _decode_image({"data": [{"url": "https://example.com/img.png"}]})
        assert result is None
