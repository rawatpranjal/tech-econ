"""Bullshit tests for fetch_logo_fallbacks.py pure helpers.

Covers: get_root_domain — URL parsing and subdomain stripping.
Network-calling functions (download_logo, process_file) are skipped.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_logo_fallbacks.py"

# Stub requests so the module loads without network dep
if "requests" not in sys.modules:
    _r = types.ModuleType("requests")
    _r.__getattr__ = lambda attr: MagicMock()
    sys.modules["requests"] = _r

_spec = importlib.util.spec_from_file_location("fetch_logo_fallbacks", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_logo_fallbacks"] = mod
_spec.loader.exec_module(mod)

get_root_domain = mod.get_root_domain


# ──────────────────────────────────────────────
# get_root_domain
# ──────────────────────────────────────────────

class TestGetRootDomain:
    def test_simple_domain(self):
        assert get_root_domain("https://github.com/foo") == "github.com"

    def test_www_stripped(self):
        assert get_root_domain("https://www.github.com/foo") == "github.com"

    def test_subdomain_stripped(self):
        result = get_root_domain("https://eng.uber.com/blog/post")
        assert result == "uber.com"

    def test_co_uk_tld(self):
        # Special 3-part TLD: co.uk
        result = get_root_domain("https://bbc.co.uk/news")
        assert "bbc" in result

    def test_http_url(self):
        result = get_root_domain("http://nber.org/papers/w1234")
        assert result == "nber.org"

    def test_path_stripped(self):
        result = get_root_domain("https://econometrics.org/paper/foo/bar")
        assert "/" not in result

    def test_empty_string_returns_none_or_empty(self):
        result = get_root_domain("")
        assert not result  # None or empty string

    def test_none_or_invalid_returns_none(self):
        result = get_root_domain(None)
        assert not result

    def test_no_subdomain_unchanged(self):
        result = get_root_domain("https://arxiv.org/abs/1234")
        assert result == "arxiv.org"

    def test_lowercased(self):
        result = get_root_domain("https://GitHub.COM/foo")
        assert result == result.lower()
