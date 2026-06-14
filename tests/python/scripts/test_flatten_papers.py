"""Tests for scripts/flatten_papers.py.

flatten_papers.py is explicitly flagged in RULES.md as a fragile area:
"papers.json vs papers_flat.json — Dual system, easy to desync."

Tests verify slugify, flatten_papers output shape, ID deduplication,
field mapping, and category construction.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.flatten_papers import slugify, flatten_papers


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class TestSlugify:

    def test_lowercase(self):
        assert slugify("DoubleML") == "doubleml"

    def test_spaces_become_hyphens(self):
        assert slugify("machine learning") == "machine-learning"

    def test_special_chars_stripped(self):
        assert slugify("Causal (Inference): A Survey!") == "causal-inference-a-survey"

    def test_leading_trailing_hyphens_removed(self):
        assert not slugify("--hello--").startswith("-")
        assert not slugify("--hello--").endswith("-")

    def test_truncates_at_100(self):
        long = "a" * 120
        assert len(slugify(long)) <= 100

    def test_empty_string(self):
        assert slugify("") == ""

    def test_numbers_preserved(self):
        assert "2024" in slugify("Paper 2024")


# ---------------------------------------------------------------------------
# flatten_papers
# ---------------------------------------------------------------------------

def make_papers_json(topics: list) -> dict:
    return {"topics": topics}


def make_topic(name: str, subtopics: list) -> dict:
    return {"name": name, "subtopics": subtopics}


def make_subtopic(name: str, papers: list) -> dict:
    return {"name": name, "papers": papers}


def make_paper(**kwargs) -> dict:
    return {"title": "Paper", "url": "https://example.com", **kwargs}


class TestFlattenPapers:

    def test_basic_structure(self, tmp_path):
        data = make_papers_json([
            make_topic("Causal Inference", [
                make_subtopic("RCTs", [make_paper(title="Basics")])
            ])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        assert len(items) == 1
        item = items[0]
        assert item["title"] == "Basics"
        assert item["name"] == "Basics"
        assert item["type"] == "paper"
        assert item["topic"] == "Causal Inference"
        assert item["subtopic"] == "RCTs"
        assert item["category"] == "Causal Inference > RCTs"

    def test_all_papers_flattened_across_topics(self, tmp_path):
        data = make_papers_json([
            make_topic("T1", [make_subtopic("S1", [make_paper(title="P1"), make_paper(title="P2")])]),
            make_topic("T2", [make_subtopic("S2", [make_paper(title="P3")])]),
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        assert len(items) == 3
        titles = {i["title"] for i in items}
        assert titles == {"P1", "P2", "P3"}

    def test_id_format_uses_slugified_title(self, tmp_path):
        data = make_papers_json([
            make_topic("T", [make_subtopic("S", [make_paper(title="My Great Paper")])])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        assert items[0]["id"] == "paper-my-great-paper"

    def test_duplicate_titles_get_unique_ids(self, tmp_path):
        data = make_papers_json([
            make_topic("T", [
                make_subtopic("S", [
                    make_paper(title="Same Title"),
                    make_paper(title="Same Title"),
                    make_paper(title="Same Title"),
                ])
            ])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        ids = [i["id"] for i in items]
        assert len(ids) == len(set(ids)), "Duplicate IDs produced"

    def test_optional_fields_defaulted(self, tmp_path):
        data = make_papers_json([
            make_topic("T", [
                make_subtopic("S", [{"title": "Minimal", "url": "https://x.com"}])
            ])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        item = items[0]
        assert item["authors"] == ""
        assert item["description"] == ""
        assert item["tag"] == ""
        assert item["tags"] == []
        assert item["year"] is None
        assert item["citations"] is None

    def test_populated_optional_fields_preserved(self, tmp_path):
        paper = {
            "title": "Full Paper",
            "url": "https://arxiv.org/abs/1234",
            "authors": "Smith, J.",
            "year": 2023,
            "citations": 42,
            "description": "A thorough study.",
            "tag": "rct",
            "tags": ["causal", "experiment"],
        }
        data = make_papers_json([make_topic("T", [make_subtopic("S", [paper])])])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        item = items[0]
        assert item["authors"] == "Smith, J."
        assert item["year"] == 2023
        assert item["citations"] == 42
        assert item["description"] == "A thorough study."
        assert item["tag"] == "rct"
        assert item["tags"] == ["causal", "experiment"]

    def test_empty_topics_returns_empty_list(self, tmp_path):
        (tmp_path / "papers.json").write_text(json.dumps({"topics": []}))
        assert flatten_papers(tmp_path) == []

    def test_empty_subtopics_returns_empty_list(self, tmp_path):
        data = make_papers_json([make_topic("T", [])])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        assert flatten_papers(tmp_path) == []

    def test_multiple_subtopics_in_one_topic(self, tmp_path):
        data = make_papers_json([
            make_topic("Econometrics", [
                make_subtopic("IV", [make_paper(title="IV Paper")]),
                make_subtopic("DiD", [make_paper(title="DiD Paper")]),
            ])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        assert len(items) == 2
        subtopics = {i["subtopic"] for i in items}
        assert subtopics == {"IV", "DiD"}

    def test_url_field_mapped(self, tmp_path):
        data = make_papers_json([
            make_topic("T", [make_subtopic("S", [make_paper(url="https://specific.com/paper")])])
        ])
        (tmp_path / "papers.json").write_text(json.dumps(data))
        items = flatten_papers(tmp_path)
        assert items[0]["url"] == "https://specific.com/paper"
