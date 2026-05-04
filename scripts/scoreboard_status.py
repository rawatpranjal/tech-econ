#!/usr/bin/env python3
"""scoreboard_status.py -- print a one-screen view of the recsys scoreboard.

Reads:
    reports/metrics.csv  -- one row per rerank-with-eval (NDCG@10, Hit-Rate@10, ...)
    reports/replays.csv  -- one row per replay_eval.py invocation (baseline vs candidate)

Prints (terse, dev-friendly):
    - row count
    - latest row's primary metrics (NDCG@10, Hit-Rate@10)
    - delta vs prior row when comparable (same holdout_days)
    - holdout_days variance warning if rows mix windows
    - replay history tail
    - decision-readiness guard: tells you whether you have enough rows to
      make a default-flip decision (rule from RULES.md: don't flip a
      ranker default until 2-3 baseline rows exist at the same
      holdout_days)

Side effects: stdout only. Read-only, never writes.

Usage:
    python3 scripts/scoreboard_status.py
    python3 scripts/scoreboard_status.py --metrics reports/metrics.csv --replays reports/replays.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


METRIC_COLS = (
    "ndcg_at_10",
    "hit_rate_at_10",
    "ndcg_at_5",
    "hit_rate_at_5",
    "mean_average_precision",
)


def load_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV into a list of dicts. Returns [] if missing/empty."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fmt_metric(row: dict[str, str], col: str) -> str:
    """Format a metric value to 4 decimal places, or '?' if missing."""
    val = row.get(col, "").strip()
    if not val:
        return "?"
    try:
        return f"{float(val):.4f}"
    except ValueError:
        return val


def fmt_delta(curr: dict[str, str], prev: dict[str, str], col: str) -> str:
    """Format the delta between curr[col] and prev[col]. Returns '' on ?'s."""
    try:
        c = float(curr.get(col, ""))
        p = float(prev.get(col, ""))
    except (ValueError, TypeError):
        return ""
    delta = c - p
    sign = "+" if delta >= 0 else ""
    pct = (delta / p * 100) if p else 0.0
    return f" ({sign}{delta:.4f}, {sign}{pct:.1f}%)"


def find_comparable_prior(
    rows: list[dict[str, str]], idx: int
) -> dict[str, str] | None:
    """Walk backwards from idx-1 looking for a row with the same holdout_days
    as rows[idx]. Returns the first match, or None."""
    if idx <= 0:
        return None
    target = rows[idx].get("holdout_days", "")
    for i in range(idx - 1, -1, -1):
        if rows[i].get("holdout_days", "") == target:
            return rows[i]
    return None


def print_scoreboard(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("scoreboard: empty (reports/metrics.csv missing or header-only)")
        return

    print(f"scoreboard: {len(rows)} row(s)")
    latest = rows[-1]
    holdout = latest.get("holdout_days", "?")
    n_eval = latest.get("n_sessions_evaluable", "?")
    notes = (latest.get("notes") or "").strip()
    print(
        f"  latest: {latest.get('run_at_utc', '?')} "
        f"(sha {latest.get('git_sha', '?')[:7]}, holdout={holdout}d, "
        f"n_evaluable={n_eval}){' -- ' + notes if notes else ''}"
    )

    prior = find_comparable_prior(rows, len(rows) - 1)
    for col in METRIC_COLS:
        delta = fmt_delta(latest, prior, col) if prior else ""
        print(f"  {col:>24} = {fmt_metric(latest, col)}{delta}")

    holdouts = Counter(r.get("holdout_days", "?") for r in rows)
    if len(holdouts) > 1:
        breakdown = ", ".join(f"{k}d×{v}" for k, v in sorted(holdouts.items()))
        print(
            f"  WARNING: rows mix {len(holdouts)} holdout windows ({breakdown}). "
            "Cross-window deltas are apples-to-oranges and the eval gate skips them."
        )


def print_replays(rows: list[dict[str, str]], tail: int = 5) -> None:
    if not rows:
        print("\nreplays: empty (reports/replays.csv missing or header-only)")
        return
    print(f"\nreplays: {len(rows)} entries; last {min(tail, len(rows))}:")
    for r in rows[-tail:]:
        verdict = r.get("verdict", "?")
        baseline = (r.get("baseline_path") or "").split("/")[-1] or "?"
        candidate = (r.get("candidate_path") or "").split("/")[-1] or "?"
        ndcg_d = r.get("ndcg_at_10_delta", "?")
        print(
            f"  {r.get('run_at_utc', '?')[:19]}  "
            f"{baseline:>30} -> {candidate:<30}  "
            f"verdict={verdict}  ndcg10_delta={ndcg_d}"
        )


def print_decision_guard(rows: list[dict[str, str]]) -> None:
    """Tell the operator whether the scoreboard is dense enough to make a
    default-flip decision. Per RULES.md: 2-3 baseline rows at the same
    holdout_days before flipping a ranker default."""
    holdouts = Counter(r.get("holdout_days", "?") for r in rows)
    if not holdouts:
        return
    most_common, count = holdouts.most_common(1)[0]
    print()
    if count >= 3:
        print(
            f"decision guard: GREEN -- {count} rows at holdout={most_common}d. "
            "Default-flip decisions are statistically supportable."
        )
    elif count == 2:
        print(
            f"decision guard: YELLOW -- only 2 rows at holdout={most_common}d. "
            "One more rerun before flipping defaults."
        )
    else:
        print(
            f"decision guard: RED -- only {count} row(s) at holdout={most_common}d. "
            "Need at least 2-3 before any default flip (e.g., Ra2 knn-bge)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n", 1)[0],
    )
    parser.add_argument(
        "--metrics", default="reports/metrics.csv", help="path to metrics.csv"
    )
    parser.add_argument(
        "--replays", default="reports/replays.csv", help="path to replays.csv"
    )
    parser.add_argument(
        "--replay-tail", type=int, default=5, help="how many recent replays to show"
    )
    args = parser.parse_args(argv)

    rows = load_csv(Path(args.metrics))
    replays = load_csv(Path(args.replays))
    print_scoreboard(rows)
    print_replays(replays, tail=args.replay_tail)
    print_decision_guard(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
