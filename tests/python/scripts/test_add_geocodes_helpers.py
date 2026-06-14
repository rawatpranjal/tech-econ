"""Bullshit tests for add_geocodes.py pure helpers.

Covers: find_coordinates — lookup table, partial matching, city fallback.
Pure function; no filesystem, no network.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "add_geocodes.py"

_spec = importlib.util.spec_from_file_location("add_geocodes", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["add_geocodes"] = mod
_spec.loader.exec_module(mod)

find_coordinates = mod.find_coordinates


# ──────────────────────────────────────────────
# find_coordinates
# ──────────────────────────────────────────────

class TestFindCoordinates:
    def test_exact_match_cambridge(self):
        result = find_coordinates("Cambridge, MA")
        assert result is not None
        lat, lng = result
        assert 40 < lat < 45
        assert -75 < lng < -70

    def test_exact_match_new_york(self):
        result = find_coordinates("New York, NY")
        assert result is not None

    def test_online_returns_none(self):
        assert find_coordinates("Online") is None

    def test_various_prefix_returns_none(self):
        assert find_coordinates("Various cities across the US") is None

    def test_none_returns_none(self):
        assert find_coordinates(None) is None

    def test_empty_string_returns_none(self):
        assert find_coordinates("") is None

    def test_returns_tuple_of_two_floats(self):
        result = find_coordinates("Boston, MA")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, (int, float)) for v in result)

    def test_partial_match_with_year(self):
        # "Cambridge, MA (2025)" should match via partial
        result = find_coordinates("Cambridge, MA (2025)")
        assert result is not None

    def test_city_fallback_matching(self):
        # "Boston" alone should match via city substring
        result = find_coordinates("Boston")
        assert result is not None

    def test_unknown_location_returns_none(self):
        result = find_coordinates("Atlantis, Underwater")
        assert result is None

    def test_stanford_gbs(self):
        result = find_coordinates("Stanford GSB")
        assert result is not None
        lat, lng = result
        assert 35 < lat < 40  # Bay Area

    def test_latitude_longitude_sign(self):
        # US locations have negative longitude
        result = find_coordinates("Chicago, IL")
        assert result is not None
        lat, lng = result
        assert lng < 0  # Western hemisphere
        assert lat > 0  # Northern hemisphere
