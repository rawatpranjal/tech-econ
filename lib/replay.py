"""Chronological replay of historical sessions against a candidate ranker.

The book's Ch7 calls Replay the bridge between offline metrics and
online A/B testing: it simulates "what would the new ranker have shown
this user, and would the user have clicked the same things?" using
captured-but-not-shown clicks from D1.

This module is pure logic — it expects the caller to pass the ranker's
output as a ranked list of item ids. The caller is responsible for
running the actual ranker against the candidate set and collecting D1
session click data.

Inputs:
    - ranking: list[str] of item ids in ranker's preferred order
    - clicked: set[str] of item ids the user actually clicked in this session
    - sessions: iterable of (ranking, clicked) pairs for aggregate metrics

Outputs:
    - SessionMetrics dataclass per session
    - AggregateMetrics dataclass averaging across sessions

Side effects:
    None.

Reproducibility:
    Pure functions. Same inputs → same outputs.

Architecture rules enforced
    - A1: typed Inputs/Outputs in docstring + dataclasses
    - A2: cross-module flow uses dataclasses, not bare dicts
    - E14: invalid k raises rather than silently returning 0
    - G18: every public function has a unit test

Why not pull D1 directly here: D1 access requires wrangler (subprocess)
or the analytics-worker HTTP API; both have their own concerns
(network, auth, rate limits). Keeping replay as pure logic means the
unit tests are deterministic and run in 50ms even on CI without
network access. The integration with D1 lives in
scripts/evaluate_recsys.py (follow-up).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from lib.metrics import (
    average_precision,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


__all__ = [
    "build_relevance_vector",
    "SessionMetrics",
    "AggregateMetrics",
    "evaluate_session",
    "aggregate_sessions",
]


def build_relevance_vector(
    ranking: Iterable[str],
    clicked: set[str] | frozenset[str],
) -> list[int]:
    """Convert (ranked list of ids, set of clicked ids) → binary relevance.

    Returned list is parallel to `ranking`: position i is 1 if
    ranking[i] is in `clicked`, else 0. Suitable for feeding into the
    metrics functions in lib.metrics.

    Notes
        - Duplicate ids in `ranking` are kept in place — caller is
          responsible for deduping if that matters. This matches how
          the live worker's RRF output sometimes has the same id from
          multiple sources (keyword + semantic).
        - `clicked` should be a set / frozenset for O(1) membership;
          we still accept any iterable but coerce on entry.
    """
    if not isinstance(clicked, (set, frozenset)):
        clicked = set(clicked)
    return [1 if item in clicked else 0 for item in ranking]


@dataclass(frozen=True)
class SessionMetrics:
    """Per-session metrics. NDCG@k and Precision@k are reported at the
    full configured `k_values` so the caller can show a curve."""
    n_ranked: int
    n_clicked: int
    n_clicked_in_ranking: int  # how many of `clicked` actually appeared

    # By-k metrics, keyed by the k value
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float]
    hit_rate_at_k: dict[int, float]
    ndcg_at_k: dict[int, float]

    # Overall (k-free) metrics
    average_precision: float


@dataclass(frozen=True)
class AggregateMetrics:
    """Mean of per-session metrics over an evaluation cohort."""
    n_sessions: int
    n_skipped: int  # sessions with no clicks → can't evaluate
    precision_at_k: dict[int, float] = field(default_factory=dict)
    recall_at_k: dict[int, float] = field(default_factory=dict)
    hit_rate_at_k: dict[int, float] = field(default_factory=dict)
    ndcg_at_k: dict[int, float] = field(default_factory=dict)
    mean_average_precision: float = 0.0


def evaluate_session(
    ranking: list[str],
    clicked: set[str] | frozenset[str] | Iterable[str],
    *,
    k_values: tuple[int, ...] = (5, 10),
) -> SessionMetrics:
    """Compute per-session metrics for one (ranking, clicked) pair.

    Sessions with zero clicks are evaluated as all-zero metrics —
    technically the metrics are undefined for them. Aggregate-level
    code should filter these out (n_skipped) rather than averaging
    them in. evaluate_session itself returns deterministic zeros so
    its output is always well-formed.
    """
    if not isinstance(clicked, (set, frozenset)):
        clicked = set(clicked)
    relevance = build_relevance_vector(ranking, clicked)

    n_ranked = len(ranking)
    n_clicked = len(clicked)
    n_in_ranking = sum(relevance)

    return SessionMetrics(
        n_ranked=n_ranked,
        n_clicked=n_clicked,
        n_clicked_in_ranking=n_in_ranking,
        precision_at_k={k: precision_at_k(relevance, k) for k in k_values},
        recall_at_k={k: recall_at_k(relevance, k) for k in k_values},
        hit_rate_at_k={k: hit_rate_at_k(relevance, k) for k in k_values},
        ndcg_at_k={k: ndcg_at_k(relevance, k) for k in k_values},
        average_precision=average_precision(relevance),
    )


def aggregate_sessions(
    sessions: Iterable[tuple[list[str], set[str] | Iterable[str]]],
    *,
    k_values: tuple[int, ...] = (5, 10),
) -> AggregateMetrics:
    """Average per-session metrics over a cohort of sessions.

    Sessions with zero clicks are skipped (they can't contribute to
    the average) and counted in `n_skipped` so the caller can decide
    whether the cohort is large enough to be statistically meaningful.

    Returns AggregateMetrics with all-zero values if every session is
    skipped — never raises.
    """
    per_k_precision: dict[int, list[float]] = {k: [] for k in k_values}
    per_k_recall: dict[int, list[float]] = {k: [] for k in k_values}
    per_k_hit: dict[int, list[float]] = {k: [] for k in k_values}
    per_k_ndcg: dict[int, list[float]] = {k: [] for k in k_values}
    aps: list[float] = []
    n_total = 0
    n_skipped = 0

    for ranking, clicked in sessions:
        n_total += 1
        clicked_set = clicked if isinstance(clicked, (set, frozenset)) else set(clicked)
        if len(clicked_set) == 0:
            n_skipped += 1
            continue
        sm = evaluate_session(ranking, clicked_set, k_values=k_values)
        for k in k_values:
            per_k_precision[k].append(sm.precision_at_k[k])
            per_k_recall[k].append(sm.recall_at_k[k])
            per_k_hit[k].append(sm.hit_rate_at_k[k])
            per_k_ndcg[k].append(sm.ndcg_at_k[k])
        aps.append(sm.average_precision)

    def _mean(xs: list[float]) -> float:
        if not xs:
            return 0.0
        return sum(xs) / len(xs)

    return AggregateMetrics(
        n_sessions=n_total,
        n_skipped=n_skipped,
        precision_at_k={k: _mean(per_k_precision[k]) for k in k_values},
        recall_at_k={k: _mean(per_k_recall[k]) for k in k_values},
        hit_rate_at_k={k: _mean(per_k_hit[k]) for k in k_values},
        ndcg_at_k={k: _mean(per_k_ndcg[k]) for k in k_values},
        mean_average_precision=_mean(aps),
    )
