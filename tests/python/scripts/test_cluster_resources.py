"""Tests for pure helpers in scripts/cluster_resources.py.

get_resource_id and format_label are pure, network/embedding-free functions.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "cluster_resources.py"
_spec = importlib.util.spec_from_file_location("cluster_resources", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["cluster_resources"] = mod
_spec.loader.exec_module(mod)

get_resource_id = mod.get_resource_id
format_label = mod.format_label


# ---------------------------------------------------------------------------
# get_resource_id
# ---------------------------------------------------------------------------

class TestGetResourceId:

    def test_prefers_existing_id(self):
        assert get_resource_id({"id": "my-id", "name": "X"}) == "my-id"

    def test_generates_from_name_when_no_id(self):
        rid = get_resource_id({"name": "Machine Learning"})
        assert rid == "resource-machine-learning"

    def test_strips_special_chars(self):
        rid = get_resource_id({"name": "A/B Testing: Best Practices (2024)"})
        assert ":" not in rid
        assert "(" not in rid
        assert "/" not in rid

    def test_collapses_consecutive_hyphens(self):
        rid = get_resource_id({"name": "Hello  World"})
        assert "--" not in rid

    def test_strips_leading_trailing_hyphens(self):
        rid = get_resource_id({"name": "..Tools.."})
        assert not rid.startswith("resource--")
        slug = rid[len("resource-"):]
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_truncates_at_50_chars(self):
        long_name = "A" * 100
        rid = get_resource_id({"name": long_name})
        slug = rid[len("resource-"):]
        assert len(slug) <= 50

    def test_lowercases_name(self):
        rid = get_resource_id({"name": "Causal Inference"})
        assert rid == get_resource_id({"name": "causal inference"})

    def test_empty_id_field_falls_back_to_name(self):
        rid = get_resource_id({"id": "", "name": "Tool"})
        assert rid == "resource-tool"

    def test_missing_name_returns_prefix_only(self):
        rid = get_resource_id({})
        assert rid.startswith("resource")

    def test_ampersand_stripped(self):
        rid = get_resource_id({"name": "Stats & ML"})
        assert "&" not in rid


# ---------------------------------------------------------------------------
# format_label
# ---------------------------------------------------------------------------

class TestFormatLabel:

    def test_none_returns_other(self):
        assert format_label(None) == "Other"

    def test_empty_string_returns_other(self):
        assert format_label("") == "Other"

    def test_hyphenated_to_title_case(self):
        assert format_label("causal-inference") == "Causal Inference"

    def test_underscore_to_title_case(self):
        assert format_label("machine_learning") == "Machine Learning"

    def test_ml_abbreviation_capitalized(self):
        label = format_label("ml-methods")
        assert "ML" in label

    def test_ai_abbreviation_capitalized(self):
        label = format_label("ai-safety")
        assert "AI" in label

    def test_llm_abbreviation(self):
        label = format_label("llm-prompting")
        assert "LLM" in label

    def test_nlp_abbreviation(self):
        label = format_label("nlp-research")
        assert "NLP" in label

    def test_did_abbreviation(self):
        label = format_label("did-estimation")
        assert "DiD" in label

    def test_rdd_abbreviation(self):
        label = format_label("rdd-designs")
        assert "RDD" in label

    def test_api_abbreviation(self):
        label = format_label("api-design")
        assert "API" in label

    def test_plain_word_title_cased(self):
        assert format_label("econometrics") == "Econometrics"

    def test_multiple_words_all_title_cased(self):
        label = format_label("causal inference methods")
        assert label == "Causal Inference Methods"

    def test_ab_abbreviation(self):
        label = format_label("ab-testing")
        assert "A/B" in label


# ---------------------------------------------------------------------------
# generate_label_from_items
# ---------------------------------------------------------------------------

generate_label_from_items = mod.generate_label_from_items


class TestGenerateLabelFromItems:
    def test_most_common_tag_used(self):
        items = [
            {"topic_tags": ["causal", "ml"]},
            {"topic_tags": ["causal", "regression"]},
            {"topic_tags": ["causal"]},
        ]
        label = generate_label_from_items(items)
        assert "causal" in label.lower() or "Causal" in label

    def test_string_tags_parsed(self):
        items = [
            {"topic_tags": "causal, inference"},
            {"topic_tags": "causal, regression"},
        ]
        label = generate_label_from_items(items)
        assert label  # non-empty

    def test_category_fallback_when_no_tags(self):
        items = [
            {"category": "Causal Inference"},
            {"category": "Causal Inference"},
        ]
        label = generate_label_from_items(items)
        assert "Causal" in label or "causal" in label.lower()

    def test_empty_items_returns_general(self):
        label = generate_label_from_items([])
        assert label == "General Topics"

    def test_items_with_no_tags_or_category(self):
        items = [{"name": "X"}, {"name": "Y"}]
        label = generate_label_from_items(items)
        assert label == "General Topics"

    def test_returns_string(self):
        label = generate_label_from_items([{"topic_tags": ["ml"]}])
        assert isinstance(label, str)
        assert len(label) > 0
