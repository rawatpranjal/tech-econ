#!/usr/bin/env python3
"""Replay a candidate ranker against historical sessions.

Inputs:
    - --baseline: scores JSON for the production ranker (defaults to
      data/global_rankings.json)
    - --candidate: scores JSON for the experiment to test (must follow
      the same {"rankings": [{"name": .., "score": ..}]} shape)
    - D1 events table for the holdout window

Outputs:
    - stdout: side-by-side metrics for baseline vs candidate
    - exit 0 if candidate is no worse than baseline beyond
      `ndcg_drop_alert_threshold`, exit 5 otherwise (so CI can gate)

Side effects:
    - Network read from analytics-worker / wrangler
    - No file writes (this is purely diagnostic; the production CSV is
      owned by evaluate_recsys.py)

Usage:
    python3 scripts/replay_eval.py \\
      --candidate /tmp/experiment_scores.json
    python3 scripts/replay_eval.py \\
      --baseline data/global_rankings.json \\
      --candidate data/experiment_rankings.json \\
      --source wrangler

Architecture rules enforced
    A1, A2, E14 (refuses to declare a winner with zero sessions).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.d1_sessions import SessionLoadError, load_sessions
from lib.data_io import current_git_sha
from lib.eval_runner import EvalResult, run_evaluation, write_replay_row
from lib.recsys_config import load as load_config

# Borrow the scores loader from evaluate_recsys -- single source of truth.
from scripts.evaluate_recsys import (  # noqa: E402  (after sys.path setup)
    DEFAULT_API,
    DEFAULT_SCORES_PATH,
    load_scores,
)


def _print_side_by_side(baseline: EvalResult, candidate: EvalResult) -> None:
    print()
    print("=" * 72)
    print("REPLAY EVALUATION")
    print("=" * 72)
    print(f"Sessions evaluated: {baseline.n_sessions_evaluable} "
          f"(of {baseline.n_sessions_total} in holdout)")
    print()
    header = f"{'metric':<24} {'baseline':>10} {'candidate':>10} {'delta':>10} {'delta_pct':>10}"
    print(header)
    print("-" * len(header))

    rows: list[tuple[str, float, float]] = [
        ("mean_average_precision",
         baseline.aggregate.mean_average_precision,
         candidate.aggregate.mean_average_precision),
    ]
    for k in baseline.k_values:
        rows.append(
            (f"ndcg_at_{k}",
             baseline.aggregate.ndcg_at_k.get(k, 0.0),
             candidate.aggregate.ndcg_at_k.get(k, 0.0))
        )
        rows.append(
            (f"precision_at_{k}",
             baseline.aggregate.precision_at_k.get(k, 0.0),
             candidate.aggregate.precision_at_k.get(k, 0.0))
        )
        rows.append(
            (f"hit_rate_at_{k}",
             baseline.aggregate.hit_rate_at_k.get(k, 0.0),
             candidate.aggregate.hit_rate_at_k.get(k, 0.0))
        )

    for name, b, c in rows:
        delta = c - b
        pct = (delta / b * 100.0) if b > 0 else 0.0
        print(f"{name:<24} {b:>10.4f} {c:>10.4f} {delta:>+10.4f} {pct:>+9.1f}%")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, default=DEFAULT_SCORES_PATH,
        help="baseline scores JSON (default: data/global_rankings.json)",
    )
    parser.add_argument(
        "--candidate", type=Path, required=True,
        help="candidate scores JSON to test against the baseline",
    )
    parser.add_argument(
        "--source", choices=["api", "wrangler"], default="api",
    )
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument(
        "--holdout-days", type=int, default=None,
        help="override config.evaluation.holdout_days",
    )
    parser.add_argument("--fill-with-global-top", type=int, default=0)
    parser.add_argument(
        "--now", default=None,
        help="ISO-8601 timestamp to freeze the holdout window (tests)",
    )
    parser.add_argument(
        "--regression-metric", default="ndcg_at_10",
        help="metric used to gate exit code (default: ndcg_at_10)",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=_REPO_ROOT / "reports" / "replays.csv",
        help="path to append a side-by-side row to (default: reports/replays.csv)",
    )
    parser.add_argument(
        "--no-output-csv", action="store_true",
        help="skip writing the replay history row",
    )
    parser.add_argument(
        "--notes", default="",
        help="free-form note appended to the replay history row",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    holdout_days = args.holdout_days or config.evaluation.holdout_days
    k_values = tuple(config.evaluation.k_values)

    print(f"replay_eval: baseline={args.baseline} candidate={args.candidate} "
          f"source={args.source} holdout_days={holdout_days}")

    baseline_scores = load_scores(args.baseline)
    candidate_scores = load_scores(args.candidate)
    print(f"  loaded {len(baseline_scores)} baseline + {len(candidate_scores)} candidate scores")

    now: datetime | None = None
    if args.now:
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

    try:
        sessions = load_sessions(
            holdout_days=holdout_days,
            source=args.source,
            api_url=args.api_url if args.source == "api" else None,
            now=now,
        )
    except SessionLoadError as e:
        print(f"  D1 unreachable: {e}", file=sys.stderr)
        return 3

    if not sessions:
        print("  Zero sessions in the holdout window. Cannot declare a winner.",
              file=sys.stderr)
        return 4

    git_sha = current_git_sha()
    baseline_result = run_evaluation(
        scores=baseline_scores,
        sessions=sessions,
        holdout_days=holdout_days,
        k_values=k_values,
        git_sha=git_sha,
        fill_with_global_top=args.fill_with_global_top,
        notes="baseline",
    )
    candidate_result = run_evaluation(
        scores=candidate_scores,
        sessions=sessions,
        holdout_days=holdout_days,
        k_values=k_values,
        git_sha=git_sha,
        fill_with_global_top=args.fill_with_global_top,
        notes="candidate",
    )
    _print_side_by_side(baseline_result, candidate_result)

    # Gate on the configured regression metric.
    metric = args.regression_metric
    threshold = config.evaluation.ndcg_drop_alert_threshold
    if metric.startswith("ndcg_at_"):
        k = int(metric.removeprefix("ndcg_at_"))
        b = baseline_result.aggregate.ndcg_at_k.get(k, 0.0)
        c = candidate_result.aggregate.ndcg_at_k.get(k, 0.0)
    elif metric == "mean_average_precision":
        b = baseline_result.aggregate.mean_average_precision
        c = candidate_result.aggregate.mean_average_precision
    else:
        print(f"  unsupported --regression-metric {metric!r}", file=sys.stderr)
        return 2

    regressed = b > 0 and (b - c) / b > threshold
    verdict = "regressed" if regressed else "ok"

    # Append history row before exit so even regressions are recorded.
    if not args.no_output_csv:
        try:
            write_replay_row(
                args.output_csv,
                baseline=baseline_result,
                candidate=candidate_result,
                baseline_path=str(args.baseline),
                candidate_path=str(args.candidate),
                regression_metric=metric,
                regression_threshold=threshold,
                verdict=verdict,
                notes=args.notes,
            )
            print(f"  appended replay row to {args.output_csv}")
        except ValueError as e:
            # Header drift -- don't block the exit code on it; just warn
            print(f"  WARNING: replay row not written ({e})", file=sys.stderr)

    if regressed:
        print(
            f"  CANDIDATE REGRESSED: {metric} dropped from {b:.4f} to {c:.4f} "
            f"(threshold {threshold * 100:.1f}%). Exit 5.",
            file=sys.stderr,
        )
        return 5
    print(f"  CANDIDATE OK on {metric}: baseline={b:.4f} candidate={c:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
