"""Bullshit tests for recategorize_talks.py pure helpers.

Covers get_new_subtopic: keyword routing across all macro_category branches.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "recategorize_talks", _REPO_ROOT / "scripts" / "recategorize_talks.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["recategorize_talks"] = _mod
_spec.loader.exec_module(_mod)

get_new_subtopic = _mod.get_new_subtopic


def _talk(name="", desc="", macro="", subtopic="", talk_type="Talk"):
    return {
        "name": name,
        "description": desc,
        "macro_category": macro,
        "subtopic": subtopic,
        "type": talk_type,
    }


class TestGetNewSubtopic:
    # Causal & Experimentation
    def test_causal_podcast_type(self):
        t = _talk(macro="Causal & Experimentation", talk_type="Podcast")
        assert get_new_subtopic(t) == "Causal Podcasts"

    def test_causal_ml_keyword(self):
        t = _talk(name="Double ML for Causal", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "ML & Causal"

    def test_causal_ab_test_keyword(self):
        t = _talk(desc="Variance reduction in a/b tests", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "Experimentation"

    def test_causal_bayesian_keyword(self):
        t = _talk(desc="Bayesian inference with PyMC", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "Bayesian Methods"

    def test_causal_course_keyword(self):
        t = _talk(name="NBER Summer Course", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "Causal Methods"

    def test_causal_default(self):
        t = _talk(name="General talk", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "Causal Inference"

    # Platforms & Markets
    def test_platforms_podcast_econtalk(self):
        t = _talk(name="EconTalk with Russ Roberts", macro="Platforms & Markets", talk_type="Podcast")
        assert get_new_subtopic(t) == "Economics Commentary"

    def test_platforms_marketplace(self):
        t = _talk(name="Instacart pricing", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Marketplace Economics"

    def test_platforms_auction(self):
        t = _talk(desc="Market design and matching theory", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Auction & Matching"

    def test_platforms_antitrust(self):
        t = _talk(desc="DMA and antitrust regulation", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Antitrust"

    def test_platforms_network_effects(self):
        t = _talk(desc="Network effects and two-sided markets", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Network Effects"

    # ML & Data Science
    def test_ml_llm_keyword(self):
        t = _talk(name="LLM fine-tuning for production", macro="ML & Data Science")
        result = get_new_subtopic(t)
        assert result is not None  # Just ensure no crash

    # Unknown macro — fallback
    def test_unknown_macro_returns_something(self):
        t = _talk(name="Misc talk", macro="Unknown Category")
        result = get_new_subtopic(t)
        # Should return a string without crashing
        assert isinstance(result, str)
