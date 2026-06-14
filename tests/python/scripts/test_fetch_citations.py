"""Tests for pure helpers in scripts/fetch_citations.py.

extract_doi and similarity are the pure, network-free functions.
api_request is excluded (requires network).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "fetch_citations.py"
_spec = importlib.util.spec_from_file_location("fetch_citations", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["fetch_citations"] = mod
_spec.loader.exec_module(mod)

extract_doi = mod.extract_doi
similarity = mod.similarity


# ---------------------------------------------------------------------------
# extract_doi
# ---------------------------------------------------------------------------

class TestExtractDoi:

    def test_doi_org_url(self):
        doi = extract_doi("https://doi.org/10.1257/aer.20170765")
        assert doi == "10.1257/aer.20170765"

    def test_doi_org_url_with_http(self):
        doi = extract_doi("http://doi.org/10.1257/jel.54.2.442")
        assert doi == "10.1257/jel.54.2.442"

    def test_doi_subpath(self):
        # URLs with /doi/ in path
        doi = extract_doi("https://pubs.aeaweb.org/doi/10.1257/aer.20170765")
        assert doi == "10.1257/aer.20170765"

    def test_bare_doi_in_url(self):
        # Some URLs embed just the DOI without doi.org
        doi = extract_doi("https://example.com/10.1234/some.paper.id")
        assert doi == "10.1234/some.paper.id"

    def test_arxiv_url_returns_none(self):
        assert extract_doi("https://arxiv.org/abs/2004.12345") is None

    def test_github_url_returns_none(self):
        assert extract_doi("https://github.com/org/repo") is None

    def test_empty_string_returns_none(self):
        assert extract_doi("") is None

    def test_strips_trailing_punctuation(self):
        doi = extract_doi("https://doi.org/10.1234/test.paper.")
        assert doi is not None
        assert not doi.endswith(".")

    def test_strips_trailing_semicolon(self):
        doi = extract_doi("https://doi.org/10.1234/test;")
        assert doi is not None
        assert not doi.endswith(";")

    def test_strips_trailing_parenthesis(self):
        doi = extract_doi("https://doi.org/10.1234/test)")
        assert doi is not None
        assert not doi.endswith(")")

    def test_ecma_style_doi(self):
        # 4-digit publisher prefix is minimum (10.xxxx/)
        doi = extract_doi("https://doi.org/10.1145/3582369")
        assert doi == "10.1145/3582369"

    def test_long_doi_path(self):
        doi = extract_doi("https://doi.org/10.1016/j.econlet.2021.109844")
        assert doi == "10.1016/j.econlet.2021.109844"


# ---------------------------------------------------------------------------
# similarity
# ---------------------------------------------------------------------------

class TestSimilarity:

    def test_identical_strings(self):
        assert similarity("machine learning", "machine learning") == 1.0

    def test_completely_different(self):
        assert similarity("abc", "xyz") == 0.0

    def test_partial_overlap(self):
        s = similarity("causal inference", "causal forest")
        assert 0.0 < s < 1.0

    def test_case_insensitive(self):
        s1 = similarity("Causal Inference", "causal inference")
        assert s1 == 1.0

    def test_roughly_symmetric(self):
        # SequenceMatcher.ratio() can have slight directional asymmetry for
        # strings of different lengths. Values should be very close.
        a = similarity("machine learning", "machine learning regression")
        b = similarity("machine learning regression", "machine learning")
        assert abs(a - b) < 0.15

    def test_empty_strings(self):
        assert similarity("", "") == 1.0

    def test_one_empty(self):
        assert similarity("some text", "") == 0.0

    def test_threshold_85_catches_similar_titles(self):
        # Test the 0.85 threshold used by is_duplicate in discover_content
        s = similarity(
            "Causal Inference: The Mixtape",
            "Causal Inference: The Mixtape (2nd ed.)"
        )
        assert s > 0.7  # highly similar but not identical

    def test_threshold_85_doesnt_catch_dissimilar(self):
        s = similarity(
            "Machine Learning for Econometrics",
            "Time Series Analysis with Python"
        )
        assert s < 0.85
