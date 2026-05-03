"""Final score blending for the ranking pipeline.

Composes the engagement / cold-start / freshness / citations scores
into a single per-item value in [0, 1]. Currently inline in
scripts/rank_all_content.py:1273-1323. Extracting it here makes the
combination logic testable and lets callers (eg. evaluate_recsys.py)
score items consistently without duplicating ~50 lines.

Inputs
    - items:            list of dicts (each with name, type, optional citations)
    - engagement_scores: dict[name -> float] for items with observed interactions
    - predicted_scores:  dict[name -> float] (model output for ALL items)
    - cold_start_names:  set[str] of item names that lack real interactions
    - freshness_boosts:  dict[name -> float] additive boost in [0, boost_max]
                         (default empty)
    - cold_start_discount: multiplier on predicted_scores for cold items
                           (default 0.3, matches legacy)

Outputs
    - dict[name -> float] in [0, 1]

Side effects
    None.

Reproducibility
    Pure function. Same inputs -> same outputs.

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    A2: typed surface (CombinedScores dataclass for the result)
    A3: cold_start_discount + citation_weight come from caller, not
        hardcoded magic numbers
    C8: missing names tolerated (treated as 0)
    E14: invalid discount / weight raises rather than producing NaN
    G18: every public function has a unit test
"""

from __future__ import annotations

import math
from dataclasses import dataclass


__all__ = [
    "CombinedScores",
    "normalize_scores",
    "blend_engagement_with_predictions",
    "apply_freshness_boost",
    "apply_citations_boost",
    "combine_scores",
]


@dataclass(frozen=True)
class CombinedScores:
    """Result of the full score-combination pipeline."""

    scores: dict[str, float]
    n_observed: int
    n_cold: int
    n_fresh_boosted: int
    n_citation_boosted: int
    max_freshness_boost: float
    max_citation_boost: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalise a score dict into [0, 1].

    Empty input or all-equal scores → returns input unchanged (or
    empty). The legacy normalize_scores in rank_all_content.py does
    the same; reproducing the contract exactly so behaviour doesn't
    drift when callers swap to this version.
    """
    if not scores:
        return {}
    values = list(scores.values())
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        # Degenerate: every score equal. Return as-is.
        return dict(scores)
    span = hi - lo
    return {k: (v - lo) / span for k, v in scores.items()}


def blend_engagement_with_predictions(
    items: list[dict],
    engagement_scores: dict[str, float],
    predicted_scores: dict[str, float],
    *,
    cold_start_names: set[str] | None = None,
    cold_start_discount: float = 0.3,
    name_key: str = "name",
) -> dict[str, float]:
    """Use observed engagement for items with interactions, discounted
    predictions for cold-start items.

    `cold_start_names` is the set of names treated as cold. If None,
    we infer "cold = not in engagement_scores", which matches the
    legacy behaviour but is more brittle than the explicit set.

    Returns a dict of unnormalised blended scores. Apply
    normalize_scores() after if you want [0, 1].
    """
    if cold_start_discount < 0:
        raise ValueError(
            f"cold_start_discount must be >= 0, got {cold_start_discount}"
        )

    cold_set = (
        set(cold_start_names)
        if cold_start_names is not None
        else set()
    )

    out: dict[str, float] = {}
    for item in items:
        name = item.get(name_key)
        if not isinstance(name, str):
            continue
        is_cold = (
            name in cold_set
            if cold_start_names is not None
            else name not in engagement_scores
        )
        if not is_cold:
            out[name] = float(engagement_scores.get(name, 0.0))
        else:
            out[name] = float(predicted_scores.get(name, 0.0)) * cold_start_discount
    return out


def apply_freshness_boost(
    scores: dict[str, float],
    freshness_boosts: dict[str, float],
    *,
    cap: float = 1.0,
) -> tuple[dict[str, float], int, float]:
    """Add freshness boost per name; cap at `cap` (default 1.0).

    Returns (new_scores, n_boosted, max_boost). Items not in
    `freshness_boosts` pass through unchanged.
    """
    if cap < 0:
        raise ValueError(f"cap must be >= 0, got {cap}")
    out = dict(scores)
    n_boosted = 0
    max_boost = 0.0
    for name in scores:
        boost = freshness_boosts.get(name)
        if boost is None or boost <= 0:
            continue
        out[name] = min(cap, out[name] + boost)
        n_boosted += 1
        if boost > max_boost:
            max_boost = boost
    return out, n_boosted, max_boost


def apply_citations_boost(
    items: list[dict],
    scores: dict[str, float],
    *,
    citation_weight: float = 0.3,
    cap: float = 1.0,
    citations_key: str = "citations",
    name_key: str = "name",
    type_key: str = "type",
    paper_type: str = "paper",
) -> tuple[dict[str, float], int, float]:
    """Add a log-scaled citations boost for paper items.

    Formula (matches legacy rank_all_content.py):
        boost = citation_weight * log(citations + 1) / log(max + 1)

    Cap at `cap` (default 1.0). Non-paper items pass through.
    """
    if citation_weight < 0:
        raise ValueError(f"citation_weight must be >= 0, got {citation_weight}")
    if cap < 0:
        raise ValueError(f"cap must be >= 0, got {cap}")

    # Find max citation count among papers for normalisation
    max_citations = 0
    for item in items:
        if item.get(type_key) != paper_type:
            continue
        c = item.get(citations_key, 0) or 0
        try:
            c = int(c)
        except (TypeError, ValueError):
            c = 0
        if c > max_citations:
            max_citations = c

    out = dict(scores)
    n_boosted = 0
    max_boost = 0.0
    if max_citations <= 0:
        return out, 0, 0.0

    log_norm = math.log(max_citations + 1)
    for item in items:
        if item.get(type_key) != paper_type:
            continue
        name = item.get(name_key)
        if not isinstance(name, str) or name not in out:
            continue
        c = item.get(citations_key, 0) or 0
        try:
            c = int(c)
        except (TypeError, ValueError):
            c = 0
        if c <= 0:
            continue
        boost = citation_weight * math.log(c + 1) / log_norm
        out[name] = min(cap, out[name] + boost)
        n_boosted += 1
        if boost > max_boost:
            max_boost = boost
    return out, n_boosted, max_boost


def combine_scores(
    items: list[dict],
    engagement_scores: dict[str, float],
    predicted_scores: dict[str, float],
    *,
    cold_start_names: set[str] | None = None,
    freshness_boosts: dict[str, float] | None = None,
    cold_start_discount: float = 0.3,
    citation_weight: float = 0.3,
    cap: float = 1.0,
    name_key: str = "name",
) -> CombinedScores:
    """End-to-end pipeline: blend → normalise → freshness → normalise →
    citations → normalise. Mirrors rank_all_content.py:1275-1323 exactly
    so a swap is a 1-line change with no behaviour drift.
    """
    blended = blend_engagement_with_predictions(
        items,
        engagement_scores,
        predicted_scores,
        cold_start_names=cold_start_names,
        cold_start_discount=cold_start_discount,
        name_key=name_key,
    )
    normalised = normalize_scores(blended)

    freshness = freshness_boosts or {}
    after_fresh, n_fresh, max_fresh = apply_freshness_boost(
        normalised, freshness, cap=cap
    )
    after_fresh_norm = normalize_scores(after_fresh) if freshness else after_fresh

    after_citations, n_cite, max_cite = apply_citations_boost(
        items,
        after_fresh_norm,
        citation_weight=citation_weight,
        cap=cap,
        name_key=name_key,
    )
    final = normalize_scores(after_citations) if n_cite > 0 else after_citations

    n_observed = sum(1 for n in engagement_scores if n in {i.get(name_key) for i in items})
    n_cold = (
        len(cold_start_names) if cold_start_names is not None
        else sum(
            1 for i in items
            if i.get(name_key) and i.get(name_key) not in engagement_scores
        )
    )

    return CombinedScores(
        scores=final,
        n_observed=n_observed,
        n_cold=n_cold,
        n_fresh_boosted=n_fresh,
        n_citation_boosted=n_cite,
        max_freshness_boost=max_fresh,
        max_citation_boost=max_cite,
    )
