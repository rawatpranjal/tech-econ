"""Tests for scripts/fetch_package_images.py.

No network calls needed — avatar URLs are deterministic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Stub requests before the module is loaded (pattern from test_fetch_book_covers.py)
sys.modules.setdefault("requests", MagicMock())

# ---------------------------------------------------------------------------
# Load the module without executing main()
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_package_images.py"

_spec = importlib.util.spec_from_file_location("fetch_package_images", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_package_images"] = mod
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# 1. parse_github_owner — happy path
# ---------------------------------------------------------------------------

class TestParseGithubOwner:
    def test_extracts_org(self):
        assert mod.parse_github_owner("https://github.com/DoubleML/doubleml-for-py") == "DoubleML"

    def test_extracts_user(self):
        assert mod.parse_github_owner("https://github.com/facebook/Ax") == "facebook"

    def test_trailing_slash(self):
        assert mod.parse_github_owner("https://github.com/tidyverse/") == "tidyverse"

    def test_query_string_stripped(self):
        assert mod.parse_github_owner("https://github.com/MyOrg/repo?tab=readme") == "MyOrg"


# ---------------------------------------------------------------------------
# 2. parse_github_owner — non-GitHub returns None
# ---------------------------------------------------------------------------

class TestParseGithubOwnerNonGithub:
    def test_cran_url_returns_none(self):
        assert mod.parse_github_owner("https://cran.r-project.org/package=did") is None

    def test_pypi_url_returns_none(self):
        assert mod.parse_github_owner("https://pypi.org/project/numpy/") is None

    def test_bare_domain_returns_none(self):
        assert mod.parse_github_owner("https://axios.dev") is None


# ---------------------------------------------------------------------------
# 3. parse_github_owner — None / empty input
# ---------------------------------------------------------------------------

class TestParseGithubOwnerNoneInput:
    def test_none_returns_none(self):
        assert mod.parse_github_owner(None) is None

    def test_empty_string_returns_none(self):
        assert mod.parse_github_owner("") is None

    def test_whitespace_returns_none(self):
        # whitespace-only is falsy after strip check in parse_github_owner
        assert mod.parse_github_owner("  ") is None


# ---------------------------------------------------------------------------
# 4. build_avatar_url format
# ---------------------------------------------------------------------------

class TestBuildAvatarUrl:
    def test_format_standard(self):
        url = mod.build_avatar_url("DoubleML")
        assert url == "https://github.com/DoubleML.png?size=128"

    def test_format_lowercase(self):
        url = mod.build_avatar_url("facebook")
        assert url == "https://github.com/facebook.png?size=128"

    def test_starts_with_https(self):
        assert mod.build_avatar_url("anyorg").startswith("https://")

    def test_size_param_present(self):
        assert "size=128" in mod.build_avatar_url("anyorg")


# ---------------------------------------------------------------------------
# 5. --dry-run makes no writes
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_no_writes(self, tmp_path):
        packages = [
            {"name": "TestPkg", "url": "https://github.com/MyOrg/repo",
             "github_url": "", "category": "tools"},
        ]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        original_mtime = pkg_path.stat().st_mtime

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            result = mod.main(["--dry-run"])

        assert result == 0
        assert pkg_path.stat().st_mtime == original_mtime

    def test_dry_run_exit_0(self, tmp_path):
        packages = [{"name": "X", "url": "", "github_url": "", "category": "tools"}]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            rc = mod.main(["--dry-run"])

        assert rc == 0


# ---------------------------------------------------------------------------
# 6. Coverage check on real packages.json
# ---------------------------------------------------------------------------

class TestRealPackagesCoverage:
    def test_coverage_at_least_450(self):
        """471 packages have GitHub URLs; expect >=450 to get image_url."""
        real_path = _REPO_ROOT / "data" / "packages.json"
        if not real_path.exists():
            pytest.skip("packages.json not found")
        packages = json.loads(real_path.read_text())
        coverage = sum(
            1 for p in packages
            if (
                mod.parse_github_owner(p.get("github_url")) or
                mod.parse_github_owner(p.get("url"))
            )
        )
        assert coverage >= 450, f"Only {coverage} packages have extractable GitHub owner"

    def test_all_551_entries_present(self):
        """Total count must stay 551."""
        real_path = _REPO_ROOT / "data" / "packages.json"
        if not real_path.exists():
            pytest.skip("packages.json not found")
        packages = json.loads(real_path.read_text())
        assert len(packages) == 551


# ---------------------------------------------------------------------------
# 7. Precedence: github_url first, then url
# ---------------------------------------------------------------------------

class TestPrecedence:
    def test_github_url_takes_priority_over_url(self, tmp_path):
        packages = [{
            "name": "Pkg",
            "github_url": "https://github.com/PrimaryOrg/repo",
            "url": "https://github.com/FallbackOrg/repo",
            "category": "tools",
        }]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main([])

        result = json.loads(pkg_path.read_text())
        assert result[0]["image_url"] == "https://github.com/PrimaryOrg.png?size=128"

    def test_falls_back_to_url_when_github_url_empty(self, tmp_path):
        packages = [{
            "name": "Pkg2",
            "github_url": "",
            "url": "https://github.com/FallbackOrg/repo",
            "category": "tools",
        }]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main([])

        result = json.loads(pkg_path.read_text())
        assert result[0]["image_url"] == "https://github.com/FallbackOrg.png?size=128"

    def test_non_github_url_gets_empty_string(self, tmp_path):
        packages = [{
            "name": "CRANPkg",
            "github_url": "",
            "url": "https://cran.r-project.org/package=did",
            "category": "tools",
        }]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main([])

        result = json.loads(pkg_path.read_text())
        assert result[0]["image_url"] == ""


# ---------------------------------------------------------------------------
# 8. --skip-existing skips entries with image_url already set
# ---------------------------------------------------------------------------

class TestSkipExisting:
    def test_skip_existing_leaves_existing_url_unchanged(self, tmp_path):
        packages = [
            {"name": "AlreadySet", "github_url": "https://github.com/NewOrg/r",
             "url": "", "category": "tools", "image_url": "https://example.com/img.png"},
            {"name": "NotSet", "github_url": "https://github.com/OtherOrg/r",
             "url": "", "category": "tools"},
        ]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main(["--skip-existing"])

        result = json.loads(pkg_path.read_text())
        # First entry: image_url must not be overwritten
        assert result[0]["image_url"] == "https://example.com/img.png"
        # Second entry: was set
        assert result[1]["image_url"] == "https://github.com/OtherOrg.png?size=128"


# ---------------------------------------------------------------------------
# 9. --limit flag
# ---------------------------------------------------------------------------

class TestLimit:
    def test_limit_respects_count(self, tmp_path):
        packages = [
            {"name": f"Pkg{i}", "github_url": f"https://github.com/Org{i}/r",
             "url": "", "category": "tools"}
            for i in range(10)
        ]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main(["--limit", "3"])

        result = json.loads(pkg_path.read_text())
        # First 3 should be set; rest should have "" (filled by final loop)
        filled = [p for p in result if p["image_url"]]
        assert len(filled) == 3


# ---------------------------------------------------------------------------
# 10. Atomic write uses os.replace
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_output_file_exists_after_run(self, tmp_path):
        packages = [{"name": "X", "github_url": "https://github.com/Org/r",
                     "url": "", "category": "tools"}]
        pkg_path = tmp_path / "packages.json"
        pkg_path.write_text(json.dumps(packages))

        import unittest.mock as mock
        with mock.patch.object(mod, "DATA_PATH", pkg_path):
            mod.main([])

        assert pkg_path.exists()
        result = json.loads(pkg_path.read_text())
        assert result[0]["image_url"] == "https://github.com/Org.png?size=128"
