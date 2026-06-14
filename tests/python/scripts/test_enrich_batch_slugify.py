"""Bullshit tests for enrich_batch.slugify (the only pure function worth testing).

The module imports enrich_metadata_v2 and openai at load time, so we stub both
in sys.modules before loading.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# ── stub enrich_metadata_v2 so enrich_batch can import it without disk I/O ──
def _make_emv2_stub():
    m = types.ModuleType("enrich_metadata_v2")
    # Minimal names referenced at module level in enrich_batch
    m.DATA_DIR = Path("data")
    m.DATA_FILES = []
    m.PAPERS_FILE = Path("data/papers.json")
    m.MODEL_VERSION = "v0"
    m.SCHEMA_VERSION = "v0"
    m.PROMPT_MAP = {}
    m.EMBEDDING_TEXT_MAP = {}
    m.EMBEDDING_TEXT_BASE = ""
    m.ANTI_HALLUCINATION = ""
    m.CLUSTERING_FIELDS_INSTRUCTION = ""
    m.SCHEMA_MAP = {}
    for fn in ("load_state", "save_state", "needs_enrichment", "get_item_id",
               "compute_hash", "apply_enrichment", "update_state",
               "calculate_confidence"):
        setattr(m, fn, lambda *a, **kw: None)

    class _Base:
        pass
    m.BaseEnrichment = _Base
    return m

if "enrich_metadata_v2" not in sys.modules:
    sys.modules["enrich_metadata_v2"] = _make_emv2_stub()

# ── stub openai ──
if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

# ── load enrich_batch ──
_spec = importlib.util.spec_from_file_location(
    "enrich_batch", _REPO_ROOT / "scripts" / "enrich_batch.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["enrich_batch"] = _mod
_spec.loader.exec_module(_mod)

slugify = _mod.slugify


class TestSlugify:
    def test_lowercase(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_replaced_with_hyphen(self):
        assert slugify("foo/bar.baz") == "foo-bar-baz"

    def test_consecutive_specials_collapse(self):
        # multiple non-alnum chars → single hyphen
        assert slugify("foo  bar") == "foo-bar"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify("  hello  ") == "hello"

    def test_numbers_preserved(self):
        assert slugify("bge-large-en-v1.5") == "bge-large-en-v1-5"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_already_slug(self):
        assert slugify("valid-slug-123") == "valid-slug-123"

    def test_max_80_chars_enforced(self):
        long = "a" * 200
        assert len(slugify(long)) == 80

    def test_unicode_chars_replaced(self):
        result = slugify("café économie")
        # non-ascii → replaced by hyphens and collapsed
        assert result == "caf-conomie"

    def test_underscore_becomes_hyphen(self):
        assert slugify("some_module_name") == "some-module-name"

    def test_mixed_case_and_symbols(self):
        result = slugify("Double/Debiased ML (DML)")
        assert result == "double-debiased-ml-dml"
