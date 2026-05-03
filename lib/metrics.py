"""Ranking quality metrics for offline evaluation (Phase 1 of audit).

Pure numpy implementations so they can run inside scripts/rank_all_content.py
without dragging in heavy ML dependencies. All functions take *binary
relevance* labels (1 = relevant / clicked, 0 = not relevant) and the
ranked predictions, and return a single scalar score.

Inputs:
    - y_true: 1-D iterable of {0, 1} labels in *ranking order*
      (most-recommended first). Length n.
    - For per-query metrics, the caller is responsible for trimming /
      padding `y_true` to the desired top-K.

Outputs:
    - Single float in [0, 1] (or [0, n] for sums where noted).

Side effects:
    None.

Reproducibility:
    - Pure functions; same inputs → same output.
    - No randomness, no hidden config.

Architecture rules enforced
    - A1: every public function has a docstring with Inputs / Outputs.
    - E14: invalid inputs raise instead of silently returning 0.
    - G18: every public function has unit tests in
      tests/python/lib/test_metrics.py.

References
    - DCG / NDCG formulation: Järvelin & Kekäläinen 2002, "Cumulated
      Gain-Based Evaluation of IR Techniques". We use the standard
      "logarithmic" gain formulation:
          DCG@k = sum_{i=1..k} rel_i / log2(i + 1)
      where rel_i is the relevance of the item at rank i (1-indexed).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np


__all__ = [
    "precision_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "average_precision",
    "dcg_at_k",
    "ndcg_at_k",
    "_to_binary_array",
]


def _to_binary_array(y_true: Iterable[int]) -> np.ndarray:
    """Internal: coerce iterable to 1-D numpy array, validate {0, 1}."""
    arr = np.asarray(list(y_true), dtype=np.int64)
    if arr.ndim != 1:
        raise ValueError(
            f"Expected 1-D array of binary labels, got shape {arr.shape}"
        )
    bad = arr[(arr != 0) & (arr != 1)]
    if bad.size > 0:
        raise ValueError(
            "y_true must contain only 0/1 binary labels; "
            f"saw {sorted(set(bad.tolist()))[:5]}"
        )
    return arr


def precision_at_k(y_true: Iterable[int], k: int) -> float:
    """Fraction of items in the top-K that are relevant.

    Examples:
        precision@3 with y_true = [1, 0, 1, 0, 0] → 2/3
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    arr = _to_binary_array(y_true)
    if arr.size == 0:
        return 0.0
    top = arr[:k]
    return float(top.sum()) / float(k)


def recall_at_k(y_true: Iterable[int], k: int) -> float:
    """Fraction of *all* relevant items recovered in the top-K.

    If there are zero relevant items in y_true, returns 0.0 (rather
    than NaN). Convention: a query with no relevant items has recall
    undefined; the offline harness collapses this to 0 so it can
    average across queries safely. Document this in your reports.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    arr = _to_binary_array(y_true)
    total_relevant = int(arr.sum())
    if total_relevant == 0:
        return 0.0
    return float(arr[:k].sum()) / float(total_relevant)


def hit_rate_at_k(y_true: Iterable[int], k: int) -> float:
    """1.0 if any of the top-K are relevant, else 0.0.

    Often the easiest metric to communicate to non-ML stakeholders:
    "did we put SOMETHING good in the top 10?". Averages cleanly
    across queries.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    arr = _to_binary_array(y_true)
    if arr.size == 0:
        return 0.0
    return 1.0 if arr[:k].sum() > 0 else 0.0


def average_precision(y_true: Iterable[int]) -> float:
    """Average precision over a single ranked list.

        AP = (1 / R) * sum_{k=1..n} precision@k * rel_k
    where R is the number of relevant items in y_true.

    AP = 0.0 if there are no relevant items (consistent with
    recall_at_k convention above).
    """
    arr = _to_binary_array(y_true)
    total_relevant = int(arr.sum())
    if total_relevant == 0:
        return 0.0

    cum_relevant = np.cumsum(arr)
    ranks = np.arange(1, arr.size + 1, dtype=np.float64)
    # precision@k for every k where rel_k = 1
    precisions = cum_relevant.astype(np.float64) / ranks
    contributions = precisions * arr  # zero-out non-relevant positions
    return float(contributions.sum()) / float(total_relevant)


def dcg_at_k(y_true: Iterable[int], k: int) -> float:
    """Discounted Cumulative Gain at K with binary relevance.

        DCG@k = sum_{i=1..k} rel_i / log2(i + 1)
    where i is 1-indexed.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    arr = _to_binary_array(y_true)
    if arr.size == 0:
        return 0.0
    top = arr[:k].astype(np.float64)
    if top.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, top.size + 2))
    return float((top * discounts).sum())


def ndcg_at_k(y_true: Iterable[int], k: int) -> float:
    """Normalised DCG at K, in [0, 1].

        NDCG@k = DCG@k / IDCG@k
    where IDCG@k is the DCG of the *best possible* ranking (all
    relevant items at the top). NDCG = 0 if there are no relevant
    items, by convention.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    arr = _to_binary_array(y_true)
    n_relevant = int(arr.sum())
    if n_relevant == 0:
        return 0.0

    dcg = dcg_at_k(arr, k)
    # Ideal: all relevant items at the top, capped by k
    n_ideal = min(n_relevant, k)
    ideal_arr = np.zeros(arr.size, dtype=np.int64)
    ideal_arr[:n_ideal] = 1
    idcg = dcg_at_k(ideal_arr, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg
