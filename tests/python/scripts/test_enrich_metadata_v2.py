"""Tests for pure helpers in scripts/enrich_metadata_v2.py.

Covers: compute_hash, get_item_id, needs_enrichment, calculate_confidence.
All are pure functions with no network/LLM dependency.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "enrich_metadata_v2.py"
_spec = importlib.util.spec_from_file_location("enrich_metadata_v2", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_metadata_v2"] = mod
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------

class TestComputeHash:

    def test_returns_16_char_hex(self):
        h = mod.compute_hash({"name": "DoubleML", "url": "https://x.com"})
        assert isinstance(h, str)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self):
        item = {"name": "A", "url": "https://a.com", "category": "ML"}
        assert mod.compute_hash(item) == mod.compute_hash(item)

    def test_different_content_different_hash(self):
        a = {"name": "Alpha", "url": "https://a.com"}
        b = {"name": "Beta",  "url": "https://b.com"}
        assert mod.compute_hash(a) != mod.compute_hash(b)

    def test_only_core_fields_compared(self):
        # model_score is NOT a core field — changes to it must not change hash
        a = {"name": "X", "url": "https://x.com", "model_score": 0.9}
        b = {"name": "X", "url": "https://x.com", "model_score": 0.1}
        assert mod.compute_hash(a) == mod.compute_hash(b)

    def test_empty_item_returns_hash(self):
        h = mod.compute_hash({})
        assert len(h) == 16


# ---------------------------------------------------------------------------
# get_item_id
# ---------------------------------------------------------------------------

class TestGetItemId:

    def test_prefers_name(self):
        assert mod.get_item_id({"name": "Pkg", "title": "Title", "url": "https://x.com"}) == "Pkg"

    def test_falls_back_to_title(self):
        assert mod.get_item_id({"title": "Paper Title", "url": "https://x.com"}) == "Paper Title"

    def test_falls_back_to_url(self):
        assert mod.get_item_id({"url": "https://x.com"}) == "https://x.com"

    def test_returns_unknown_for_empty(self):
        assert mod.get_item_id({}) == "unknown"

    def test_empty_name_falls_back(self):
        # Empty string is falsy — should fall back to title/url
        assert mod.get_item_id({"name": "", "title": "Title"}) == "Title"


# ---------------------------------------------------------------------------
# needs_enrichment
# ---------------------------------------------------------------------------

def _make_state(file_key: str, item_id: str, item: dict) -> dict:
    """Build a minimal state dict that says `item` was already enriched."""
    return {
        "items": {
            file_key: {
                item_id: {
                    "content_hash": mod.compute_hash(item),
                    "schema_version": mod.SCHEMA_VERSION,
                }
            }
        }
    }


class TestNeedsEnrichment:

    def test_new_item_needs_enrichment(self):
        item = {"name": "New", "url": "https://new.com"}
        assert mod.needs_enrichment(item, {}, "packages.json") is True

    def test_unchanged_item_does_not_need_enrichment(self):
        item = {"name": "Existing", "url": "https://x.com"}
        state = _make_state("packages.json", "Existing", item)
        assert mod.needs_enrichment(item, state, "packages.json") is False

    def test_content_change_triggers_enrichment(self):
        item_old = {"name": "Pkg", "url": "https://x.com", "description": "Old"}
        state = _make_state("packages.json", "Pkg", item_old)
        item_new = {"name": "Pkg", "url": "https://x.com", "description": "Updated!"}
        assert mod.needs_enrichment(item_new, state, "packages.json") is True

    def test_force_flag_always_enriches(self):
        item = {"name": "Existing", "url": "https://x.com"}
        state = _make_state("packages.json", "Existing", item)
        assert mod.needs_enrichment(item, state, "packages.json", force=True) is True

    def test_old_schema_version_triggers_enrichment(self):
        item = {"name": "Old", "url": "https://x.com"}
        state = {
            "items": {
                "packages.json": {
                    "Old": {
                        "content_hash": mod.compute_hash(item),
                        "schema_version": "0.1",  # old
                    }
                }
            }
        }
        assert mod.needs_enrichment(item, state, "packages.json") is True


# ---------------------------------------------------------------------------
# calculate_confidence
# ---------------------------------------------------------------------------

def _good_enrichment() -> dict:
    return {
        "summary": "A" * 60,
        "difficulty": "intermediate",
        "synthetic_questions": ["Q1?", "Q2?", "Q3?", "Q4?"],
        "tags": ["causal", "ml"],
        "best_for": ["researchers"],
    }


class TestCalculateConfidence:

    def test_full_enrichment_gives_high_confidence(self):
        score = mod.calculate_confidence(_good_enrichment(), {"name": "X"}, "packages")
        assert score >= 0.8

    def test_missing_synthetic_questions_reduces_score(self):
        e = _good_enrichment()
        e["synthetic_questions"] = []
        score = mod.calculate_confidence(e, {"name": "X"}, "packages")
        assert score < mod.calculate_confidence(_good_enrichment(), {"name": "X"}, "packages")

    def test_missing_summary_reduces_score(self):
        e = _good_enrichment()
        e["summary"] = ""
        score = mod.calculate_confidence(e, {"name": "X"}, "packages")
        assert score < mod.calculate_confidence(_good_enrichment(), {"name": "X"}, "packages")

    def test_invalid_difficulty_reduces_score(self):
        e = _good_enrichment()
        e["difficulty"] = "not-valid"
        score_bad = mod.calculate_confidence(e, {"name": "X"}, "packages")
        score_good = mod.calculate_confidence(_good_enrichment(), {"name": "X"}, "packages")
        assert score_bad < score_good

    def test_score_clamped_between_0_and_1(self):
        score = mod.calculate_confidence({}, {"name": "X"}, "packages")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# apply_enrichment
# ---------------------------------------------------------------------------

class TestApplyEnrichment:
    def test_base_field_applied(self):
        item = {"name": "X"}
        enrichment = {"difficulty": "intermediate", "summary": "A great tool"}
        mod.apply_enrichment(item, enrichment, "package")
        assert item["difficulty"] == "intermediate"
        assert item["summary"] == "A great tool"

    def test_extended_field_for_package(self):
        item = {"name": "X"}
        enrichment = {"api_complexity": "low", "maintenance_status": "active"}
        mod.apply_enrichment(item, enrichment, "package")
        assert item["api_complexity"] == "low"
        assert item["maintenance_status"] == "active"

    def test_extended_field_for_paper(self):
        item = {"name": "X"}
        enrichment = {"key_findings": ["finding 1", "finding 2"], "methodology_tags": ["RDD"]}
        mod.apply_enrichment(item, enrichment, "paper")
        assert item["key_findings"] == ["finding 1", "finding 2"]

    def test_extended_field_not_applied_to_wrong_type(self):
        item = {"name": "X"}
        enrichment = {"key_findings": ["finding"]}  # paper-only field
        mod.apply_enrichment(item, enrichment, "package")
        assert "key_findings" not in item

    def test_empty_enrichment_no_change(self):
        item = {"name": "X", "category": "ML"}
        mod.apply_enrichment(item, {}, "package")
        assert item == {"name": "X", "category": "ML"}

    def test_empty_extended_field_not_applied(self):
        item = {"name": "X"}
        enrichment = {"implements_paper": ""}  # empty → not applied
        mod.apply_enrichment(item, enrichment, "package")
        assert "implements_paper" not in item

    def test_none_base_field_not_applied(self):
        item = {"name": "X"}
        # Base fields are always applied even if None (field in enrichment dict check only)
        enrichment = {"difficulty": None}
        mod.apply_enrichment(item, enrichment, "package")
        # The function applies if key in enrichment — None gets applied for base fields
        assert "difficulty" in item

    def test_unknown_content_type_only_base_fields(self):
        item = {"name": "X"}
        enrichment = {"difficulty": "easy", "speaker_expertise": "expert"}
        mod.apply_enrichment(item, enrichment, "unknown_type")
        assert item["difficulty"] == "easy"
        assert "speaker_expertise" not in item  # talk-only, not in unknown_type


# ---------------------------------------------------------------------------
# update_state
# ---------------------------------------------------------------------------

class TestUpdateState:
    def test_creates_items_key_when_missing(self):
        state = {}
        mod.update_state(state, "packages", {"name": "ToolA"}, 0.9)
        assert "items" in state
        assert "packages" in state["items"]

    def test_stores_content_hash(self):
        item = {"name": "ToolA", "description": "A great tool"}
        state = {}
        mod.update_state(state, "packages", item, 0.85)
        record = state["items"]["packages"]["ToolA"]
        assert "content_hash" in record
        assert len(record["content_hash"]) == 16

    def test_stores_confidence(self):
        state = {}
        mod.update_state(state, "packages", {"name": "T"}, 0.75)
        assert state["items"]["packages"]["T"]["confidence"] == pytest.approx(0.75)

    def test_enriched_at_is_iso_string(self):
        state = {}
        mod.update_state(state, "packages", {"name": "T"}, 0.5)
        ts = state["items"]["packages"]["T"]["enriched_at"]
        assert "T" in ts  # ISO format contains T separator

    def test_second_update_overwrites(self):
        state = {}
        mod.update_state(state, "packages", {"name": "T"}, 0.5)
        mod.update_state(state, "packages", {"name": "T"}, 0.9)
        assert state["items"]["packages"]["T"]["confidence"] == pytest.approx(0.9)
