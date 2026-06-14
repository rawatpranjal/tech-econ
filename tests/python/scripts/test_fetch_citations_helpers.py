"""Bullshit tests for fetch_citations.py pure helpers.

Covers: extract_doi (doi.org URL, direct DOI, rstrip punctuation, non-DOI),
        similarity (identical, completely different, partial match).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_citations.py"

_spec = importlib.util.spec_from_file_location("fetch_citations", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_citations"] = mod
_spec.loader.exec_module(mod)

extract_doi = mod.extract_doi
similarity = mod.similarity


class TestExtractDoi:
    def test_doi_org_url(self):
        result = extract_doi("https://doi.org/10.1257/aer.20151326")
        assert result == "10.1257/aer.20151326"

    def test_direct_doi_in_url(self):
        result = extract_doi("https://example.com/doi/10.1145/1234.5678")
        assert result == "10.1145/1234.5678"

    def test_trailing_period_stripped(self):
        result = extract_doi("https://doi.org/10.1257/aer.20151326.")
        assert result is not None
        assert not result.endswith(".")

    def test_trailing_comma_stripped(self):
        result = extract_doi("https://doi.org/10.1257/aer.20151326,")
        assert result is not None
        assert not result.endswith(",")

    def test_no_doi_returns_none(self):
        assert extract_doi("https://arxiv.org/abs/1234.5678") is None

    def test_empty_string_returns_none(self):
        assert extract_doi("") is None

    def test_non_url_with_doi_pattern(self):
        result = extract_doi("See also 10.1257/aer.20151326 for reference")
        assert result == "10.1257/aer.20151326"


class TestSimilarity:
    def test_identical_strings(self):
        assert similarity("hello", "hello") == pytest.approx(1.0)

    def test_completely_different(self):
        result = similarity("aaaaaa", "bbbbbb")
        assert result == pytest.approx(0.0)

    def test_partial_match(self):
        result = similarity("machine learning", "machine learning methods")
        assert 0.5 < result < 1.0

    def test_case_insensitive(self):
        assert similarity("HELLO", "hello") == pytest.approx(1.0)

    def test_empty_strings(self):
        assert similarity("", "") == pytest.approx(1.0)

    def test_one_empty(self):
        assert similarity("hello", "") == pytest.approx(0.0)

    def test_result_in_unit_interval(self):
        for a, b in [("causal", "causal inference"), ("deep", "learning"), ("a", "b")]:
            r = similarity(a, b)
            assert 0.0 <= r <= 1.0
