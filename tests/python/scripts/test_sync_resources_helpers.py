"""Bullshit tests for sync_resources.py normalize_url.

Covers: prefix stripping, trailing slash, case normalization.
No filesystem / network.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "sync_resources.py"

# The script reads JSON files at module level — stub open() won't help,
# but the constants are just Path objects and nothing runs at import time
# beyond defining functions. Safe to load directly.
_spec = importlib.util.spec_from_file_location("sync_resources", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_resources"] = mod
_spec.loader.exec_module(mod)

normalize_url = mod.normalize_url


class TestNormalizeUrl:
    def test_strips_https_www(self):
        assert normalize_url("https://www.example.com") == "example.com"

    def test_strips_http_www(self):
        assert normalize_url("http://www.example.com") == "example.com"

    def test_strips_https(self):
        assert normalize_url("https://example.com") == "example.com"

    def test_strips_http(self):
        assert normalize_url("http://example.com") == "example.com"

    def test_trailing_slash_removed(self):
        assert normalize_url("https://example.com/") == "example.com"

    def test_path_preserved(self):
        assert normalize_url("https://example.com/path/to/page") == "example.com/path/to/page"

    def test_trailing_slash_on_path_removed(self):
        assert normalize_url("https://example.com/path/") == "example.com/path"

    def test_lowercased(self):
        assert normalize_url("https://EXAMPLE.COM") == "example.com"

    def test_leading_whitespace_stripped(self):
        assert normalize_url("  https://example.com  ") == "example.com"

    def test_https_www_beats_http_www(self):
        # https://www. should be stripped, not partially matched by http://
        result = normalize_url("https://www.github.com/org/repo")
        assert result == "github.com/org/repo"

    def test_empty_string(self):
        # No prefix matches; empty input stripped, trailing slash already absent
        assert normalize_url("") == ""

    def test_no_prefix_passthrough(self):
        assert normalize_url("ftp://example.com") == "ftp://example.com"

    def test_arxiv_url(self):
        result = normalize_url("https://arxiv.org/abs/1234.5678")
        assert result == "arxiv.org/abs/1234.5678"

    def test_github_url(self):
        result = normalize_url("https://github.com/user/repo/")
        assert result == "github.com/user/repo"

    def test_idempotent_on_already_normalized(self):
        normalized = normalize_url("https://example.com/path")
        assert normalize_url(normalized) == normalized


# ──────────────────────────────────────────────
# extract_urls_from_source
# ──────────────────────────────────────────────

extract_urls_from_source = mod.extract_urls_from_source


class TestExtractUrlsFromSource:
    def _item(self, name="TestDomain", resources=None, packages=None):
        return {
            "name": name,
            "resources": resources or [],
            "packages": packages or [],
        }

    def test_empty_data_returns_empty(self):
        assert extract_urls_from_source([], "test") == []

    def test_extracts_resources(self):
        item = self._item(resources=[
            {"name": "Blog Post", "url": "https://example.com/post", "why": "Useful"}
        ])
        result = extract_urls_from_source([item], "roadmaps")
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/post"
        assert result[0]["type"] == "Resource"

    def test_extracts_packages(self):
        item = self._item(packages=[
            {"name": "MyPkg", "url": "https://pypi.org/project/mypkg", "why": "Great"}
        ])
        result = extract_urls_from_source([item], "roadmaps")
        assert len(result) == 1
        assert result[0]["type"] == "Package"

    def test_source_name_injected(self):
        item = self._item(resources=[{"name": "X", "url": "https://x.com", "why": ""}])
        result = extract_urls_from_source([item], "my_source")
        assert result[0]["source"] == "my_source"

    def test_source_item_name_injected(self):
        item = self._item(name="Causal Inference", resources=[{"name": "X", "url": "https://x.com", "why": ""}])
        result = extract_urls_from_source([item], "s")
        assert result[0]["source_item"] == "Causal Inference"

    def test_missing_url_defaults_to_empty(self):
        item = self._item(resources=[{"name": "No URL", "why": "ok"}])
        result = extract_urls_from_source([item], "s")
        assert result[0]["url"] == ""

    def test_multiple_items_all_extracted(self):
        items = [
            self._item("Domain1", resources=[{"name": "R1", "url": "https://a.com", "why": ""}]),
            self._item("Domain2", packages=[{"name": "P1", "url": "https://b.com", "why": ""}]),
        ]
        result = extract_urls_from_source(items, "s")
        assert len(result) == 2

    def test_package_has_python_package_tag(self):
        item = self._item(packages=[{"name": "Pkg", "url": "https://pkg.org", "why": ""}])
        result = extract_urls_from_source([item], "s")
        assert "Python Package" in result[0]["tags"]
