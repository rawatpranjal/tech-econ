"""Homepage trending row selection: filtering + MMR diversification.

This module is the testable core of the "top 12 items shown on the
homepage" decision. It lives in lib/ (not in scripts/rank_all_content.py)
so unit tests can import it without dragging in sklearn /
sentence-transformers / lightgbm — those are only needed for the
training pass that produces the input rankings, not for the trending
selection itself.

Inputs
    - rankings:        list of dicts with at least `name`, `score`,
                       `type`, `cold_start` keys (the shape produced
                       by rank_all_content.py:1490-1530)
    - encoder:         object with `.encode(list[str], show_progress_bar)`
                       returning an (n, dim) ndarray. The script-loaded
                       SentenceTransformer model satisfies this; tests
                       inject a stub.

Outputs
    - select_diverse_trending: list of items (subset of `rankings`)
      reordered + truncated to top_n via MMR
    - build_trending_embedding_lookup: callable(name) -> ndarray | None,
      ready to feed into mmr_rerank

Side effects
    None. The encoder may make network calls on first use (model
    download); that's the caller's concern.

Reproducibility
    - select_diverse_trending: pure given a fixed embedding_lookup
    - build_trending_embedding_lookup: deterministic per encoder

Architecture rules enforced
    A1 (Inputs/Outputs/Side effects/Reproducibility documented),
    A2 (typed surface: callable embedding_lookup, ndarray vectors),
    A3 (lambda_, pool_multiplier, min_pool_size from caller — no
        magic constants),
    C8 (missing embedding -> pure-relevance fallback, never crash),
    E14 (encoder failure logged + returns None, not silent NaN),
    G18 (every public function has a unit test in
         tests/python/lib/test_trending.py).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from lib.diversity import mmr_rerank


__all__ = [
    "select_diverse_trending",
    "build_trending_embedding_lookup",
]


def select_diverse_trending(
    rankings: list[dict[str, Any]],
    *,
    n: int = 12,
    lambda_: float = 0.7,
    pool_multiplier: int = 3,
    min_pool_size: int = 30,
    embedding_lookup: Callable[[Any], np.ndarray | None] | None = None,
) -> list[dict[str, Any]]:
    """Pick the homepage trending row with MMR diversification.

    Replaces the legacy "max-2-per-type / max-2-per-category" rule
    (commit cce2ebd) with a principled MMR pass via lib.diversity.mmr_rerank
    (the same module that powers search-side diversification at lambda=0.7).

    Filters
        - cold-start items (no observed engagement)
        - 'career' items (legacy: career portals shouldn't trend)

    `embedding_lookup` is callable(name) -> ndarray | None. When None
    we fall through to mmr_rerank's pure-relevance path -- the homepage
    row still works, it just isn't diversified.
    """
    candidates = [
        r for r in rankings
        if not r.get("cold_start", False) and r.get("type") != "career"
    ]
    if not candidates:
        return []

    pool_size = max(n * pool_multiplier, min_pool_size)
    pool = candidates[:pool_size]

    return mmr_rerank(
        pool,
        embedding_lookup=embedding_lookup,
        lambda_=lambda_,
        top_k=n,
        score_field="score",
        id_field="name",
    )


def build_trending_embedding_lookup(
    rankings: list[dict[str, Any]],
    encoder: Any,
    *,
    pool_size: int = 60,
) -> Callable[[Any], np.ndarray | None] | None:
    """Encode the trending candidate pool's text via `encoder` and
    return a name->vector lookup callable suitable for mmr_rerank.

    `encoder` is anything with `.encode(list[str], show_progress_bar=...)`
    returning a (n, dim) ndarray. The script-loaded SBERT model
    satisfies this; tests inject any stub.

    Returns None when:
      - the candidate pool is empty (everything cold or career), or
      - the encoder raises (network outage, model download failed, etc.)
    Callers should treat None as "MMR falls back to pure-relevance"
    rather than aborting the rerank.
    """
    pool = [
        r for r in rankings
        if not r.get("cold_start", False)
        and r.get("type") != "career"
        and isinstance(r.get("name"), str)
    ][:pool_size]
    if not pool:
        return None
    texts = [
        f"{r.get('name', '')} {(r.get('description', '') or '')[:200]}"
        for r in pool
    ]
    try:
        vectors = encoder.encode(texts, show_progress_bar=False)
    except Exception as e:
        print(
            f"  Warning: SBERT encode failed for trending pool ({e}); "
            "MMR will fall back to pure-relevance ordering."
        )
        return None
    by_name = {r["name"]: vectors[i] for i, r in enumerate(pool)}
    return by_name.get
