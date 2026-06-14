"""Tests for the MMR-related functions added to generate_homepage_rows.py.

Focuses on:
  - apply_mmr_ordering: returns same items, possibly reordered
  - load_embeddings_lookup: callable returns numpy array or None
  - Integration: generated rows carry items_mmr with correct shape
"""

import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# Allow script imports without installing
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.generate_homepage_rows import (
    apply_mmr_ordering,
    load_embeddings_lookup,
    apply_type_cap,
    dedup_against_used,
    mark_used,
    build_score_lookup,
    load_content_lookup,
    load_json,
    make_item,
    make_item_from_meta,
)


# ---------------------------------------------------------------------------
# apply_mmr_ordering
# ---------------------------------------------------------------------------

def _make_items(n: int, same_embedding: bool = False) -> list[dict]:
    """Generate n fake items with descending scores and synthetic embeddings."""
    rng = np.random.default_rng(42)
    items = []
    for i in range(n):
        if same_embedding:
            emb = [1.0, 0.0, 0.0]
        else:
            v = rng.standard_normal(3).tolist()
            emb = v
        items.append({"name": f"item-{i}", "score": 1.0 - i * 0.05, "_emb": emb})
    return items


def _lookup_from_items(items):
    """Build embedding lookup from items with '_emb' field."""
    table = {it["name"]: np.array(it["_emb"], dtype=np.float32) for it in items}
    return lambda name: table.get(name)


class TestApplyMmrOrdering:
    def test_returns_same_length(self):
        items = _make_items(8)
        lookup = _lookup_from_items(items)
        result = apply_mmr_ordering(items, lookup)
        assert len(result) == 8

    def test_contains_same_items(self):
        items = _make_items(6)
        lookup = _lookup_from_items(items)
        result = apply_mmr_ordering(items, lookup)
        assert {it["name"] for it in result} == {it["name"] for it in items}

    def test_reorders_near_duplicates(self):
        """Items with identical embeddings should be spread out by MMR."""
        # First 3 are near-identical; item-3, item-4 are orthogonal
        items = [
            {"name": "dup-a", "score": 1.0, "_emb": [1.0, 0.0, 0.0]},
            {"name": "dup-b", "score": 0.95, "_emb": [1.0, 0.02, 0.0]},
            {"name": "diverse-c", "score": 0.90, "_emb": [0.0, 1.0, 0.0]},
            {"name": "dup-d", "score": 0.85, "_emb": [1.0, 0.01, 0.0]},
        ]
        lookup = _lookup_from_items(items)
        result = apply_mmr_ordering(items, lookup)
        names = [it["name"] for it in result]
        # dup-a must be first (highest score, always seeded)
        assert names[0] == "dup-a"
        # diverse-c should appear before dup-d (MMR pushes the diverse item up)
        assert names.index("diverse-c") < names.index("dup-d")

    def test_returns_original_when_lookup_is_none(self):
        items = _make_items(4)
        result = apply_mmr_ordering(items, None)
        assert [it["name"] for it in result] == [it["name"] for it in items]

    def test_handles_empty_list(self):
        assert apply_mmr_ordering([], None) == []
        assert apply_mmr_ordering([], _lookup_from_items([])) == []

    def test_items_missing_embedding_appended_at_end(self):
        """Items with no embedding get appended after the diverse set."""
        items = [
            {"name": "has-emb-a", "score": 1.0, "_emb": [1.0, 0.0]},
            {"name": "no-emb-b",  "score": 0.9},        # no _emb key
            {"name": "has-emb-c", "score": 0.8, "_emb": [0.0, 1.0]},
        ]
        # Lookup returns None for no-emb-b since it has no embedding
        table = {}
        for it in items:
            if "_emb" in it:
                table[it["name"]] = np.array(it["_emb"], dtype=np.float32)
        lookup = lambda name: table.get(name)

        result = apply_mmr_ordering(items, lookup)
        assert len(result) == 3
        names = [it["name"] for it in result]
        # no-emb-b should be last because it has no embedding
        assert names[-1] == "no-emb-b"


# ---------------------------------------------------------------------------
# load_embeddings_lookup
# ---------------------------------------------------------------------------

class TestLoadEmbeddingsLookup:
    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        """Gracefully returns None when the embeddings file doesn't exist."""
        import scripts.generate_homepage_rows as mod
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", tmp_path / "nonexistent.json")
        result = load_embeddings_lookup()
        assert result is None

    def test_lookup_returns_numpy_array(self, tmp_path, monkeypatch):
        """Callable returns a numpy array for a known item name."""
        import scripts.generate_homepage_rows as mod

        fake_data = {
            "model": "test",
            "dimensions": 3,
            "count": 2,
            "items": [
                {"id": "pkg-a", "name": "Package A", "embedding": [0.1, 0.2, 0.3]},
                {"id": "pkg-b", "name": "Package B", "embedding": [0.4, 0.5, 0.6]},
            ],
        }
        emb_path = tmp_path / "search-embeddings.json"
        emb_path.write_text(json.dumps(fake_data))
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", emb_path)

        lookup = load_embeddings_lookup()
        assert lookup is not None
        assert callable(lookup)

        emb = lookup("Package A")
        assert isinstance(emb, np.ndarray)
        assert emb.shape == (3,)
        np.testing.assert_allclose(emb, [0.1, 0.2, 0.3], atol=1e-6)

    def test_lookup_is_case_insensitive(self, tmp_path, monkeypatch):
        import scripts.generate_homepage_rows as mod

        fake_data = {
            "items": [{"id": "x", "name": "Causal Forest", "embedding": [1.0, 0.0]}],
        }
        emb_path = tmp_path / "search-embeddings.json"
        emb_path.write_text(json.dumps(fake_data))
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", emb_path)

        lookup = load_embeddings_lookup()
        assert lookup("causal forest") is not None
        assert lookup("CAUSAL FOREST") is not None
        assert lookup("Causal Forest") is not None

    def test_lookup_returns_none_for_unknown_name(self, tmp_path, monkeypatch):
        import scripts.generate_homepage_rows as mod

        fake_data = {"items": [{"id": "x", "name": "Known Item", "embedding": [1.0]}]}
        emb_path = tmp_path / "search-embeddings.json"
        emb_path.write_text(json.dumps(fake_data))
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", emb_path)

        lookup = load_embeddings_lookup()
        assert lookup("Unknown Item") is None
        assert lookup(None) is None
        assert lookup("") is None


# ---------------------------------------------------------------------------
# Integration: items_mmr in generated rows
# ---------------------------------------------------------------------------

class TestItemsMmrIntegration:
    """Smoke-tests that the generate_rows pipeline writes items_mmr correctly."""

    def _make_minimal_data_dir(self, tmp_path: Path) -> Path:
        """Write the minimum JSON files needed by generate_rows."""
        packages = [
            {
                "name": f"Package {i}",
                "model_score": 1.0 - i * 0.1,
                "description": f"Desc {i}",
                "url": f"https://example.com/{i}",
            }
            for i in range(10)
        ]
        talks = [
            {
                "name": f"Talk {i}",
                "model_score": 1.0 - i * 0.1,
                "description": f"Talk desc {i}",
                "url": f"https://talk.example.com/{i}",
            }
            for i in range(8)
        ]
        resources = [
            {
                "name": f"Resource {i}",
                "model_score": 1.0 - i * 0.1,
                "description": f"Resource desc {i}",
                "url": f"https://resource.example.com/{i}",
            }
            for i in range(8)
        ]
        (tmp_path / "packages.json").write_text(json.dumps(packages))
        (tmp_path / "talks.json").write_text(json.dumps(talks))
        (tmp_path / "resources.json").write_text(json.dumps(resources))
        # Empty files for other content types
        for fname in ["datasets.json", "papers_flat.json", "books.json",
                      "career.json", "community.json"]:
            (tmp_path / fname).write_text("[]")
        return tmp_path

    def test_items_mmr_present_on_every_row(self, tmp_path, monkeypatch):
        """Every row in the output must have an items_mmr key."""
        import scripts.generate_homepage_rows as mod

        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", tmp_path / "nonexistent.json")
        self._make_minimal_data_dir(tmp_path)

        result = mod.generate_rows(tmp_path)
        for row in result["rows"]:
            assert "items_mmr" in row, f"Row '{row['id']}' missing items_mmr"

    def test_items_mmr_same_length_as_items(self, tmp_path, monkeypatch):
        """items_mmr must be the same length as items (no items dropped)."""
        import scripts.generate_homepage_rows as mod

        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", tmp_path / "nonexistent.json")
        self._make_minimal_data_dir(tmp_path)

        result = mod.generate_rows(tmp_path)
        for row in result["rows"]:
            assert len(row["items_mmr"]) == len(row["items"]), (
                f"Row '{row['id']}': items_mmr length {len(row['items_mmr'])} "
                f"!= items length {len(row['items'])}"
            )

    def test_items_mmr_contains_same_item_set(self, tmp_path, monkeypatch):
        """items_mmr must contain the same items as items (just reordered)."""
        import scripts.generate_homepage_rows as mod

        monkeypatch.setattr(mod, "DATA_DIR", tmp_path)
        monkeypatch.setattr(mod, "EMBEDDINGS_PATH", tmp_path / "nonexistent.json")
        self._make_minimal_data_dir(tmp_path)

        result = mod.generate_rows(tmp_path)
        for row in result["rows"]:
            names_items = {it["name"] for it in row["items"]}
            names_mmr   = {it["name"] for it in row["items_mmr"]}
            assert names_items == names_mmr, (
                f"Row '{row['id']}': items and items_mmr have different item sets"
            )


# ---------------------------------------------------------------------------
# apply_type_cap
# ---------------------------------------------------------------------------

class TestApplyTypeCap:
    def _items(self, specs):
        return [{"name": f"i{i}", "type": t} for i, t in enumerate(specs)]

    def test_no_cap_exceeded(self):
        items = self._items(["package", "dataset", "resource"])
        assert len(apply_type_cap(items, 2)) == 3

    def test_cap_applied_per_type(self):
        items = self._items(["package"] * 5 + ["dataset"] * 3)
        result = apply_type_cap(items, 2)
        types = [i["type"] for i in result]
        assert types.count("package") == 2
        assert types.count("dataset") == 2

    def test_zero_cap_returns_empty(self):
        items = self._items(["package", "dataset"])
        assert apply_type_cap(items, 0) == []

    def test_preserves_order_within_type(self):
        items = [{"name": "first", "type": "pkg"}, {"name": "second", "type": "pkg"}]
        result = apply_type_cap(items, 1)
        assert result[0]["name"] == "first"

    def test_empty_input(self):
        assert apply_type_cap([], 3) == []


# ---------------------------------------------------------------------------
# dedup_against_used
# ---------------------------------------------------------------------------

class TestDedupAgainstUsed:
    def test_removes_used_items(self):
        items = [{"name": "Alpha"}, {"name": "Beta"}]
        used = {"alpha"}  # lowercase-stripped
        result = dedup_against_used(items, used)
        assert len(result) == 1
        assert result[0]["name"] == "Beta"

    def test_empty_used_set_returns_all(self):
        items = [{"name": "A"}, {"name": "B"}]
        assert dedup_against_used(items, set()) == items

    def test_all_used_returns_empty(self):
        items = [{"name": "X"}, {"name": "Y"}]
        used = {"x", "y"}
        assert dedup_against_used(items, used) == []

    def test_case_insensitive_match(self):
        items = [{"name": "  DoubleML  "}]
        used = {"doubleml"}
        assert dedup_against_used(items, used) == []


# ---------------------------------------------------------------------------
# mark_used
# ---------------------------------------------------------------------------

class TestMarkUsed:
    def test_adds_lowercased_names_to_set(self):
        items = [{"name": "Alpha"}, {"name": "  Beta  "}]
        used: set[str] = set()
        mark_used(items, used)
        assert "alpha" in used
        assert "beta" in used

    def test_mutates_in_place(self):
        used: set[str] = {"existing"}
        mark_used([{"name": "New"}], used)
        assert "existing" in used
        assert "new" in used

    def test_empty_items_no_change(self):
        used: set[str] = {"a"}
        mark_used([], used)
        assert used == {"a"}


# ---------------------------------------------------------------------------
# build_score_lookup
# ---------------------------------------------------------------------------

class TestBuildScoreLookup:
    def test_lowercases_and_strips_keys(self):
        rankings = [{"name": "  MyPkg  ", "score": 0.9}]
        lookup = build_score_lookup(rankings)
        assert lookup["mypkg"] == 0.9

    def test_missing_score_defaults_to_zero(self):
        rankings = [{"name": "NoPkg"}]
        assert build_score_lookup(rankings)["nopkg"] == 0.0

    def test_empty_input(self):
        assert build_score_lookup([]) == {}

    def test_multiple_items(self):
        rankings = [{"name": "A", "score": 0.5}, {"name": "B", "score": 0.8}]
        lookup = build_score_lookup(rankings)
        assert len(lookup) == 2


# ---------------------------------------------------------------------------
# make_item_from_meta
# ---------------------------------------------------------------------------

class TestMakeItemFromMeta:
    def _meta(self, name="Pkg", **kwargs):
        return {"name": name, "type": "package", "url": "https://x.com", **kwargs}

    def test_uses_score_lookup_over_model_score(self):
        meta = self._meta(name="Foo", model_score=0.3)
        item = make_item_from_meta(meta, {"foo": 0.9})
        assert item["score"] == 0.9

    def test_falls_back_to_model_score_when_not_in_lookup(self):
        meta = self._meta(name="Bar", model_score=0.4)
        item = make_item_from_meta(meta, {})
        assert item["score"] == 0.4

    def test_cold_start_true_when_not_in_lookup(self):
        meta = self._meta(name="Cold")
        item = make_item_from_meta(meta, {})
        assert item["cold_start"] is True

    def test_cold_start_false_when_in_lookup(self):
        meta = self._meta(name="Hot")
        item = make_item_from_meta(meta, {"hot": 0.7})
        assert item["cold_start"] is False

    def test_name_preserved(self):
        meta = self._meta(name="MyTool")
        item = make_item_from_meta(meta, {})
        assert item["name"] == "MyTool"

    def test_signals_always_empty_dict(self):
        meta = self._meta(name="Z")
        item = make_item_from_meta(meta, {})
        assert item["signals"] == {}


# ---------------------------------------------------------------------------
# make_item (from ranking_entry + content_lookup)
# ---------------------------------------------------------------------------

class TestMakeItem:
    def _ranking(self, name="Pkg", **kwargs):
        return {"name": name, "score": 0.5, **kwargs}

    def _content(self, name="Pkg", **kwargs):
        return {name.lower(): {"type": "package", "description": "desc", "url": "https://x.com", **kwargs}}

    def test_name_preserved(self):
        item = make_item(self._ranking(name="EconML"), self._content("EconML"))
        assert item["name"] == "EconML"

    def test_score_from_ranking(self):
        item = make_item(self._ranking(name="T", score=0.77), {})
        assert item["score"] == 0.77

    def test_type_from_ranking_overrides_content(self):
        item = make_item(
            self._ranking(name="T", type="resource"),
            {"t": {"type": "package"}}
        )
        assert item["type"] == "resource"

    def test_type_falls_back_to_content_lookup(self):
        entry = {"name": "T", "score": 0.5}  # no type in ranking
        content = {"t": {"type": "dataset"}}
        item = make_item(entry, content)
        assert item["type"] == "dataset"

    def test_type_unknown_when_not_in_either(self):
        item = make_item({"name": "Ghost", "score": 0.0}, {})
        assert item["type"] == "unknown"

    def test_image_url_from_content_when_missing_in_ranking(self):
        entry = {"name": "Img", "score": 0.1}
        content = {"img": {"image_url": "/img/foo.webp"}}
        item = make_item(entry, content)
        assert item["image_url"] == "/img/foo.webp"

    def test_cold_start_from_ranking(self):
        item = make_item(self._ranking(name="T", cold_start=False), {})
        assert item["cold_start"] is False

    def test_cold_start_defaults_to_true(self):
        item = make_item({"name": "T", "score": 0.1}, {})
        assert item["cold_start"] is True

    def test_signals_from_ranking(self):
        signals = {"clicks": 5, "scroll_90": 1}
        item = make_item(self._ranking(name="T", signals=signals), {})
        assert item["signals"] == signals

    def test_signals_defaults_to_empty(self):
        item = make_item({"name": "T", "score": 0.0}, {})
        assert item["signals"] == {}


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    def test_returns_none_for_missing_file(self, tmp_path):
        result = load_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        assert load_json(f) is None

    def test_returns_list(self, tmp_path):
        f = tmp_path / "items.json"
        f.write_text('[{"name": "X"}]')
        result = load_json(f)
        assert result == [{"name": "X"}]

    def test_returns_dict(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "val"}')
        result = load_json(f)
        assert result == {"key": "val"}


# ---------------------------------------------------------------------------
# load_content_lookup
# ---------------------------------------------------------------------------

class TestLoadContentLookup:
    def _write_file(self, tmp_path, filename, content):
        (tmp_path / filename).write_text(json.dumps(content))

    def test_package_github_avatar_url_constructed(self, tmp_path):
        self._write_file(tmp_path, "packages.json", [
            {"name": "DoubleML", "github_url": "https://github.com/DoubleML/doubleml-for-py"}
        ])
        lookup = load_content_lookup(tmp_path)
        assert "doubleml" in lookup
        assert lookup["doubleml"]["image_url"] == "https://github.com/DoubleML.png?size=128"

    def test_book_isbn_image_url_constructed(self, tmp_path):
        self._write_file(tmp_path, "books.json", [
            {"name": "Mostly Harmless", "isbn": "9780393979824", "url": "https://example.com"}
        ])
        lookup = load_content_lookup(tmp_path)
        assert "mostly harmless" in lookup
        assert "9780393979824" in lookup["mostly harmless"]["image_url"]

    def test_paper_uses_title_as_name(self, tmp_path):
        self._write_file(tmp_path, "papers_flat.json", [
            {"title": "Double ML Paper", "url": "https://arxiv.org/abs/123"}
        ])
        lookup = load_content_lookup(tmp_path)
        assert "double ml paper" in lookup

    def test_url_priority_chain(self, tmp_path):
        self._write_file(tmp_path, "packages.json", [
            {"name": "Pkg", "github_url": "https://github.com/x/y", "docs_url": "https://docs.x.com"}
        ])
        lookup = load_content_lookup(tmp_path)
        # github_url wins when url is missing
        assert lookup["pkg"]["url"] == "https://github.com/x/y"

    def test_items_without_name_skipped(self, tmp_path):
        self._write_file(tmp_path, "packages.json", [
            {"category": "ML"},  # no name or title
            {"name": "Valid", "url": "https://example.com"},
        ])
        lookup = load_content_lookup(tmp_path)
        assert len(lookup) == 1
        assert "valid" in lookup

    def test_key_is_lowercased_and_stripped(self, tmp_path):
        self._write_file(tmp_path, "packages.json", [
            {"name": "  CausalML  ", "url": "https://example.com"}
        ])
        lookup = load_content_lookup(tmp_path)
        assert "causalml" in lookup

    def test_missing_file_skipped_gracefully(self, tmp_path):
        # packages.json missing — should not crash
        lookup = load_content_lookup(tmp_path)
        assert isinstance(lookup, dict)
