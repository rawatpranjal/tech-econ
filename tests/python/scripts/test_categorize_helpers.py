"""Bullshit tests for categorize_bloggers.py and categorize_industry_blogs.py.

Covers keyword-dispatch logic in categorize_blogger and get_sector.
Both are pure functions with no filesystem / network.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_bloggers = _load("categorize_bloggers", _REPO_ROOT / "scripts" / "categorize_bloggers.py")
_industry = _load("categorize_industry_blogs", _REPO_ROOT / "scripts" / "categorize_industry_blogs.py")

categorize_blogger = _bloggers.categorize_blogger
get_sector = _industry.get_sector


# ──────────────────────────────────────────────
# categorize_blogger
# ──────────────────────────────────────────────

class TestCategorizeBlogger:
    def test_causal_keyword_in_tags(self):
        blog = {"name": "Unknown", "topic_tags": ["causal inference"], "description": ""}
        assert categorize_blogger(blog) == "Causal Inference"

    def test_ml_keyword_in_description(self):
        blog = {"name": "Unknown", "topic_tags": [], "description": "deep learning and llm research"}
        assert categorize_blogger(blog) == "Machine Learning & AI"

    def test_experiment_keyword(self):
        blog = {"name": "Unknown", "topic_tags": ["a/b test"], "description": ""}
        assert categorize_blogger(blog) == "Experimentation"

    def test_growth_keyword(self):
        blog = {"name": "Unknown", "topic_tags": [], "description": "growth and product monetization"}
        assert categorize_blogger(blog) == "Growth & Product"

    def test_platform_keyword(self):
        blog = {"name": "Unknown", "topic_tags": [], "description": "network effect and platform dynamics"}
        assert categorize_blogger(blog) == "Platform Economics"

    def test_economics_keyword(self):
        blog = {"name": "Unknown", "topic_tags": [], "description": "market design and policy research"}
        assert categorize_blogger(blog) == "Economics & Research"

    def test_fallback_default(self):
        blog = {"name": "Unknown", "topic_tags": [], "description": "general analytics blog"}
        assert categorize_blogger(blog) == "Data Science & Analytics"

    def test_empty_blog(self):
        result = categorize_blogger({})
        assert isinstance(result, str)
        assert len(result) > 0


# ──────────────────────────────────────────────
# get_sector
# ──────────────────────────────────────────────

class TestGetSector:
    def test_marketplace_keyword(self):
        blog = {"name": "TestBlog", "description": "marketplace and rideshare analytics"}
        assert get_sector(blog) == "Marketplaces"

    def test_streaming_keyword(self):
        blog = {"name": "TestBlog", "description": "streaming recommendation systems"}
        assert get_sector(blog) == "Streaming"

    def test_adtech_keyword(self):
        blog = {"name": "TestBlog", "description": "advertising attribution and mmm"}
        assert get_sector(blog) == "AdTech"

    def test_fintech_keyword(self):
        blog = {"name": "TestBlog", "description": "payment systems and fintech"}
        assert get_sector(blog) == "Fintech"

    def test_creator_economy_keyword(self):
        blog = {"name": "TestBlog", "description": "creator economy and passion economy"}
        assert get_sector(blog) == "Creator Economy"

    def test_operations_research_keyword(self):
        blog = {"name": "TestBlog", "description": "operations research scheduling solver"}
        assert get_sector(blog) == "Operations Research"

    def test_fallback_default(self):
        blog = {"name": "SomeAcademicBlog", "description": "general research papers"}
        assert get_sector(blog) == "Research & Academia"

    def test_empty_blog_returns_string(self):
        result = get_sector({})
        assert isinstance(result, str)
