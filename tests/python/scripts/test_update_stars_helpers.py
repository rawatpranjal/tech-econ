"""Bullshit tests for update_stars.py extract_repo_info.

Covers: GitHub URL parsing — owner/repo extraction, .git stripping,
non-GitHub URLs, empty input.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "update_stars.py"

# Stub requests so the module doesn't need network at import
if "requests" not in sys.modules:
    _r = types.ModuleType("requests")
    _r.get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    sys.modules["requests"] = _r

_spec = importlib.util.spec_from_file_location("update_stars", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["update_stars"] = mod
_spec.loader.exec_module(mod)

extract_repo_info = mod.extract_repo_info


class TestExtractRepoInfo:
    def test_basic_github_url(self):
        result = extract_repo_info("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_http_url(self):
        result = extract_repo_info("http://github.com/user/project")
        assert result == ("user", "project")

    def test_dot_git_stripped(self):
        result = extract_repo_info("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_trailing_path_ignored(self):
        result = extract_repo_info("https://github.com/owner/repo/tree/main/src")
        assert result is not None
        assert result[0] == "owner"
        assert result[1] == "repo"

    def test_non_github_url_returns_none(self):
        assert extract_repo_info("https://gitlab.com/owner/repo") is None

    def test_empty_string_returns_none(self):
        assert extract_repo_info("") is None

    def test_none_returns_none(self):
        assert extract_repo_info(None) is None

    def test_arxiv_url_returns_none(self):
        assert extract_repo_info("https://arxiv.org/abs/1234.5678") is None

    def test_org_name_preserved(self):
        result = extract_repo_info("https://github.com/DoubleML/doubleml-for-py")
        assert result == ("DoubleML", "doubleml-for-py")

    def test_hyphenated_repo_name(self):
        result = extract_repo_info("https://github.com/microsoft/LightGBM")
        assert result == ("microsoft", "LightGBM")

    def test_repo_ending_in_t_not_stripped(self):
        # Regression: str.rstrip(".git") strips individual chars {'.','g','i','t'}
        # from the end — "econometrist" → "econometr". re.sub("\.git$", ...) is safe.
        result = extract_repo_info("https://github.com/user/econometrist")
        assert result == ("user", "econometrist")

    def test_repo_ending_in_g_not_stripped(self):
        # Same regression: name ending in 'g' must not be truncated
        result = extract_repo_info("https://github.com/user/causal-dag")
        assert result == ("user", "causal-dag")

    def test_repo_ending_in_dot_git_stripped_correctly(self):
        # Only the literal ".git" suffix should be removed
        result = extract_repo_info("https://github.com/user/my-toolkit.git")
        assert result == ("user", "my-toolkit")
