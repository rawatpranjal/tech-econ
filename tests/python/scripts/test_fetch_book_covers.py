"""Tests for scripts/fetch_book_covers.py.

All network calls are mocked — no real HTTP in CI.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Stub requests before the module is loaded so the import doesn't fail in CI.
sys.modules.setdefault("requests", MagicMock())

# ---------------------------------------------------------------------------
# Load the module without executing main()
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_book_covers.py"

_spec = importlib.util.spec_from_file_location("fetch_book_covers", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_book_covers"] = mod
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200, content: bytes = b"") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


def _gb_api_response(thumbnail: str | None) -> MagicMock:
    """Build a fake Google Books API response."""
    image_links = {"thumbnail": thumbnail} if thumbnail else {}
    payload = {
        "items": [
            {"volumeInfo": {"imageLinks": image_links}}
        ]
    }
    resp = _make_response(200, json.dumps(payload).encode())
    resp.json = MagicMock(return_value=payload)
    return resp


def _gb_empty_response() -> MagicMock:
    payload = {"items": []}
    resp = _make_response(200, json.dumps(payload).encode())
    resp.json = MagicMock(return_value=payload)
    return resp


# ---------------------------------------------------------------------------
# 1. build_ol_url format check
# ---------------------------------------------------------------------------

class TestBuildOlUrl:
    def test_clean_isbn(self):
        url = mod.build_ol_url("9780521536721")
        assert url == "https://covers.openlibrary.org/b/isbn/9780521536721-M.jpg?default=false"

    def test_hyphenated_isbn_is_cleaned(self):
        url = mod.build_ol_url("978-0521536721")
        assert "978-" not in url
        assert "9780521536721" in url


# ---------------------------------------------------------------------------
# 2. slugify_isbn
# ---------------------------------------------------------------------------

class TestSlugifyIsbn:
    def test_strips_hyphens(self):
        assert mod.slugify_isbn("978-0-521-53672-1") == "9780521536721"

    def test_strips_spaces(self):
        assert mod.slugify_isbn("978 0521 536721") == "9780521536721"

    def test_already_clean(self):
        assert mod.slugify_isbn("0691120358") == "0691120358"


# ---------------------------------------------------------------------------
# 3. is_placeholder
# ---------------------------------------------------------------------------

class TestIsPlaceholder:
    def test_small_body_is_placeholder(self):
        assert mod.is_placeholder(b"x" * 100) is True

    def test_body_at_threshold_is_not_placeholder(self):
        # exactly 2048 bytes → not a placeholder (< 2048 required)
        assert mod.is_placeholder(b"x" * 2048) is False

    def test_body_just_below_threshold_is_placeholder(self):
        assert mod.is_placeholder(b"x" * 2047) is True

    def test_large_body_is_not_placeholder(self):
        assert mod.is_placeholder(b"x" * 50_000) is False


# ---------------------------------------------------------------------------
# 4. build_gb_thumbnail_url
# ---------------------------------------------------------------------------

class TestBuildGbThumbnailUrl:
    def test_strips_zoom_param(self):
        vi = {"imageLinks": {"thumbnail": "http://books.google.com/img?id=abc&zoom=1"}}
        result = mod.build_gb_thumbnail_url(vi)
        assert result is not None
        assert "zoom" not in result

    def test_no_image_links_returns_none(self):
        assert mod.build_gb_thumbnail_url({}) is None

    def test_no_thumbnail_key_returns_none(self):
        assert mod.build_gb_thumbnail_url({"imageLinks": {}}) is None


# ---------------------------------------------------------------------------
# 5. OL happy path → image saved
# ---------------------------------------------------------------------------

class TestOlHappyPath:
    def test_valid_ol_response_saves_image(self, tmp_path):
        """200 + >2048 bytes from OL → file written, image_url set."""
        big_image = b"FAKE_JPEG" * 1000  # >> 2048

        book = {"name": "Test Book", "isbn": "9780521536721", "image_url": ""}
        books = [book]

        # Patch DATA_PATH, OUTPUT_DIR, and requests.get
        with patch.object(mod, "DATA_PATH", tmp_path / "books.json"), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get") as mock_get, \
             patch("fetch_book_covers.time.sleep"):

            # OL returns a big image
            mock_get.return_value = _make_response(200, big_image)

            # Write a minimal books.json
            (tmp_path / "books.json").write_text(json.dumps(books))

            mod.main([])

        updated = json.loads((tmp_path / "books.json").read_text())
        assert updated[0]["image_url"] == "/images/books/9780521536721.jpg"
        assert (tmp_path / "images" / "9780521536721.jpg").exists()


# ---------------------------------------------------------------------------
# 6. OL placeholder → falls through to Google Books
# ---------------------------------------------------------------------------

class TestOlPlaceholderFallsToGb:
    def test_ol_small_body_triggers_gb_fallback(self, tmp_path):
        """OL returns <2048 bytes → script tries Google Books next."""
        big_image = b"REAL_COVER" * 1000

        book = {"name": "Placeholder Book", "isbn": "0691120358", "image_url": ""}
        books = [book]

        thumbnail_url = "http://books.google.com/cover?id=x&zoom=1"
        gb_api = _gb_api_response(thumbnail_url)
        gb_img = _make_response(200, big_image)

        call_counter = [0]

        def fake_get(url, **kwargs):
            call_counter[0] += 1
            if "openlibrary" in url:
                return _make_response(200, b"tiny")  # placeholder
            if "googleapis.com" in url:
                return gb_api
            # thumbnail download
            return gb_img

        with patch.object(mod, "DATA_PATH", tmp_path / "books.json"), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get", side_effect=fake_get), \
             patch("fetch_book_covers.time.sleep"):

            (tmp_path / "books.json").write_text(json.dumps(books))
            mod.main([])

        updated = json.loads((tmp_path / "books.json").read_text())
        assert updated[0]["image_url"] == "/images/books/0691120358.jpg"


# ---------------------------------------------------------------------------
# 7. OL 404 → falls through to Google Books
# ---------------------------------------------------------------------------

class TestOl404FallsToGb:
    def test_ol_404_triggers_gb_fallback(self, tmp_path):
        big_image = b"COVER_DATA" * 1000
        book = {"name": "404 Book", "isbn": "0553418815", "image_url": ""}
        books = [book]

        thumbnail_url = "http://books.google.com/cover?id=y"
        gb_api = _gb_api_response(thumbnail_url)
        gb_img = _make_response(200, big_image)

        def fake_get(url, **kwargs):
            if "openlibrary" in url:
                return _make_response(404, b"")
            if "googleapis.com" in url:
                return gb_api
            return gb_img

        with patch.object(mod, "DATA_PATH", tmp_path / "books.json"), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get", side_effect=fake_get), \
             patch("fetch_book_covers.time.sleep"):

            (tmp_path / "books.json").write_text(json.dumps(books))
            mod.main([])

        updated = json.loads((tmp_path / "books.json").read_text())
        assert updated[0]["image_url"] == "/images/books/0553418815.jpg"


# ---------------------------------------------------------------------------
# 8. GB has thumbnail → image saved
# ---------------------------------------------------------------------------

class TestGbThumbnailFound:
    def test_gb_thumbnail_saved(self, tmp_path):
        big_image = b"GB_IMAGE_DATA" * 500
        book = {"name": "GB Book", "isbn": "0470660929", "image_url": ""}
        books = [book]

        thumbnail_url = "http://books.google.com/cover?id=z&zoom=1"
        gb_api = _gb_api_response(thumbnail_url)
        gb_img = _make_response(200, big_image)

        def fake_get(url, **kwargs):
            if "openlibrary" in url:
                return _make_response(404, b"")
            if "googleapis.com" in url:
                return gb_api
            return gb_img

        with patch.object(mod, "DATA_PATH", tmp_path / "books.json"), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get", side_effect=fake_get), \
             patch("fetch_book_covers.time.sleep"):

            (tmp_path / "books.json").write_text(json.dumps(books))
            mod.main([])

        updated = json.loads((tmp_path / "books.json").read_text())
        assert updated[0]["image_url"].startswith("/images/books/")
        assert (tmp_path / "images" / "0470660929.jpg").exists()


# ---------------------------------------------------------------------------
# 9. GB empty → image_url stays ""
# ---------------------------------------------------------------------------

class TestGbEmpty:
    def test_no_gb_results_leaves_image_url_empty(self, tmp_path):
        book = {"name": "Obscure Book", "isbn": "1234567890", "image_url": ""}
        books = [book]

        def fake_get(url, **kwargs):
            if "openlibrary" in url:
                return _make_response(404, b"")
            if "googleapis.com" in url:
                return _gb_empty_response()
            return _make_response(404, b"")

        with patch.object(mod, "DATA_PATH", tmp_path / "books.json"), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get", side_effect=fake_get), \
             patch("fetch_book_covers.time.sleep"):

            (tmp_path / "books.json").write_text(json.dumps(books))
            mod.main([])

        updated = json.loads((tmp_path / "books.json").read_text())
        assert updated[0]["image_url"] == ""


# ---------------------------------------------------------------------------
# 10. dry-run produces no writes
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_makes_no_network_calls_and_no_writes(self, tmp_path):
        books = [{"name": "Book A", "isbn": "9780521536721", "image_url": ""}]
        books_path = tmp_path / "books.json"
        books_path.write_text(json.dumps(books))

        original_mtime = books_path.stat().st_mtime

        with patch.object(mod, "DATA_PATH", books_path), \
             patch.object(mod, "OUTPUT_DIR", tmp_path / "images"), \
             patch("fetch_book_covers.requests.get") as mock_get:

            result = mod.main(["--dry-run"])

        # No network calls
        mock_get.assert_not_called()
        # books.json unchanged
        assert books_path.stat().st_mtime == original_mtime
        # Exit 0
        assert result == 0
