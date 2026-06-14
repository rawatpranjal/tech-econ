"""Tests for scripts/fetch_career_community_images.py.

No network calls needed — favicon URLs are deterministic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Load the module without executing main()
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_career_community_images.py"

_spec = importlib.util.spec_from_file_location(
    "fetch_career_community_images", _SCRIPT_PATH
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_career_community_images"] = mod
_spec.loader.exec_module(mod)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAVICON_PREFIX = "https://www.google.com/s2/favicons?domain="


def _make_career(tmp_path, entries):
    p = tmp_path / "career.json"
    p.write_text(json.dumps(entries))
    return p


def _make_community(tmp_path, entries):
    p = tmp_path / "community.json"
    p.write_text(json.dumps(entries))
    return p


# ===========================================================================
# 1. extract_domain — happy path
# ===========================================================================

class TestExtractDomainHappyPath:
    def test_extracts_plain_domain(self):
        assert mod.extract_domain("https://instacart.careers/") == "instacart.careers"

    def test_extracts_with_path(self):
        assert mod.extract_domain("https://recsys.acm.org/conference/2024/") == "recsys.acm.org"

    def test_extracts_with_query_string(self):
        assert mod.extract_domain("https://arxiv.org/abs/1234?v=1") == "arxiv.org"

    def test_extracts_subdomain_non_www(self):
        assert mod.extract_domain("https://research.netflix.com/area/ml") == "research.netflix.com"

    def test_extracts_http_scheme(self):
        assert mod.extract_domain("http://example.com/path") == "example.com"


# ===========================================================================
# 2. extract_domain — www. stripping
# ===========================================================================

class TestExtractDomainStripsWww:
    def test_strips_www_prefix(self):
        assert mod.extract_domain("https://www.linkedin.com/in/foo") == "linkedin.com"

    def test_strips_www_with_path(self):
        assert mod.extract_domain("https://www.kaggle.com/discussions") == "kaggle.com"

    def test_non_www_subdomain_preserved(self):
        result = mod.extract_domain("https://blog.google.com/page")
        assert result == "blog.google.com"

    def test_www_only_host(self):
        # edge: "www." followed by nothing → returns ""
        result = mod.extract_domain("https://www./")
        # after stripping "www." netloc becomes "" → None
        assert result is None


# ===========================================================================
# 3. extract_domain — None / empty / bad input
# ===========================================================================

class TestExtractDomainNoneEmpty:
    def test_none_returns_none(self):
        assert mod.extract_domain(None) is None

    def test_empty_string_returns_none(self):
        assert mod.extract_domain("") is None

    def test_whitespace_only_returns_none(self):
        assert mod.extract_domain("   ") is None

    def test_relative_path_returns_none(self):
        # No scheme → urlparse netloc is ""
        assert mod.extract_domain("/images/logos/uber.png") is None

    def test_local_path_url_returns_none(self):
        assert mod.extract_domain("images/foo.png") is None

    def test_bare_string_no_scheme_returns_none(self):
        # "linkedin.com" without scheme → netloc="" in urlparse
        result = mod.extract_domain("linkedin.com")
        assert result is None


# ===========================================================================
# 4. build_favicon_url — format
# ===========================================================================

class TestBuildFaviconUrl:
    def test_format_standard(self):
        url = mod.build_favicon_url("linkedin.com")
        assert url == "https://www.google.com/s2/favicons?domain=linkedin.com&sz=128"

    def test_starts_with_prefix(self):
        assert mod.build_favicon_url("anysite.com").startswith(FAVICON_PREFIX)

    def test_contains_sz_128(self):
        assert "&sz=128" in mod.build_favicon_url("example.com")

    def test_domain_embedded(self):
        url = mod.build_favicon_url("recsys.acm.org")
        assert "domain=recsys.acm.org" in url

    def test_https_scheme(self):
        assert mod.build_favicon_url("x.com").startswith("https://")

    def test_no_trailing_slash(self):
        url = mod.build_favicon_url("example.com")
        assert not url.endswith("/")


# ===========================================================================
# 5. --dry-run makes no writes to either file
# ===========================================================================

class TestDryRun:
    def test_dry_run_no_writes(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/"}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/"}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        mtime_c = cp.stat().st_mtime
        mtime_p = pp.stat().st_mtime

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            rc = mod.main(["--dry-run"])

        assert rc == 0
        assert cp.stat().st_mtime == mtime_c, "career.json was written in dry-run"
        assert pp.stat().st_mtime == mtime_p, "community.json was written in dry-run"

    def test_dry_run_exit_0(self, tmp_path):
        career = [{"name": "X", "url": ""}]
        community = [{"name": "Y", "url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)
        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            assert mod.main(["--dry-run"]) == 0

    def test_dry_run_content_unchanged(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/"}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        original_cp = cp.read_text()
        original_pp = pp.read_text()

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--dry-run"])

        assert cp.read_text() == original_cp
        assert pp.read_text() == original_pp


# ===========================================================================
# 6. Coverage ≥ 580 on real career.json
# ===========================================================================

class TestRealCareerCoverage:
    def test_coverage_at_least_580(self):
        """All 639 career entries have valid URLs → expect ≥580 favicon-able domains."""
        real_path = _REPO_ROOT / "data" / "career.json"
        if not real_path.exists():
            pytest.skip("career.json not found")
        data = json.loads(real_path.read_text())
        coverage = sum(
            1 for item in data
            if mod.extract_domain(item.get("url")) is not None
        )
        assert coverage >= 580, (
            f"Only {coverage}/639 career entries have extractable domain"
        )

    def test_career_entry_count_639(self):
        """Data integrity: total must stay 639."""
        real_path = _REPO_ROOT / "data" / "career.json"
        if not real_path.exists():
            pytest.skip("career.json not found")
        data = json.loads(real_path.read_text())
        assert len(data) == 639

    def test_all_career_have_image_url_key(self):
        """Every career entry must already have the image_url key."""
        real_path = _REPO_ROOT / "data" / "career.json"
        if not real_path.exists():
            pytest.skip("career.json not found")
        data = json.loads(real_path.read_text())
        missing = [item.get("name") for item in data if "image_url" not in item]
        assert not missing, f"Entries missing image_url key: {missing[:5]}"


# ===========================================================================
# 7. Pre-existing community images preserved (--skip-existing)
# ===========================================================================

class TestCommunityPreexistingPreserved:
    def test_preexisting_nonempty_not_overwritten(self, tmp_path):
        community = [
            {"name": "Already", "url": "https://google.com/",
             "image_url": "https://custom.example.com/logo.png"},
            {"name": "Empty", "url": "https://recsys.acm.org/", "image_url": ""},
        ]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--skip-existing"])

        result = json.loads(pp.read_text())
        assert result[0]["image_url"] == "https://custom.example.com/logo.png"

    def test_preexisting_with_skip_existing_others_filled(self, tmp_path):
        community = [
            {"name": "Already", "url": "https://google.com/",
             "image_url": "https://custom.example.com/logo.png"},
            {"name": "Empty", "url": "https://recsys.acm.org/", "image_url": ""},
        ]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--skip-existing"])

        result = json.loads(pp.read_text())
        # Empty entry should now have a favicon URL
        assert result[1]["image_url"].startswith(FAVICON_PREFIX)

    def test_real_community_preexisting_count(self):
        """Real community.json: 307 entries already have non-empty image_url."""
        real_path = _REPO_ROOT / "data" / "community.json"
        if not real_path.exists():
            pytest.skip("community.json not found")
        data = json.loads(real_path.read_text())
        nonempty = sum(1 for item in data if item.get("image_url", ""))
        assert nonempty >= 307, f"Expected ≥307 non-empty, got {nonempty}"

    def test_community_entry_count_452(self):
        """Data integrity: community total must stay 452."""
        real_path = _REPO_ROOT / "data" / "community.json"
        if not real_path.exists():
            pytest.skip("community.json not found")
        data = json.loads(real_path.read_text())
        assert len(data) == 452


# ===========================================================================
# 8. image_url key always added to entries missing it (community)
# ===========================================================================

class TestKeyAddedToMissingEntries:
    def test_missing_key_gets_added(self, tmp_path):
        community = [
            {"name": "NoKey", "url": "https://recsys.acm.org/"},  # no image_url key
        ]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(pp.read_text())
        assert "image_url" in result[0]

    def test_missing_key_gets_filled(self, tmp_path):
        community = [{"name": "NoKey", "url": "https://recsys.acm.org/"}]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(pp.read_text())
        assert result[0]["image_url"].startswith(FAVICON_PREFIX)

    def test_missing_key_gets_added_even_with_skip_existing(self, tmp_path):
        """--skip-existing only skips non-empty values; missing key always gets added."""
        community = [{"name": "NoKey", "url": "https://nber.org/"}]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--skip-existing"])

        result = json.loads(pp.read_text())
        assert "image_url" in result[0]
        assert result[0]["image_url"].startswith(FAVICON_PREFIX)

    def test_beyond_limit_entries_also_get_key(self, tmp_path):
        """Entries beyond --limit still get the image_url key set to ""."""
        community = [
            {"name": f"Entry{i}", "url": "https://recsys.acm.org/"}
            for i in range(5)
        ]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--limit", "2"])

        result = json.loads(pp.read_text())
        for item in result:
            assert "image_url" in item, f"Entry {item['name']} missing image_url key"


# ===========================================================================
# 9. New image_url values format (starts with favicon prefix)
# ===========================================================================

class TestNewImageUrlFormat:
    def test_new_value_starts_with_favicon_prefix(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        career_result = json.loads(cp.read_text())
        community_result = json.loads(pp.read_text())
        assert career_result[0]["image_url"].startswith(FAVICON_PREFIX)
        assert community_result[0]["image_url"].startswith(FAVICON_PREFIX)

    def test_no_url_entry_gets_empty_string(self, tmp_path):
        career = [{"name": "NoUrl", "url": "", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(cp.read_text())
        assert result[0]["image_url"] == ""

    def test_url_none_entry_gets_empty_string(self, tmp_path):
        career = [{"name": "NoUrl", "image_url": ""}]  # no url key at all
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(cp.read_text())
        assert result[0]["image_url"] == ""


# ===========================================================================
# 10. --skip-existing flag
# ===========================================================================

class TestSkipExisting:
    def test_skip_leaves_nonempty_unchanged(self, tmp_path):
        career = [
            {"name": "HasImg", "url": "https://google.com/",
             "image_url": "https://original.example.com/img.png"},
            {"name": "NoImg", "url": "https://amazon.com/", "image_url": ""},
        ]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--skip-existing"])

        result = json.loads(cp.read_text())
        assert result[0]["image_url"] == "https://original.example.com/img.png"
        assert result[1]["image_url"].startswith(FAVICON_PREFIX)

    def test_without_skip_existing_overwrites(self, tmp_path):
        career = [
            {"name": "HasImg", "url": "https://amazon.com/",
             "image_url": "https://original.example.com/img.png"},
        ]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])  # no --skip-existing

        result = json.loads(cp.read_text())
        assert result[0]["image_url"].startswith(FAVICON_PREFIX)

    def test_empty_image_url_is_not_skipped(self, tmp_path):
        """An empty string is not 'existing' — should be filled."""
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--skip-existing"])

        result = json.loads(cp.read_text())
        assert result[0]["image_url"].startswith(FAVICON_PREFIX)


# ===========================================================================
# 11. --limit flag
# ===========================================================================

class TestLimit:
    def test_limit_respects_count_per_file(self, tmp_path):
        career = [
            {"name": f"Co{i}", "url": f"https://company{i}.com/", "image_url": ""}
            for i in range(10)
        ]
        community = [
            {"name": f"Conf{i}", "url": f"https://conf{i}.org/", "image_url": ""}
            for i in range(10)
        ]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--limit", "3"])

        career_result = json.loads(cp.read_text())
        community_result = json.loads(pp.read_text())
        career_filled = [p for p in career_result if p["image_url"]]
        community_filled = [p for p in community_result if p["image_url"]]
        assert len(career_filled) == 3
        assert len(community_filled) == 3

    def test_limit_zero_processes_nothing(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main(["--limit", "0"])

        career_result = json.loads(cp.read_text())
        community_result = json.loads(pp.read_text())
        assert career_result[0]["image_url"] == ""
        assert community_result[0]["image_url"] == ""


# ===========================================================================
# 12. Atomic write (os.replace pattern)
# ===========================================================================

class TestAtomicWrite:
    def test_output_file_exists_after_run(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        assert cp.exists()
        assert pp.exists()

    def test_output_is_valid_json(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        json.loads(cp.read_text())  # must not raise
        json.loads(pp.read_text())  # must not raise

    def test_no_other_fields_modified(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/",
                   "description": "My desc", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/",
                      "category": "Research", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        cr = json.loads(cp.read_text())
        pr = json.loads(pp.read_text())
        assert cr[0]["name"] == "Co"
        assert cr[0]["description"] == "My desc"
        assert pr[0]["name"] == "Conf"
        assert pr[0]["category"] == "Research"

    def test_temp_file_not_left_behind(self, tmp_path):
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        assert not (tmp_path / "career.json.tmp").exists()
        assert not (tmp_path / "community.json.tmp").exists()


# ===========================================================================
# 13. No data loss — entry counts preserved
# ===========================================================================

class TestNoDataLoss:
    def test_career_count_preserved(self, tmp_path):
        career = [
            {"name": f"Co{i}", "url": f"https://c{i}.com/", "image_url": ""}
            for i in range(20)
        ]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(cp.read_text())
        assert len(result) == 20

    def test_community_count_preserved(self, tmp_path):
        community = [
            {"name": f"Conf{i}", "url": f"https://conf{i}.org/"}
            for i in range(15)
        ]
        career = [{"name": "Co", "url": "https://amazon.com/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(pp.read_text())
        assert len(result) == 15

    def test_all_keys_preserved_on_entry(self, tmp_path):
        """All original fields survive the run."""
        entry = {
            "name": "TestCo", "url": "https://amazon.com/",
            "description": "desc", "tags": ["a", "b"],
            "model_score": 0.5, "image_url": "",
        }
        career = [entry]
        community = [{"name": "Conf", "url": "https://recsys.acm.org/", "image_url": ""}]
        cp = _make_career(tmp_path, career)
        pp = _make_community(tmp_path, community)

        with patch.object(mod, "CAREER_PATH", cp), \
             patch.object(mod, "COMMUNITY_PATH", pp):
            mod.main([])

        result = json.loads(cp.read_text())
        for key in ("name", "url", "description", "tags", "model_score"):
            assert key in result[0], f"Key '{key}' was lost"


# ===========================================================================
# 14. _process helper unit tests
# ===========================================================================

class TestProcessHelper:
    def test_returns_four_tuple(self):
        data = [{"name": "X", "url": "https://example.com/", "image_url": ""}]
        result = mod._process(data, skip_existing=False, limit=None)
        assert len(result) == 4

    def test_updated_count(self):
        data = [
            {"name": "A", "url": "https://amazon.com/", "image_url": ""},
            {"name": "B", "url": "", "image_url": ""},
        ]
        _, updated, _, _ = mod._process(data, skip_existing=False, limit=None)
        assert updated == 1  # only A gets a URL

    def test_skipped_count(self):
        data = [
            {"name": "A", "url": "https://amazon.com/",
             "image_url": "https://existing.com/img.png"},
            {"name": "B", "url": "https://google.com/", "image_url": ""},
        ]
        _, _, skipped, _ = mod._process(data, skip_existing=True, limit=None)
        assert skipped == 1

    def test_processed_count_with_limit(self):
        data = [
            {"name": f"X{i}", "url": f"https://site{i}.com/", "image_url": ""}
            for i in range(10)
        ]
        _, _, _, processed = mod._process(data, skip_existing=False, limit=3)
        assert processed == 3

    def test_missing_key_filled_beyond_limit(self):
        data = [
            {"name": f"X{i}", "url": f"https://site{i}.com/"}  # no image_url
            for i in range(5)
        ]
        result_data, _, _, _ = mod._process(data, skip_existing=False, limit=2)
        for item in result_data:
            assert "image_url" in item
