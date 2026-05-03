"""Tests for scripts.rank_all_content.select_diverse_trending and
build_trending_embedding_lookup -- the MMR-diversified homepage row.

We import the module under test in test setup and skip the module's
SBERT load by stubbing sentence_transformers ahead of time. That keeps
this file runnable in CI without HuggingFace access.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Module loader: import scripts.rank_all_content with SBERT stubbed so
# the test file is honest about its dependencies (and fast in CI).
# ---------------------------------------------------------------------------
def _load_module():
    """Return scripts.rank_all_content with sentence_transformers stubbed.

    rank_all_content.py loads SBERT at import time. For unit tests we
    don't want a network round-trip, so we install a tiny stub that
    returns deterministic vectors before the import.
    """
    if "scripts.rank_all_content" in sys.modules:
        return sys.modules["scripts.rank_all_content"]

    stub_pkg = types.ModuleType("sentence_transformers")

    class _DummyTransformer:
        def __init__(self, *_a, **_kw): pass
        def encode(self, texts, show_progress_bar=False, batch_size=64):
            # 4-dim hash-based vectors so the tests don't depend on
            # any real model weights.
            out = []
            for t in texts:
                h = hash(t) & 0xFFFFFFFF
                vec = np.array([
                    (h >> 0) & 0xFF,
                    (h >> 8) & 0xFF,
                    (h >> 16) & 0xFF,
                    (h >> 24) & 0xFF,
                ], dtype=np.float32)
                vec = vec / (np.linalg.norm(vec) or 1.0)
                out.append(vec)
            return np.array(out, dtype=np.float32)

    stub_pkg.SentenceTransformer = _DummyTransformer
    sys.modules["sentence_transformers"] = stub_pkg

    # Also stub sklearn pieces if not present (rank_all_content imports them
    # at module level, but they're available in the dev env).
    import scripts.rank_all_content as mod  # noqa: E402
    return mod


@pytest.fixture(scope="module")
def rank_module():
    return _load_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _r(name, score=0.5, type_="package", category="ml", cold=False, desc=""):
    return {
        "name": name, "score": score, "type": type_, "category": category,
        "cold_start": cold, "description": desc, "rank": 1,
    }


# ---------------------------------------------------------------------------
# select_diverse_trending: filtering + delegation to mmr_rerank
# ---------------------------------------------------------------------------
class TestSelectDiverseTrending:
    def test_filters_cold_start(self, rank_module):
        rankings = [
            _r("A", score=0.9, cold=True),
            _r("B", score=0.8),
            _r("C", score=0.7),
        ]
        out = rank_module.select_diverse_trending(rankings, n=10)
        names = {x["name"] for x in out}
        assert "A" not in names
        assert names == {"B", "C"}

    def test_filters_career_type(self, rank_module):
        rankings = [
            _r("Job1", score=0.9, type_="career"),
            _r("B", score=0.8),
        ]
        out = rank_module.select_diverse_trending(rankings, n=10)
        names = {x["name"] for x in out}
        assert "Job1" not in names
        assert names == {"B"}

    def test_empty_input(self, rank_module):
        assert rank_module.select_diverse_trending([], n=12) == []

    def test_all_filtered_returns_empty(self, rank_module):
        rankings = [
            _r("A", cold=True),
            _r("B", type_="career"),
        ]
        assert rank_module.select_diverse_trending(rankings, n=12) == []

    def test_top_n_capped(self, rank_module):
        rankings = [_r(f"item{i}", score=1.0 - i * 0.01) for i in range(50)]
        out = rank_module.select_diverse_trending(rankings, n=12)
        assert len(out) == 12

    def test_no_embedding_lookup_falls_back_to_pure_relevance(self, rank_module):
        rankings = [_r("A", score=0.9), _r("B", score=0.5), _r("C", score=0.7)]
        out = rank_module.select_diverse_trending(
            rankings, n=3, embedding_lookup=None
        )
        # mmr_rerank with embedding_lookup=None returns input order capped
        # to top_k. Input order here is the rankings list order.
        names = [x["name"] for x in out]
        assert names == ["A", "B", "C"]

    def test_lambda_one_falls_through_to_relevance_sorted(self, rank_module):
        # lambda_=1 in mmr_rerank means defensively re-sort by score desc
        rankings = [_r("low", score=0.1), _r("hi", score=0.9), _r("mid", score=0.5)]
        emb = {"low": np.array([1.0, 0]), "hi": np.array([0, 1.0]),
               "mid": np.array([0.5, 0.5])}
        out = rank_module.select_diverse_trending(
            rankings, n=3, lambda_=1.0, embedding_lookup=emb.get
        )
        names = [x["name"] for x in out]
        assert names == ["hi", "mid", "low"]

    def test_mmr_diversifies_near_duplicates(self, rank_module):
        # Three high-scoring near-duplicates + one different item.
        # Pure relevance would surface the duplicates; MMR should
        # break them up by picking the different item second.
        rankings = [
            _r("dup1", score=0.95),
            _r("dup2", score=0.94),
            _r("dup3", score=0.93),
            _r("diff", score=0.80),
            _r("low", score=0.10),
        ]
        emb = {
            "dup1": np.array([1.0, 0.0]),
            "dup2": np.array([0.99, 0.01]),
            "dup3": np.array([0.98, 0.02]),
            "diff": np.array([0.0, 1.0]),
            "low": np.array([0.5, 0.5]),
        }
        out = rank_module.select_diverse_trending(
            rankings, n=3, lambda_=0.5, embedding_lookup=emb.get
        )
        names = [x["name"] for x in out]
        # First pick is the highest-scoring item.
        assert names[0] == "dup1"
        # MMR with lambda=0.5 and a near-orthogonal "diff" should
        # prefer it over the near-duplicate "dup2".
        assert "diff" in names[:3]

    def test_pool_multiplier_caps_input_to_mmr(self, rank_module):
        # If we pass 100 items, MMR shouldn't try to encode all 100 --
        # the pool is limited by pool_multiplier * n.
        rankings = [_r(f"item{i}", score=1.0 - i * 0.001) for i in range(100)]
        out = rank_module.select_diverse_trending(
            rankings, n=12, pool_multiplier=3, min_pool_size=30
        )
        assert len(out) == 12
        # Output items must come from the top 36 (= 12 * 3) by score
        # in input order. The lowest-ranked output item's index in
        # input must be < 36.
        input_names = [r["name"] for r in rankings]
        for x in out:
            assert input_names.index(x["name"]) < 36


# ---------------------------------------------------------------------------
# build_trending_embedding_lookup
# ---------------------------------------------------------------------------
class _StubEncoder:
    """Deterministic 2-D encoder; lets us assert exact embedding outputs."""
    def __init__(self):
        self.calls: list[list[str]] = []

    def encode(self, texts, show_progress_bar=False, batch_size=64):
        self.calls.append(list(texts))
        return np.array(
            [[float(len(t)), float(t.count(" "))] for t in texts],
            dtype=np.float32,
        )


class _ExplodingEncoder:
    def encode(self, *_a, **_kw):
        raise RuntimeError("encoder went boom")


class TestBuildTrendingEmbeddingLookup:
    def test_returns_callable_with_correct_lookup(self, rank_module):
        rankings = [_r("Foo", desc="a tool"), _r("Bar", desc="another tool")]
        encoder = _StubEncoder()
        lookup = rank_module.build_trending_embedding_lookup(
            rankings, encoder, pool_size=10
        )
        assert callable(lookup)
        v_foo = lookup("Foo")
        v_bar = lookup("Bar")
        assert v_foo is not None and v_bar is not None
        # Stub encoded "Foo a tool" (10 chars, 2 spaces)
        assert v_foo[0] == pytest.approx(len("Foo a tool"))

    def test_returns_none_for_unknown_name(self, rank_module):
        rankings = [_r("Foo")]
        lookup = rank_module.build_trending_embedding_lookup(
            rankings, _StubEncoder(), pool_size=10
        )
        assert lookup("Missing") is None

    def test_skips_cold_and_career(self, rank_module):
        rankings = [
            _r("Cold", cold=True),
            _r("Career", type_="career"),
            _r("Hot"),
        ]
        encoder = _StubEncoder()
        rank_module.build_trending_embedding_lookup(
            rankings, encoder, pool_size=10
        )
        # Encoder only saw the Hot item
        assert len(encoder.calls) == 1
        assert len(encoder.calls[0]) == 1
        assert "Hot" in encoder.calls[0][0]

    def test_pool_size_caps_encode_input(self, rank_module):
        rankings = [_r(f"i{n}") for n in range(20)]
        encoder = _StubEncoder()
        rank_module.build_trending_embedding_lookup(
            rankings, encoder, pool_size=5
        )
        assert len(encoder.calls[0]) == 5

    def test_empty_pool_returns_none(self, rank_module):
        # Everything cold -> nothing to encode
        rankings = [_r("A", cold=True), _r("B", cold=True)]
        encoder = _StubEncoder()
        lookup = rank_module.build_trending_embedding_lookup(
            rankings, encoder, pool_size=10
        )
        assert lookup is None
        assert encoder.calls == []  # encoder never invoked

    def test_encoder_failure_returns_none_no_raise(self, rank_module, capsys):
        rankings = [_r("A"), _r("B")]
        lookup = rank_module.build_trending_embedding_lookup(
            rankings, _ExplodingEncoder(), pool_size=10,
        )
        assert lookup is None
        captured = capsys.readouterr().out
        assert "SBERT encode failed" in captured
