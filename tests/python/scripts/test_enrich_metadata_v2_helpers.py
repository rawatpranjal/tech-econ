"""Bullshit tests for enrich_metadata_v2.py pure helpers.

Covers:
  - compute_hash: deterministic, changes on content change, truncated to 16 chars
  - get_item_id: prefers name, falls back to title, then url
  - needs_enrichment: force=True always True, unknown item True, hash mismatch True,
      schema version mismatch True, already-enriched False
  - calculate_confidence: full-quality starts at 1.0, deductions for missing fields
"""

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr: MagicMock()
    sys.modules[name] = m
    return m


for _dep in ["anthropic", "openai", "requests", "pydantic"]:
    if _dep not in sys.modules:
        _stub(_dep)

# pydantic.BaseModel stub needs to be a real class
import pydantic as _pydantic_stub
_pydantic_stub.BaseModel = object
_pydantic_stub.Field = MagicMock(return_value=None)
_pydantic_stub.validator = MagicMock(return_value=lambda f: f)

_spec = importlib.util.spec_from_file_location(
    "enrich_metadata_v2",
    _REPO_ROOT / "scripts" / "enrich_metadata_v2.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_metadata_v2"] = _mod
_spec.loader.exec_module(_mod)

compute_hash = _mod.compute_hash
get_item_id = _mod.get_item_id
needs_enrichment = _mod.needs_enrichment
calculate_confidence = _mod.calculate_confidence
SCHEMA_VERSION = _mod.SCHEMA_VERSION


# ──────────────────────────────────────────────
# compute_hash
# ──────────────────────────────────────────────

class TestComputeHash:
    def test_deterministic(self):
        item = {"name": "Tool A", "description": "Does stuff", "url": "https://example.com"}
        assert compute_hash(item) == compute_hash(item)

    def test_same_content_same_hash(self):
        a = {"name": "X", "description": "Desc", "tags": ["ml"]}
        b = {"name": "X", "description": "Desc", "tags": ["ml"]}
        assert compute_hash(a) == compute_hash(b)

    def test_changed_name_changes_hash(self):
        a = {"name": "Tool A"}
        b = {"name": "Tool B"}
        assert compute_hash(a) != compute_hash(b)

    def test_result_is_16_chars(self):
        item = {"name": "A", "url": "https://x.com"}
        assert len(compute_hash(item)) == 16

    def test_extra_fields_ignored(self):
        # Only core_fields matter: name, title, description, category, tags, url
        a = {"name": "X", "model_score": 0.9}
        b = {"name": "X", "model_score": 0.1}
        assert compute_hash(a) == compute_hash(b)

    def test_empty_item(self):
        h = compute_hash({})
        assert isinstance(h, str)
        assert len(h) == 16


# ──────────────────────────────────────────────
# get_item_id
# ──────────────────────────────────────────────

class TestGetItemId:
    def test_prefers_name(self):
        item = {"name": "Tool", "title": "Title", "url": "https://x.com"}
        assert get_item_id(item) == "Tool"

    def test_falls_back_to_title(self):
        item = {"title": "My Title", "url": "https://x.com"}
        assert get_item_id(item) == "My Title"

    def test_falls_back_to_url(self):
        item = {"url": "https://example.com"}
        assert get_item_id(item) == "https://example.com"

    def test_unknown_if_nothing(self):
        assert get_item_id({}) == "unknown"

    def test_empty_name_falls_through(self):
        item = {"name": "", "title": "Has Title"}
        # Empty string is falsy
        assert get_item_id(item) == "Has Title"


# ──────────────────────────────────────────────
# needs_enrichment
# ──────────────────────────────────────────────

class TestNeedsEnrichment:
    def _state_with_item(self, item, file_key="packages.json",
                          schema_version=None, confidence=0.9):
        from enrich_metadata_v2 import compute_hash, get_item_id, SCHEMA_VERSION as SV
        sv = schema_version or SV
        return {
            "items": {
                file_key: {
                    get_item_id(item): {
                        "content_hash": compute_hash(item),
                        "schema_version": sv,
                        "confidence": confidence,
                    }
                }
            }
        }

    def test_force_always_true(self):
        item = {"name": "X"}
        state = self._state_with_item(item)
        assert needs_enrichment(item, state, "packages.json", force=True) is True

    def test_unknown_item_needs_enrichment(self):
        item = {"name": "New Item"}
        assert needs_enrichment(item, {}, "packages.json") is True

    def test_unchanged_item_no_enrichment_needed(self):
        item = {"name": "Stable Item", "description": "Unchanged"}
        state = self._state_with_item(item)
        assert needs_enrichment(item, state, "packages.json") is False

    def test_changed_content_needs_enrichment(self):
        item = {"name": "Item", "description": "Old desc"}
        state = self._state_with_item(item)
        item_changed = {"name": "Item", "description": "New desc"}
        assert needs_enrichment(item_changed, state, "packages.json") is True

    def test_old_schema_version_needs_enrichment(self):
        item = {"name": "Item"}
        state = self._state_with_item(item, schema_version="0.1")
        assert needs_enrichment(item, state, "packages.json") is True

    def test_wrong_file_key_needs_enrichment(self):
        item = {"name": "Item"}
        state = self._state_with_item(item, file_key="other.json")
        # Looking under "packages.json" which doesn't have the item
        assert needs_enrichment(item, state, "packages.json") is True


# ──────────────────────────────────────────────
# calculate_confidence
# ──────────────────────────────────────────────

def _full_enrichment():
    return {
        "synthetic_questions": ["q1", "q2", "q3", "q4"],
        "summary": "A sufficiently long summary about this content item for testing.",
        "difficulty": "intermediate",
        "audience": ["Mid-DS", "Senior-DS"],
    }


class TestCalculateConfidence:
    def test_full_quality_high_score(self):
        e = _full_enrichment()
        score = calculate_confidence(e, {"name": "X"}, "resource")
        assert score >= 0.8

    def test_missing_questions_penalized(self):
        e = _full_enrichment()
        del e["synthetic_questions"]
        score = calculate_confidence(e, {"name": "X"}, "resource")
        assert score < calculate_confidence(_full_enrichment(), {"name": "X"}, "resource")

    def test_few_questions_small_penalty(self):
        e = _full_enrichment()
        e["synthetic_questions"] = ["q1", "q2"]  # less than 4
        score_few = calculate_confidence(e, {"name": "X"}, "resource")
        e2 = _full_enrichment()
        del e2["synthetic_questions"]
        score_none = calculate_confidence(e2, {"name": "X"}, "resource")
        assert score_few > score_none  # fewer is better than none

    def test_missing_summary_penalized(self):
        e = _full_enrichment()
        del e["summary"]
        score = calculate_confidence(e, {"name": "X"}, "resource")
        assert score < 1.0

    def test_short_summary_small_penalty(self):
        e = _full_enrichment()
        e["summary"] = "Short"
        score = calculate_confidence(e, {"name": "X"}, "resource")
        # Should be penalized but not as much as missing
        assert score < 1.0

    def test_invalid_difficulty_penalized(self):
        e = _full_enrichment()
        e["difficulty"] = "unknown_level"
        score = calculate_confidence(e, {"name": "X"}, "resource")
        assert score < calculate_confidence(_full_enrichment(), {"name": "X"}, "resource")

    def test_invalid_audience_penalized(self):
        e = _full_enrichment()
        e["audience"] = ["InvalidAudience"]
        score = calculate_confidence(e, {"name": "X"}, "resource")
        assert score < calculate_confidence(_full_enrichment(), {"name": "X"}, "resource")

    def test_paper_without_methodology_tags_penalized(self):
        e = _full_enrichment()
        score_no_method = calculate_confidence(e, {"name": "X"}, "paper")
        e["methodology_tags"] = ["diff-in-diff"]
        score_with = calculate_confidence(e, {"name": "X"}, "paper")
        assert score_with > score_no_method

    def test_package_without_primary_use_cases_penalized(self):
        e = _full_enrichment()
        score_no = calculate_confidence(e, {"name": "X"}, "package")
        e["primary_use_cases"] = ["regression"]
        score_with = calculate_confidence(e, {"name": "X"}, "package")
        assert score_with > score_no

    def test_score_clamped_to_unit_interval(self):
        # Worst possible enrichment should still be >= 0
        score = calculate_confidence({}, {}, "resource")
        assert 0.0 <= score <= 1.0

    def test_perfect_enrichment_at_most_1(self):
        e = _full_enrichment()
        e["methodology_tags"] = ["OLS"]
        score = calculate_confidence(e, {"name": "X"}, "paper")
        assert score <= 1.0


# ──────────────────────────────────────────────
# apply_enrichment
# ──────────────────────────────────────────────
apply_enrichment = _mod.apply_enrichment


class TestApplyEnrichment:
    def test_base_field_set(self):
        item = {}
        apply_enrichment(item, {"difficulty": "Intermediate"}, "package")
        assert item["difficulty"] == "Intermediate"

    def test_extended_paper_field_set(self):
        item = {}
        enrichment = {"methodology_tags": ["OLS", "IV"]}
        apply_enrichment(item, enrichment, "paper")
        assert item["methodology_tags"] == ["OLS", "IV"]

    def test_extended_field_skipped_for_wrong_type(self):
        item = {}
        enrichment = {"methodology_tags": ["OLS"]}
        apply_enrichment(item, enrichment, "resource")  # paper field in resource → not applied
        assert "methodology_tags" not in item

    def test_empty_extended_field_not_applied(self):
        # extended fields with falsy values are skipped
        item = {}
        apply_enrichment(item, {"related_packages": []}, "package")
        assert "related_packages" not in item

    def test_base_field_missing_from_enrichment_not_set(self):
        item = {}
        apply_enrichment(item, {}, "resource")
        assert "difficulty" not in item

    def test_overwrites_existing_field(self):
        item = {"difficulty": "Beginner"}
        apply_enrichment(item, {"difficulty": "Advanced"}, "resource")
        assert item["difficulty"] == "Advanced"

    def test_synthetic_questions_as_list(self):
        item = {}
        qs = ["What is this?", "How does it work?"]
        apply_enrichment(item, {"synthetic_questions": qs}, "package")
        assert item["synthetic_questions"] == qs

    def test_unknown_content_type_only_base_fields(self):
        item = {}
        apply_enrichment(item, {"difficulty": "Beginner", "role_type": "PM"}, "unknown_type")
        assert item.get("difficulty") == "Beginner"
        # extended fields only applied for known types
        assert "role_type" not in item
