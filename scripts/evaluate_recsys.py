#!/usr/bin/env python3
"""Offline evaluation runner for the recsys ranker.

Inputs:
    - data/global_rankings.json (or --scores-file): the current
      ranker's per-item scores.
    - D1 events table via --source api or --source wrangler
    - data/recsys_config.json (key: evaluation)

Outputs:
    - reports/metrics.csv  (one row appended per run)
    - stdout: a one-screen summary

Side effects:
    - Network read from analytics-worker (or wrangler subprocess)
    - Atomic CSV append at reports/metrics.csv

Reproducibility:
    - --now lets tests freeze the holdout window
    - --git-sha overrides the auto-detected sha for deterministic test
      output

Usage:
    python3 scripts/evaluate_recsys.py
    python3 scripts/evaluate_recsys.py --source wrangler
    python3 scripts/evaluate_recsys.py --scores-file data/global_rankings.json
    python3 scripts/evaluate_recsys.py --skip-regression-check

Architecture rules enforced
    A1, A2, A3 (config-driven k_values + threshold), D11 (logs
    inputs at start), E14 (raises rather than silently producing
    NDCG = 0), G19 (the script has an output-shape test).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make `lib/` importable when this script is run directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.d1_sessions import SessionLoadError, load_sessions
from lib.data_io import current_git_sha
from lib.eval_runner import (
    EvalResult,
    RegressionAlert,
    check_regression,
    format_metrics_row,
    read_last_metrics_row,
    run_evaluation,
    write_metrics_row,
)
from lib.recsys_config import load as load_config


DEFAULT_API = "https://tech-econ-analytics-v2.pp712.workers.dev"
DEFAULT_METRICS_CSV = _REPO_ROOT / "reports" / "metrics.csv"
DEFAULT_SCORES_PATH = _REPO_ROOT / "data" / "global_rankings.json"


def _scores_from_global_rankings(payload: dict[str, Any]) -> dict[str, float]:
    """Pull (lowercased name -> score) out of data/global_rankings.json.

    The file shape is `{"rankings": [{"name": "...", "score": 0.xx, ...}]}`.
    """
    rankings = payload.get("rankings")
    if not isinstance(rankings, list):
        raise ValueError(
            "global_rankings.json has no 'rankings' list -- did the "
            "rerank pipeline finish?"
        )
    out: dict[str, float] = {}
    for item in rankings:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        score = item.get("score")
        if not isinstance(name, str) or not isinstance(score, (int, float)):
            continue
        out[name.strip().lower()] = float(score)
    if not out:
        raise ValueError(
            "global_rankings.json had no usable (name, score) pairs"
        )
    return out


def load_scores(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run rank_all_content.py first, "
            "or pass --scores-file pointing at a valid JSON."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "rankings" in payload:
        return _scores_from_global_rankings(payload)
    if isinstance(payload, dict):
        # Allow plain {name: score} as a debug shortcut
        return {
            str(k).strip().lower(): float(v)
            for k, v in payload.items()
            if isinstance(k, str) and isinstance(v, (int, float))
        }
    raise ValueError(f"{path} has unsupported shape (expected dict)")


def print_summary(result: EvalResult, csv_path: Path) -> None:
    print()
    print("=" * 60)
    print("OFFLINE EVALUATION RESULT")
    print("=" * 60)
    print(f"Run at:               {result.run_at_utc}")
    print(f"Git sha:              {result.git_sha or '(none)'}")
    print(f"Holdout window:       {result.holdout_days} days")
    print(f"Sessions in window:   {result.n_sessions_total}")
    print(f"  Evaluable:          {result.n_sessions_evaluable}")
    print(f"  Skipped (no click): {result.n_sessions_skipped}")
    print()
    for k in result.k_values:
        ndcg = result.aggregate.ndcg_at_k.get(k, 0.0)
        prec = result.aggregate.precision_at_k.get(k, 0.0)
        hit = result.aggregate.hit_rate_at_k.get(k, 0.0)
        print(f"  NDCG@{k:<3}  {ndcg:>7.4f}    "
              f"Precision@{k:<3}  {prec:>7.4f}    "
              f"Hit-Rate@{k:<3}  {hit:>7.4f}")
    print(f"  MAP        {result.aggregate.mean_average_precision:>7.4f}")
    print()
    print(f"Appended to: {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", choices=["api", "wrangler"], default="api",
        help="How to read D1 events (default: api)",
    )
    parser.add_argument(
        "--api-url", default=DEFAULT_API,
        help=f"analytics-worker URL (default: {DEFAULT_API})",
    )
    parser.add_argument(
        "--scores-file", type=Path, default=DEFAULT_SCORES_PATH,
        help=f"path to scores JSON (default: {DEFAULT_SCORES_PATH})",
    )
    parser.add_argument(
        "--metrics-csv", type=Path, default=DEFAULT_METRICS_CSV,
        help=f"path to metrics history CSV (default: {DEFAULT_METRICS_CSV})",
    )
    parser.add_argument(
        "--holdout-days", type=int, default=None,
        help="override config.evaluation.holdout_days",
    )
    parser.add_argument(
        "--fill-with-global-top", type=int, default=0,
        help="pad each session candidate set with top-N globally-ranked items "
             "(useful when sessions are sparse; 0 = strict per-session candidates)",
    )
    parser.add_argument(
        "--notes", default="",
        help="free-form note appended to the metrics row (eg. 'Ra1 watch-time on')",
    )
    parser.add_argument(
        "--skip-regression-check", action="store_true",
        help="don't raise on NDCG@10 regression (use when k_values changed)",
    )
    parser.add_argument(
        "--git-sha", default=None,
        help="override auto-detected git sha (deterministic test output)",
    )
    parser.add_argument(
        "--now", default=None,
        help="ISO-8601 timestamp to freeze the holdout window (tests / replay)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="compute metrics but do NOT append to the CSV",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()

    holdout_days = args.holdout_days or config.evaluation.holdout_days
    k_values = tuple(config.evaluation.k_values)

    # Log inputs at start (rule D11)
    print(f"evaluate_recsys: source={args.source} holdout_days={holdout_days} "
          f"k_values={k_values} scores={args.scores_file} "
          f"metrics_csv={args.metrics_csv}")

    scores = load_scores(args.scores_file)
    print(f"  loaded {len(scores)} item scores")

    now: datetime | None = None
    if args.now:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        except ValueError as e:
            print(f"  bad --now value: {e}", file=sys.stderr)
            return 2

    try:
        sessions = load_sessions(
            holdout_days=holdout_days,
            source=args.source,
            api_url=args.api_url if args.source == "api" else None,
            now=now,
        )
    except SessionLoadError as e:
        print(f"  D1 unreachable: {e}", file=sys.stderr)
        print("  Refusing to evaluate against zero sessions (rule E14).",
              file=sys.stderr)
        return 3

    print(f"  loaded {len(sessions)} sessions in the holdout window")
    if len(sessions) == 0:
        print("  Zero sessions: nothing to evaluate. Exit 4.")
        return 4

    git_sha = args.git_sha if args.git_sha is not None else current_git_sha()
    result = run_evaluation(
        scores=scores,
        sessions=sessions,
        holdout_days=holdout_days,
        k_values=k_values,
        git_sha=git_sha,
        now=now,
        fill_with_global_top=args.fill_with_global_top,
        notes=args.notes,
    )

    # Regression check vs the previous row (if any).
    previous = read_last_metrics_row(args.metrics_csv)
    if not args.skip_regression_check:
        try:
            check_regression(
                result, previous,
                threshold=config.evaluation.ndcg_drop_alert_threshold,
            )
        except RegressionAlert as e:
            print(f"\nREGRESSION DETECTED:\n  {e}", file=sys.stderr)
            return 5

    if not args.dry_run:
        write_metrics_row(args.metrics_csv, result)
    else:
        print("  --dry-run: metrics not written")
        # Still print the row so a human can inspect it.
        print(f"  row: {format_metrics_row(result)}")

    print_summary(result, args.metrics_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
