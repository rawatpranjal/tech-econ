"""Bullshit tests for scripts/fetch_logo_fallbacks.py pure helpers.

Only covers get_root_domain — it's the only pure function.
download_logo and process_file make network / filesystem calls; skipped.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_logo_fallbacks.py"

# Stub `requests` so the module loads without it being installed in CI
_requests_stub = MagicMock()
sys.modules.setdefault("requests", _requests_stub)

_spec = importlib.util.spec_from_file_location("fetch_logo_fallbacks", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

get_root_domain = mod.get_root_domain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetRootDomain:
    def test_simple_domain(self):
        assert get_root_domain("https://example.com") == "example.com"

    def test_www_prefix_stripped(self):
        assert get_root_domain("https://www.example.com") == "example.com"

    def test_subdomain_stripped(self):
        assert get_root_domain("https://eng.uber.com") == "uber.com"

    def test_blog_subdomain_stripped(self):
        assert get_root_domain("https://blog.openai.com") == "openai.com"

    def test_co_uk_preserved(self):
        # parts[-2] == "co" is in the special-TLD list → keep 3 parts
        assert get_root_domain("https://sub.example.co.uk") == "example.co.uk"

    def test_dot_org(self):
        assert get_root_domain("https://example.org") == "example.org"

    def test_dot_edu_with_subdomain(self):
        assert get_root_domain("https://dept.mit.edu") == "mit.edu"

    def test_dot_net(self):
        assert get_root_domain("https://cdn.example.net") == "example.net"

    def test_none_input_returns_none(self):
        assert get_root_domain(None) is None

    def test_lowercase_output(self):
        assert get_root_domain("https://ENG.EXAMPLE.COM") == "example.com"

    def test_path_and_query_ignored(self):
        assert get_root_domain("https://blog.stripe.com/path?foo=bar") == "stripe.com"

    def test_www_plus_subdomain_stripped(self):
        # www is stripped first, then subdomain logic applies
        assert get_root_domain("https://www.blog.example.com") == "example.com"
