"""Tests for scripts/recategorize_talks.py :: get_new_subtopic.

Covers macro_category branches not exercised by the _helpers file:
  - AI & Technology (AI & Labor, ML Engineering, Recommendations, AI Research default)
  - Industry Economics (Energy & Climate, Other Industries, keep-current fallback)
  - Labor & Careers (Career Advice, Tech Strategy, Labor Economics default)
  - Platforms & Markets: Tech Interviews and Platform Strategy default
  - Priority ordering within Causal (ML keyword beats experiment keyword)
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(script_name, alias):
    path = _REPO_ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[alias] = m
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        spec.loader.exec_module(m)
    return m


_mod = _load("recategorize_talks.py", "recategorize_talks_mod")
get_new_subtopic = _mod.get_new_subtopic


def _talk(name="", desc="", macro="", subtopic="existing", talk_type="Talk"):
    return {
        "name": name,
        "description": desc,
        "macro_category": macro,
        "subtopic": subtopic,
        "type": talk_type,
    }


# ---------------------------------------------------------------------------
# AI & Technology branch
# ---------------------------------------------------------------------------

class TestAITechnology:
    def test_ai_labor_keyword_in_name(self):
        t = _talk(name="How automation affects labor markets", macro="AI & Technology")
        assert get_new_subtopic(t) == "AI & Labor"

    def test_ai_labor_keyword_autor(self):
        t = _talk(desc="David Autor on the future of work and jobs", macro="AI & Technology")
        assert get_new_subtopic(t) == "AI & Labor"

    def test_ml_engineering_mlops_keyword(self):
        t = _talk(name="MLOps and production deployment", macro="AI & Technology")
        assert get_new_subtopic(t) == "ML Engineering"

    def test_ml_engineering_infrastructure_keyword(self):
        t = _talk(desc="ML infrastructure at scale", macro="AI & Technology")
        assert get_new_subtopic(t) == "ML Engineering"

    def test_recommendations_keyword(self):
        t = _talk(desc="Personalization and recommendation systems", macro="AI & Technology")
        assert get_new_subtopic(t) == "Recommendations"

    def test_ai_research_default(self):
        # No labor/mlops/recommendation keywords — falls to default
        t = _talk(name="GPT-4 architecture overview", macro="AI & Technology")
        assert get_new_subtopic(t) == "AI Research"


# ---------------------------------------------------------------------------
# Industry Economics branch
# ---------------------------------------------------------------------------

class TestIndustryEconomics:
    def test_energy_climate_keyword(self):
        t = _talk(desc="Electricity markets and climate policy", macro="Industry Economics", subtopic="Energy")
        assert get_new_subtopic(t) == "Energy & Climate"

    def test_energy_utility_keyword(self):
        t = _talk(name="Utility regulation and energy", macro="Industry Economics", subtopic="Old")
        assert get_new_subtopic(t) == "Energy & Climate"

    def test_healthcare_keyword(self):
        t = _talk(desc="Healthcare insurance economics", macro="Industry Economics", subtopic="Old")
        assert get_new_subtopic(t) == "Other Industries"

    def test_defense_keyword(self):
        t = _talk(desc="Defense and cyber security procurement", macro="Industry Economics", subtopic="Old")
        assert get_new_subtopic(t) == "Other Industries"

    def test_keep_current_subtopic_when_no_keyword_match(self):
        # "Gig Economy" subtopic — nothing matches energy/healthcare, should return current
        t = _talk(name="Gig economy overview", macro="Industry Economics", subtopic="Gig Economy")
        assert get_new_subtopic(t) == "Gig Economy"

    def test_keep_tech_industry_subtopic(self):
        t = _talk(name="Big tech overview", macro="Industry Economics", subtopic="Tech Industry")
        assert get_new_subtopic(t) == "Tech Industry"


# ---------------------------------------------------------------------------
# Labor & Careers branch
# ---------------------------------------------------------------------------

class TestLaborCareers:
    def test_career_advice_keyword_career(self):
        t = _talk(desc="Career advice for new data scientists", macro="Labor & Careers")
        assert get_new_subtopic(t) == "Career Advice"

    def test_career_advice_keyword_interview(self):
        t = _talk(name="Data science interview prep", macro="Labor & Careers")
        assert get_new_subtopic(t) == "Career Advice"

    def test_career_advice_keyword_hire(self):
        t = _talk(desc="How companies hire economists", macro="Labor & Careers")
        assert get_new_subtopic(t) == "Career Advice"

    def test_tech_strategy_preserved(self):
        t = _talk(name="Platform strategy talk", macro="Labor & Careers", subtopic="Tech Strategy")
        assert get_new_subtopic(t) == "Tech Strategy"

    def test_labor_economics_default(self):
        t = _talk(name="Wage inequality over time", macro="Labor & Careers", subtopic="Other")
        assert get_new_subtopic(t) == "Labor Economics"


# ---------------------------------------------------------------------------
# Platforms & Markets: remaining branches
# ---------------------------------------------------------------------------

class TestPlatformsRemaining:
    def test_tech_interview_type(self):
        t = _talk(name="A conversation about pricing", macro="Platforms & Markets", talk_type="Interview")
        assert get_new_subtopic(t) == "Tech Interviews"

    def test_tech_interview_bajari_in_content(self):
        t = _talk(desc="Patrick Bajari on Amazon demand forecasting", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Tech Interviews"

    def test_platform_strategy_default(self):
        # No keyword from any earlier branch
        t = _talk(name="General platform talk", macro="Platforms & Markets")
        assert get_new_subtopic(t) == "Platform Strategy"


# ---------------------------------------------------------------------------
# Priority ordering edge cases
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    def test_ml_keyword_beats_experiment_in_causal(self):
        # "double ml" triggers ML & Causal before "experiment" triggers Experimentation
        t = _talk(desc="Double ML for experiment analysis", macro="Causal & Experimentation")
        assert get_new_subtopic(t) == "ML & Causal"

    def test_podcast_series_type_triggers_causal_podcasts(self):
        t = _talk(macro="Causal & Experimentation", talk_type="Podcast Series")
        assert get_new_subtopic(t) == "Causal Podcasts"

    def test_unknown_macro_returns_current_subtopic(self):
        t = _talk(name="Random talk", macro="Completely Unknown", subtopic="My Subtopic")
        assert get_new_subtopic(t) == "My Subtopic"
