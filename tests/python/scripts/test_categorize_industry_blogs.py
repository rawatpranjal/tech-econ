"""Tests for scripts/categorize_industry_blogs.py :: get_sector.

Focuses on the description-keyword fallback paths and edge cases
not already covered by test_categorize_industry_blogs_helpers.py.
The _helpers file validates individual keyword hits; this file
validates: name-mapping priority over description, boundary tokens
(e.g. "ad " vs "ads "), and mutual-exclusion ordering.
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


_mod = _load("categorize_industry_blogs.py", "categorize_industry_blogs_mod")
get_sector = _mod.get_sector


def _blog(name="Unknown Co", desc=""):
    return {"name": name, "description": desc}


# ---------------------------------------------------------------------------
# Name-mapping wins over description keywords
# ---------------------------------------------------------------------------

class TestNameMappingPriority:
    def test_name_match_overrides_desc_keyword(self):
        # "Stripe" maps to Fintech via name; desc says "marketplace" → name wins
        blog = _blog(name="Stripe Engineering", desc="marketplace payments platform")
        assert get_sector(blog) == "Fintech"

    def test_name_match_partial_substring(self):
        # "DoorDash Engineering Blog" contains "DoorDash" → Marketplaces
        blog = _blog(name="DoorDash Engineering Blog", desc="")
        assert get_sector(blog) == "Marketplaces"

    def test_name_match_case_insensitive_google(self):
        # SECTOR_MAPPING has "Google" → AdTech; name is lower-case
        blog = _blog(name="google research blog", desc="")
        assert get_sector(blog) == "AdTech"


# ---------------------------------------------------------------------------
# Description keyword fallback — AdTech boundary tokens
# ---------------------------------------------------------------------------

class TestAdTechBoundaryTokens:
    def test_ad_space_keyword_matches(self):
        # "ad " (with trailing space) is one of the AdTech keywords
        blog = _blog(name="Unknown", desc="we run ad networks for publishers")
        assert get_sector(blog) == "AdTech"

    def test_ads_space_keyword_matches(self):
        blog = _blog(name="Unknown", desc="programmatic ads bidding platform")
        assert get_sector(blog) == "AdTech"

    def test_advertising_keyword_matches(self):
        blog = _blog(name="Unknown", desc="digital advertising attribution")
        assert get_sector(blog) == "AdTech"

    def test_media_mix_keyword_matches(self):
        blog = _blog(name="Unknown", desc="media mix modeling for marketers")
        assert get_sector(blog) == "AdTech"


# ---------------------------------------------------------------------------
# Description keyword fallback — other sectors
# ---------------------------------------------------------------------------

class TestDescriptionFallbacks:
    def test_rideshare_keyword(self):
        blog = _blog(name="Unknown", desc="rideshare driver dispatch algorithm")
        assert get_sector(blog) == "Marketplaces"

    def test_delivery_keyword(self):
        blog = _blog(name="Unknown", desc="last-mile delivery routing")
        assert get_sector(blog) == "Marketplaces"

    def test_banking_keyword(self):
        blog = _blog(name="Unknown", desc="banking infrastructure for fintechs")
        assert get_sector(blog) == "Fintech"

    def test_passion_economy_keyword(self):
        blog = _blog(name="Unknown", desc="building in the passion economy")
        assert get_sector(blog) == "Creator Economy"

    def test_gurobi_solver_keyword(self):
        blog = _blog(name="Unknown", desc="gurobi solver for logistics planning")
        assert get_sector(blog) == "Operations Research"

    def test_cplex_keyword(self):
        blog = _blog(name="Unknown", desc="cplex integer programming tutorial")
        assert get_sector(blog) == "Operations Research"

    def test_aggregation_theory_keyword(self):
        blog = _blog(name="Unknown", desc="aggregation theory and platform strategy")
        assert get_sector(blog) == "VC & Strategy"

    def test_fallback_no_match(self):
        blog = _blog(name="Academic Blog", desc="general statistics and econometrics")
        assert get_sector(blog) == "Research & Academia"
