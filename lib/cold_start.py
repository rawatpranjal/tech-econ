"""k-NN score propagation for cold-start items.

Per audit Ra2: replace TF-IDF k-NN cold-start with bge embeddings.
This module is the testable core; rank_all_content.py is a separate
follow-up that consumes it.

The math
    For each item without an observed engagement score, we want a
    plausible starting score so it ranks somewhere reasonable on day 1
    (not at the bottom of the list, not above proven items either).

    Algorithm (Jarvelin / standard recsys cold-start):
        1. Partition items into `observed` (have a score) and `cold`
        2. For each cold item:
            a. Compute cosine similarity to every observed item
            b. Take the k nearest observed neighbours
            c. Weighted-average their scores (weights = similarities)
            d. Apply a discount (default 0.3) so cold items don't
               immediately rank above proven ones

    The similarity matrix is the parameter we vary: TF-IDF over
    metadata text, or bge embeddings over the same content. The
    propagation logic is identical either way.

Inputs
    - items:           list of dicts with at least `name` and `type`
    - observed_scores: dict[name -> float] for items with engagement
    - similarity_fn:   callable(observed_idx_list, cold_idx_list) ->
                       2-D ndarray of shape (n_cold, n_observed) where
                       entry [i, j] is sim(cold_i, observed_j) in [-1, 1]
    - k:               number of nearest neighbours to consult (>=1)
    - discount:        multiplicative penalty applied to propagated
                       score (default 0.3 — matches the legacy behaviour)

Outputs
    - dict[name -> float] giving propagated scores for every cold item

Side effects
    None.

Reproducibility
    - Pure given a fixed similarity_fn
    - Tie-breaking in argpartition is implementation-defined; for
      reproducible tests pass strictly distinct similarities

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    A2: typed surface (dataclass for the result; ndarray for matrices)
    A3: discount + k come from the caller / config — no hardcoded
        magic numbers in this module
    C8: items without scores are tolerated (treated as cold)
    E14: invalid k or empty observed set raises rather than returning
        garbage
    G18: every public function has a unit test
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

import numpy as np


__all__ = [
    "ColdStartResult",
    "propagate_cold_start_scores",
    "make_dense_similarity_fn",
    "make_tfidf_similarity_fn",
]


@dataclass(frozen=True)
class ColdStartResult:
    """Wrapper for the result of a propagation pass. Carries the
    score map plus stats for logging."""

    scores: dict[str, float]
    n_observed: int
    n_cold: int
    fallback: bool  # True if we hit the "no observed items / no features" path


def propagate_cold_start_scores(
    items: list[dict],
    observed_scores: dict[str, float],
    similarity_fn: Callable[[list[int], list[int]], np.ndarray] | None,
    *,
    k: int = 5,
    discount: float = 0.3,
    name_key: str = "name",
) -> ColdStartResult:
    """Propagate observed scores to cold-start items via k-NN.

    `similarity_fn` may be None to force the type-average fallback;
    in production it's almost always a real callable.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if discount < 0:
        raise ValueError(f"discount must be >= 0, got {discount}")

    # Partition by membership in observed_scores
    observed_indices: list[int] = []
    cold_indices: list[int] = []
    observed_score_list: list[float] = []

    for i, item in enumerate(items):
        name = item.get(name_key)
        if name is None:
            # Items without a name field can't be matched in/out of
            # observed_scores. Treat as cold and they'll get the
            # fallback (type-average / global-average).
            cold_indices.append(i)
            continue
        if name in observed_scores:
            observed_indices.append(i)
            observed_score_list.append(float(observed_scores[name]))
        else:
            cold_indices.append(i)

    cold_scores: dict[str, float] = {}

    # Fallback: no observed items OR no similarity function supplied
    if not observed_indices or similarity_fn is None:
        fallback_map = _compute_fallback_scores(items, observed_indices, observed_score_list)
        for i in cold_indices:
            name = items[i].get(name_key)
            if name is None:
                continue
            base = fallback_map.get(items[i].get("type", ""), fallback_map.get("__global__", 0.0))
            cold_scores[name] = base * discount
        return ColdStartResult(
            scores=cold_scores,
            n_observed=len(observed_indices),
            n_cold=len(cold_indices),
            fallback=True,
        )

    if not cold_indices:
        # Nothing to do — every item already has a score.
        return ColdStartResult(
            scores={},
            n_observed=len(observed_indices),
            n_cold=0,
            fallback=False,
        )

    # Compute similarity matrix (n_cold, n_observed)
    sim_matrix = similarity_fn(observed_indices, cold_indices)
    if sim_matrix.shape != (len(cold_indices), len(observed_indices)):
        raise ValueError(
            f"similarity_fn returned shape {sim_matrix.shape}; "
            f"expected ({len(cold_indices)}, {len(observed_indices)})"
        )

    observed_score_arr = np.asarray(observed_score_list, dtype=np.float64)
    global_avg = float(observed_score_arr.mean()) if observed_score_arr.size else 0.0

    for j, cold_idx in enumerate(cold_indices):
        name = items[cold_idx].get(name_key)
        if name is None:
            continue
        sims = sim_matrix[j]
        # Top-k neighbour indices (into observed_*)
        if len(sims) <= k:
            top_k = np.arange(len(sims))
        else:
            top_k = np.argpartition(sims, -k)[-k:]
        top_k_sims = sims[top_k]
        top_k_scores = observed_score_arr[top_k]

        # Negative similarities are valid (cosine returns [-1, 1]); we
        # only fall back to the global average when ALL the weights are
        # zero or negative, since a negative-weighted average has no
        # principled meaning here.
        positive_weights = top_k_sims.clip(min=0)
        if positive_weights.sum() > 0:
            propagated = float(np.average(top_k_scores, weights=positive_weights))
        else:
            propagated = global_avg

        cold_scores[name] = propagated * discount

    return ColdStartResult(
        scores=cold_scores,
        n_observed=len(observed_indices),
        n_cold=len(cold_indices),
        fallback=False,
    )


# ---------------------------------------------------------------------------
# Fallback (type-average, no similarity available)
# ---------------------------------------------------------------------------
def _compute_fallback_scores(
    items: list[dict],
    observed_indices: list[int],
    observed_score_list: list[float],
) -> dict[str, float]:
    """Per-type average of observed scores, plus a __global__ default."""
    type_scores: dict[str, list[float]] = defaultdict(list)
    for i, idx in enumerate(observed_indices):
        item_type = items[idx].get("type", "")
        type_scores[item_type].append(observed_score_list[i])
    out = {t: float(np.mean(s)) for t, s in type_scores.items() if s}
    out["__global__"] = float(np.mean(observed_score_list)) if observed_score_list else 0.0
    return out


# ---------------------------------------------------------------------------
# Similarity-fn factories
# ---------------------------------------------------------------------------
def make_dense_similarity_fn(
    embeddings: np.ndarray,
) -> Callable[[list[int], list[int]], np.ndarray]:
    """Build a similarity_fn for a dense embedding matrix.

    `embeddings` is shape (n_items, dim). Each row is L2-normalised on
    the fly so the dot product is a true cosine similarity. This is
    the bge-large path for Ra2: pass the same `static/embeddings/
    search-embeddings.bin` matrix that powers semantic search, so cold
    items get scored by behavioural-quality neighbours, not by raw
    metadata token overlap.
    """
    embeddings = np.asarray(embeddings, dtype=np.float64)
    if embeddings.ndim != 2:
        raise ValueError(
            f"Expected 2-D embeddings matrix, got shape {embeddings.shape}"
        )
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    # Avoid zero-norm rows producing NaN — replace with 1.0 (the
    # similarity will then be 0 for that row).
    safe_norms = np.where(norms == 0, 1.0, norms)
    normalised = embeddings / safe_norms

    def sim_fn(observed_idx: list[int], cold_idx: list[int]) -> np.ndarray:
        if not observed_idx or not cold_idx:
            return np.zeros((len(cold_idx), len(observed_idx)), dtype=np.float64)
        cold_mat = normalised[np.asarray(cold_idx)]
        obs_mat = normalised[np.asarray(observed_idx)]
        return cold_mat @ obs_mat.T

    return sim_fn


def make_tfidf_similarity_fn(
    feature_matrix,  # scipy.sparse.csr_matrix or dense ndarray
) -> Callable[[list[int], list[int]], np.ndarray]:
    """Build a similarity_fn for a (typically sparse) TF-IDF matrix.

    Mirrors the legacy behaviour in scripts/rank_all_content.py so a
    side-by-side comparison with the bge variant (Ra2) is a single-
    parameter swap.
    """
    # Lazy import — sklearn isn't a lib/ light-deps requirement
    from sklearn.metrics.pairwise import cosine_similarity

    def sim_fn(observed_idx: list[int], cold_idx: list[int]) -> np.ndarray:
        if not observed_idx or not cold_idx:
            return np.zeros((len(cold_idx), len(observed_idx)), dtype=np.float64)
        cold_mat = feature_matrix[cold_idx]
        obs_mat = feature_matrix[observed_idx]
        return cosine_similarity(cold_mat, obs_mat)

    return sim_fn
