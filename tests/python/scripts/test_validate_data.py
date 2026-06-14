"""Tests for the pure validation functions in scripts/validate_data.py.

Focuses on validate_required_fields and find_duplicate_urls — the two
functions that run in CI without network access. Link-checking is excluded
(it requires real HTTP connections).
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.validate_data import validate_required_fields, find_duplicate_urls, check_papers_sync, check_url, check_featured_json, check_experiments_json


# ---------------------------------------------------------------------------
# validate_required_fields
# ---------------------------------------------------------------------------

class TestValidateRequiredFields:

    def test_passes_clean_packages(self):
        files = {
            "packages.json": [
                {"name": "DoubleML", "url": "https://example.com", "category": "ML"},
            ]
        }
        assert validate_required_fields(files) == []

    def test_flags_missing_required_field(self):
        files = {
            "packages.json": [
                {"name": "Pkg", "url": "https://example.com"},  # missing category
            ]
        }
        errors = validate_required_fields(files)
        assert len(errors) == 1
        assert "category" in errors[0]
        assert "Pkg" in errors[0]

    def test_flags_empty_string_as_missing(self):
        files = {
            "packages.json": [
                {"name": "Pkg", "url": "", "category": "ML"},  # empty url
            ]
        }
        errors = validate_required_fields(files)
        assert any("url" in e for e in errors)

    def test_books_require_author_field(self):
        files = {
            "books.json": [
                {"name": "Book", "url": "https://example.com", "category": "ML"},  # no author
            ]
        }
        errors = validate_required_fields(files)
        assert any("author" in e for e in errors)

    def test_unknown_filename_skipped(self):
        files = {
            "unknown_file.json": [{"name": "X"}]
        }
        assert validate_required_fields(files) == []

    def test_multiple_errors_reported(self):
        files = {
            "packages.json": [
                {"name": "A"},              # missing url, category
                {"url": "https://a.com"},   # missing name, category
            ]
        }
        errors = validate_required_fields(files)
        assert len(errors) >= 3  # at least A missing url, A missing category, ?name missing name

    def test_papers_json_nested_structure(self):
        files = {
            "papers.json": {
                "topics": [{
                    "id": "topic1",
                    "subtopics": [{
                        "id": "sub1",
                        "papers": [
                            {"title": "Good Paper", "url": "https://paper.com"},
                            {"title": "Bad Paper"},  # missing url
                        ]
                    }]
                }]
            }
        }
        errors = validate_required_fields(files)
        assert len(errors) == 1
        assert "Bad Paper" in errors[0]
        assert "url" in errors[0]

    def test_papers_json_missing_title(self):
        files = {
            "papers.json": {
                "topics": [{
                    "subtopics": [{
                        "id": "sub1",
                        "papers": [{"url": "https://x.com"}]  # missing title
                    }]
                }]
            }
        }
        errors = validate_required_fields(files)
        assert any("title" in e for e in errors)

    def test_empty_list_no_errors(self):
        files = {"packages.json": []}
        assert validate_required_fields(files) == []

    def test_non_dict_items_skipped(self):
        files = {"packages.json": ["string_item", 42, None]}
        assert validate_required_fields(files) == []


# ---------------------------------------------------------------------------
# find_duplicate_urls
# ---------------------------------------------------------------------------

class TestFindDuplicateUrls:

    def test_no_duplicates_clean(self):
        files = {
            "packages.json": [
                {"name": "Pkg A", "url": "https://a.com", "category": "ML"},
                {"name": "Pkg B", "url": "https://b.com", "category": "ML"},
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_same_url_same_name_same_category_is_duplicate(self):
        files = {
            "packages.json": [
                {"name": "Pkg A", "url": "https://a.com", "category": "ML"},
                {"name": "Pkg A", "url": "https://a.com", "category": "ML"},
            ]
        }
        errors = find_duplicate_urls(files)
        assert len(errors) == 1
        assert "https://a.com" in errors[0]
        assert "Pkg A" in errors[0]

    def test_same_url_different_name_allowed(self):
        """Hub pages (e.g. dunnhumby) have multiple datasets on the same URL."""
        files = {
            "datasets.json": [
                {"name": "Dataset A", "url": "https://hub.com/data", "category": "Commerce"},
                {"name": "Dataset B", "url": "https://hub.com/data", "category": "Commerce"},
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_same_url_different_category_allowed(self):
        files = {
            "packages.json": [
                {"name": "Pkg", "url": "https://a.com", "category": "ML"},
                {"name": "Pkg", "url": "https://a.com", "category": "Stats"},
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_cross_file_duplicates_allowed(self):
        """Same URL can appear in packages.json AND datasets.json."""
        files = {
            "packages.json": [
                {"name": "X", "url": "https://shared.com", "category": "ML"},
            ],
            "datasets.json": [
                {"name": "X", "url": "https://shared.com", "category": "ML"},
            ],
        }
        assert find_duplicate_urls(files) == []

    def test_items_without_url_skipped(self):
        files = {
            "packages.json": [
                {"name": "A"},
                {"name": "A"},  # both have no URL → no duplicate error
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_papers_flat_same_category_is_duplicate(self):
        """Same paper in the exact same 'Topic > Subtopic' category is a true dup."""
        files = {
            "papers_flat.json": [
                {"name": "P", "url": "https://paper.com", "category": "Pricing > Algorithmic Pricing"},
                {"name": "P", "url": "https://paper.com", "category": "Pricing > Algorithmic Pricing"},
            ]
        }
        errors = find_duplicate_urls(files)
        assert len(errors) == 1

    def test_papers_flat_different_subtopics_not_duplicate(self):
        """Same paper cross-listed in different subtopics of the same topic is allowed."""
        files = {
            "papers_flat.json": [
                {"name": "Privacy Paper", "url": "https://paper.com", "category": "Pricing > Algorithmic Pricing"},
                {"name": "Privacy Paper", "url": "https://paper.com", "category": "Pricing > Personalized Pricing"},
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_papers_flat_different_topics_not_duplicate(self):
        files = {
            "papers_flat.json": [
                {"name": "P", "url": "https://paper.com", "category": "Causal Inference > RCTs"},
                {"name": "P", "url": "https://paper.com", "category": "Machine Learning > Deep Learning"},
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_papers_flat_cross_subtopic_uses_category_not_topic(self):
        # Regression: old code used item.get("topic") for papers_flat.json —
        # papers with the same "topic" string but different "category" subtopics
        # were incorrectly flagged as duplicates. Must use "category" instead.
        files = {
            "papers_flat.json": [
                {
                    "name": "Privacy Paper", "url": "https://paper.com",
                    "topic": "Pricing",
                    "category": "Pricing > Algorithmic Pricing",
                },
                {
                    "name": "Privacy Paper", "url": "https://paper.com",
                    "topic": "Pricing",  # same topic — old code would flag this
                    "category": "Pricing > Personalized Pricing",  # different subtopic
                },
            ]
        }
        assert find_duplicate_urls(files) == []

    def test_empty_files_no_errors(self):
        assert find_duplicate_urls({"packages.json": []}) == []


# ---------------------------------------------------------------------------
# check_papers_sync
# ---------------------------------------------------------------------------

def _papers_nested(papers_per_subtopic: list) -> dict:
    """Build a minimal papers.json structure."""
    return {
        "topics": [{
            "name": "Topic A",
            "subtopics": [{
                "name": "Sub A",
                "papers": [{"title": f"P{i}", "url": f"https://p{i}.com"} for i in range(papers_per_subtopic[0])]
            }]
        }]
    }


class TestCheckPapersSync:

    def test_equal_counts_no_error(self):
        files = {
            "papers.json": _papers_nested([2]),
            "papers_flat.json": [{"title": "P0"}, {"title": "P1"}],
        }
        assert check_papers_sync(files) == []

    def test_flat_has_fewer_papers(self):
        files = {
            "papers.json": _papers_nested([3]),
            "papers_flat.json": [{"title": "P0"}, {"title": "P1"}],
        }
        errors = check_papers_sync(files)
        assert len(errors) == 1
        assert "desync" in errors[0]
        assert "3" in errors[0] and "2" in errors[0]

    def test_flat_has_more_papers(self):
        files = {
            "papers.json": _papers_nested([1]),
            "papers_flat.json": [{"title": "P0"}, {"title": "P1"}, {"title": "P2"}],
        }
        errors = check_papers_sync(files)
        assert len(errors) == 1
        assert "1" in errors[0] and "3" in errors[0]

    def test_missing_papers_json_skipped(self):
        files = {"papers_flat.json": [{"title": "X"}]}
        assert check_papers_sync(files) == []

    def test_missing_papers_flat_skipped(self):
        files = {"papers.json": _papers_nested([1])}
        assert check_papers_sync(files) == []

    def test_empty_nested_empty_flat_is_sync(self):
        files = {
            "papers.json": {"topics": []},
            "papers_flat.json": [],
        }
        assert check_papers_sync(files) == []

    def test_error_message_includes_flatten_command(self):
        files = {
            "papers.json": _papers_nested([2]),
            "papers_flat.json": [],
        }
        errors = check_papers_sync(files)
        assert "flatten_papers.py" in errors[0]


# ---------------------------------------------------------------------------
# check_url — only test the skip-domain fast-path (no network calls)
# ---------------------------------------------------------------------------

class TestCheckUrlSkipDomains:
    """Only exercises the SKIP_DOMAINS early-return path — no network."""

    def test_linkedin_skipped(self):
        url, err = check_url("https://linkedin.com/in/somebody")
        assert err is None

    def test_twitter_skipped(self):
        url, err = check_url("https://twitter.com/user/post")
        assert err is None

    def test_x_com_skipped(self):
        url, err = check_url("https://x.com/user/post")
        assert err is None

    def test_ssrn_skipped(self):
        url, err = check_url("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=123")
        assert err is None

    def test_jstor_skipped(self):
        url, err = check_url("https://jstor.org/stable/12345")
        assert err is None

    def test_returns_url_unchanged(self):
        url = "https://linkedin.com/in/testuser"
        returned_url, _ = check_url(url)
        assert returned_url == url

    def test_returns_tuple_of_two(self):
        result = check_url("https://linkedin.com/foo")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# check_url — mocked network paths (HEAD/GET fallback, errors)
# ---------------------------------------------------------------------------

class TestCheckUrlNetworkPaths:
    """Tests for check_url error handling using mocked requests.

    Design note: requests may be replaced by a MagicMock stub in sys.modules
    by test_fetch_logo_fallbacks_helpers.py (which runs earlier alphabetically).
    To stay isolation-safe we:
      (a) patch scripts.validate_data.requests.head/get directly so status_code
          comparisons work (using SimpleNamespace, not MagicMock),
      (b) use inline exception subclasses for the error-path tests and also
          patch validate_data's requests.exceptions namespace so the except
          clauses catch the right type.
    """

    def _resp(self, status_code):
        return SimpleNamespace(status_code=status_code, close=lambda: None)

    def test_head_200_returns_no_error(self):
        with patch("scripts.validate_data.requests.head", return_value=self._resp(200)):
            url, err = check_url("https://example.com/page")
        assert err is None

    def test_head_400_falls_back_to_get_200(self):
        with patch("scripts.validate_data.requests.head", return_value=self._resp(404)), \
             patch("scripts.validate_data.requests.get", return_value=self._resp(200)):
            url, err = check_url("https://example.com/page")
        assert err is None

    def test_head_400_get_400_returns_http_error(self):
        with patch("scripts.validate_data.requests.head", return_value=self._resp(404)), \
             patch("scripts.validate_data.requests.get", return_value=self._resp(404)):
            url, err = check_url("https://example.com/gone")
        assert err is not None
        assert "HTTP 404" in err

    def _patch_exc(self, timeout_cls, ssl_cls, conn_cls):
        """Return a patch for validate_data's requests.exceptions namespace."""
        exc_ns = SimpleNamespace(Timeout=timeout_cls, SSLError=ssl_cls, ConnectionError=conn_cls)
        return patch("scripts.validate_data.requests.exceptions", exc_ns)

    def test_timeout_returns_timeout_message(self):
        class FakeTimeout(Exception): pass
        class FakeSSL(Exception): pass
        class FakeConn(Exception): pass
        with self._patch_exc(FakeTimeout, FakeSSL, FakeConn), \
             patch("scripts.validate_data.requests.head", side_effect=FakeTimeout()):
            _, err = check_url("https://example.com/slow")
        assert err == "Timeout"

    def test_ssl_error_returns_ssl_message(self):
        class FakeTimeout(Exception): pass
        class FakeSSL(Exception): pass
        class FakeConn(Exception): pass
        with self._patch_exc(FakeTimeout, FakeSSL, FakeConn), \
             patch("scripts.validate_data.requests.head", side_effect=FakeSSL("cert error")):
            _, err = check_url("https://example.com/ssl")
        assert err is not None
        assert "SSL" in err

    def test_connection_error_returns_connection_message(self):
        class FakeTimeout(Exception): pass
        class FakeSSL(Exception): pass
        class FakeConn(Exception): pass
        with self._patch_exc(FakeTimeout, FakeSSL, FakeConn), \
             patch("scripts.validate_data.requests.head", side_effect=FakeConn("refused")):
            _, err = check_url("https://example.com/offline")
        assert err is not None
        assert "Connection" in err

    def test_generic_exception_returns_error_message(self):
        class FakeTimeout(Exception): pass
        class FakeSSL(Exception): pass
        class FakeConn(Exception): pass
        with self._patch_exc(FakeTimeout, FakeSSL, FakeConn), \
             patch("scripts.validate_data.requests.head", side_effect=RuntimeError("unexpected")):
            _, err = check_url("https://example.com/weird")
        assert err is not None
        assert "Error" in err

    def test_returned_url_matches_input(self):
        with patch("scripts.validate_data.requests.head", return_value=self._resp(200)):
            input_url = "https://example.com/test"
            returned_url, _ = check_url(input_url)
        assert returned_url == input_url
