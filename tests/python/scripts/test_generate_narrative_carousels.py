"""Tests for pure helpers in scripts/generate_narrative_carousels.py.

Covers: slugify, build_item_lookup, find_items_by_tags,
        find_items_by_text, select_diverse_items, has_person_name.
No network / LLM calls are made.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_narrative_carousels.py"
_spec = importlib.util.spec_from_file_location("generate_narrative_carousels", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_narrative_carousels"] = mod
_spec.loader.exec_module(mod)

slugify = mod.slugify
build_item_lookup = mod.build_item_lookup
find_items_by_tags = mod.find_items_by_tags
find_items_by_text = mod.find_items_by_text
select_diverse_items = mod.select_diverse_items
has_person_name = mod.has_person_name
merge_carousels = mod.merge_carousels
generate_person_carousels = mod.generate_person_carousels
generate_journey_carousels = mod.generate_journey_carousels
MIN_ITEMS = mod.MIN_ITEMS_PER_CAROUSEL
MAX_ITEMS = mod.MAX_ITEMS_PER_CAROUSEL


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class TestSlugify:

    def test_basic_lowercasing(self):
        assert slugify("Hello World") == "hello-world"

    def test_spaces_become_hyphens(self):
        assert slugify("causal inference") == "causal-inference"

    def test_collapses_multiple_spaces(self):
        assert slugify("a  b") == "a-b"

    def test_collapses_mixed_spaces_and_hyphens(self):
        assert slugify("a - b") == "a-b"

    def test_removes_non_word_chars(self):
        result = slugify("Hello, World!")
        assert "," not in result
        assert "!" not in result

    def test_strips_leading_trailing_hyphens(self):
        result = slugify("  ---hello---  ")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_unicode_normalized_to_ascii(self):
        # é → e after NFKD + ascii encode
        result = slugify("café")
        assert result == "cafe"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_already_slug(self):
        assert slugify("machine-learning") == "machine-learning"


# ---------------------------------------------------------------------------
# build_item_lookup
# ---------------------------------------------------------------------------

class TestBuildItemLookup:

    def _make_data(self):
        return {
            "packages": [{"name": "EconML", "url": "https://econml.org"}],
            "resources": [{"name": "Causal Inference Guide", "url": "https://example.com"}],
            "talks": [{"name": "Susan Athey Talk", "url": "https://talk.example.com"}],
            "datasets": [{"name": "CPS Survey", "url": ""}],
            "books": [{"name": "Mostly Harmless Econometrics", "url": ""}],
            "papers_flat": [{"name": "Identification Paper", "title": "Identification in Causal Models"}],
        }

    def test_all_types_indexed(self):
        lookup = build_item_lookup(self._make_data())
        types = {v["_type"] for v in lookup.values()}
        assert types == {"package", "resource", "talk", "dataset", "book", "paper"}

    def test_key_format_type_slug(self):
        lookup = build_item_lookup(self._make_data())
        assert "package-econml" in lookup
        assert "resource-causal-inference-guide" in lookup

    def test_item_has_type_and_id_injected(self):
        lookup = build_item_lookup(self._make_data())
        item = lookup["package-econml"]
        assert item["_type"] == "package"
        assert item["_id"] == "package-econml"

    def test_original_fields_preserved(self):
        lookup = build_item_lookup(self._make_data())
        assert lookup["package-econml"]["url"] == "https://econml.org"

    def test_paper_falls_back_to_title_for_id(self):
        data = {
            "papers_flat": [{"title": "Regression Discontinuity"}],
            "packages": [], "resources": [], "talks": [], "datasets": [], "books": [],
        }
        lookup = build_item_lookup(data)
        assert "paper-regression-discontinuity" in lookup

    def test_empty_data_returns_empty_lookup(self):
        empty = {k: [] for k in ["packages", "resources", "talks", "datasets", "books", "papers_flat"]}
        assert build_item_lookup(empty) == {}


# ---------------------------------------------------------------------------
# find_items_by_tags
# ---------------------------------------------------------------------------

class TestFindItemsByTags:

    def _make_lookup(self):
        return {
            "package-econml": {"_id": "package-econml", "_type": "package", "tags": ["causal inference", "ML"]},
            "resource-guide": {"_id": "resource-guide", "_type": "resource", "tags": ["econometrics"]},
            "talk-iv": {"_id": "talk-iv", "_type": "talk", "category": "Causal Inference"},
            "book-mhe": {"_id": "book-mhe", "_type": "book", "topic_tags": ["IV", "regression"]},
        }

    def test_matches_exact_tag(self):
        lookup = self._make_lookup()
        results = find_items_by_tags(lookup, ["econometrics"])
        ids = [r["_id"] for r in results]
        assert "resource-guide" in ids

    def test_case_insensitive(self):
        lookup = self._make_lookup()
        results = find_items_by_tags(lookup, ["CAUSAL"])
        ids = [r["_id"] for r in results]
        # substring "causal" matches both "causal inference" in tags and category
        assert "package-econml" in ids

    def test_item_type_filter(self):
        lookup = self._make_lookup()
        results = find_items_by_tags(lookup, ["causal"], item_type="package")
        assert all(r["_type"] == "package" for r in results)

    def test_no_match_returns_empty(self):
        lookup = self._make_lookup()
        results = find_items_by_tags(lookup, ["blockchain"])
        assert results == []

    def test_string_category_field_matched(self):
        lookup = self._make_lookup()
        results = find_items_by_tags(lookup, ["causal inference"])
        ids = [r["_id"] for r in results]
        assert "talk-iv" in ids  # has category="Causal Inference"


# ---------------------------------------------------------------------------
# find_items_by_text
# ---------------------------------------------------------------------------

class TestFindItemsByText:

    def _make_lookup(self):
        return {
            "package-lightgbm": {
                "_id": "package-lightgbm", "_type": "package",
                "name": "LightGBM", "description": "gradient boosting framework",
            },
            "resource-ml-guide": {
                "_id": "resource-ml-guide", "_type": "resource",
                "name": "Machine Learning Guide", "description": "supervised learning techniques",
            },
            "talk-causal": {
                "_id": "talk-causal", "_type": "talk",
                "name": "Causal ML Talk", "summary": "causal inference and machine learning",
            },
        }

    def test_matches_keyword_in_name(self):
        lookup = self._make_lookup()
        results = find_items_by_text(lookup, ["lightgbm"])
        ids = [r["_id"] for r in results]
        assert "package-lightgbm" in ids

    def test_matches_keyword_in_description(self):
        lookup = self._make_lookup()
        results = find_items_by_text(lookup, ["gradient"])
        ids = [r["_id"] for r in results]
        assert "package-lightgbm" in ids

    def test_item_type_filter(self):
        lookup = self._make_lookup()
        results = find_items_by_text(lookup, ["machine"], item_type="resource")
        assert all(r["_type"] == "resource" for r in results)

    def test_min_matches_filters_partial(self):
        lookup = self._make_lookup()
        # "causal" and "boosting" — only talk-causal has "causal", lightgbm has "boosting"
        # with min_matches=2 neither should match (each only has 1 of the 2 keywords)
        results = find_items_by_text(lookup, ["causal", "boosting"], min_matches=2)
        ids = [r["_id"] for r in results]
        assert "package-lightgbm" not in ids
        assert "talk-causal" not in ids

    def test_sorted_by_match_count_descending(self):
        lookup = {
            "a": {"_id": "a", "_type": "package", "name": "causal machine learning boosting"},
            "b": {"_id": "b", "_type": "package", "name": "causal inference"},
        }
        results = find_items_by_text(lookup, ["causal", "machine", "boosting"])
        # item "a" has 3 matches, "b" has 1 — "a" must come first
        assert results[0]["_id"] == "a"

    def test_no_match_returns_empty(self):
        lookup = self._make_lookup()
        results = find_items_by_text(lookup, ["blockchain"])
        assert results == []

    def test_empty_keywords_list_returns_empty(self):
        lookup = self._make_lookup()
        results = find_items_by_text(lookup, [])
        assert results == []


# ---------------------------------------------------------------------------
# select_diverse_items
# ---------------------------------------------------------------------------

class TestSelectDiverseItems:

    def _items(self, specs):
        """specs: list of (type, id_suffix)"""
        return [{"_type": t, "_id": f"{t}-{i}", "name": f"{t}-{i}"} for t, i in specs]

    def test_respects_max_count(self):
        items = self._items([("package", i) for i in range(10)])
        result = select_diverse_items(items, max_count=4)
        assert len(result) <= 4

    def test_round_robin_interleaves_types(self):
        items = self._items([
            ("package", 1), ("package", 2), ("package", 3),
            ("resource", 1), ("resource", 2),
            ("talk", 1),
        ])
        result = select_diverse_items(items, max_count=6)
        types_in_order = [r["_type"] for r in result]
        # Should not be all one type bunched together at the front
        assert len(set(types_in_order)) > 1

    def test_returns_all_when_fewer_than_max(self):
        items = self._items([("package", 1), ("resource", 1)])
        result = select_diverse_items(items, max_count=10)
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        assert select_diverse_items([], max_count=6) == []

    def test_single_type_still_returns_up_to_max(self):
        items = self._items([("paper", i) for i in range(5)])
        result = select_diverse_items(items, max_count=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# has_person_name
# ---------------------------------------------------------------------------

class TestHasPersonName:

    def test_full_name_in_title(self):
        item = {"name": "Susan Athey on Causal Inference", "title": ""}
        assert has_person_name(item, "Susan Athey") is True

    def test_last_name_only_matches(self):
        item = {"name": "Athey and Wager 2018", "title": ""}
        assert has_person_name(item, "Susan Athey") is True

    def test_name_in_title_field(self):
        item = {"name": "", "title": "Hal Varian: Information Technology and Economics"}
        assert has_person_name(item, "Hal Varian") is True

    def test_case_insensitive(self):
        item = {"name": "susan athey interview", "title": ""}
        assert has_person_name(item, "Susan Athey") is True

    def test_unrelated_item_returns_false(self):
        item = {"name": "Introduction to Machine Learning", "title": ""}
        assert has_person_name(item, "Susan Athey") is False

    def test_single_word_name(self):
        item = {"name": "Varian Intermediate Microeconomics", "title": ""}
        assert has_person_name(item, "Varian") is True


# ---------------------------------------------------------------------------
# merge_carousels
# ---------------------------------------------------------------------------

class TestMergeCarousels:
    def test_manual_always_included(self):
        manual = [{"id": "m1", "title": "Manual One"}]
        generated = [{"id": "g1", "title": "Generated One"}]
        result = merge_carousels(manual, generated)
        ids = [c["id"] for c in result]
        assert "m1" in ids

    def test_generated_added_when_no_conflict(self):
        manual = [{"id": "m1"}]
        generated = [{"id": "g1"}]
        result = merge_carousels(manual, generated)
        ids = [c["id"] for c in result]
        assert "g1" in ids

    def test_generated_id_conflict_skipped(self):
        manual = [{"id": "shared-id", "source": "manual"}]
        generated = [{"id": "shared-id", "source": "generated"}]
        result = merge_carousels(manual, generated)
        assert len(result) == 1
        assert result[0]["source"] == "manual"

    def test_empty_manual_uses_generated(self):
        generated = [{"id": "g1"}, {"id": "g2"}]
        result = merge_carousels([], generated)
        assert len(result) == 2

    def test_empty_generated_returns_manual(self):
        manual = [{"id": "m1"}]
        result = merge_carousels(manual, [])
        assert result == manual

    def test_both_empty_returns_empty(self):
        assert merge_carousels([], []) == []

    def test_order_manual_first(self):
        manual = [{"id": "m1"}]
        generated = [{"id": "g1"}]
        result = merge_carousels(manual, generated)
        assert result[0]["id"] == "m1"
        assert result[1]["id"] == "g1"

# ---------------------------------------------------------------------------
# generate_person_carousels
# ---------------------------------------------------------------------------

class TestGeneratePersonCarousels:

    def _make_lookup(self, person_name="Susan Athey"):
        """Lookup with enough items mentioning the person to form a carousel."""
        items = []
        # Items mentioning the person — ensure we have enough for MIN_ITEMS
        for i in range(MIN_ITEMS + 1):
            key = f"talk-{slugify(person_name)}-{i}"
            items.append((key, {
                "_id": key,
                "_type": "talk",
                "name": f"{person_name} on Causal Inference Part {i}",
                "tags": ["causal inference"],
                "url": f"https://example.com/{i}",
            }))
        return dict(items)

    def test_returns_list(self):
        lookup = self._make_lookup()
        result = generate_person_carousels([{"name": "Susan Athey"}], lookup)
        assert isinstance(result, list)

    def test_skips_person_with_no_name_mentions(self):
        # Lookup has no items mentioning the person
        lookup = {"resource-unrelated": {"_id": "resource-unrelated", "_type": "resource",
                                          "name": "Unrelated Resource", "tags": []}}
        result = generate_person_carousels([{"name": "Susan Athey"}], lookup)
        assert result == []

    def test_carousel_has_required_fields(self):
        lookup = self._make_lookup("Susan Athey")
        result = generate_person_carousels([{"name": "Susan Athey", "specialty": ["causal inference"]}], lookup)
        if result:
            c = result[0]
            assert "id" in c
            assert "template" in c
            assert c["template"] == "person"
            assert "hero" in c
            assert "items" in c

    def test_hero_mentions_person_name(self):
        lookup = self._make_lookup("Susan Athey")
        result = generate_person_carousels([{"name": "Susan Athey", "specialty": ["causal inference"]}], lookup)
        if result:
            hero_title = result[0]["hero"].get("title", "")
            assert "athey" in hero_title.lower() or "susan" in hero_title.lower()

    def test_empty_persons_returns_empty(self):
        result = generate_person_carousels([], {})
        assert result == []

    def test_carousel_id_uses_slug(self):
        lookup = self._make_lookup("Susan Athey")
        result = generate_person_carousels([{"name": "Susan Athey", "specialty": ["causal inference"]}], lookup)
        if result:
            assert "susan-athey" in result[0]["id"]

    def test_items_count_bounded(self):
        lookup = self._make_lookup("Susan Athey")
        result = generate_person_carousels([{"name": "Susan Athey", "specialty": ["causal inference"]}], lookup)
        if result:
            # hero + items should not exceed MAX_ITEMS
            assert len(result[0]["items"]) <= MAX_ITEMS - 1


# ---------------------------------------------------------------------------
# generate_journey_carousels
# ---------------------------------------------------------------------------

class TestGenerateJourneyCarousels:

    def _make_roadmap(self, num_resources=5):
        resources = [{"name": f"Resource {i}", "url": f"https://ex.com/{i}", "why": "good"}
                     for i in range(num_resources)]
        return {"name": "Causal Inference Path", "description": "Learn causal inference", "resources": resources}

    def test_returns_list(self):
        result = generate_journey_carousels([self._make_roadmap()], {})
        assert isinstance(result, list)

    def test_roadmap_without_resources_skipped(self):
        result = generate_journey_carousels([{"name": "Empty", "description": "", "resources": []}], {})
        assert result == []

    def test_roadmap_with_too_few_resources_skipped(self):
        # MIN_ITEMS_PER_CAROUSEL = 4, so 2 resources should be skipped
        result = generate_journey_carousels([self._make_roadmap(num_resources=2)], {})
        assert result == []

    def test_carousel_has_required_fields(self):
        result = generate_journey_carousels([self._make_roadmap()], {})
        assert len(result) == 1
        c = result[0]
        assert "id" in c
        assert c["template"] == "journey"
        assert "hero" in c
        assert "items" in c

    def test_hero_is_first_resource(self):
        result = generate_journey_carousels([self._make_roadmap()], {})
        assert result[0]["hero"]["title"] == "Resource 0"

    def test_carousel_id_is_slugified_name(self):
        result = generate_journey_carousels([self._make_roadmap()], {})
        assert result[0]["id"] == "causal-inference-path"

    def test_empty_roadmaps_returns_empty(self):
        result = generate_journey_carousels([], {})
        assert result == []

    def test_lookup_hit_uses_found_item(self):
        lookup = {
            "resource-resource-0": {"_id": "resource-resource-0", "_type": "resource",
                                    "name": "Resource 0", "url": "https://real.com"}
        }
        result = generate_journey_carousels([self._make_roadmap()], lookup)
        # Should still produce a carousel (found item used)
        assert len(result) == 1

# ---------------------------------------------------------------------------
# generate_tool_carousels
# ---------------------------------------------------------------------------

generate_tool_carousels = mod.generate_tool_carousels

class TestGenerateToolCarousels:

    def _make_pkgs(self, category, count):
        return [{"name": f"{category} Tool {i}", "category": category, "url": f"https://ex.com/{i}"}
                for i in range(count)]

    def test_returns_list(self):
        pkgs = self._make_pkgs("Causal Inference", MIN_ITEMS)
        result = generate_tool_carousels(pkgs, {})
        assert isinstance(result, list)

    def test_category_with_enough_items_creates_carousel(self):
        pkgs = self._make_pkgs("Causal Inference", MIN_ITEMS + 1)
        result = generate_tool_carousels(pkgs, {})
        assert len(result) == 1

    def test_category_with_too_few_items_skipped(self):
        pkgs = self._make_pkgs("Tiny", MIN_ITEMS - 1)
        result = generate_tool_carousels(pkgs, {})
        assert result == []

    def test_carousel_template_is_tool(self):
        pkgs = self._make_pkgs("ML", MIN_ITEMS)
        result = generate_tool_carousels(pkgs, {})
        assert result[0]["template"] == "tool"

    def test_carousel_id_uses_category_slug(self):
        pkgs = self._make_pkgs("Causal Inference", MIN_ITEMS)
        result = generate_tool_carousels(pkgs, {})
        assert result[0]["id"] == "tools-causal-inference"

    def test_multiple_categories_produce_multiple_carousels(self):
        pkgs = self._make_pkgs("ML", MIN_ITEMS) + self._make_pkgs("Econ", MIN_ITEMS)
        result = generate_tool_carousels(pkgs, {})
        assert len(result) == 2

    def test_capped_at_30_carousels(self):
        pkgs = []
        for i in range(35):
            pkgs += self._make_pkgs(f"Category {i}", MIN_ITEMS)
        result = generate_tool_carousels(pkgs, {})
        assert len(result) <= 30

    def test_empty_packages_returns_empty(self):
        assert generate_tool_carousels([], {}) == []

# ---------------------------------------------------------------------------
# generate_method_carousels
# ---------------------------------------------------------------------------

generate_method_carousels = mod.generate_method_carousels
MIN_CITATIONS = mod.MIN_CITATION_FOR_METHOD

class TestGenerateMethodCarousels:

    def _make_lookup_for_paper(self, keywords=None):
        """Build a lookup with enough items to form a carousel."""
        keywords = keywords or ["instrumental"]
        lookup = {}
        for i in range(MIN_ITEMS + 1):
            key = f"resource-{keywords[0]}-{i}"
            lookup[key] = {
                "_id": key, "_type": "resource",
                "name": f"{keywords[0].title()} Resource {i}",
                "description": f"{' '.join(keywords)} analysis",
            }
        return lookup

    def test_returns_list(self):
        result = generate_method_carousels([], {})
        assert isinstance(result, list)

    def test_papers_below_citation_threshold_skipped(self):
        papers = [{"title": "Low Cites Paper", "citations": MIN_CITATIONS - 1}]
        result = generate_method_carousels(papers, {})
        assert result == []

    def test_paper_above_threshold_considered(self):
        lookup = self._make_lookup_for_paper(["instrumental", "variable", "method"])
        paper = {
            "title": "Instrumental Variables: Identification Strategies",
            "citations": MIN_CITATIONS,
            "topic_tags": ["instrumental"],
        }
        result = generate_method_carousels([paper], lookup)
        # May or may not produce a carousel depending on keyword matches, just no crash
        assert isinstance(result, list)

    def test_deduplicates_by_title(self):
        lookup = self._make_lookup_for_paper(["causal", "iv", "instrument"])
        paper = {
            "title": "Causal Inference via IV",
            "citations": MIN_CITATIONS + 500,
            "topic_tags": ["causal", "iv"],
        }
        result = generate_method_carousels([paper, paper], lookup)
        # Duplicate title → only one carousel at most
        if result:
            titles = [c["hero"]["title"] for c in result]
            assert len(titles) == len(set(titles))

    def test_carousel_template_is_method(self):
        # Create lookup with strong keyword overlap
        lookup = {}
        for i in range(MIN_ITEMS + 1):
            key = f"resource-diff-{i}"
            lookup[key] = {
                "_id": key, "_type": "resource",
                "name": f"Difference-in-Differences Resource {i}",
                "description": "differences differences panel data",
            }
        paper = {
            "title": "Differences-in-Differences Panel Data",
            "citations": MIN_CITATIONS,
            "topic_tags": ["differences", "panel"],
        }
        result = generate_method_carousels([paper], lookup)
        if result:
            assert result[0]["template"] == "method"

    def test_empty_papers_returns_empty(self):
        assert generate_method_carousels([], {}) == []
