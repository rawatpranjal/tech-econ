"""Bullshit tests for convert_readme.py pure functions.

Covers: parse_links, generate_tags, parse_readme
All three are pure; no network/filesystem needed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Load convert_readme without triggering main()
spec = importlib.util.spec_from_file_location(
    "convert_readme", Path(__file__).parents[3] / "scripts" / "convert_readme.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules.setdefault("convert_readme", mod)
spec.loader.exec_module(mod)

parse_links = mod.parse_links
generate_tags = mod.generate_tags
parse_readme = mod.parse_readme
CATEGORY_TAG_MAP = mod.CATEGORY_TAG_MAP


# ──────────────────────────────────────────────
# parse_links
# ──────────────────────────────────────────────

class TestParseLinks:
    def test_github_and_docs_extracted(self):
        cell = "[Docs](https://docs.example.com) . [GitHub](https://github.com/org/repo)"
        docs, gh = parse_links(cell)
        assert docs == "https://docs.example.com"
        assert gh == "https://github.com/org/repo"

    def test_github_only(self):
        cell = "[GitHub](https://github.com/org/pkg)"
        docs, gh = parse_links(cell)
        assert gh == "https://github.com/org/pkg"
        assert docs is None

    def test_docs_only(self):
        cell = "[Docs](https://readthedocs.org/pkg)"
        docs, gh = parse_links(cell)
        assert docs == "https://readthedocs.org/pkg"
        assert gh is None

    def test_pypi_link_treated_as_docs(self):
        cell = "[PyPI](https://pypi.org/project/pkg/)"
        docs, gh = parse_links(cell)
        assert docs == "https://pypi.org/project/pkg/"

    def test_git_in_text_treated_as_github(self):
        cell = "[Git](https://gitlab.com/org/repo)"
        docs, gh = parse_links(cell)
        assert gh == "https://gitlab.com/org/repo"

    def test_empty_string_returns_nones(self):
        docs, gh = parse_links("")
        assert docs is None
        assert gh is None

    def test_first_unknown_link_becomes_docs_fallback(self):
        cell = "[Website](https://example.com)"
        docs, gh = parse_links(cell)
        assert docs == "https://example.com"
        assert gh is None

    def test_multiple_unknown_links_first_wins_for_docs(self):
        cell = "[Site](https://a.com) [Other](https://b.com)"
        docs, gh = parse_links(cell)
        assert docs == "https://a.com"

    def test_no_markdown_links_returns_nones(self):
        docs, gh = parse_links("plain text no brackets")
        assert docs is None
        assert gh is None

    def test_github_url_without_github_in_text_not_captured_as_gh(self):
        # If the text doesn't say "github" / "git" it falls into docs fallback
        cell = "[Source](https://github.com/foo/bar)"
        docs, gh = parse_links(cell)
        # "Source" text has neither 'doc' nor 'github'/'git' → docs fallback
        assert docs == "https://github.com/foo/bar"

    def test_case_insensitive_doc_match(self):
        cell = "[Documentation](https://pkg.readthedocs.io)"
        docs, gh = parse_links(cell)
        assert docs == "https://pkg.readthedocs.io"


# ──────────────────────────────────────────────
# generate_tags
# ──────────────────────────────────────────────

class TestGenerateTags:
    def test_known_category_produces_tags(self):
        tags = generate_tags("Causal Inference & Matching", "some package")
        assert "causal inference" in tags
        assert "matching" in tags

    def test_unknown_category_produces_empty_without_keyword_match(self):
        tags = generate_tags("Unknown Category XYZ", "no relevant description")
        assert tags == []

    def test_keyword_in_description_adds_tag(self):
        tags = generate_tags("Unknown Category", "uses propensity score weighting")
        assert "matching" in tags

    def test_keyword_matching_case_insensitive(self):
        # "bayesian" is lowercase in KEYWORD_TAGS
        tags = generate_tags("Unknown Category", "A Bayesian approach to forecasting")
        assert "Bayesian" in tags

    def test_max_4_tags_enforced(self):
        # Category that produces 2 tags + description keywords that add more
        tags = generate_tags("Causal Inference & Matching", "bayesian neural gradient boost xgboost")
        assert len(tags) <= 4

    def test_dedup_preserves_order(self):
        # Category already has "causal inference"; description also mentions it
        tags = generate_tags("Causal Inference & Matching", "treatment effect propensity")
        assert tags.count("causal inference") == 1

    def test_time_series_category(self):
        tags = generate_tags("Time Series Econometrics", "ARIMA model")
        assert "time series" in tags
        assert "econometrics" in tags

    def test_did_category(self):
        tags = generate_tags("Program Evaluation Methods (DiD, SC, RDD)", "diff-in-diff study")
        assert "DiD" in tags

    def test_all_known_categories_have_entries(self):
        for cat in CATEGORY_TAG_MAP:
            tags = generate_tags(cat, "")
            assert len(tags) > 0, f"Category {cat!r} produced no tags"

    def test_deep_learning_keyword(self):
        tags = generate_tags("Unknown", "deep learning for NLP")
        assert "machine learning" in tags

    def test_gradient_boost_keyword(self):
        tags = generate_tags("Unknown", "gradient boost model")
        assert "machine learning" in tags


# ──────────────────────────────────────────────
# parse_readme
# ──────────────────────────────────────────────

class TestParseReadme:
    def _make_readme(self, category: str, rows: list[str]) -> str:
        header = f"## {category}\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
        return header + "\n".join(rows) + "\n"

    def test_basic_row_parsed(self):
        readme = self._make_readme(
            "Causal Inference & Matching",
            ["| MyPkg | A description | [GitHub](https://github.com/org/mypkg) | `pip install mypkg` |"]
        )
        pkgs = parse_readme(readme)
        assert len(pkgs) == 1
        p = pkgs[0]
        assert p["name"] == "MyPkg"
        assert p["description"] == "A description"
        assert p["github_url"] == "https://github.com/org/mypkg"
        assert p["install"] == "pip install mypkg"
        assert p["category"] == "Causal Inference & Matching"

    def test_bold_package_name_stripped(self):
        readme = self._make_readme(
            "Bayesian Econometrics",
            ["| **BoldPkg** | desc | [Docs](https://docs.bp.io) | `pip install boldpkg` |"]
        )
        pkgs = parse_readme(readme)
        assert pkgs[0]["name"] == "BoldPkg"

    def test_header_rows_skipped(self):
        readme = self._make_readme("Bayesian Econometrics", [])
        pkgs = parse_readme(readme)
        assert len(pkgs) == 0

    def test_skipped_sections(self):
        readme = (
            "## Contributing\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
            "| Secret | hidden | [GitHub](https://github.com/x) | `pip install x` |\n"
            "## Causal Inference & Matching\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
            "| RealPkg | real | [GitHub](https://github.com/real) | `pip install real` |\n"
        )
        pkgs = parse_readme(readme)
        names = [p["name"] for p in pkgs]
        assert "Secret" not in names
        assert "RealPkg" in names

    def test_multiple_categories(self):
        readme = (
            "## Category A\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
            "| PkgA | desc a | [GitHub](https://github.com/a) | `pip install a` |\n"
            "## Category B\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
            "| PkgB | desc b | [GitHub](https://github.com/b) | `pip install b` |\n"
        )
        pkgs = parse_readme(readme)
        assert len(pkgs) == 2
        assert {p["category"] for p in pkgs} == {"Category A", "Category B"}

    def test_github_url_used_as_primary_when_available(self):
        readme = self._make_readme(
            "Time Series Econometrics",
            ["| TsPkg | ts desc | [GitHub](https://github.com/ts) | `pip install ts` |"]
        )
        pkgs = parse_readme(readme)
        assert pkgs[0]["url"] == "https://github.com/ts"

    def test_pypi_fallback_url_when_no_links(self):
        readme = self._make_readme(
            "Time Series Econometrics",
            ["| NoPkg | no link | | `pip install nopkg` |"]
        )
        pkgs = parse_readme(readme)
        assert pkgs[0]["url"] == "https://pypi.org/project/NoPkg/"

    def test_install_backticks_stripped(self):
        readme = self._make_readme(
            "Core Libraries & Linear Models",
            ["| Pkg | d | [GitHub](https://github.com/x) | `pip install pkg` |"]
        )
        pkgs = parse_readme(readme)
        assert pkgs[0]["install"] == "pip install pkg"

    def test_empty_readme_returns_empty_list(self):
        assert parse_readme("") == []

    def test_row_with_fewer_than_3_cells_ignored(self):
        readme = "## Core Libraries & Linear Models\n\n| Package |\n|---|\n| OnlyName |\n"
        pkgs = parse_readme(readme)
        assert len(pkgs) == 0

    def test_name_package_sentinel_skipped(self):
        # A row whose first cell is literally "Package" or "Name" should be skipped
        readme = "## Core Libraries & Linear Models\n\n| Package | Description | Links | Install |\n|---|---|---|---|\n"
        pkgs = parse_readme(readme)
        assert len(pkgs) == 0
