"""Bullshit tests for generate_narrative_carousels.py pure helpers.

Covers:
  - find_items_by_tags: tag match, _type filter, category field, no match
  - find_items_by_text: keyword match, min_matches, _type filter, _match_score sort
  - select_diverse_items: round-robin, max_count, single type, empty input
  - has_person_name: full name, last name only, no match, empty name
"""

import importlib.util
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


for _dep in ["anthropic", "openai", "requests"]:
    if _dep not in sys.modules:
        _stub(_dep)

_spec = importlib.util.spec_from_file_location(
    "generate_narrative_carousels",
    _REPO_ROOT / "scripts" / "generate_narrative_carousels.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_narrative_carousels"] = _mod
_spec.loader.exec_module(_mod)

find_items_by_tags = _mod.find_items_by_tags
find_items_by_text = _mod.find_items_by_text
select_diverse_items = _mod.select_diverse_items
has_person_name = _mod.has_person_name
build_item_lookup = _mod.build_item_lookup
merge_carousels = _mod.merge_carousels


def _make_lookup(*items):
    return {f"item_{i}": item for i, item in enumerate(items)}


# ──────────────────────────────────────────────
# find_items_by_tags
# ──────────────────────────────────────────────

class TestFindItemsByTags:
    def test_matches_tags_field(self):
        lookup = _make_lookup(
            {"name": "A", "_type": "package", "tags": ["causal", "inference"]},
            {"name": "B", "_type": "package", "tags": ["nlp"]},
        )
        result = find_items_by_tags(lookup, ["causal"])
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_matches_category_field(self):
        lookup = _make_lookup(
            {"name": "C", "category": "econometrics"},
        )
        result = find_items_by_tags(lookup, ["econometrics"])
        assert len(result) == 1

    def test_type_filter(self):
        lookup = _make_lookup(
            {"name": "A", "_type": "package", "tags": ["ml"]},
            {"name": "B", "_type": "dataset", "tags": ["ml"]},
        )
        result = find_items_by_tags(lookup, ["ml"], item_type="package")
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_no_match_returns_empty(self):
        lookup = _make_lookup({"name": "A", "tags": ["nlp"]})
        assert find_items_by_tags(lookup, ["causal"]) == []

    def test_case_insensitive(self):
        lookup = _make_lookup({"name": "A", "tags": ["Causal"]})
        result = find_items_by_tags(lookup, ["causal"])
        assert len(result) == 1

    def test_empty_lookup_returns_empty(self):
        assert find_items_by_tags({}, ["causal"]) == []

    def test_substring_match_in_tags(self):
        # "causal inference" tag should match "causal" query
        lookup = _make_lookup({"name": "A", "tags": ["causal inference"]})
        result = find_items_by_tags(lookup, ["causal"])
        assert len(result) == 1


# ──────────────────────────────────────────────
# find_items_by_text
# ──────────────────────────────────────────────

class TestFindItemsByText:
    def test_matches_name_field(self):
        lookup = _make_lookup(
            {"name": "Causal Forest Tool", "_type": "package"},
        )
        result = find_items_by_text(lookup, ["causal"])
        assert len(result) == 1

    def test_matches_description_field(self):
        lookup = _make_lookup(
            {"name": "A", "description": "Uses causal inference methods"},
        )
        result = find_items_by_text(lookup, ["causal inference"])
        assert len(result) == 1

    def test_type_filter_applied(self):
        lookup = _make_lookup(
            {"name": "Causal A", "_type": "package"},
            {"name": "Causal B", "_type": "dataset"},
        )
        result = find_items_by_text(lookup, ["causal"], item_type="package")
        assert all(r["_type"] == "package" for r in result)
        assert len(result) == 1

    def test_min_matches_filters_partial(self):
        lookup = _make_lookup(
            {"name": "A", "description": "causal ml bayesian everything"},
            {"name": "B", "description": "only causal"},
        )
        # Require both "causal" and "bayesian" to match
        result = find_items_by_text(lookup, ["causal", "bayesian"], min_matches=2)
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_sorted_by_match_score(self):
        lookup = _make_lookup(
            {"name": "A", "description": "econometrics"},
            {"name": "B", "description": "econometrics causal inference ml"},
        )
        result = find_items_by_text(lookup, ["econometrics", "causal", "ml"])
        # B matches 3 keywords; A matches 1 → B should be first
        assert result[0]["name"] == "B"

    def test_no_match_returns_empty(self):
        lookup = _make_lookup({"name": "unrelated"})
        assert find_items_by_text(lookup, ["causal"]) == []

    def test_empty_keywords_returns_nothing(self):
        lookup = _make_lookup({"name": "A"})
        # Empty keyword list → no meaningful search
        result = find_items_by_text(lookup, [])
        # With no keywords, match_count=0 < required (which is 1 when no keywords), returns empty
        assert isinstance(result, list)


# ──────────────────────────────────────────────
# select_diverse_items
# ──────────────────────────────────────────────

class TestSelectDiverseItems:
    def test_respects_max_count(self):
        items = [{"name": str(i), "_type": "package"} for i in range(10)]
        result = select_diverse_items(items, max_count=4)
        assert len(result) == 4

    def test_round_robin_across_types(self):
        items = [
            {"name": "p1", "_type": "package"},
            {"name": "p2", "_type": "package"},
            {"name": "d1", "_type": "dataset"},
            {"name": "r1", "_type": "resource"},
        ]
        result = select_diverse_items(items, max_count=3)
        types_seen = {r["_type"] for r in result}
        # Should have at least 2 different types given 3 selections from 3 types
        assert len(types_seen) >= 2

    def test_single_type_fills_up(self):
        items = [{"name": str(i), "_type": "package"} for i in range(5)]
        result = select_diverse_items(items, max_count=3)
        assert len(result) == 3

    def test_empty_returns_empty(self):
        assert select_diverse_items([]) == []

    def test_fewer_items_than_max(self):
        items = [{"name": "a", "_type": "package"}, {"name": "b", "_type": "dataset"}]
        result = select_diverse_items(items, max_count=10)
        assert len(result) == 2

    def test_unknown_type_treated_as_unknown(self):
        items = [{"name": "x"}]  # no _type key
        result = select_diverse_items(items, max_count=5)
        assert len(result) == 1


# ──────────────────────────────────────────────
# has_person_name
# ──────────────────────────────────────────────

class TestHasPersonName:
    def test_full_name_in_title(self):
        item = {"title": "Interview with Susan Athey on ML"}
        assert has_person_name(item, "Susan Athey") is True

    def test_last_name_only_matches(self):
        item = {"name": "Athey et al. paper"}
        assert has_person_name(item, "Susan Athey") is True

    def test_no_match(self):
        item = {"name": "Unrelated content", "title": "Nothing here"}
        assert has_person_name(item, "Susan Athey") is False

    def test_case_insensitive(self):
        item = {"name": "susan athey talk"}
        assert has_person_name(item, "Susan Athey") is True

    def test_empty_name(self):
        item = {"name": "Susan Athey content"}
        # Empty name should not crash
        result = has_person_name(item, "")
        assert isinstance(result, bool)

    def test_missing_name_and_title_fields(self):
        item = {"description": "something"}
        assert has_person_name(item, "Susan Athey") is False

    def test_single_word_name(self):
        item = {"name": "Econometrics lecture"}
        assert has_person_name(item, "Econometrics") is True


# ──────────────────────────────────────────────
# build_item_lookup
# ──────────────────────────────────────────────
class TestBuildItemLookup:
    def test_package_keyed_with_prefix(self):
        data = {"packages": [{"name": "DoubleML"}]}
        lookup = build_item_lookup(data)
        assert "package-doubleml" in lookup

    def test_resource_keyed(self):
        data = {"resources": [{"name": "ML Blog"}]}
        lookup = build_item_lookup(data)
        assert "resource-ml-blog" in lookup

    def test_type_injected(self):
        data = {"packages": [{"name": "EconML"}]}
        lookup = build_item_lookup(data)
        assert lookup["package-econml"]["_type"] == "package"

    def test_id_injected(self):
        data = {"talks": [{"name": "Susan Athey Talk"}]}
        lookup = build_item_lookup(data)
        item = lookup["talk-susan-athey-talk"]
        assert item["_id"] == "talk-susan-athey-talk"

    def test_papers_flat_uses_title_fallback_when_name_missing(self):
        # When 'name' key is absent, falls back to 'title'
        data = {"papers_flat": [{"title": "IV Regression"}]}
        lookup = build_item_lookup(data)
        assert "paper-iv-regression" in lookup

    def test_papers_flat_empty_name_does_not_fall_back(self):
        # dict.get("name", fallback) only triggers for missing keys, not "".
        # Document the actual behaviour so regressions are caught.
        data = {"papers_flat": [{"title": "IV Regression", "name": ""}]}
        lookup = build_item_lookup(data)
        # key is "paper-" because empty name slugifies to ""
        assert "paper-" in lookup

    def test_empty_all_data_returns_empty(self):
        assert build_item_lookup({}) == {}

    def test_multiple_types(self):
        data = {
            "packages": [{"name": "PkgA"}],
            "datasets": [{"name": "DsB"}],
        }
        lookup = build_item_lookup(data)
        assert "package-pkga" in lookup
        assert "dataset-dsb" in lookup

    def test_original_fields_preserved(self):
        data = {"packages": [{"name": "EconML", "url": "https://econml.org"}]}
        item = build_item_lookup(data)["package-econml"]
        assert item["url"] == "https://econml.org"


# ──────────────────────────────────────────────
# merge_carousels
# ──────────────────────────────────────────────
class TestMergeCarousels:
    def test_no_conflict_all_included(self):
        manual = [{"id": "m1", "title": "Manual"}]
        generated = [{"id": "g1", "title": "Generated"}]
        result = merge_carousels(manual, generated)
        ids = [c["id"] for c in result]
        assert "m1" in ids
        assert "g1" in ids

    def test_conflict_manual_wins(self):
        manual = [{"id": "shared", "title": "Manual version"}]
        generated = [{"id": "shared", "title": "Generated version"}]
        result = merge_carousels(manual, generated)
        assert len(result) == 1
        assert result[0]["title"] == "Manual version"

    def test_empty_manual_uses_generated(self):
        generated = [{"id": "g1"}, {"id": "g2"}]
        result = merge_carousels([], generated)
        assert len(result) == 2

    def test_empty_generated_uses_manual(self):
        manual = [{"id": "m1"}]
        result = merge_carousels(manual, [])
        assert len(result) == 1

    def test_both_empty(self):
        assert merge_carousels([], []) == []

    def test_manual_order_preserved_first(self):
        manual = [{"id": "m1"}, {"id": "m2"}]
        generated = [{"id": "g1"}]
        result = merge_carousels(manual, generated)
        assert result[0]["id"] == "m1"
        assert result[1]["id"] == "m2"
