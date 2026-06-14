"""Tests for validate_item in scripts/discover_content.py.

validate_item is the gate that blocks malformed items from entering the
data pipeline. Testing it ensures autoresearch can't inject bad data.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "discover_content.py"
_spec = importlib.util.spec_from_file_location("discover_content", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["discover_content"] = mod
_spec.loader.exec_module(mod)

validate_item = mod.validate_item


def _pkg(**kwargs):
    """Minimal valid package item (all required fields per REQUIRED_FIELDS)."""
    base = {
        "name": "DoubleML",
        "url": "https://example.com",
        "category": "ML",
        "description": "A causal ML package",
        "tags": ["causal", "ml"],
        "language": "Python",
    }
    base.update(kwargs)
    return base


def _paper(**kwargs):
    """Minimal valid paper item."""
    base = {
        "title": "Causal Paper",
        "authors": "Angrist, J.",
        "year": 2022,
        "url": "https://arxiv.org/abs/1234",
        "tags": ["causal"],
        "citations": 42,
    }
    base.update(kwargs)
    return base


def _community(**kwargs):
    """Minimal valid community item."""
    base = {
        "name": "EconCS Conference",
        "url": "https://x.com",
        "description": "A top conference",
        "category": "Conferences",
        "type": "Conference",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Valid items pass
# ---------------------------------------------------------------------------

class TestValidItemsPassed:

    def test_clean_package(self):
        is_valid, issues = validate_item(_pkg(), "packages")
        assert is_valid, issues

    def test_clean_dataset(self):
        item = {
            "name": "COMPAS Dataset",
            "url": "https://example.com",
            "category": "Ethics",
            "description": "Criminal recidivism dataset",
            "tags": ["fairness", "ml"],
        }
        is_valid, issues = validate_item(item, "datasets")
        assert is_valid, issues

    def test_clean_paper(self):
        is_valid, issues = validate_item(_paper(), "papers")
        assert is_valid, issues


# ---------------------------------------------------------------------------
# Missing required fields fail
# ---------------------------------------------------------------------------

class TestMissingRequiredFields:

    def test_missing_name_fails(self):
        item = {"url": "https://example.com", "category": "ML", "type": "package"}
        is_valid, issues = validate_item(item, "packages")
        assert not is_valid
        assert any("missing required" in i for i in issues)

    def test_missing_url_fails(self):
        item = {"name": "Tool", "category": "ML", "type": "package"}
        is_valid, issues = validate_item(item, "packages")
        assert not is_valid
        assert any("missing required" in i for i in issues)

    def test_empty_string_name_fails(self):
        item = {"name": "", "url": "https://example.com", "category": "ML", "type": "package"}
        is_valid, issues = validate_item(item, "packages")
        # Missing required: name
        assert any("missing required" in i for i in issues)


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

class TestUrlValidation:

    def test_invalid_url_no_scheme_flagged(self):
        _, issues = validate_item(_pkg(url="example.com"), "packages")
        assert any("invalid URL" in i for i in issues)

    def test_invalid_url_no_host_flagged(self):
        _, issues = validate_item(_pkg(url="not-a-url"), "packages")
        assert any("invalid URL" in i for i in issues)

    def test_valid_https_url_passes(self):
        is_valid, issues = validate_item(_pkg(url="https://github.com/org/repo"), "packages")
        assert is_valid, issues

    def test_empty_url_missing_required_not_invalid_url(self):
        # Empty url → "missing required" check fires, NOT "invalid URL" check
        item = _pkg()
        del item["url"]
        _, issues = validate_item(item, "packages")
        assert not any("invalid URL" in i for i in issues)


# ---------------------------------------------------------------------------
# Name length validation
# ---------------------------------------------------------------------------

class TestNameLength:

    def test_short_name_flagged(self):
        _, issues = validate_item(_pkg(name="AB"), "packages")
        assert any("name too short" in i for i in issues)

    def test_name_exactly_3_chars_is_ok(self):
        is_valid, issues = validate_item(_pkg(name="ABS"), "packages")
        assert not any("name too" in i for i in issues), issues

    def test_very_long_name_flagged(self):
        _, issues = validate_item(_pkg(name="A" * 201), "packages")
        assert any("name too long" in i for i in issues)

    def test_name_200_chars_is_ok(self):
        _, issues = validate_item(_pkg(name="A" * 200), "packages")
        assert not any("name too" in i for i in issues), issues


# ---------------------------------------------------------------------------
# Tags validation
# ---------------------------------------------------------------------------

class TestTagsValidation:

    def test_non_list_tags_flagged(self):
        _, issues = validate_item(_pkg(tags="causal, ml"), "packages")
        assert any("tags is not a list" in i for i in issues)

    def test_list_tags_no_error(self):
        _, issues = validate_item(_pkg(tags=["causal", "ml"]), "packages")
        assert not any("tags" in i for i in issues), issues


# ---------------------------------------------------------------------------
# Papers-specific validation
# ---------------------------------------------------------------------------

class TestPapersValidation:

    def test_suspiciously_old_year_flagged(self):
        item = {"name": "Old Paper", "url": "https://x.com", "year": 1900}
        _, issues = validate_item(item, "papers")
        assert any("suspicious year" in i for i in issues)

    def test_future_year_flagged(self):
        future = datetime.now().year + 5
        item = {"name": "Future Paper", "url": "https://x.com", "year": future}
        _, issues = validate_item(item, "papers")
        assert any("suspicious year" in i for i in issues)

    def test_current_year_no_year_error(self):
        _, issues = validate_item(_paper(year=datetime.now().year), "papers")
        assert not any("suspicious year" in i for i in issues), issues


# ---------------------------------------------------------------------------
# Community-specific validation
# ---------------------------------------------------------------------------

class TestCommunityValidation:

    def test_workshop_excluded_from_community(self):
        item = _community(name="ML Workshop 2024", type="Workshop")
        is_valid, issues = validate_item(item, "community")
        assert not is_valid
        assert any("excluded" in i for i in issues)

    def test_conference_in_community_no_exclusion(self):
        is_valid, issues = validate_item(_community(), "community")
        assert is_valid, issues
        assert not any("excluded" in i for i in issues)


# ---------------------------------------------------------------------------
# generate_digest
# ---------------------------------------------------------------------------

generate_digest = mod.generate_digest


class TestGenerateDigest:
    def _result(self, **kwargs):
        base = {
            "added": [],
            "rejected": [],
            "staged": [],
            "errors": [],
            "api_usage": {},
            "dry_run": False,
            "run_date": "2026-05-25T09:00:00",
            "duration_seconds": 42,
        }
        base.update(kwargs)
        return base

    def test_returns_html_string(self):
        html = generate_digest(self._result())
        assert isinstance(html, str)
        assert "<html" in html.lower()

    def test_empty_result_no_crash(self):
        html = generate_digest(self._result())
        assert "Weekly Discovery Report" in html

    def test_dry_run_label(self):
        html = generate_digest(self._result(dry_run=True))
        assert "DRY RUN" in html

    def test_added_item_appears(self):
        added = [{"type": "package", "url": "https://pkg.org", "item": {"name": "CoolPkg", "category": "ML"}}]
        html = generate_digest(self._result(added=added))
        assert "CoolPkg" in html

    def test_error_appears(self):
        html = generate_digest(self._result(errors=["Fetch failed for https://x.com"]))
        assert "Fetch failed" in html

    def test_api_usage_included(self):
        api = {"brave": 5, "tavily": 3, "openai_calls": 10, "openai_cost_usd": 0.025}
        html = generate_digest(self._result(api_usage=api))
        assert "5" in html  # brave calls

    def test_empty_added_shows_no_items_message(self):
        html = generate_digest(self._result(added=[]))
        assert "No items added" in html
