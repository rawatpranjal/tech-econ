#!/usr/bin/env python3
"""Offline evaluation pipeline for the ranking model (Phase 1 capstone).

Composes lib.metrics + lib.holdout + lib.replay against historical
search-click sessions from D1, scores them via the *current* per-item
model_score in data/*.json, and writes a row to
reports/metrics-YYYY-MM-DD.csv.

The point: every weekly /rerank emits a metrics row, so we can tell
whether the model is improving or regressing. The audit gates further
ranker tuning (Ra4, Ra5, MTL, etc.) behind this measurement loop.

Inputs
    --source {d1,api,fixture}   how to read sessions
                                 d1      = wrangler subprocess (legacy
                                           pattern from rank_all_content.py)
                                 api     = HTTP to analytics worker
                                           (wrapper around lib.d1_client
                                           if available; falls back to
                                           urllib otherwise)
                                 fixture = read from a JSON file
                                           (--fixture-path)
    --holdout-days N             temporal split window (default: from
                                 lib.recsys_config)
    --k k1,k2,...                k values for NDCG/Precision/Hit-Rate
                                 (default: from config)
    --output PATH                output CSV (default reports/metrics-DATE.csv)
    --dry-run                    print the row but don't write
    --baseline                   compare against the previous row in the
                                 CSV; exit 1 if NDCG@10 dropped > threshold
    --fixture-path PATH          for --source fixture

Outputs
    - reports/metrics-YYYY-MM-DD.csv (append-only) with columns:
        date, n_sessions, n_skipped, ndcg@5, ndcg@10, p@5, p@10,
        hit_rate@5, hit_rate@10, map, model_score_mean,
        model_score_p99, exit_code, scoring_method
    - exit code 0 on success, 1 on regression alert, 2 on usage error

Side effects
    - Writes to reports/ directory
    - Reads from data/*.json (no writes)
    - Optionally calls D1 (network)

Reproducibility
    - --now N flag pins the temporal split's reference time (defaults to
      datetime.now(UTC))
    - All thresholds + k-values come from lib.recsys_config; bumping
      them is a config change, not a code change

Architecture rules enforced
    A1: full Inputs/Outputs/Side effects/Reproducibility docstring
    A3: thresholds + k-values from config, not hardcoded
    C7: tolerates missing reports/ dir (creates it)
    E14: D1 fetch failures fail loud rather than silently producing
         empty metrics
    G18: every helper has a unit test in tests/python/scripts/
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.holdout import temporal_split
from lib.recsys_config import load as load_config
from lib.replay import aggregate_sessions


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_item_scores(data_dir: Path) -> dict[str, float]:
    """Load model_score for every item in data/*.json into a flat dict
    keyed by lowercased + stripped name (matching rank_all_content's
    deduplication convention)."""
    scores: dict[str, float] = {}
    content_files = [
        "papers_flat.json",
        "packages.json",
        "datasets.json",
        "talks.json",
        "resources.json",
        "books.json",
        "career.json",
        "community.json",
    ]
    for filename in content_files:
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("items", [])
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("title")
            if not isinstance(name, str):
                continue
            score = item.get("model_score")
            if isinstance(score, (int, float)):
                scores[name.lower().strip()] = float(score)
    return scores


def fetch_sessions_from_d1(timeout_sec: float = 60.0) -> list[dict[str, Any]]:
    """Pull search_sessions rows via wrangler subprocess.

    Schema reminder (from analytics-worker):
        search_sessions(
            session_id,
            queries,        -- JSON array of query strings
            clicks,         -- JSON array of {id, position, ts, ...}
            started_at,
            updated_at
        )

    Returns a list of dicts with the parsed `clicks` array per session.
    """
    cmd = [
        "npx", "wrangler", "d1", "execute", "tech-econ-analytics-db",
        "--remote",
        "--command",
        "SELECT session_id, queries, clicks, started_at, updated_at "
        "FROM search_sessions "
        "ORDER BY updated_at DESC LIMIT 5000",
        "--json",
    ]
    cwd = REPO_ROOT / "analytics-worker"
    if not cwd.exists():
        raise FileNotFoundError(
            f"analytics-worker dir not found at {cwd}. "
            "Run from a repo with the worker checked out, or use "
            "--source fixture for a canned dataset."
        )
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout_sec
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"wrangler d1 query failed (exit {result.returncode}): "
            f"{result.stderr[:300]}"
        )
    try:
        wrapped = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"wrangler returned invalid JSON: {e}") from e
    if not wrapped or not isinstance(wrapped, list):
        return []
    rows = wrapped[0].get("results") if isinstance(wrapped[0], dict) else None
    return rows or []


def load_fixture_sessions(fixture_path: Path) -> list[dict[str, Any]]:
    """Load sessions from a JSON file. Supports either a bare list or
    {sessions: [...]} envelope."""
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        sessions = raw.get("sessions") or raw.get("items") or raw.get("results")
        if isinstance(sessions, list):
            return sessions
    raise ValueError(
        f"Fixture at {fixture_path} must be a list or "
        "{sessions: [...]}; got " + type(raw).__name__
    )


# ---------------------------------------------------------------------------
# Session shaping
# ---------------------------------------------------------------------------
def session_to_ranking_clicks(
    session: dict[str, Any],
    item_scores: dict[str, float],
    *,
    top_k: int = 50,
) -> tuple[list[str], set[str]] | None:
    """Convert a D1 search_session row into a (ranking, clicked) pair.

    The ranking is the top-K items by current model_score (the "what
    the live ranker WOULD show" — replay convention). The clicked set
    is the items the user actually clicked in this session.

    Returns None if the session has no clicks (caller filters with
    aggregate_sessions's n_skipped counter).
    """
    raw_clicks = session.get("clicks")
    if isinstance(raw_clicks, str):
        try:
            raw_clicks = json.loads(raw_clicks)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw_clicks, list) or not raw_clicks:
        return None

    clicked: set[str] = set()
    for c in raw_clicks:
        if isinstance(c, dict):
            cid = c.get("id") or c.get("name")
        elif isinstance(c, str):
            cid = c
        else:
            cid = None
        if isinstance(cid, str) and cid.strip():
            clicked.add(cid.lower().strip())

    if not clicked:
        return None

    # Build the ranking: top-K items by model_score
    ranked = sorted(item_scores.items(), key=lambda kv: -kv[1])
    ranking = [name for name, _ in ranked[:top_k]]
    return (ranking, clicked)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def write_metrics_row(
    csv_path: Path,
    row: dict[str, Any],
) -> None:
    """Append a metrics row, creating the CSV with headers if absent."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    fieldnames = list(row.keys())
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def read_last_row(csv_path: Path) -> dict[str, str] | None:
    """Read the previous row from the metrics CSV (if any)."""
    if not csv_path.exists():
        return None
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows[-1] if rows else None


def detect_regression(
    previous: dict[str, str] | None,
    current: dict[str, Any],
    threshold: float,
) -> tuple[bool, str]:
    """Compare current NDCG@10 against the previous row.

    Returns (is_regression, message).
    """
    if not previous or "ndcg@10" not in previous:
        return False, "no prior baseline; skipping regression check"
    try:
        prior = float(previous["ndcg@10"])
    except (TypeError, ValueError):
        return False, "prior NDCG@10 unparseable; skipping check"
    cur = float(current.get("ndcg@10", 0.0))
    drop = prior - cur
    if drop <= 0:
        return False, f"NDCG@10 {prior:.4f} -> {cur:.4f} (no drop)"
    if drop / max(prior, 1e-9) > threshold:
        pct = drop / prior * 100
        return True, (
            f"REGRESSION: NDCG@10 dropped {pct:.2f}% "
            f"({prior:.4f} -> {cur:.4f}); threshold {threshold * 100:.1f}%"
        )
    return False, f"NDCG@10 dropped {drop:.4f} (within tolerance)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_k_values(arg: str | None, default: tuple[int, ...]) -> tuple[int, ...]:
    if not arg:
        return default
    return tuple(int(x.strip()) for x in arg.split(",") if x.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline recsys evaluation")
    parser.add_argument(
        "--source",
        choices=("d1", "fixture"),
        default="fixture",
        help="Where to read sessions (default: fixture for safety)",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=None,
        help="Path to JSON fixture (required for --source fixture)",
    )
    parser.add_argument("--holdout-days", type=int, default=None)
    parser.add_argument("--k", type=str, default=None,
                        help="Comma-separated k values for NDCG/P/HR")
    parser.add_argument("--top-k-per-session", type=int, default=50,
                        help="How many items to take from the ranker per session")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--baseline", action="store_true",
                        help="Fail loud if NDCG@10 regresses beyond threshold")
    parser.add_argument("--now", type=str, default=None,
                        help="ISO timestamp for reproducibility (default: now)")
    args = parser.parse_args(argv)

    config = load_config()
    holdout_days = args.holdout_days or config.evaluation.holdout_days
    k_values = parse_k_values(args.k, config.evaluation.k_values)
    threshold = config.evaluation.ndcg_drop_alert_threshold

    if args.now:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        except ValueError as e:
            print(f"--now must be ISO 8601: {e}", file=sys.stderr)
            return 2
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    # 1. Load sessions
    if args.source == "fixture":
        if not args.fixture_path:
            print("--fixture-path required when --source fixture", file=sys.stderr)
            return 2
        sessions_raw = load_fixture_sessions(args.fixture_path)
    elif args.source == "d1":
        try:
            sessions_raw = fetch_sessions_from_d1()
        except (FileNotFoundError, RuntimeError) as e:
            print(f"D1 fetch failed: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Unknown source: {args.source}", file=sys.stderr)
        return 2

    # 2. Load current scores
    data_dir = REPO_ROOT / "data"
    item_scores = load_item_scores(data_dir)
    print(f"Loaded {len(item_scores)} items with model_score")
    if not item_scores:
        print("No items with model_score; aborting", file=sys.stderr)
        return 1

    # 3. Temporal split
    if not sessions_raw:
        print("No sessions to evaluate")
        return 1

    # Use updated_at as the timestamp field for splitting
    try:
        train, test, stats = temporal_split(
            sessions_raw,
            holdout_days=holdout_days,
            timestamp_key="updated_at",
            now=now,
        )
    except (KeyError, AttributeError, ValueError) as e:
        print(f"Temporal split failed: {e}", file=sys.stderr)
        return 1
    print(
        f"Temporal split: {stats.n_train} train / {stats.n_test} test "
        f"(cutoff {stats.cutoff.isoformat()})"
    )

    # 4. Build (ranking, clicked) pairs from test sessions
    pairs: list[tuple[list[str], set[str]]] = []
    for session in test:
        result = session_to_ranking_clicks(
            session, item_scores, top_k=args.top_k_per_session
        )
        if result is not None:
            pairs.append(result)

    # 5. Aggregate
    agg = aggregate_sessions(pairs, k_values=k_values)
    print(
        f"Aggregated: n_sessions={agg.n_sessions} n_skipped={agg.n_skipped} "
        f"map={agg.mean_average_precision:.4f}"
    )

    # 6. Build the metrics row
    row = {
        "date": now.date().isoformat(),
        "n_sessions": agg.n_sessions,
        "n_skipped": agg.n_skipped,
        "map": round(agg.mean_average_precision, 6),
    }
    for k in k_values:
        row[f"ndcg@{k}"] = round(agg.ndcg_at_k.get(k, 0.0), 6)
        row[f"p@{k}"] = round(agg.precision_at_k.get(k, 0.0), 6)
        row[f"hit_rate@{k}"] = round(agg.hit_rate_at_k.get(k, 0.0), 6)
    score_values = list(item_scores.values())
    score_values_sorted = sorted(score_values)
    row["model_score_mean"] = round(
        sum(score_values) / len(score_values), 6
    ) if score_values else 0.0
    row["model_score_p99"] = round(
        score_values_sorted[int(len(score_values_sorted) * 0.99)], 6
    ) if score_values_sorted else 0.0
    row["holdout_days"] = holdout_days
    row["scoring_method"] = "current_model_score"

    # 7. Regression check (optional)
    output_csv = args.output or (
        REPO_ROOT / "reports" / f"metrics-{now.date().isoformat()}.csv"
    )
    regressed = False
    if args.baseline:
        previous = read_last_row(output_csv)
        regressed, msg = detect_regression(previous, row, threshold)
        print(msg)

    # 8. Write
    if args.dry_run:
        print("Dry run — would write:")
        for k, v in row.items():
            print(f"  {k}={v}")
    else:
        write_metrics_row(output_csv, row)
        print(f"Wrote {output_csv}")

    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
