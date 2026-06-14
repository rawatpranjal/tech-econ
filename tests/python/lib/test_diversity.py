"""Tests for lib.diversity (Python port of static/js/search/mmr.js).

Mirrors the structure of tests/js/mmr.test.js so the two
implementations stay behaviourally aligned.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lib.diversity import cosine_sim, mmr_rerank


# Helpers
def vec(*xs):
    return np.array(xs, dtype=np.float64)


def make_item(item_id, score, embedding=None):
    return {"id": item_id, "name": item_id, "rrfScore": score, "_emb": embedding}


def lookup_from_items(items):
    m = {it["id"]: it.get("_emb") for it in items}
    return lambda i: m.get(i)


# ---------------------------------------------------------------------------
# cosine_sim
# ---------------------------------------------------------------------------
class TestCosineSim:
    def test_identical(self):
        assert math.isclose(cosine_sim(vec(1, 0, 0), vec(1, 0, 0)), 1.0)

    def test_orthogonal(self):
        assert math.isclose(cosine_sim(vec(1, 0, 0), vec(0, 1, 0)), 0.0)

    def test_opposite(self):
        assert math.isclose(cosine_sim(vec(1, 0, 0), vec(-1, 0, 0)), -1.0)

    def test_unequal_lengths(self):
        assert cosine_sim(vec(1, 2, 3), vec(1, 2)) == 0.0

    def test_zero_norm(self):
        assert cosine_sim(vec(0, 0, 0), vec(1, 1, 1)) == 0.0
        assert cosine_sim(vec(1, 1, 1), vec(0, 0, 0)) == 0.0

    def test_none_inputs(self):
        assert cosine_sim(None, vec(1, 0, 0)) == 0.0
        assert cosine_sim(vec(1, 0, 0), None) == 0.0
        assert cosine_sim(None, None) == 0.0

    def test_45_degree(self):
        # cos(45°) = 1 / sqrt(2)
        out = cosine_sim(vec(1, 1, 0), vec(1, 0, 0))
        assert math.isclose(out, 1.0 / math.sqrt(2), rel_tol=1e-9)

    def test_scale_invariance(self):
        # Same direction, different magnitudes
        assert math.isclose(cosine_sim(vec(2, 0, 0), vec(5, 0, 0)), 1.0)


# ---------------------------------------------------------------------------
# mmr_rerank — base behaviour
# ---------------------------------------------------------------------------
class TestMMR:
    def test_empty_input(self):
        assert mmr_rerank([], None) == []
        assert mmr_rerank([], lambda i: None) == []

    def test_no_lookup_returns_identity(self):
        items = [make_item("a", 1.0), make_item("b", 0.9)]
        out = mmr_rerank(items, None, lambda_=0.5)
        assert [i["id"] for i in out] == ["a", "b"]

    def test_lambda_one_pure_relevance(self):
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.9, vec(1, 0, 0)),  # dup of a
            make_item("c", 0.8, vec(0, 1, 0)),
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=1.0)
        assert [i["id"] for i in out] == ["a", "b", "c"]

    def test_lambda_demotes_duplicate(self):
        # With lambda=0.5, the diversity bonus on c outweighs b's
        # slightly higher relevance.
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.95, vec(1, 0, 0)),  # identical to a
            make_item("c", 0.9, vec(0, 1, 0)),    # orthogonal
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=0.5)
        assert out[0]["id"] == "a"
        assert out[1]["id"] == "c"
        assert out[2]["id"] == "b"

    def test_lambda_zero_pure_diversity_after_seed(self):
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.9, vec(1, 0, 0)),
            make_item("c", 0.5, vec(0, 1, 0)),
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=0.0)
        # First pick is always highest-relevance seed (a)
        assert out[0]["id"] == "a"
        # Second pick maximises -max_sim → orthogonal c wins
        assert out[1]["id"] == "c"

    def test_top_k(self):
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.9, vec(0, 1, 0)),
            make_item("c", 0.8, vec(0, 0, 1)),
            make_item("d", 0.7, vec(1, 1, 0)),
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=0.7, top_k=2)
        assert len(out) == 2

    def test_items_without_embeddings_appended_at_tail(self):
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.9, None),  # no embedding
            make_item("c", 0.8, vec(0, 1, 0)),
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=0.5)
        ids = [i["id"] for i in out]
        # a + c (with embeddings) come first via MMR; b appended after
        assert ids == ["a", "c", "b"]

    def test_lambda_clamped(self):
        items = [
            make_item("a", 1.0, vec(1, 0, 0)),
            make_item("b", 0.9, vec(0, 1, 0)),
        ]
        # lambda=-1 clamped to 0; lambda=5 clamped to 1
        for bad_lambda in [-1.0, 5.0, float("nan")]:
            out = mmr_rerank(items, lookup_from_items(items), lambda_=bad_lambda)
            # Doesn't crash, returns 2 items
            assert len(out) == 2

    def test_custom_score_field(self):
        items = [
            {"id": "a", "customScore": 0.5, "_emb": vec(1, 0, 0), "rrfScore": 999},
            {"id": "b", "customScore": 1.0, "_emb": vec(0, 1, 0), "rrfScore": 0},
        ]
        out = mmr_rerank(
            items,
            lookup_from_items(items),
            lambda_=1.0,  # pure relevance
            score_field="customScore",
        )
        # b's customScore (1.0) > a's (0.5), so b should win even though
        # rrfScore would say otherwise
        assert out[0]["id"] == "b"

    def test_missing_score_field_treated_as_zero(self):
        items = [
            {"id": "a", "_emb": vec(1, 0, 0)},  # no rrfScore
            {"id": "b", "_emb": vec(0, 1, 0)},
        ]
        out = mmr_rerank(items, lookup_from_items(items), lambda_=0.7)
        assert len(out) == 2

    def test_top_k_zero_returns_empty(self):
        items = [make_item("a", 1.0, vec(1, 0, 0))]
        assert mmr_rerank(items, lookup_from_items(items), top_k=0) == []

    def test_non_callable_lookup_raises(self):
        items = [make_item("a", 1.0, vec(1, 0, 0))]
        with pytest.raises(TypeError, match="callable"):
            mmr_rerank(items, "not a function")  # type: ignore[arg-type]

    def test_custom_id_field(self):
        # generate_homepage_rows.py calls mmr_rerank(..., id_field="name")
        # Items use "name" as the identifier, not the default "id".
        # The embedding lookup receives item["name"] rather than item["id"].
        items = [
            {"name": "DoubleML", "rrfScore": 0.9, "_emb": vec(1, 0, 0)},
            {"name": "EconML",   "rrfScore": 0.8, "_emb": vec(0, 1, 0)},
            {"name": "causalml", "rrfScore": 0.7, "_emb": vec(0.95, 0.05, 0)},
        ]

        def lookup_by_name(name):
            for it in items:
                if it["name"] == name:
                    return np.array(it["_emb"])
            return None

        out = mmr_rerank(items, lookup_by_name, id_field="name", lambda_=0.5)
        assert len(out) == 3
        # With lambda=0.5 and causalml nearly co-linear with DoubleML, EconML
        # should be selected 2nd (maximally diverse)
        names = [it["name"] for it in out]
        assert "DoubleML" in names
        assert "EconML" in names
        assert "causalml" in names

    def test_items_missing_custom_id_field_appended_at_end(self):
        # Items without the custom id_field key have no embedding → appended after
        items = [
            {"name": "DoubleML", "rrfScore": 0.9, "_emb": vec(1, 0, 0)},
            {"name": "EconML",   "rrfScore": 0.8, "_emb": vec(0, 1, 0)},
            {"title": "No Name Field", "rrfScore": 0.5},  # no "name" key
        ]

        def lookup_by_name(name):
            for it in items:
                if it.get("name") == name:
                    return np.array(it["_emb"])
            return None

        out = mmr_rerank(items, lookup_by_name, id_field="name", lambda_=0.7)
        assert len(out) == 3
        # The item without "name" has no embedding → appended last
        assert out[-1].get("title") == "No Name Field"


# ---------------------------------------------------------------------------
# Realistic scenario (mirrors the JS test)
# ---------------------------------------------------------------------------
class TestRealistic:
    def test_breaks_up_near_duplicate_triplet(self):
        items = [
            # 3 near-duplicates clustered in causal-inference space
            make_item("causal-1", 0.95, vec(1.0, 0.05, 0.0)),
            make_item("causal-2", 0.93, vec(1.0, 0.08, 0.0)),
            make_item("causal-3", 0.91, vec(1.0, 0.06, 0.01)),
            # Diverse neighbours at slightly lower relevance
            make_item("bayesian", 0.85, vec(0.0, 1.0, 0.0)),
            make_item("time-series", 0.8, vec(0.0, 0.0, 1.0)),
            make_item("econometrics", 0.75, vec(0.5, 0.5, 0.0)),
        ]
        lookup = lookup_from_items(items)

        baseline = mmr_rerank(items, lookup, lambda_=1.0, top_k=4)
        diverse = mmr_rerank(items, lookup, lambda_=0.7, top_k=4)

        baseline_ids = [i["id"] for i in baseline[:3]]
        assert baseline_ids == ["causal-1", "causal-2", "causal-3"]

        diverse_ids = [i["id"] for i in diverse[:3]]
        causal_count = sum(1 for x in diverse_ids if x.startswith("causal-"))
        assert causal_count <= 2
        assert diverse_ids[0] == "causal-1"  # top relevance always seed
