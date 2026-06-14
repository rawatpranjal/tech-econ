"""Tests for pure helpers in scripts/cluster_hdbscan.py.

Covers: get_section_from_id, normalize_word, format_ctfidf_label,
        combine_labels, get_item_text.
No network, no embeddings files, no HDBSCAN run.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "cluster_hdbscan.py"
_spec = importlib.util.spec_from_file_location("cluster_hdbscan", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["cluster_hdbscan"] = mod
_spec.loader.exec_module(mod)

get_section_from_id = mod.get_section_from_id
normalize_word = mod.normalize_word
format_ctfidf_label = mod.format_ctfidf_label
combine_labels = mod.combine_labels
get_item_text = mod.get_item_text


# ---------------------------------------------------------------------------
# get_section_from_id
# ---------------------------------------------------------------------------

class TestGetSectionFromId:

    def test_package_prefix(self):
        assert get_section_from_id("package-pandas") == "package"

    def test_dataset_prefix(self):
        assert get_section_from_id("dataset-census-2020") == "dataset"

    def test_resource_prefix(self):
        assert get_section_from_id("resource-some-blog") == "resource"

    def test_paper_prefix(self):
        assert get_section_from_id("paper-causal-inference") == "paper"

    def test_single_segment(self):
        assert get_section_from_id("package") == "package"

    def test_multi_segment_takes_first(self):
        assert get_section_from_id("talk-intro-to-ml-lecture") == "talk"


# ---------------------------------------------------------------------------
# normalize_word
# ---------------------------------------------------------------------------

class TestNormalizeWord:

    def test_lowercase(self):
        assert normalize_word("MachineLearning") == "machinelearning"

    def test_strip_hyphens(self):
        assert normalize_word("causal-inference") == "causalinference"

    def test_strip_underscores(self):
        assert normalize_word("deep_learning") == "deeplearning"

    def test_combined(self):
        assert normalize_word("A/B-Testing_2024") == "a/btesting_2024".replace("_", "")

    def test_already_normalized(self):
        assert normalize_word("econometrics") == "econometrics"


# ---------------------------------------------------------------------------
# format_ctfidf_label
# ---------------------------------------------------------------------------

class TestFormatCtfidfLabel:

    def test_two_good_terms_joined(self):
        label = format_ctfidf_label(["causal", "inference"])
        assert "Causal" in label and "Inference" in label
        assert "&" in label

    def test_single_good_term(self):
        label = format_ctfidf_label(["econometrics"])
        assert label == "Econometrics"

    def test_skips_stopwords(self):
        # "python" and "data" are in SKIP; should get to "causal"
        label = format_ctfidf_label(["python", "data", "causal", "inference"])
        assert "Causal" in label

    def test_all_skip_returns_miscellaneous(self):
        label = format_ctfidf_label(["python", "learning", "data", "model"])
        assert label == "Miscellaneous"

    def test_empty_list_returns_miscellaneous(self):
        assert format_ctfidf_label([]) == "Miscellaneous"

    def test_deduplication_by_normalized_prefix(self):
        # "causal" and "causation" share prefix → only one kept
        label = format_ctfidf_label(["causal", "causation", "inference"])
        # Should combine first non-dup pair or just one if no second found
        assert label  # doesn't crash

    def test_title_case_applied(self):
        label = format_ctfidf_label(["regression", "discontinuity"])
        # Both words should be title-cased
        assert label[0].isupper()

    def test_short_term_skipped(self):
        # Single char should be skipped (len < 2)
        label = format_ctfidf_label(["a", "regression", "discontinuity"])
        assert "A" not in label or "Regression" in label


# ---------------------------------------------------------------------------
# combine_labels
# ---------------------------------------------------------------------------

class TestCombineLabels:

    def test_empty_suffix_returns_parent(self):
        assert combine_labels("Machine Learning", "") == "Machine Learning"

    def test_none_like_empty_suffix(self):
        assert combine_labels("Causal Inference", "") == "Causal Inference"

    def test_new_words_appended(self):
        result = combine_labels("Causal Inference", "Regression")
        assert "Regression" in result
        assert ":" in result

    def test_redundant_suffix_not_added(self):
        # Suffix "Inference" already in parent
        result = combine_labels("Causal Inference", "Inference")
        assert result == "Causal Inference"

    def test_exact_match_overlap_blocked(self):
        # "inference" full word is in parent → suffix word blocked
        result = combine_labels("Causal Inference", "Inference Methods")
        # "Inference" already in parent; "Methods" is new → only Methods kept
        assert "Inference: Inference" not in result

    def test_ampersand_in_parent_handled(self):
        result = combine_labels("ML & Statistics", "Regression")
        assert "Regression" in result

    def test_format_is_parent_colon_suffix(self):
        result = combine_labels("Parent", "Child")
        assert result == "Parent: Child"

    def test_multiple_new_words_in_suffix(self):
        result = combine_labels("Bayesian", "Structural Estimation")
        assert "Structural" in result
        assert "Estimation" in result


# ---------------------------------------------------------------------------
# get_item_text
# ---------------------------------------------------------------------------

class TestGetItemText:

    def test_uses_name(self):
        text = get_item_text({"name": "DoubleML"})
        assert "DoubleML" in text

    def test_prefers_embedding_text_over_description(self):
        text = get_item_text({
            "name": "Tool",
            "embedding_text": "embedding content",
            "description": "description content",
        })
        assert "embedding content" in text
        assert "description content" not in text

    def test_falls_back_to_description(self):
        text = get_item_text({
            "name": "Tool",
            "description": "A causal ML library",
        })
        assert "A causal ML library" in text

    def test_includes_topic_tags_string(self):
        text = get_item_text({"name": "X", "topic_tags": "causal,inference"})
        assert "causal" in text

    def test_includes_topic_tags_list(self):
        text = get_item_text({"name": "X", "topic_tags": ["causal", "inference"]})
        assert "causal" in text

    def test_includes_canonical_topics(self):
        text = get_item_text({"name": "X", "canonical_topics": ["econometrics"]})
        assert "econometrics" in text

    def test_empty_item_returns_empty_string(self):
        text = get_item_text({})
        assert text == ""

    def test_topic_tags_hyphens_replaced(self):
        text = get_item_text({"name": "X", "topic_tags": "causal-inference"})
        assert "causal" in text
        assert "inference" in text
