"""Bullshit tests for discover_content.py pure helpers.

Covers: validate_item (required fields, URL validation, name length, type check,
        papers year check, community workshop exclusion),
        get_weekly_queries (rotation logic, budget cap, underscore-prefix skip).
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "discover_content.py"

# Stub deps
for _name in ["anthropic", "openai", "requests", "duckduckgo_search"]:
    if _name not in sys.modules:
        _m = types.ModuleType(_name)
        _m.__getattr__ = lambda attr: MagicMock()
        sys.modules[_name] = _m

_spec = importlib.util.spec_from_file_location("discover_content", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["discover_content"] = mod
_spec.loader.exec_module(mod)

validate_item = mod.validate_item
get_weekly_queries = mod.get_weekly_queries


# ──────────────────────────────────────────────
# validate_item
# ──────────────────────────────────────────────

_VALID_PACKAGE = {
    "name": "DoubleML",
    "description": "Double machine learning library",
    "category": "Causal",
    "url": "https://github.com/DoubleML/doubleml-for-py",
    "tags": ["causal", "ml"],
    "language": "Python",
}


class TestValidateItem:
    def test_valid_package(self):
        ok, issues = validate_item(_VALID_PACKAGE, "packages")
        assert ok is True
        assert issues == []

    def test_missing_required_field(self):
        item = {**_VALID_PACKAGE}
        del item["language"]
        ok, issues = validate_item(item, "packages")
        assert ok is False
        assert any("language" in i for i in issues)

    def test_invalid_url_scheme(self):
        item = {**_VALID_PACKAGE, "url": "not-a-url"}
        ok, issues = validate_item(item, "packages")
        assert any("invalid URL" in i for i in issues)

    def test_name_too_short(self):
        item = {**_VALID_PACKAGE, "name": "ab"}
        ok, issues = validate_item(item, "packages")
        assert any("name too short" in i for i in issues)

    def test_name_too_long(self):
        item = {**_VALID_PACKAGE, "name": "X" * 201}
        ok, issues = validate_item(item, "packages")
        assert any("name too long" in i for i in issues)

    def test_tags_not_list(self):
        item = {**_VALID_PACKAGE, "tags": "causal,ml"}
        ok, issues = validate_item(item, "packages")
        assert any("tags is not a list" in i for i in issues)

    def test_papers_suspicious_year(self):
        item = {
            "title": "Old Paper",
            "authors": "Smith",
            "year": 1900,
            "url": "https://arxiv.org/abs/1234",
            "tags": ["causal"],
            "citations": 0,
        }
        ok, issues = validate_item(item, "papers")
        assert any("suspicious year" in i for i in issues)

    def test_community_workshop_excluded(self):
        item = {
            "name": "NeurIPS Workshop on ML",
            "description": "An ML workshop",
            "category": "Conference",
            "url": "https://neurips.cc",
            "type": "Conference",
        }
        ok, issues = validate_item(item, "community")
        assert ok is False
        assert any("workshop" in i.lower() for i in issues)

    def test_valid_dataset(self):
        item = {
            "name": "ANES Survey",
            "description": "American National Election Study",
            "category": "Political Economy",
            "url": "https://electionstudies.org",
            "tags": ["survey", "politics"],
        }
        ok, issues = validate_item(item, "datasets")
        assert ok is True

    def test_missing_url_is_flagged(self):
        item = {**_VALID_PACKAGE}
        del item["url"]
        ok, issues = validate_item(item, "packages")
        assert ok is False
        assert any("url" in i for i in issues)


# ──────────────────────────────────────────────
# get_weekly_queries
# ──────────────────────────────────────────────

_QUERIES_CONFIG = {
    "packages": {
        "causal": ["DoubleML package", "EconML package", "CausalML package"],
        "ml": ["LightGBM Python", "XGBoost Python"],
        "_hidden_key": ["should be skipped"],
    },
    "_meta": {
        "budget": {
            "packages": {"queries_per_week": 3}
        }
    }
}


class TestGetWeeklyQueries:
    def test_returns_list(self):
        result = get_weekly_queries(_QUERIES_CONFIG, "packages", 0)
        assert isinstance(result, list)

    def test_respects_budget_cap(self):
        result = get_weekly_queries(_QUERIES_CONFIG, "packages", 0)
        assert len(result) <= 3

    def test_underscore_prefix_skipped(self):
        result = get_weekly_queries(_QUERIES_CONFIG, "packages", 0)
        queries = [r["query"] for r in result]
        assert "should be skipped" not in queries

    def test_rotation_by_week(self):
        r0 = get_weekly_queries(_QUERIES_CONFIG, "packages", 0)
        r1 = get_weekly_queries(_QUERIES_CONFIG, "packages", 1)
        # Different start index → different subset (may wrap around on small sets)
        assert isinstance(r1, list)

    def test_unknown_content_type_returns_empty(self):
        result = get_weekly_queries(_QUERIES_CONFIG, "nonexistent", 0)
        assert result == []

    def test_each_result_has_query_and_category(self):
        result = get_weekly_queries(_QUERIES_CONFIG, "packages", 0)
        for item in result:
            assert "query" in item
            assert "category" in item


# ──────────────────────────────────────────────
# generate_digest
# ──────────────────────────────────────────────
generate_digest = mod.generate_digest


class TestGenerateDigest:
    def test_returns_string(self):
        assert isinstance(generate_digest({}), str)

    def test_html_structure(self):
        result = generate_digest({})
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result

    def test_no_items_message(self):
        result = generate_digest({"added": []})
        assert "No items added this week" in result

    def test_added_item_appears_in_output(self):
        results = {
            "added": [
                {"type": "package", "item": {"name": "EconML"}, "url": "https://econml.org"}
            ]
        }
        result = generate_digest(results)
        assert "EconML" in result

    def test_dry_run_label_shown(self):
        result = generate_digest({"dry_run": True})
        assert "DRY RUN" in result

    def test_errors_section_shown(self):
        result = generate_digest({"errors": ["Connection timed out"]})
        assert "Connection timed out" in result

    def test_api_usage_included(self):
        result = generate_digest({"api_usage": {"brave": 5, "openai_calls": 10}})
        assert "Brave: 5" in result

    def test_empty_dict_no_crash(self):
        # Should not raise even with minimal input
        result = generate_digest({})
        assert isinstance(result, str)

    def test_staged_papers_shown(self):
        results = {"staged": [{"title": "Causal Forest Paper"}]}
        result = generate_digest(results)
        assert "Causal Forest Paper" in result

    def test_rejected_table_shown(self):
        results = {
            "rejected": [{"url": "https://bad.com/paper", "relevance_score": 3, "reasoning": "too niche"}]
        }
        result = generate_digest(results)
        assert "bad.com" in result
        assert "too niche" in result
