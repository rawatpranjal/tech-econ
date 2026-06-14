"""Bullshit tests for generate_creative_names.py pure helpers.

Covers: is_valid_creative_name (NAME_BLACKLIST, word count, length)
Network/LLM functions are not tested.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "generate_creative_names.py"

# Stub openai so the import doesn't fail if not installed
if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

_spec = importlib.util.spec_from_file_location("generate_creative_names", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_creative_names"] = mod
_spec.loader.exec_module(mod)

is_valid = mod.is_valid_creative_name
NAME_BLACKLIST = mod.NAME_BLACKLIST


class TestIsValidCreativeName:
    def test_valid_two_word_name(self):
        assert is_valid("Causal Magic") is True

    def test_valid_three_word_name(self):
        assert is_valid("The Prediction Game") is True

    def test_valid_six_word_name(self):
        assert is_valid("When All The Experiments Go Wrong") is True

    def test_empty_string_invalid(self):
        assert is_valid("") is False

    def test_none_invalid(self):
        assert is_valid(None) is False

    def test_too_short_name(self):
        # len < 3
        assert is_valid("AI") is False

    def test_one_word_invalid(self):
        # 1 word < 2-word minimum
        assert is_valid("Forecasting") is False

    def test_seven_words_invalid(self):
        assert is_valid("One Two Three Four Five Six Seven") is False

    def test_blacklist_topics_rejected(self):
        assert is_valid("Causal Topics Collection") is False

    def test_blacklist_resources_rejected(self):
        assert is_valid("Best Resources For ML") is False

    def test_blacklist_methods_rejected(self):
        assert is_valid("Statistical Methods Overview") is False

    def test_blacklist_case_insensitive(self):
        # NAME_BLACKLIST uses lower() comparison
        assert is_valid("Great TOPICS For You") is False

    def test_blacklist_substring_match(self):
        # "papers on" is in blacklist — partial phrase match
        assert is_valid("New Papers on NLP") is False

    def test_guide_to_rejected(self):
        assert is_valid("Guide To Causal Inference") is False

    def test_introduction_to_rejected(self):
        assert is_valid("Introduction To Econometrics") is False

    def test_all_blacklist_terms_reject(self):
        for term in NAME_BLACKLIST:
            name = f"Amazing {term} Here"
            assert is_valid(name) is False, f"Expected {term!r} to be rejected"

    def test_legitimate_names_pass(self):
        good_names = [
            "The Transformer Revolution",
            "Taming Your Data Jungle",
            "Beyond A/B Testing",
            "Causal Magic",
            "Time Series Whisperers",
        ]
        for name in good_names:
            assert is_valid(name) is True, f"Expected {name!r} to be valid"
