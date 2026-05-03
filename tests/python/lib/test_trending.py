"""Tests for lib.trending: homepage trending row selection + embedding lookup.

These tests run offline -- no SBERT, no sklearn -- because the lib
module is intentionally light on deps (only numpy + lib.diversity).
"""

from __future__ import annotations

import numpy as np
import pytest

from lib.trending import (
    build_trending_embedding_lookup,
    select_diverse_trending,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _r(name, score=0.5, type_="package", category="ml", cold=False, desc=""):
    return {
        "name": name, "score": score, "type": type_, "category": category,
        "cold_start": cold, "description": desc, "rank": 1,
    }


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


# ---------------------------------------------------------------------------
# select_diverse_trending: filtering + MMR delegation
# ---------------------------------------------------------------------------
class TestSelectDiverseTrending:
    def test_filters_cold_start(self):
        rankings = [
            _r("A", score=0.9, cold=True),
            _r("B", score=0.8),
            _r("C", score=0.7),
        ]
        out = select_diverse_trending(rankings, n=10)
        names = {x["name"] for x in out}
        assert "A" not in names
        assert names == {"B", "C"}

    def test_filters_career_type(self):
        rankings = [
            _r("Job1", score=0.9, type_="career"),
            _r("B", score=0.8),
        ]
        out = select_diverse_trending(rankings, n=10)
        names = {x["name"] for x in out}
        assert "Job1" not in names
        assert names == {"B"}

    def test_empty_input(self):
        assert select_diverse_trending([], n=12) == []

    def test_all_filtered_returns_empty(self):
        rankings = [
            _r("A", cold=True),
            _r("B", type_="career"),
        ]
        assert select_diverse_trending(rankings, n=12) == []

    def test_top_n_capped(self):
        rankings = [_r(f"item{i}", score=1.0 - i * 0.01) for i in range(50)]
        out = select_diverse_trending(rankings, n=12)
        assert len(out) == 12

    def test_no_embedding_lookup_falls_back_to_pure_relevance(self):
        rankings = [_r("A", score=0.9), _r("B", score=0.5), _r("C", score=0.7)]
        out = select_diverse_trending(rankings, n=3, embedding_lookup=None)
        # mmr_rerank with embedding_lookup=None returns input order
        # capped to top_k.
        names = [x["name"] for x in out]
        assert names == ["A", "B", "C"]

    def test_lambda_one_falls_through_to_relevance_sorted(self):
        # lambda_=1 in mmr_rerank means defensively re-sort by score desc
        rankings = [_r("low", score=0.1), _r("hi", score=0.9), _r("mid", score=0.5)]
        emb = {"low": np.array([1.0, 0]), "hi": np.array([0, 1.0]),
               "mid": np.array([0.5, 0.5])}
        out = select_diverse_trending(
            rankings, n=3, lambda_=1.0, embedding_lookup=emb.get
        )
        names = [x["name"] for x in out]
        assert names == ["hi", "mid", "low"]

    def test_mmr_diversifies_near_duplicates(self):
        # Three high-scoring near-duplicates + one different item.
        # Pure relevance would surface the duplicates first; MMR
        # should slot the different item in to break them up.
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
        out = select_diverse_trending(
            rankings, n=3, lambda_=0.5, embedding_lookup=emb.get
        )
        names = [x["name"] for x in out]
        assert names[0] == "dup1"  # first pick is highest-scoring
        assert "diff" in names[:3]  # MMR should surface the orthogonal item

    def test_pool_multiplier_caps_input_to_mmr(self):
        # 100 items in. Pool = 12 * 3 = 36. Output items must come
        # from the top 36 by input score order.
        rankings = [_r(f"item{i}", score=1.0 - i * 0.001) for i in range(100)]
        out = select_diverse_trending(
            rankings, n=12, pool_multiplier=3, min_pool_size=30
        )
        assert len(out) == 12
        input_names = [r["name"] for r in rankings]
        for x in out:
            assert input_names.index(x["name"]) < 36


# ---------------------------------------------------------------------------
# build_trending_embedding_lookup
# ---------------------------------------------------------------------------
class TestBuildTrendingEmbeddingLookup:
    def test_returns_callable_with_correct_lookup(self):
        rankings = [_r("Foo", desc="a tool"), _r("Bar", desc="another tool")]
        encoder = _StubEncoder()
        lookup = build_trending_embedding_lookup(
            rankings, encoder, pool_size=10
        )
        assert callable(lookup)
        v_foo = lookup("Foo")
        v_bar = lookup("Bar")
        assert v_foo is not None and v_bar is not None
        # Stub encoded "Foo a tool" (10 chars, 2 spaces)
        assert v_foo[0] == pytest.approx(len("Foo a tool"))

    def test_returns_none_for_unknown_name(self):
        rankings = [_r("Foo")]
        lookup = build_trending_embedding_lookup(
            rankings, _StubEncoder(), pool_size=10
        )
        assert lookup("Missing") is None

    def test_skips_cold_and_career(self):
        rankings = [
            _r("Cold", cold=True),
            _r("Career", type_="career"),
            _r("Hot"),
        ]
        encoder = _StubEncoder()
        build_trending_embedding_lookup(rankings, encoder, pool_size=10)
        assert len(encoder.calls) == 1
        assert len(encoder.calls[0]) == 1
        assert "Hot" in encoder.calls[0][0]

    def test_pool_size_caps_encode_input(self):
        rankings = [_r(f"i{n}") for n in range(20)]
        encoder = _StubEncoder()
        build_trending_embedding_lookup(rankings, encoder, pool_size=5)
        assert len(encoder.calls[0]) == 5

    def test_empty_pool_returns_none(self):
        rankings = [_r("A", cold=True), _r("B", cold=True)]
        encoder = _StubEncoder()
        lookup = build_trending_embedding_lookup(
            rankings, encoder, pool_size=10
        )
        assert lookup is None
        assert encoder.calls == []

    def test_encoder_failure_returns_none_no_raise(self, capsys):
        rankings = [_r("A"), _r("B")]
        lookup = build_trending_embedding_lookup(
            rankings, _ExplodingEncoder(), pool_size=10,
        )
        assert lookup is None
        captured = capsys.readouterr().out
        assert "SBERT encode failed" in captured

    def test_skips_items_without_string_name(self):
        rankings = [
            {"name": None, "score": 0.5, "type": "package",
             "cold_start": False, "description": ""},
            _r("Real"),
        ]
        encoder = _StubEncoder()
        build_trending_embedding_lookup(rankings, encoder, pool_size=10)
        assert len(encoder.calls[0]) == 1
        assert "Real" in encoder.calls[0][0]
