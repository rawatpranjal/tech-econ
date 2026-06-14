"""Bullshit tests for fetch_og_images.py pure helpers.

Covers: extract_youtube_thumbnail — pure URL parsing, no network.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_og_images.py"

# Stub requests and bs4
for _name in ["requests", "bs4", "bs4.BeautifulSoup"]:
    if _name not in sys.modules:
        _s = types.ModuleType(_name)
        _s.__getattr__ = lambda attr: MagicMock()
        sys.modules[_name] = _s

_spec = importlib.util.spec_from_file_location("fetch_og_images", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_og_images"] = mod
_spec.loader.exec_module(mod)

extract_youtube_thumbnail = mod.extract_youtube_thumbnail


# ──────────────────────────────────────────────
# extract_youtube_thumbnail
# ──────────────────────────────────────────────

class TestExtractYoutubeThumbnail:
    def test_standard_watch_url(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result is not None
        assert "dQw4w9WgXcQ" in result

    def test_short_youtu_be_url(self):
        result = extract_youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ")
        assert result is not None
        assert "dQw4w9WgXcQ" in result

    def test_embed_url(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert result is not None
        assert "dQw4w9WgXcQ" in result

    def test_thumbnail_url_format(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/watch?v=abc1234DEFG")
        assert result is not None
        assert "img.youtube.com" in result
        assert "abc1234DEFG" in result

    def test_channel_url_returns_none(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/c/some-channel")
        assert result is None

    def test_at_channel_returns_none(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/@SomeChannel")
        assert result is None

    def test_channel_id_url_returns_none(self):
        result = extract_youtube_thumbnail("https://www.youtube.com/channel/UCxxxxx")
        assert result is None

    def test_non_youtube_returns_none(self):
        result = extract_youtube_thumbnail("https://vimeo.com/12345678")
        assert result is None

    def test_empty_string_returns_none(self):
        result = extract_youtube_thumbnail("")
        assert result is None

    def test_arbitrary_url_returns_none(self):
        result = extract_youtube_thumbnail("https://example.com/video")
        assert result is None

    def test_video_id_exactly_11_chars(self):
        vid = "a" * 11
        result = extract_youtube_thumbnail(f"https://www.youtube.com/watch?v={vid}")
        assert result is not None
        assert vid in result

    def test_returns_string_url(self):
        result = extract_youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ")
        assert isinstance(result, str)
        assert result.startswith("https://")
