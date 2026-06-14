"""Tests for pure helpers in scripts/sync_resources.py.

Covers: normalize_url (prefix stripping, trailing slash, casing),
        extract_urls_from_source (empty input, resources/packages arrays,
        source field propagation, DOMAIN_MAPPING lookup).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(script_name: str, alias: str):
    path = _REPO_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


sync_resources_mod = _load("sync_resources.py", "sync_resources_mod")
normalize_url = sync_resources_mod.normalize_url
extract_urls_from_source = sync_resources_mod.extract_urls_from_source
DOMAIN_MAPPING = sync_resources_mod.DOMAIN_MAPPING


# ──────────────────────────────────────────────
# normalize_url
# ──────────────────────────────────────────────

class TestNormalizeUrl:
    def test_https_www_prefix_with_trailing_slash(self):
        assert normalize_url("https://www.example.com/path/") == "example.com/path"

    def test_http_www_prefix(self):
        assert normalize_url("http://www.example.com") == "example.com"

    def test_https_prefix(self):
        assert normalize_url("https://example.com") == "example.com"

    def test_http_prefix(self):
        assert normalize_url("http://example.com") == "example.com"

    def test_already_clean(self):
        assert normalize_url("example.com") == "example.com"

    def test_trailing_slash_no_prefix(self):
        assert normalize_url("example.com/") == "example.com"

    def test_uppercase_lowercased(self):
        assert normalize_url("HTTPS://Example.COM/Path") == "example.com/path"

    def test_https_www_takes_priority_over_https(self):
        # Must strip "https://www." not just "https://", leaving bare domain
        result = normalize_url("https://www.example.com")
        assert result == "example.com"
        assert not result.startswith("www.")

    def test_leading_and_trailing_whitespace_stripped(self):
        assert normalize_url("  https://example.com  ") == "example.com"

    def test_path_preserved(self):
        assert normalize_url("https://example.com/some/path") == "example.com/some/path"

    def test_multiple_trailing_slashes_removed(self):
        # rstrip("/") removes all trailing slashes
        assert normalize_url("https://example.com///") == "example.com"


# ──────────────────────────────────────────────
# extract_urls_from_source
# ──────────────────────────────────────────────

class TestExtractUrlsFromSource:
    def test_empty_list_returns_empty(self):
        assert extract_urls_from_source([], "roadmaps") == []

    def test_resources_array_produces_resource_type(self):
        data = [
            {
                "name": "Learn Python",
                "resources": [
                    {"name": "Real Python", "url": "https://realpython.com", "why": "Great tutorials"}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert len(results) == 1
        assert results[0]["type"] == "Resource"

    def test_resource_entry_has_correct_fields(self):
        data = [
            {
                "name": "Learn Python",
                "resources": [
                    {"name": "Real Python", "url": "https://realpython.com", "why": "Great tutorials"}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        entry = results[0]
        assert entry["url"] == "https://realpython.com"
        assert entry["name"] == "Real Python"
        assert entry["source"] == "roadmaps"
        assert entry["type"] == "Resource"

    def test_packages_array_produces_package_type(self):
        data = [
            {
                "name": "Learn Python",
                "packages": [
                    {"name": "pandas", "url": "https://pandas.pydata.org", "why": "Data frames"}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert len(results) == 1
        assert results[0]["type"] == "Package"

    def test_packages_have_python_package_tag(self):
        data = [
            {
                "name": "Learn Python",
                "packages": [
                    {"name": "numpy", "url": "https://numpy.org", "why": "Arrays"}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert "Python Package" in results[0]["tags"]

    def test_both_resources_and_packages_all_included(self):
        data = [
            {
                "name": "Learn Python",
                "resources": [
                    {"name": "Res A", "url": "https://a.com", "why": ""}
                ],
                "packages": [
                    {"name": "Pkg B", "url": "https://b.com", "why": ""}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert len(results) == 2
        types = {r["type"] for r in results}
        assert types == {"Resource", "Package"}

    def test_source_name_flows_into_each_entry(self):
        data = [
            {
                "name": "Learn SQL",
                "resources": [
                    {"name": "SQLZoo", "url": "https://sqlzoo.net", "why": "Practice"}
                ]
            }
        ]
        results = extract_urls_from_source(data, "domains")
        assert results[0]["source"] == "domains"

    def test_item_with_no_resources_or_packages_adds_nothing(self):
        data = [{"name": "Empty Item"}]
        assert extract_urls_from_source(data, "roadmaps") == []

    def test_known_domain_mapping_sets_domain_and_category(self):
        # "Learn Python" is in DOMAIN_MAPPING → ("Programming & Tools", "Python Fundamentals")
        data = [
            {
                "name": "Learn Python",
                "resources": [
                    {"name": "Docs", "url": "https://docs.python.org", "why": ""}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        expected_domain, expected_category = DOMAIN_MAPPING["Learn Python"]
        assert results[0]["domain"] == expected_domain
        assert results[0]["category"] == expected_category

    def test_unknown_item_gets_other_domain_and_category(self):
        data = [
            {
                "name": "Some Unknown Topic",
                "resources": [
                    {"name": "X", "url": "https://x.com", "why": ""}
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert results[0]["domain"] == "Other"
        assert results[0]["category"] == "Other"

    def test_multiple_resources_in_one_item(self):
        data = [
            {
                "name": "Learn ML",
                "resources": [
                    {"name": "R1", "url": "https://r1.com", "why": ""},
                    {"name": "R2", "url": "https://r2.com", "why": ""},
                    {"name": "R3", "url": "https://r3.com", "why": ""},
                ]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert len(results) == 3

    def test_multiple_items_aggregated(self):
        data = [
            {
                "name": "Learn Python",
                "resources": [{"name": "A", "url": "https://a.com", "why": ""}]
            },
            {
                "name": "Learn SQL",
                "resources": [{"name": "B", "url": "https://b.com", "why": ""}]
            }
        ]
        results = extract_urls_from_source(data, "roadmaps")
        assert len(results) == 2
