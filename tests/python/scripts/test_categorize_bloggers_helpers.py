"""Tests for pure helpers in scripts/categorize_bloggers.py.

Covers: categorize_blogger (keyword-based classifier).
No I/O is performed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "categorize_bloggers.py"
_spec = importlib.util.spec_from_file_location("categorize_bloggers", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["categorize_bloggers"] = mod
_spec.loader.exec_module(mod)

categorize_blogger = mod.categorize_blogger


class TestCategorizeBlogger:

    def test_manual_mapping_takes_priority(self):
        # "Nick Huntington-Klein" is hard-coded in BLOGGER_TOPICS
        blog = {"name": "Nick Huntington-Klein", "topic_tags": [], "description": ""}
        assert categorize_blogger(blog) == "Causal Inference"

    def test_causal_keyword_in_tags(self):
        blog = {"name": "Unknown Blogger", "topic_tags": ["causal", "did"], "description": ""}
        assert categorize_blogger(blog) == "Causal Inference"

    def test_treatment_effect_in_tags(self):
        blog = {"name": "Nobody", "topic_tags": ["treatment effect", "policy"], "description": ""}
        assert categorize_blogger(blog) == "Causal Inference"

    def test_machine_learning_keyword(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "deep learning and neural networks"}
        assert categorize_blogger(blog) == "Machine Learning & AI"

    def test_llm_keyword(self):
        blog = {"name": "Nobody", "topic_tags": ["llm", "transformers"], "description": ""}
        assert categorize_blogger(blog) == "Machine Learning & AI"

    def test_experimentation_keyword(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "a/b test methodology"}
        assert categorize_blogger(blog) == "Experimentation"

    def test_randomized_trial_keyword(self):
        blog = {"name": "Nobody", "topic_tags": ["randomized"], "description": ""}
        assert categorize_blogger(blog) == "Experimentation"

    def test_growth_keyword(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "growth and product analytics"}
        assert categorize_blogger(blog) == "Growth & Product"

    def test_platform_keyword(self):
        blog = {"name": "Nobody", "topic_tags": ["platform"], "description": "network effect analysis"}
        assert categorize_blogger(blog) == "Platform Economics"

    def test_economics_keyword(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "economic policy research"}
        assert categorize_blogger(blog) == "Economics & Research"

    def test_fallback_for_no_match(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "visualization tips for beginners"}
        assert categorize_blogger(blog) == "Data Science & Analytics"

    def test_missing_keys_do_not_raise(self):
        # Minimal dict — no tags or description
        blog = {"name": "Nobody"}
        result = categorize_blogger(blog)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_blog_dict_returns_fallback(self):
        result = categorize_blogger({})
        assert result == "Data Science & Analytics"

    def test_case_insensitive_description(self):
        blog = {"name": "Nobody", "topic_tags": [], "description": "CAUSAL INFERENCE paper"}
        assert categorize_blogger(blog) == "Causal Inference"
