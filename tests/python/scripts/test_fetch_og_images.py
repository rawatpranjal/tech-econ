"""Tests for extract_youtube_thumbnail in scripts/fetch_og_images.py.

requests and beautifulsoup4 are stubbed before load so no network calls happen.
Only tests the pure regex helper.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# stub requests and bs4 so the module doesn't sys.exit(1) if not installed
sys.modules.setdefault("requests", MagicMock())
sys.modules.setdefault("bs4", MagicMock())
sys.modules.setdefault("bs4.BeautifulSoup", MagicMock())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "fetch_og_images_mod", _REPO_ROOT / "scripts" / "fetch_og_images.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_og_images_mod"] = mod
_spec.loader.exec_module(mod)

extract_youtube_thumbnail = mod.extract_youtube_thumbnail


# ---------------------------------------------------------------------------
# extract_youtube_thumbnail
# ---------------------------------------------------------------------------
class TestExtractYoutubeThumbnail:
    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = extract_youtube_thumbnail(url)
        assert result == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"

    def test_short_youtu_be_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        result = extract_youtube_thumbnail(url)
        assert result == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        result = extract_youtube_thumbnail(url)
        assert result == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"

    def test_video_id_in_thumbnail_url(self):
        # Verify the video_id is correctly extracted and placed in the URL
        url = "https://youtube.com/watch?v=abc123defGH"
        result = extract_youtube_thumbnail(url)
        assert "abc123defGH" in result

    def test_channel_url_c_returns_none(self):
        assert extract_youtube_thumbnail("https://www.youtube.com/c/SomeChannel") is None

    def test_channel_url_at_returns_none(self):
        assert extract_youtube_thumbnail("https://www.youtube.com/@SomeUser") is None

    def test_channel_url_channel_returns_none(self):
        assert extract_youtube_thumbnail("https://www.youtube.com/channel/UC12345") is None

    def test_non_youtube_url_returns_none(self):
        assert extract_youtube_thumbnail("https://vimeo.com/123456789") is None

    def test_empty_string_returns_none(self):
        assert extract_youtube_thumbnail("") is None

    def test_watch_url_with_extra_params(self):
        # ?v= param may have other query params after it
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s"
        result = extract_youtube_thumbnail(url)
        assert "dQw4w9WgXcQ" in result

    def test_thumbnail_url_format(self):
        url = "https://youtube.com/watch?v=ABCDEFGHIJK"
        result = extract_youtube_thumbnail(url)
        assert result.startswith("https://img.youtube.com/vi/")
        assert result.endswith("/hqdefault.jpg")
