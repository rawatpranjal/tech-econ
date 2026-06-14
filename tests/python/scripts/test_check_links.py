"""Tests for extract_urls in scripts/check_links.py.

extract_urls recursively extracts all URLs from a data structure.
No network calls are made — this is purely structural.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "check_links.py"
_spec = importlib.util.spec_from_file_location("check_links", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_links"] = mod
_spec.loader.exec_module(mod)


def extract(data) -> set:
    urls = set()
    mod.extract_urls(data, urls)
    return urls


class TestExtractUrls:

    def test_extracts_url_field(self):
        assert "https://example.com" in extract({"url": "https://example.com"})

    def test_extracts_github_url(self):
        assert "https://github.com/org/repo" in extract({"github_url": "https://github.com/org/repo"})

    def test_extracts_docs_url(self):
        assert "https://docs.example.com" in extract({"docs_url": "https://docs.example.com"})

    def test_extracts_image_url(self):
        assert "https://img.example.com/logo.png" in extract({"image_url": "https://img.example.com/logo.png"})

    def test_ignores_non_http_values(self):
        result = extract({"url": "ftp://example.com"})
        assert len(result) == 0

    def test_ignores_non_url_fields(self):
        result = extract({"name": "https://fake.com", "description": "https://also-fake.com"})
        assert len(result) == 0

    def test_extracts_from_list(self):
        data = [
            {"url": "https://a.com"},
            {"url": "https://b.com"},
        ]
        assert extract(data) == {"https://a.com", "https://b.com"}

    def test_extracts_multiple_url_fields_from_same_item(self):
        item = {"url": "https://main.com", "github_url": "https://github.com/x"}
        result = extract(item)
        assert "https://main.com" in result
        assert "https://github.com/x" in result

    def test_nested_dict_extraction(self):
        data = {"items": [{"url": "https://nested.com"}]}
        assert "https://nested.com" in extract(data)

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"url": "https://deep.com"}}}}
        assert "https://deep.com" in extract(data)

    def test_empty_dict_returns_empty(self):
        assert extract({}) == set()

    def test_empty_list_returns_empty(self):
        assert extract([]) == set()

    def test_no_duplicates(self):
        data = [
            {"url": "https://same.com"},
            {"url": "https://same.com"},
        ]
        assert extract(data) == {"https://same.com"}

    def test_non_string_url_ignored(self):
        assert extract({"url": 42}) == set()
        assert extract({"url": None}) == set()
        assert extract({"url": ["https://a.com"]}) == set()
