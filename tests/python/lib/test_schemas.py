"""Tests for lib/schemas.py — TypedDict shapes for our JSON files.

These tests don't run mypy (that's a separate gate); they exercise the
runtime introspection of TypedDict (`__optional_keys__`,
`__required_keys__`) plus a smoke check that every shape can hold real
data without exploding.

Architecture rule C8: every TypedDict here is `total=False` so existing
data files that pre-date a field don't crash readers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.schemas import (
    Book,
    Career,
    Community,
    Dataset,
    GlobalRankingsFile,
    OutputMetaDict,
    Package,
    PaperFlat,
    RelatedItem,
    RelatedItemsFile,
    Resource,
    Talk,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------
class TestSurface:
    def test_all_typeddicts_are_total_false_for_content(self):
        # Content-item TypedDicts must allow missing fields (forward
        # compat). RelatedItem is the only required-keys exception
        # since it's an internal shape we own end-to-end.
        for cls in (Package, PaperFlat, Dataset, Resource, Talk, Book, Career, Community):
            assert (
                cls.__total__ is False
            ), f"{cls.__name__} must be total=False (rule C8)"

    def test_related_item_has_required_fields(self):
        # RelatedItem is the only one we control fully — id+score are
        # always present in the output of generate_embeddings.py.
        assert RelatedItem.__total__ is True


# ---------------------------------------------------------------------------
# Real-data smoke: every typed shape can hold an actual entry from disk
# ---------------------------------------------------------------------------
def _is_subset_of_keys(item: dict, schema_cls: type) -> bool:
    """Return True if every key in `item` is declared on the schema or
    starts with `_` (meta keys we tolerate but don't type)."""
    declared = set(schema_cls.__optional_keys__) | set(
        getattr(schema_cls, "__required_keys__", set())
    )
    return all(
        k in declared or k.startswith("_") for k in item
    )


def _load(path: str) -> object:
    p = REPO_ROOT / path
    if not p.exists():
        pytest.skip(f"{path} not present in this checkout")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


class TestRealData:
    def test_package_typeddict_real_data(self):
        items = _load("data/packages.json")
        assert isinstance(items, list) and items, "packages.json should be a non-empty list"
        # Use a sample; assert no surprise keys.
        sample = items[0]
        assert isinstance(sample, dict)
        # We expect at minimum a name + url
        assert "name" in sample
        unknown = [
            k for k in sample
            if k not in (set(Package.__optional_keys__) | set(Package.__required_keys__))
            and not k.startswith("_")
        ]
        # Schema should cover the prevalent fields; tolerate up to 2
        # surprise fields so the test doesn't immediately break the
        # next time someone adds a field. CI is the warning, not the
        # gate.
        assert len(unknown) <= 2, (
            f"packages.json sample has unexpected keys not in Package schema: {unknown}"
        )

    def test_paper_flat_typeddict_real_data(self):
        items = _load("data/papers_flat.json")
        assert isinstance(items, list) and items
        sample = items[0]
        assert "name" in sample or "title" in sample
        unknown = [
            k for k in sample
            if k not in (set(PaperFlat.__optional_keys__) | set(PaperFlat.__required_keys__))
            and not k.startswith("_")
        ]
        assert len(unknown) <= 2, (
            f"papers_flat.json sample has unexpected keys: {unknown}"
        )

    def test_related_items_real_data(self):
        data = _load("static/embeddings/related-items.json")
        assert isinstance(data, dict)
        # Must have at least one of the documented keys
        known = set(RelatedItemsFile.__optional_keys__) | set(
            RelatedItemsFile.__required_keys__
        )
        present = set(data.keys())
        # Every present top-level key should be either declared or a
        # tolerated meta key.
        unknown = [k for k in present if k not in known and not k.startswith("_")]
        assert not unknown, (
            f"related-items.json has unexpected top-level keys: {unknown}"
        )
        # Items value, when present, must be a dict of id -> list
        if "items" in data and data["items"]:
            first_id = next(iter(data["items"]))
            neighbours = data["items"][first_id]
            assert isinstance(neighbours, list)
            for n in neighbours:
                assert "id" in n and "score" in n

    def test_global_rankings_real_data(self):
        data = _load("data/global_rankings.json")
        assert isinstance(data, dict)
        known = set(GlobalRankingsFile.__optional_keys__) | set(
            GlobalRankingsFile.__required_keys__
        )
        unknown = [k for k in data if k not in known and not k.startswith("_")]
        # Schema may not cover every field exactly; small unknown set
        # is acceptable.
        assert len(unknown) <= 2, (
            f"global_rankings.json has unexpected keys: {unknown}"
        )


# ---------------------------------------------------------------------------
# OutputMetaDict mirrors lib.data_io.OutputMeta
# ---------------------------------------------------------------------------
class TestOutputMetaDict:
    def test_keys_match_outputmeta_dataclass(self):
        from lib.data_io import OutputMeta

        dataclass_keys = {f.name for f in OutputMeta.__dataclass_fields__.values()}
        typed_keys = set(OutputMetaDict.__optional_keys__) | set(
            getattr(OutputMetaDict, "__required_keys__", set())
        )
        assert dataclass_keys == typed_keys, (
            f"OutputMeta dataclass and OutputMetaDict diverge: "
            f"dataclass={dataclass_keys}, typeddict={typed_keys}"
        )
