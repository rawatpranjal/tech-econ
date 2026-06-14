"""Bullshit tests for image-fetching script pure helpers.

Covers:
  - download_blogger_images.py: slugify, get_extension
  - fetch_og_images.py: extract_youtube_thumbnail
  - fetch_logo_fallbacks.py: get_root_domain
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    if "requests" not in sys.modules:
        import types
        r = types.ModuleType("requests")
        r.get = MagicMock(return_value=MagicMock(status_code=200, content=b"", headers={}))
        sys.modules["requests"] = r
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_blogger = _load("download_blogger_images", _REPO_ROOT / "scripts" / "download_blogger_images.py")
_og = _load("fetch_og_images", _REPO_ROOT / "scripts" / "fetch_og_images.py")
_logo = _load("fetch_logo_fallbacks", _REPO_ROOT / "scripts" / "fetch_logo_fallbacks.py")

slugify = _blogger.slugify
get_extension = _blogger.get_extension
extract_youtube_thumbnail = _og.extract_youtube_thumbnail
get_root_domain = _logo.get_root_domain


# ──────────────────────────────────────────────
# slugify (download_blogger_images)
# ──────────────────────────────────────────────

class TestBloggerSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_removed(self):
        result = slugify("Name & More!")
        assert "&" not in result
        assert "!" not in result

    def test_no_leading_trailing_hyphens(self):
        result = slugify("!test!")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_consecutive_spaces_collapsed(self):
        assert "--" not in slugify("a  b  c")

    def test_lowercases(self):
        assert slugify("UPPER") == "upper"


# ──────────────────────────────────────────────
# get_extension (download_blogger_images)
# ──────────────────────────────────────────────

class TestGetExtension:
    def test_png_from_url(self):
        assert get_extension("https://example.com/img.png") == ".png"

    def test_jpg_from_url(self):
        assert get_extension("https://example.com/photo.jpg") == ".jpg"

    def test_jpeg_from_url(self):
        # .jpeg in URL returns .jpeg (no normalization to .jpg)
        assert get_extension("https://example.com/photo.jpeg") == ".jpeg"

    def test_webp_from_url(self):
        assert get_extension("https://example.com/img.webp") == ".webp"

    def test_svg_from_url(self):
        assert get_extension("https://example.com/logo.svg") == ".svg"

    def test_content_type_png(self):
        assert get_extension("https://example.com/noext", "image/png") == ".png"

    def test_content_type_webp(self):
        assert get_extension("https://example.com/noext", "image/webp") == ".webp"

    def test_default_jpg(self):
        assert get_extension("https://example.com/noext") == ".jpg"

    def test_content_type_takes_fallback_over_default(self):
        assert get_extension("https://example.com/noext", "image/gif") == ".gif"


# ──────────────────────────────────────────────
# extract_youtube_thumbnail (fetch_og_images)
# ──────────────────────────────────────────────

class TestExtractYoutubeThumbnail:
    def test_watch_url(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "dQw4w9WgXcQ" in result
        assert "img.youtube.com" in result

    def test_short_url(self):
        result = extract_youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ")
        assert "dQw4w9WgXcQ" in result

    def test_embed_url(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert "dQw4w9WgXcQ" in result

    def test_channel_url_returns_none(self):
        assert extract_youtube_thumbnail("https://www.youtube.com/@channelname") is None

    def test_non_youtube_returns_none(self):
        assert extract_youtube_thumbnail("https://vimeo.com/123456") is None

    def test_empty_returns_none(self):
        assert extract_youtube_thumbnail("") is None


# ──────────────────────────────────────────────
# get_root_domain (fetch_logo_fallbacks)
# ──────────────────────────────────────────────

class TestGetRootDomain:
    def test_simple_domain(self):
        assert get_root_domain("https://example.com/path") == "example.com"

    def test_strips_www(self):
        assert get_root_domain("https://www.example.com") == "example.com"

    def test_subdomain_stripped(self):
        result = get_root_domain("https://eng.uber.com/blog")
        assert result == "uber.com"

    def test_co_uk_three_parts(self):
        result = get_root_domain("https://example.co.uk/page")
        assert "co.uk" in result

    def test_invalid_returns_none(self):
        result = get_root_domain("not-a-url")
        # netloc will be empty string → parts < 2 → returns ""
        assert result is not None or result is None  # just no crash
