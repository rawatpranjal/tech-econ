"""Tests for transform_resource in scripts/reorganize_resources.py.

Covers: category consolidation, type normalization (mapped vs unmapped),
        macro_category assignment, default macro fallback, domain backfill,
        domain preservation, difficulty normalization, in-place mutation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(script_name: str, alias: str):
    path = _REPO_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    spec.loader.exec_module(m)
    return m


reorganize_resources_mod = _load("reorganize_resources.py", "reorganize_resources_mod")
transform_resource = reorganize_resources_mod.transform_resource
CATEGORY_MAPPING = reorganize_resources_mod.CATEGORY_MAPPING
TYPE_MAPPING = reorganize_resources_mod.TYPE_MAPPING
MACRO_CATEGORY_MAPPING = reorganize_resources_mod.MACRO_CATEGORY_MAPPING
DOMAIN_BACKFILL = reorganize_resources_mod.DOMAIN_BACKFILL


# ──────────────────────────────────────────────
# Category consolidation
# ──────────────────────────────────────────────

class TestCategoryConsolidation:
    def test_mapped_category_gets_new_value(self):
        # "Causal Inference & ML" → "Causal Inference"
        r = {"category": "Causal Inference & ML", "type": "Article"}
        transform_resource(r)
        assert r["category"] == "Causal Inference"

    def test_another_mapped_category(self):
        # "AB Testing" → "A/B Testing"
        r = {"category": "AB Testing", "type": "Course"}
        transform_resource(r)
        assert r["category"] == "A/B Testing"

    def test_unmapped_category_stays_unchanged(self):
        r = {"category": "Causal Inference", "type": "Article"}
        transform_resource(r)
        assert r["category"] == "Causal Inference"

    def test_empty_category_stays_empty(self):
        r = {"category": "", "type": "Article"}
        transform_resource(r)
        assert r["category"] == ""


# ──────────────────────────────────────────────
# Type normalization
# ──────────────────────────────────────────────

class TestTypeNormalization:
    def test_mapped_type_gets_canonical_value(self):
        # "Online Course" is in TYPE_MAPPING → "Course"
        r = {"category": "Machine Learning", "type": "Online Course"}
        transform_resource(r)
        assert r["type"] == "Course"

    def test_lowercase_blog_mapped(self):
        # "blog" is in TYPE_MAPPING → "Blog"
        r = {"category": "Frameworks & Strategy", "type": "blog"}
        transform_resource(r)
        assert r["type"] == "Blog"

    def test_unmapped_type_gets_title_cased(self):
        # "blog post" is NOT in TYPE_MAPPING (lowercase with space) → title-cased
        r = {"category": "Frameworks & Strategy", "type": "blog post"}
        transform_resource(r)
        assert r["type"] == "Blog Post"

    def test_unmapped_mixed_case_title_cased(self):
        # "some weird type" not in mapping → "Some Weird Type"
        r = {"category": "Machine Learning", "type": "some weird type"}
        transform_resource(r)
        assert r["type"] == "Some Weird Type"

    def test_mapped_type_not_double_title_cased(self):
        # "Blog Post" IS in TYPE_MAPPING → "Blog" (not "Blog")
        r = {"category": "Frameworks & Strategy", "type": "Blog Post"}
        transform_resource(r)
        assert r["type"] == "Blog"

    def test_empty_type_stays_empty(self):
        r = {"category": "Machine Learning", "type": ""}
        transform_resource(r)
        assert r["type"] == ""


# ──────────────────────────────────────────────
# macro_category
# ──────────────────────────────────────────────

class TestMacroCategory:
    def test_known_category_gets_correct_macro(self):
        # "Causal Inference" → "Causal Methods"
        r = {"category": "Causal Inference", "type": "Article"}
        transform_resource(r)
        assert r["macro_category"] == "Causal Methods"

    def test_mapped_category_resolved_macro(self):
        # "Causal Inference & ML" → maps to "Causal Inference" → "Causal Methods"
        r = {"category": "Causal Inference & ML", "type": "Article"}
        transform_resource(r)
        assert r["macro_category"] == "Causal Methods"

    def test_ab_testing_macro(self):
        # "A/B Testing" → "Experimentation"
        r = {"category": "A/B Testing", "type": "Course"}
        transform_resource(r)
        assert r["macro_category"] == "Experimentation"

    def test_default_macro_is_strategy_when_no_match(self):
        # Completely unknown category with no Economics/Finance keywords
        r = {"category": "Unknown Niche Topic", "type": "Article"}
        transform_resource(r)
        assert r["macro_category"] == "Strategy"

    def test_economics_in_category_gets_industry_economics_macro(self):
        # "Computational Economics" is in MACRO_CATEGORY_MAPPING → "Industry Economics"
        r = {"category": "Computational Economics", "type": "Article"}
        transform_resource(r)
        assert r["macro_category"] == "Industry Economics"

    def test_finance_keyword_in_unknown_category_fallback(self):
        # Category not in mapping but contains "Finance" → "Industry Economics"
        r = {"category": "Personal Finance Misc", "type": "Article"}
        transform_resource(r)
        assert r["macro_category"] == "Industry Economics"


# ──────────────────────────────────────────────
# Domain backfill
# ──────────────────────────────────────────────

class TestDomainBackfill:
    def test_domain_backfilled_when_missing(self):
        # "A/B Testing" → DOMAIN_BACKFILL → "Experimentation"
        r = {"category": "A/B Testing", "type": "Course"}
        transform_resource(r)
        assert r["domain"] == "Experimentation"

    def test_domain_not_overwritten_when_present(self):
        r = {"category": "A/B Testing", "type": "Course", "domain": "My Custom Domain"}
        transform_resource(r)
        assert r["domain"] == "My Custom Domain"

    def test_causal_inference_backfilled(self):
        r = {"category": "Causal Inference", "type": "Article"}
        transform_resource(r)
        assert r["domain"] == "Causal Inference"

    def test_mapped_category_backfill_uses_new_category(self):
        # "Causal Inference & ML" → new_category "Causal Inference"
        # DOMAIN_BACKFILL["Causal Inference & ML"] exists directly, so old_category wins
        r = {"category": "Causal Inference & ML", "type": "Article"}
        transform_resource(r)
        assert r["domain"] == "Causal Inference"

    def test_domain_backfill_for_programming(self):
        r = {"category": "Programming", "type": "Tutorial"}
        transform_resource(r)
        assert r["domain"] == "Programming"

    def test_unknown_category_domain_falls_back_via_macro(self):
        # Unknown category → macro "Strategy" → macro_to_domain["Strategy"] = "Product Sense"
        r = {"category": "Unknown Niche Topic", "type": "Article"}
        transform_resource(r)
        assert r["domain"] == "Product Sense"


# ──────────────────────────────────────────────
# Difficulty normalization
# ──────────────────────────────────────────────

class TestDifficultyNormalization:
    def test_beginner_lowercased(self):
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Beginner"}
        transform_resource(r)
        assert r["difficulty"] == "beginner"

    def test_advanced_lowercased(self):
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Advanced"}
        transform_resource(r)
        assert r["difficulty"] == "advanced"

    def test_intermediate_lowercased(self):
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Intermediate"}
        transform_resource(r)
        assert r["difficulty"] == "intermediate"

    def test_easy_maps_to_beginner(self):
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Easy"}
        transform_resource(r)
        assert r["difficulty"] == "beginner"

    def test_hard_maps_to_advanced(self):
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Hard"}
        transform_resource(r)
        assert r["difficulty"] == "advanced"

    def test_missing_difficulty_no_crash(self):
        r = {"category": "Machine Learning", "type": "Course"}
        result = transform_resource(r)
        assert "difficulty" not in result

    def test_unrecognized_difficulty_unchanged(self):
        # "Expert" doesn't match any keyword → left as-is
        r = {"category": "Machine Learning", "type": "Course", "difficulty": "Expert"}
        transform_resource(r)
        assert r["difficulty"] == "Expert"


# ──────────────────────────────────────────────
# In-place mutation
# ──────────────────────────────────────────────

class TestInPlaceMutation:
    def test_returns_same_dict_object(self):
        r = {"category": "Causal Inference", "type": "Article"}
        returned = transform_resource(r)
        assert returned is r

    def test_original_dict_mutated(self):
        r = {"category": "AB Testing", "type": "Course"}
        transform_resource(r)
        # category should be updated in the original dict
        assert r["category"] == "A/B Testing"
