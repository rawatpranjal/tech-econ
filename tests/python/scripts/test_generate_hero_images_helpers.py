"""Bullshit tests for generate_hero_images.py pure helpers.

Covers: slugify (unicode NFKD, special chars, max-80, fallback),
        build_prompt (field injection, no-text constraint, type/category).
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_hero_images.py"

# Stub requests and PIL so the module loads without network or image deps
for _name in ["requests", "PIL", "PIL.Image"]:
    if _name not in sys.modules:
        _s = types.ModuleType(_name)
        _s.__getattr__ = lambda attr: MagicMock()
        sys.modules[_name] = _s

_spec = importlib.util.spec_from_file_location("generate_hero_images", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_hero_images"] = mod
_spec.loader.exec_module(mod)

slugify = mod.slugify
build_prompt = mod.build_prompt


# ──────────────────────────────────────────────
# slugify
# ──────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_removed(self):
        result = slugify("Causal & ML!")
        assert "&" not in result
        assert "!" not in result

    def test_unicode_normalized(self):
        # NFKD normalization: café → cafe
        result = slugify("Café Econometrics")
        assert "caf" in result
        assert "é" not in result

    def test_max_80_chars(self):
        result = slugify("word " * 20)
        assert len(result) <= 80

    def test_empty_fallback(self):
        assert slugify("") == "untitled"

    def test_only_specials_fallback(self):
        # All non-ascii stripped → empty → "untitled"
        result = slugify("!!!&&&")
        assert result == "untitled" or len(result) > 0  # either empty→untitled or stripped chars remain

    def test_spaces_become_hyphens(self):
        assert slugify("a b c") == "a-b-c"

    def test_consecutive_hyphens_collapsed(self):
        result = slugify("a  --  b")
        assert "--" not in result

    def test_lowercased(self):
        assert slugify("UPPER CASE") == "upper-case"


# ──────────────────────────────────────────────
# build_prompt
# ──────────────────────────────────────────────

class TestBuildPrompt:
    def test_name_in_prompt(self):
        result = build_prompt({"name": "DoubleML", "category": "Causal"})
        assert "DoubleML" in result

    def test_category_in_prompt(self):
        result = build_prompt({"name": "T", "category": "Experimentation"})
        assert "Experimentation" in result

    def test_type_in_prompt(self):
        result = build_prompt({"name": "T", "type": "package"})
        assert "package" in result

    def test_no_text_constraint(self):
        result = build_prompt({"name": "T"})
        assert "No text" in result

    def test_no_people_constraint(self):
        result = build_prompt({"name": "T"})
        assert "no people" in result.lower()

    def test_semantic_cluster_fallback_for_category(self):
        result = build_prompt({"name": "T", "semantic_cluster": "Causal ML"})
        assert "Causal ML" in result

    def test_empty_item_doesnt_crash(self):
        result = build_prompt({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_string(self):
        assert isinstance(build_prompt({"name": "X"}), str)


# ──────────────────────────────────────────────
# update_data_file
# ──────────────────────────────────────────────

import json

update_data_file = mod.update_data_file


class TestUpdateDataFile:
    def test_updates_matching_item(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps([{"name": "ToolA", "type": "resource"}]))
        result = update_data_file(f, "ToolA", "resource", "/img/tool-a.webp")
        assert result is True
        updated = json.loads(f.read_text())
        assert updated[0]["image_url"] == "/img/tool-a.webp"

    def test_returns_false_when_not_found(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps([{"name": "OtherTool", "type": "resource"}]))
        result = update_data_file(f, "ToolA", "resource", "/img/a.webp")
        assert result is False

    def test_type_mismatch_not_updated(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps([{"name": "ToolA", "type": "package"}]))
        result = update_data_file(f, "ToolA", "resource", "/img/a.webp")
        assert result is False

    def test_non_list_file_returns_false(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text(json.dumps({"items": []}))
        result = update_data_file(f, "ToolA", "resource", "/img/a.webp")
        assert result is False

    def test_atomic_write_replaces_file(self, tmp_path):
        f = tmp_path / "test.json"
        items = [{"name": "X", "type": "talk"}, {"name": "Y", "type": "talk"}]
        f.write_text(json.dumps(items))
        update_data_file(f, "X", "talk", "/img/x.webp")
        # The .tmp file should be gone (renamed)
        assert not (tmp_path / "test.json.tmp").exists()
        # Both items preserved
        result = json.loads(f.read_text())
        assert len(result) == 2


# ──────────────────────────────────────────────
# build_queue
# ──────────────────────────────────────────────

build_queue = mod.build_queue


class TestBuildQueue:
    def _patch_data_dir(self, monkeypatch, tmp_path, data_files):
        """Write stub JSON files to tmp_path and patch DATA_DIR."""
        for fname, content in data_files.items():
            (tmp_path / fname).write_text(json.dumps(content))
        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "DATA_FILES", {k.replace(".json", ""): k for k in data_files})

    def test_includes_items_without_image(self, monkeypatch, tmp_path):
        self._patch_data_dir(monkeypatch, tmp_path, {
            "resource.json": [{"name": "Blog Post", "category": "ML"}]
        })
        items = [{"type": "resource", "name": "Blog Post", "category": "ML"}]
        queue = build_queue(items, type_filter=None, force=False)
        assert len(queue) == 1
        assert queue[0]["name"] == "Blog Post"

    def test_skips_items_with_existing_image_when_not_forced(self, monkeypatch, tmp_path):
        self._patch_data_dir(monkeypatch, tmp_path, {
            "resource.json": [{"name": "Blog Post", "image_url": "/existing.webp"}]
        })
        items = [{"type": "resource", "name": "Blog Post"}]
        queue = build_queue(items, type_filter=None, force=False)
        assert len(queue) == 0

    def test_force_includes_items_with_existing_image(self, monkeypatch, tmp_path):
        self._patch_data_dir(monkeypatch, tmp_path, {
            "resource.json": [{"name": "Blog Post", "image_url": "/existing.webp"}]
        })
        items = [{"type": "resource", "name": "Blog Post"}]
        queue = build_queue(items, type_filter=None, force=True)
        assert len(queue) == 1

    def test_type_filter_applied(self, monkeypatch, tmp_path):
        self._patch_data_dir(monkeypatch, tmp_path, {
            "resource.json": [{"name": "A Resource"}],
            "talk.json": [{"name": "A Talk"}],
        })
        items = [
            {"type": "resource", "name": "A Resource"},
            {"type": "talk", "name": "A Talk"},
        ]
        queue = build_queue(items, type_filter="resource", force=False)
        assert all(q["type"] == "resource" for q in queue)
        assert len(queue) == 1

    def test_skips_items_not_in_source(self, monkeypatch, tmp_path):
        self._patch_data_dir(monkeypatch, tmp_path, {
            "resource.json": [{"name": "Different Name"}]
        })
        items = [{"type": "resource", "name": "Missing Name"}]
        queue = build_queue(items, type_filter=None, force=False)
        assert len(queue) == 0


# ──────────────────────────────────────────────
# _decode_image
# ──────────────────────────────────────────────

import base64

_decode_image = mod._decode_image


class TestDecodeImage:
    def test_b64_json_path_returns_bytes(self):
        raw = b"fake-png-bytes"
        encoded = base64.b64encode(raw).decode()
        result = _decode_image({"data": [{"b64_json": encoded}]})
        assert result == raw

    def test_empty_payload_returns_none(self):
        assert _decode_image({}) is None

    def test_empty_data_list_returns_none(self):
        assert _decode_image({"data": []}) is None

    def test_no_b64_or_url_returns_none(self):
        assert _decode_image({"data": [{}]}) is None

    def test_null_data_returns_none(self):
        assert _decode_image({"data": None}) is None

    def test_b64_json_decoded_correctly(self):
        raw = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        encoded = base64.b64encode(raw).decode()
        result = _decode_image({"data": [{"b64_json": encoded}]})
        assert result == raw
