"""Tests for pure helpers in scripts/categorize_industry_blogs.py.

Covers: get_sector (keyword-based sector classifier).
No I/O is performed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "categorize_industry_blogs.py"
_spec = importlib.util.spec_from_file_location("categorize_industry_blogs", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["categorize_industry_blogs"] = mod
_spec.loader.exec_module(mod)

get_sector = mod.get_sector


class TestGetSector:

    def test_manual_mapping_by_name(self):
        # "Uber" is in SECTOR_MAPPING → Marketplaces
        blog = {"name": "Uber Engineering", "description": ""}
        assert get_sector(blog) == "Marketplaces"

    def test_manual_mapping_case_insensitive(self):
        # mapping checks name.lower() contains pattern.lower()
        blog = {"name": "NETFLIX Tech Blog", "description": ""}
        assert get_sector(blog) == "Streaming"

    def test_marketplace_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "we run a marketplace for gig workers"}
        assert get_sector(blog) == "Marketplaces"

    def test_streaming_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "recommendation system for streaming content"}
        assert get_sector(blog) == "Streaming"

    def test_social_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "social network effect analysis"}
        assert get_sector(blog) == "Social Media"

    def test_ecommerce_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "ecommerce and online shopping platform"}
        assert get_sector(blog) == "E-commerce"

    def test_adtech_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "advertising attribution and media mix modeling"}
        assert get_sector(blog) == "AdTech"

    def test_fintech_keyword_in_description(self):
        blog = {"name": "SomeCompany", "description": "payment processing and fintech solutions"}
        assert get_sector(blog) == "Fintech"

    def test_creator_economy_keyword(self):
        blog = {"name": "SomeCompany", "description": "creator economy platform"}
        assert get_sector(blog) == "Creator Economy"

    def test_operations_research_keyword(self):
        blog = {"name": "SomeCompany", "description": "operations research and scheduling optimization"}
        assert get_sector(blog) == "Operations Research"

    def test_vc_strategy_keyword(self):
        blog = {"name": "SomeCompany", "description": "venture capital and aggregation strategy"}
        assert get_sector(blog) == "VC & Strategy"

    def test_fallback_for_no_match(self):
        blog = {"name": "AcademicBlog", "description": "economics research findings"}
        assert get_sector(blog) == "Research & Academia"

    def test_missing_keys_do_not_raise(self):
        blog = {"name": "SomeCompany"}
        result = get_sector(blog)
        assert isinstance(result, str)

    def test_empty_dict_returns_fallback(self):
        result = get_sector({})
        assert result == "Research & Academia"

    def test_sector_is_string_for_any_input(self):
        for desc in ["", "unknown", "analytics platform"]:
            result = get_sector({"name": "Co", "description": desc})
            assert isinstance(result, str) and len(result) > 0
