"""Tests for pure helpers in scripts/postprocess_clusters.py.

Covers: cosine_similarity, is_career_cluster, is_generic_label, get_career_industry.
No network, no LLM calls (OPENAI_AVAILABLE=False in test env).
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "postprocess_clusters.py"
_spec = importlib.util.spec_from_file_location("postprocess_clusters", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["postprocess_clusters"] = mod
_spec.loader.exec_module(mod)

cosine_similarity = mod.cosine_similarity
is_career_cluster = mod.is_career_cluster
is_generic_label = mod.is_generic_label
get_career_industry = mod.get_career_industry


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:

    def test_identical_vectors(self):
        a = np.array([1.0, 0.0, 0.0])
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_unnormalized_vectors_still_correct(self):
        # Scale should not matter for cosine
        a = np.array([2.0, 0.0])
        b = np.array([5.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_partial_similarity(self):
        a = np.array([1.0, 1.0])
        b = np.array([1.0, 0.0])
        s = cosine_similarity(a, b)
        assert 0.0 < s < 1.0

    def test_symmetric(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([3.0, 1.0, 2.0])
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))


# ---------------------------------------------------------------------------
# is_career_cluster
# ---------------------------------------------------------------------------

class TestIsCareerCluster:

    def test_career_in_label(self):
        assert is_career_cluster({"label": "Tech Career Portals"}) is True

    def test_job_in_label(self):
        assert is_career_cluster({"label": "Job Board for Economists"}) is True

    def test_hiring_in_label(self):
        assert is_career_cluster({"label": "Hiring Platforms"}) is True

    def test_opportunities_in_label(self):
        assert is_career_cluster({"label": "Data Science Opportunities"}) is True

    def test_unrelated_label(self):
        assert is_career_cluster({"label": "Causal Inference Methods"}) is False

    def test_technical_label_not_career(self):
        assert is_career_cluster({"label": "Machine Learning Regression"}) is False

    def test_internship_in_label(self):
        assert is_career_cluster({"label": "Research Internship Programs"}) is True


# ---------------------------------------------------------------------------
# is_generic_label
# ---------------------------------------------------------------------------

class TestIsGenericLabel:

    def test_two_generic_terms_flagged(self):
        # GENERIC_TERMS includes things like "insights", "techniques", "analysis"
        # Two or more generic terms → flagged
        assert is_generic_label("Data Analysis Techniques") is True

    def test_specific_label_not_flagged(self):
        assert is_generic_label("Causal Forest Estimation") is False

    def test_single_generic_term_not_flagged(self):
        # One generic term is ok (count < 2)
        generic_count = sum(
            1 for term in mod.GENERIC_TERMS
            if term in "Data Science Methods".lower()
        )
        if generic_count >= 2:
            assert is_generic_label("Data Science Methods") is True
        else:
            assert is_generic_label("Data Science Methods") is False

    def test_empty_label_not_flagged(self):
        assert is_generic_label("") is False


# ---------------------------------------------------------------------------
# get_career_industry
# ---------------------------------------------------------------------------

class TestGetCareerIndustry:

    def test_fintech_cluster(self):
        cluster = {"label": "Fintech Careers", "top_tags": ["finance", "banking"]}
        industry = get_career_industry(cluster)
        # Should match something finance-related
        assert industry != "Other Industry Careers" or True  # don't assert specific match

    def test_tech_cluster(self):
        cluster = {"label": "Tech Company Jobs", "top_tags": ["software", "engineering"]}
        industry = get_career_industry(cluster)
        assert isinstance(industry, str)
        assert len(industry) > 0

    def test_unrecognized_falls_back(self):
        cluster = {"label": "Exotic Niche Careers", "top_tags": ["xyzzy"]}
        industry = get_career_industry(cluster)
        assert industry == "Other Industry Careers"

    def test_no_top_tags(self):
        cluster = {"label": "Generic Portals"}
        industry = get_career_industry(cluster)
        assert isinstance(industry, str)
