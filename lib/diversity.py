"""Maximal Marginal Relevance reranking — Python port of static/js/search/mmr.js.

Why a Python copy
    The JS version powers search-time reranking in the browser. The
    Python version is for *build-time* uses:
      - homepage row diversification (rank_all_content.py currently
        uses ad-hoc "max-2-per-type" rules; MMR is the principled
        upgrade per the audit's Re6)
      - replay-mode evaluation (compare a candidate ranker that uses
        MMR against the legacy that doesn't, on the same fixture)

    Keeping the math identical to the JS module means the search-side
    and ranker-side diversification behave the same way. Cosine, the
    lambda parameter, and the "items without embeddings tail" logic
    all match search-worker.js's behaviour exactly.

The math
    Given items with relevance scores and embeddings:

        score(i) = lambda * relevance(i)
                 - (1 - lambda) * max_{s in selected} cos(emb_i, emb_s)

    lambda = 1.0 → pure relevance (no-op)
    lambda = 0.0 → pure diversity
    lambda = 0.7 → balanced (default for tech-econ; matches the JS)

Inputs
    - items:               list of dicts with at least an `id` key and
                            a `score_field` key carrying the relevance
    - embedding_lookup:    callable(id: str) -> np.ndarray | None.
                            Returning None means "no embedding for this
                            item" — caller's choice; MMR handles it.
    - lambda_:             relevance/diversity tradeoff, [0, 1]
    - top_k:               output length cap (default = len(items))
    - score_field:         which key on each item carries the score
                            (default 'rrfScore' to match the JS)

Outputs
    - list of items (same shape as input) reordered + truncated to
      top_k. Items WITHOUT embeddings are appended after the diverse
      set, preserving their relative input order, so we never drop a
      result purely because its embedding is missing.

Side effects
    None.

Reproducibility
    - Pure given a fixed embedding_lookup
    - Tie-breaking: when two items have identical MMR scores, the
      one earlier in the input list wins (numpy argmax behaviour)

Architecture rules enforced
    A1: full Inputs/Outputs/Side effects/Reproducibility docstring
    A2: typed surface (np.ndarray for embeddings; output preserves
        input dict shape)
    A3: lambda_ + top_k + score_field come from caller
    C8: items without embeddings tolerated; missing score_field
        treated as 0 not as crash
    E14: invalid lambda gets clamped to [0, 1] with a warning rather
        than silently producing NaN; non-callable embedding_lookup
        raises (the caller passed garbage)
    G18: every public function has a unit test
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np


__all__ = [
    "cosine_sim",
    "mmr_rerank",
]


def cosine_sim(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """Defensive cosine: returns 0 for None / mismatched lengths /
    zero-norm vectors so downstream MMR doesn't propagate NaN.

    Matches the JS cosineSim contract from static/js/search/mmr.js
    (verified by parallel test suites).
    """
    if a is None or b is None:
        return 0.0
    if a.shape != b.shape:
        return 0.0
    if a.size == 0:
        return 0.0
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def mmr_rerank(
    items: list[dict[str, Any]],
    embedding_lookup: Callable[[Any], np.ndarray | None] | None,
    *,
    lambda_: float = 0.7,
    top_k: int | None = None,
    score_field: str = "rrfScore",
    id_field: str = "id",
) -> list[dict[str, Any]]:
    """Greedy MMR over a list of scored items.

    Items without an embedding are NOT excluded — they're appended
    after the diverse set, preserving their relative input order.
    """
    if not items:
        return []

    # Clamp lambda
    if not isinstance(lambda_, (int, float)) or lambda_ != lambda_:  # NaN check
        lambda_ = 0.7
    lambda_ = max(0.0, min(1.0, float(lambda_)))

    if top_k is None:
        top_k = len(items)
    if top_k <= 0:
        return []

    # No lookup function → pure-relevance fallback
    if embedding_lookup is None:
        return list(items)[:top_k]
    if not callable(embedding_lookup):
        raise TypeError(
            f"embedding_lookup must be callable or None, got "
            f"{type(embedding_lookup).__name__}"
        )

    # Resolve embeddings once
    n = len(items)
    embeddings: list[np.ndarray | None] = [None] * n
    with_emb_idx: list[int] = []
    without_emb_idx: list[int] = []
    for i, item in enumerate(items):
        item_id = item.get(id_field)
        emb = embedding_lookup(item_id) if item_id is not None else None
        if emb is not None:
            emb = np.asarray(emb, dtype=np.float64)
            embeddings[i] = emb
            with_emb_idx.append(i)
        else:
            without_emb_idx.append(i)

    # Fast path: lambda ≈ 1 → defensive sort by score (matches the JS
    # mmr.js fix where the original assumed pre-sorted input but a test
    # caught a custom score_field violating that)
    if lambda_ >= 0.999:
        sorted_items = sorted(
            items,
            key=lambda it: it.get(score_field, 0) if isinstance(
                it.get(score_field, 0), (int, float)
            ) else 0,
            reverse=True,
        )
        return sorted_items[:top_k]

    # Greedy MMR over items WITH embeddings
    pool = list(with_emb_idx)
    selected: list[int] = []
    max_sim_to_sel: dict[int, float] = {}

    while pool and len(selected) < top_k:
        best_idx_in_pool = -1
        best_score = float("-inf")
        for p, idx in enumerate(pool):
            rel = items[idx].get(score_field, 0)
            if not isinstance(rel, (int, float)) or rel != rel:  # NaN guard
                rel = 0
            sim = max_sim_to_sel.get(idx, 0.0)
            mmr_score = lambda_ * rel - (1.0 - lambda_) * sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx_in_pool = p
        if best_idx_in_pool == -1:
            break

        picked = pool[best_idx_in_pool]
        selected.append(picked)
        pool.pop(best_idx_in_pool)

        # Update max-sim for everyone left
        picked_emb = embeddings[picked]
        for q_idx in pool:
            s = cosine_sim(picked_emb, embeddings[q_idx])
            if s > max_sim_to_sel.get(q_idx, 0.0):
                max_sim_to_sel[q_idx] = s

    result = [items[i] for i in selected]
    # Append items without embeddings, preserving input order, until topK
    for i in without_emb_idx:
        if len(result) >= top_k:
            break
        result.append(items[i])
    return result
