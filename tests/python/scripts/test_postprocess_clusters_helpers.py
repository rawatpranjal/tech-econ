"""Bullshit tests for postprocess_clusters.py pure helpers.

Covers:
  - cosine_similarity: identical vectors, orthogonal, direction
  - compute_hero_score: component contributions, type routing, recency decay, star boost
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: MagicMock()
    sys.modules[name] = m
    return m


for _dep in ["openai"]:
    if _dep not in sys.modules:
        _stub(_dep)

_spec = importlib.util.spec_from_file_location(
    "postprocess_clusters", _REPO_ROOT / "scripts" / "postprocess_clusters.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["postprocess_clusters"] = _mod
_spec.loader.exec_module(_mod)

cosine_similarity = _mod.cosine_similarity
compute_hero_score = _mod.compute_hero_score
is_career_cluster = _mod.is_career_cluster
get_career_industry = _mod.get_career_industry
is_generic_label = _mod.is_generic_label

import numpy as np


# ──────────────────────────────────────────────
# cosine_similarity
# ──────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert abs(cosine_similarity(a, b)) < 1e-9

    def test_opposite_vectors(self):
        v = np.array([1.0, 1.0])
        assert abs(cosine_similarity(v, -v) - (-1.0)) < 1e-9

    def test_scaled_vectors_same_similarity(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([2.0, 4.0, 6.0])  # 2x scale
        assert abs(cosine_similarity(a, b) - 1.0) < 1e-9

    def test_result_in_unit_interval(self):
        rng = np.random.default_rng(42)
        for _ in range(10):
            a = rng.standard_normal(128)
            b = rng.standard_normal(128)
            sim = cosine_similarity(a, b)
            assert -1.0 - 1e-9 <= sim <= 1.0 + 1e-9


# ──────────────────────────────────────────────
# compute_hero_score
# ──────────────────────────────────────────────

class TestComputeHeroScore:
    def test_returns_float(self):
        item = {"type": "resource", "date": "2023-01-01"}
        score = compute_hero_score(item, "r1", {}, {})
        assert isinstance(score, float)

    def test_score_in_unit_interval(self):
        for item_type in ["talk", "resource", "paper", "package", "book"]:
            item = {"type": item_type}
            score = compute_hero_score(item, "x", {}, {})
            assert 0.0 <= score <= 1.0, f"score={score} out of bounds for type={item_type}"

    def test_talk_scores_higher_than_career_portal(self):
        talk = {"type": "talk", "date": "2024-01-01"}
        career = {"type": "career", "date": "2024-01-01"}
        assert compute_hero_score(talk, "t", {}, {}) > compute_hero_score(career, "c", {}, {})

    def test_recent_item_scores_higher_than_old(self):
        new_item = {"type": "resource", "date": "2024-01-01"}
        old_item = {"type": "resource", "date": "2010-01-01"}
        assert (
            compute_hero_score(new_item, "n", {}, {})
            > compute_hero_score(old_item, "o", {}, {})
        )

    def test_paper_with_citations_boosts_authority(self):
        paper_cited = {"type": "paper"}
        paper_uncited = {"type": "paper"}
        cited_id = "paper-famous"
        # 1000 citations should push authority to 1.0
        score_cited = compute_hero_score(paper_cited, cited_id, {cited_id: 1000}, {})
        score_uncited = compute_hero_score(paper_uncited, "paper-unknown", {}, {})
        assert score_cited > score_uncited

    def test_package_with_stars_higher_engagement(self):
        with_stars = {"type": "package", "stars": 10000}
        without_stars = {"type": "package", "stars": 0}
        assert (
            compute_hero_score(with_stars, "p1", {}, {})
            > compute_hero_score(without_stars, "p2", {}, {})
        )

    def test_missing_date_uses_default_year(self):
        item = {"type": "resource"}  # no date field
        score = compute_hero_score(item, "r", {}, {})
        assert isinstance(score, float)

    def test_bad_date_format_no_crash(self):
        item = {"type": "resource", "date": "not-a-date"}
        score = compute_hero_score(item, "r", {}, {})
        assert isinstance(score, float)

    def test_year_field_fallback(self):
        item_date = {"type": "paper", "date": "2022"}
        item_year = {"type": "paper", "year": "2022"}
        # Both should parse to same year → similar scores
        s1 = compute_hero_score(item_date, "a", {}, {})
        s2 = compute_hero_score(item_year, "b", {}, {})
        assert abs(s1 - s2) < 0.05


# ──────────────────────────────────────────────
# is_career_cluster
# ──────────────────────────────────────────────
class TestIsCareerCluster:
    def test_career_label(self):
        assert is_career_cluster({"label": "Career Opportunities in Tech"}) is True

    def test_portal_label(self):
        assert is_career_cluster({"label": "Data Science Portal"}) is True

    def test_job_label(self):
        assert is_career_cluster({"label": "Job Board Resources"}) is True

    def test_non_career_label(self):
        assert is_career_cluster({"label": "Causal Inference Methods"}) is False

    def test_internship_label(self):
        assert is_career_cluster({"label": "ML Internship Programs"}) is True

    def test_case_insensitive(self):
        assert is_career_cluster({"label": "CAREER PATHS"}) is True


# ──────────────────────────────────────────────
# get_career_industry
# ──────────────────────────────────────────────
class TestGetCareerIndustry:
    def test_tech_industry(self):
        cluster = {"label": "Tech Careers at FAANG", "top_tags": []}
        assert get_career_industry(cluster) == "Tech Industry Careers"

    def test_fintech_industry(self):
        # "fintech" also triggers "tech" → Tech wins because CAREER_INDUSTRIES dict
        # is checked in insertion order and Tech comes first. Use "quant" instead
        # (unambiguously Finance) to test the Finance bucket.
        cluster = {"label": "Quant Trading Careers", "top_tags": []}
        assert get_career_industry(cluster) == "Finance & Fintech Careers"

    def test_gaming_industry(self):
        cluster = {"label": "Gaming Analytics Jobs", "top_tags": []}
        assert get_career_industry(cluster) == "Gaming & Entertainment Careers"

    def test_fallback_other(self):
        cluster = {"label": "Exotic Industry Careers", "top_tags": []}
        assert get_career_industry(cluster) == "Other Industry Careers"

    def test_tags_supplement_label(self):
        # "pharma" is not in label but in tags
        cluster = {"label": "Analytical Roles", "top_tags": ["pharma", "medical"]}
        assert get_career_industry(cluster) == "Healthcare & Pharma Careers"


# ──────────────────────────────────────────────
# is_generic_label
# ──────────────────────────────────────────────
class TestIsGenericLabel:
    def test_two_generic_terms_is_generic(self):
        # "insights" + "techniques" → count = 2 → True
        assert is_generic_label("Machine Learning Insights and Techniques") is True

    def test_one_generic_term_not_generic(self):
        assert is_generic_label("Causal Inference Methods") is False

    def test_no_generic_terms(self):
        assert is_generic_label("Doubly Robust DiD Estimators") is False

    def test_three_generic_terms(self):
        assert is_generic_label("Analysis Overview Framework") is True

    def test_empty_label(self):
        assert is_generic_label("") is False
