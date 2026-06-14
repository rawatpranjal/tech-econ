"""Bullshit tests for download image script pure helpers.

Covers:
  - download_conference_images.py: get_domain
  - download_dataset_images.py: slugify, get_extension, get_github_avatar, get_favicon_url
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: MagicMock()
    sys.modules[name] = m
    return m


for _dep in ["requests", "bs4", "beautifulsoup4"]:
    if _dep not in sys.modules:
        _stub(_dep)

# Stub bs4.BeautifulSoup explicitly
if "bs4" not in sys.modules or not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    bs4 = types.ModuleType("bs4")
    bs4.BeautifulSoup = MagicMock()
    sys.modules["bs4"] = bs4


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_conf = _load("download_conference_images", _REPO_ROOT / "scripts" / "download_conference_images.py")
_dataset = _load("download_dataset_images", _REPO_ROOT / "scripts" / "download_dataset_images.py")

get_domain = _conf.get_domain
slugify = _dataset.slugify
get_extension = _dataset.get_extension
get_github_avatar = _dataset.get_github_avatar
get_favicon_url = _dataset.get_favicon_url


# ──────────────────────────────────────────────
# get_domain (download_conference_images)
# ──────────────────────────────────────────────

class TestGetDomain:
    def test_simple(self):
        assert get_domain("https://nber.org/conference") == "nber.org"

    def test_www_preserved(self):
        assert get_domain("https://www.aeaweb.org/") == "www.aeaweb.org"

    def test_path_stripped(self):
        assert get_domain("https://icml.cc/Conferences/2024/CallForPapers") == "icml.cc"

    def test_empty_url_returns_empty(self):
        assert get_domain("") == ""

    def test_no_scheme_returns_empty(self):
        # urlparse without scheme gives empty netloc
        result = get_domain("nber.org/something")
        assert result == ""


# ──────────────────────────────────────────────
# slugify (download_dataset_images)
# ──────────────────────────────────────────────

class TestDatasetSlugify:
    def test_basic(self):
        assert slugify("My Dataset") == "my-dataset"

    def test_special_chars_removed(self):
        result = slugify("MNIST (60K)")
        assert "(" not in result
        assert ")" not in result

    def test_max_80_chars(self):
        long_name = "a" * 100
        assert len(slugify(long_name)) <= 80

    def test_consecutive_hyphens_collapsed(self):
        result = slugify("A  B  C")
        assert "--" not in result

    def test_no_leading_trailing_hyphens(self):
        result = slugify("!test!")
        assert not result.startswith("-")
        assert not result.endswith("-")


# ──────────────────────────────────────────────
# get_extension (download_dataset_images)
# ──────────────────────────────────────────────

class TestDatasetGetExtension:
    def test_png(self):
        assert get_extension("https://example.com/img.png") == ".png"

    def test_webp(self):
        assert get_extension("https://example.com/img.webp") == ".webp"

    def test_content_type_png(self):
        assert get_extension("https://example.com/img", "image/png") == ".png"

    def test_content_type_webp(self):
        assert get_extension("https://example.com/img", "image/webp") == ".webp"

    def test_default_jpg(self):
        assert get_extension("https://example.com/noext") == ".jpg"

    def test_svg(self):
        assert get_extension("https://example.com/logo.svg") == ".svg"


# ──────────────────────────────────────────────
# get_github_avatar (download_dataset_images)
# ──────────────────────────────────────────────

class TestGetGithubAvatar:
    def test_repo_url(self):
        url = get_github_avatar("https://github.com/openai/whisper")
        assert "openai" in url
        assert "github.com" in url

    def test_org_url(self):
        url = get_github_avatar("https://github.com/huggingface")
        assert "huggingface" in url

    def test_none_input_returns_none(self):
        assert get_github_avatar(None) is None

    def test_empty_string_returns_none(self):
        assert get_github_avatar("") is None

    def test_non_github_url_returns_none(self):
        assert get_github_avatar("https://gitlab.com/owner/repo") is None

    def test_avatar_url_format(self):
        url = get_github_avatar("https://github.com/scikit-learn/scikit-learn")
        assert url.endswith(".png?size=256")


# ──────────────────────────────────────────────
# get_favicon_url (download_dataset_images)
# ──────────────────────────────────────────────

class TestGetFaviconUrl:
    def test_contains_domain(self):
        url = get_favicon_url("https://huggingface.co/datasets/squad")
        assert "huggingface.co" in url

    def test_uses_google_service(self):
        url = get_favicon_url("https://example.com")
        assert "google.com" in url

    def test_has_size_param(self):
        url = get_favicon_url("https://example.com")
        assert "sz=128" in url or "size=128" in url
