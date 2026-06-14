"""Bullshit tests for reorganize_resources.py pure helpers.

Covers transform_resource:
  - Category consolidation via CATEGORY_MAPPING
  - Type normalization via TYPE_MAPPING + title-case fallback
  - macro_category assignment
  - difficulty normalization (beginner/intermediate/advanced)
  - Does not mutate original dict (in-place, so tests verify the new state)
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

for _dep in ["requests", "anthropic", "openai"]:
    if _dep not in sys.modules:
        m = types.ModuleType(_dep)
        m.__getattr__ = lambda attr: MagicMock()
        sys.modules[_dep] = m

_spec = importlib.util.spec_from_file_location(
    "reorganize_resources", _REPO_ROOT / "scripts" / "reorganize_resources.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["reorganize_resources"] = _mod
_spec.loader.exec_module(_mod)

transform_resource = _mod.transform_resource


class TestTransformResource:
    def test_category_mapping_applied(self):
        r = {"category": "Causal Inference & ML", "type": "Blog"}
        transform_resource(r)
        assert r["category"] == "Causal Inference"

    def test_unknown_category_preserved(self):
        r = {"category": "Some Niche Topic", "type": "Blog"}
        transform_resource(r)
        assert r["category"] == "Some Niche Topic"

    def test_type_mapping_blog_variants(self):
        for variant in ["Blog Post", "Blog Series", "Company Blog", "blog"]:
            r = {"category": "Machine Learning", "type": variant}
            transform_resource(r)
            assert r["type"] == "Blog", f"Expected 'Blog' for type={variant!r}, got {r['type']!r}"

    def test_type_unknown_gets_title_case(self):
        r = {"category": "Machine Learning", "type": "whitepaper"}
        transform_resource(r)
        assert r["type"] == "Whitepaper"

    def test_macro_category_assigned(self):
        r = {"category": "A/B Testing", "type": "Blog"}
        transform_resource(r)
        assert r.get("macro_category") is not None

    def test_macro_category_causal_inference(self):
        r = {"category": "Causal Inference", "type": "Blog"}
        transform_resource(r)
        assert r["macro_category"] == "Causal Methods"

    def test_macro_category_ab_testing(self):
        r = {"category": "A/B Testing", "type": "Blog"}
        transform_resource(r)
        assert r["macro_category"] == "Experimentation"

    def test_macro_category_fallback_strategy(self):
        r = {"category": "Unknown Niche", "type": "Blog"}
        transform_resource(r)
        assert r["macro_category"] == "Strategy"

    def test_difficulty_beginner_normalized(self):
        for val in ["Beginner", "beginner", "easy", "Easy"]:
            r = {"category": "Machine Learning", "type": "Blog", "difficulty": val}
            transform_resource(r)
            assert r["difficulty"] == "beginner", f"Expected 'beginner' for {val!r}"

    def test_difficulty_advanced_normalized(self):
        for val in ["Advanced", "advanced", "hard", "Hard"]:
            r = {"category": "Machine Learning", "type": "Blog", "difficulty": val}
            transform_resource(r)
            assert r["difficulty"] == "advanced", f"Expected 'advanced' for {val!r}"

    def test_difficulty_intermediate_normalized(self):
        for val in ["Intermediate", "intermediate", "medium"]:
            r = {"category": "Machine Learning", "type": "Blog", "difficulty": val}
            transform_resource(r)
            assert r["difficulty"] == "intermediate"

    def test_missing_difficulty_not_added(self):
        r = {"category": "Machine Learning", "type": "Blog"}
        transform_resource(r)
        assert "difficulty" not in r

    def test_domain_backfilled_when_missing(self):
        r = {"category": "Causal Inference", "type": "Blog"}
        transform_resource(r)
        assert r.get("domain") is not None

    def test_existing_domain_preserved(self):
        r = {"category": "Causal Inference", "type": "Blog", "domain": "My Domain"}
        transform_resource(r)
        assert r["domain"] == "My Domain"

    def test_ab_testing_mapped_before_category_consolidation(self):
        # "A/B Testing Fundamentals" maps to "A/B Testing" → "Experimentation"
        r = {"category": "A/B Testing Fundamentals", "type": "Blog"}
        transform_resource(r)
        assert r["category"] == "A/B Testing"
        assert r["macro_category"] == "Experimentation"
