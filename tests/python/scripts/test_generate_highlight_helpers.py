"""Bullshit tests for generate-highlight.py pure helpers.

Covers: select_topic (override, uncovered, reset-on-all-covered),
        find_related_packages (keyword matching, max-5, short-word skip)
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate-highlight.py"

_spec = importlib.util.spec_from_file_location("generate_highlight", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_highlight"] = mod
_spec.loader.exec_module(mod)

select_topic = mod.select_topic
find_related_packages = mod.find_related_packages


TOPICS = [
    {"id": "causal", "name": "Causal Inference", "description": ""},
    {"id": "ml", "name": "Machine Learning", "description": ""},
    {"id": "exp", "name": "Experimentation", "description": ""},
]


class TestSelectTopic:
    def test_override_by_id(self):
        result = select_topic(TOPICS, {}, override="ml")
        assert result["id"] == "ml"

    def test_override_by_name_case_insensitive(self):
        result = select_topic(TOPICS, {}, override="causal inference")
        assert result["id"] == "causal"

    def test_override_not_found_returns_random(self):
        # Falls through to uncovered selection — random but not None
        result = select_topic(TOPICS, {}, override="nonexistent")
        assert result in TOPICS

    def test_uncovered_topics_selected(self):
        history = {"covered": ["causal", "ml"]}
        result = select_topic(TOPICS, history)
        assert result["id"] == "exp"

    def test_all_covered_resets_and_picks(self):
        history = {"covered": ["causal", "ml", "exp"]}
        result = select_topic(TOPICS, history)
        # History should be reset
        assert history["covered"] == []
        assert result in TOPICS

    def test_empty_history_picks_from_all(self):
        result = select_topic(TOPICS, {})
        assert result in TOPICS

    def test_empty_covered_list_picks_from_all(self):
        result = select_topic(TOPICS, {"covered": []})
        assert result in TOPICS


PACKAGES = [
    {"name": "DoubleML", "description": "Double machine learning for causal inference"},
    {"name": "EconML", "description": "Causal ML library from Microsoft"},
    {"name": "pandas", "description": "Data manipulation library"},
    {"name": "statsmodels", "description": "Statistical models estimation"},
    {"name": "scikit-learn", "description": "Machine learning in Python"},
    {"name": "linearmodels", "description": "Linear panel models for econometrics"},
]


class TestFindRelatedPackages:
    def test_keyword_match_in_description(self):
        topic = {"name": "Causal Inference", "description": ""}
        result = find_related_packages(topic, PACKAGES)
        names = [p["name"] for p in result]
        assert "DoubleML" in names

    def test_keyword_match_in_name(self):
        topic = {"name": "Machine Learning", "description": ""}
        result = find_related_packages(topic, PACKAGES)
        names = [p["name"] for p in result]
        assert "scikit-learn" in names or "EconML" in names

    def test_max_5_results(self):
        topic = {"name": "models statistical machine causal linear", "description": ""}
        result = find_related_packages(topic, PACKAGES)
        assert len(result) <= 5

    def test_no_match_returns_empty(self):
        topic = {"name": "Astrophysics Quantum Field", "description": ""}
        result = find_related_packages(topic, PACKAGES)
        assert result == []

    def test_short_keywords_skipped(self):
        # Keywords with len <= 3 are skipped (e.g., "for", "the", "and")
        topic = {"name": "for the and", "description": ""}
        result = find_related_packages(topic, PACKAGES)
        assert result == []

    def test_result_is_subset_of_input(self):
        topic = {"name": "Causal Inference Machine Learning", "description": "econometrics"}
        result = find_related_packages(topic, PACKAGES)
        for p in result:
            assert p in PACKAGES


# ──────────────────────────────────────────────
# find_related_resources
# ──────────────────────────────────────────────

find_related_resources = mod.find_related_resources

RESOURCES = [
    {"name": "Causal Inference Guide", "description": "A guide to causal inference methods"},
    {"name": "Machine Learning Tutorial", "description": "Learn machine learning basics"},
    {"name": "Bayesian Statistics Course", "description": "Bayesian methods for econometrics"},
    {"name": "Python Intro", "description": "Introduction to Python programming"},
    {"name": "SQL Basics", "description": "Database query language"},
    {"name": "R Programming", "description": "Statistical computing with R"},
]


class TestFindRelatedResources:
    def test_keyword_match_in_name(self):
        topic = {"name": "Causal Inference", "description": ""}
        result = find_related_resources(topic, RESOURCES)
        names = [r["name"] for r in result]
        assert "Causal Inference Guide" in names

    def test_keyword_match_in_description(self):
        topic = {"name": "Econometrics", "description": "bayesian"}
        result = find_related_resources(topic, RESOURCES)
        names = [r["name"] for r in result]
        assert "Bayesian Statistics Course" in names

    def test_max_5_results(self):
        topic = {"name": "Statistics Machine Learning Causal Bayesian Python", "description": ""}
        result = find_related_resources(topic, RESOURCES)
        assert len(result) <= 5

    def test_short_words_skipped(self):
        topic = {"name": "for the and", "description": ""}
        result = find_related_resources(topic, RESOURCES)
        assert result == []

    def test_empty_resources_returns_empty(self):
        topic = {"name": "Causal Inference", "description": ""}
        assert find_related_resources(topic, []) == []

    def test_result_subset_of_input(self):
        topic = {"name": "Machine Learning", "description": ""}
        result = find_related_resources(topic, RESOURCES)
        for r in result:
            assert r in RESOURCES
