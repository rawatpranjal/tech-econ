"""Tests for extract_repo_info in scripts/update_stars.py.

extract_repo_info is a pure function — no network, no filesystem.
We stub ``requests`` before loading the module so the top-level import
does not require the real package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub requests before the module is loaded so the import doesn't fail.
sys.modules.setdefault("requests", MagicMock())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "update_stars.py"
_spec = importlib.util.spec_from_file_location("update_stars_mod", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["update_stars_mod"] = mod
_spec.loader.exec_module(mod)

extract_repo_info = mod.extract_repo_info


class TestExtractRepoInfo:
    def test_basic_github_url(self):
        assert extract_repo_info("https://github.com/owner/repo") == ("owner", "repo")

    def test_dot_git_stripped(self):
        assert extract_repo_info("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_extra_path_segments_ok(self):
        assert extract_repo_info("https://github.com/owner/repo/tree/main") == ("owner", "repo")

    def test_non_github_url_returns_none(self):
        assert extract_repo_info("https://gitlab.com/owner/repo") is None

    def test_empty_string_returns_none(self):
        assert extract_repo_info("") is None

    def test_none_returns_none(self):
        assert extract_repo_info(None) is None

    def test_only_git_suffix_stripped_not_inner_dots(self):
        # "my.lib.git" -> "my.lib"; only the trailing ".git" is removed
        assert extract_repo_info("https://github.com/owner/my.lib.git") == ("owner", "my.lib")

    def test_repo_ending_in_t_not_clobbered(self):
        # Regression guard: str.rstrip(".git") strips chars {.git} from the tail,
        # so "econometrist" becomes "econometr". re.sub(r"\.git$", ...) is safe.
        assert extract_repo_info("https://github.com/user/econometrist") == ("user", "econometrist")

    def test_repo_ending_in_g_not_clobbered(self):
        assert extract_repo_info("https://github.com/user/causal-dag") == ("user", "causal-dag")

    def test_arxiv_url_returns_none(self):
        assert extract_repo_info("https://arxiv.org/abs/1234.5678") is None
