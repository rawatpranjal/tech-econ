"""Offline evaluation orchestration: items + sessions -> metrics row.

This is the glue between:
    - lib.d1_sessions     (where the sessions come from)
    - lib.replay          (per-session metric primitives)
    - reports/metrics.csv (where the run lands on disk)

A "ranker" here is just a `dict[name -> score]` because that is what
the live pipeline produces (rank_all_content.py builds a `model_score`
per item). Replacing the ranker with an experimental candidate is
literally a different score dict.

Inputs
    - scores: dict[str, float], lowercase item name -> model_score
    - sessions: list[Session] from lib.d1_sessions
    - config: Config.evaluation (k_values, ndcg_drop_alert_threshold)

Outputs
    - EvalResult dataclass
    - Side-effect: append a row to `reports/metrics.csv` (caller
      decides when to call write_metrics_row)

Side effects
    - write_metrics_row uses `lib.data_io.write_json_atomic`-style
      atomic CSV append (write tmp -> os.replace) so a crash never
      corrupts the existing history.

Reproducibility
    - run_evaluation is pure given the same scores + sessions
    - timestamps in the CSV row come from `now()` so the caller passes
      a fixed datetime in tests

Architecture rules enforced
    A1, A2, B6 (_meta on the CSV header), C8, D12 (atomic write),
    E14 (regression check raises rather than silently overwriting),
    G18 (every public function has a unit test).
"""

from __future__ import annotations

import csv
import io
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.d1_sessions import Session
from lib.replay import AggregateMetrics, aggregate_sessions


__all__ = [
    "EvalResult",
    "RegressionAlert",
    "build_session_pairs",
    "run_evaluation",
    "format_metrics_row",
    "write_metrics_row",
    "read_last_metrics_row",
    "check_regression",
    "format_replay_row",
    "write_replay_row",
]


# ---------------------------------------------------------------------------
# Result dataclass + regression sentinel
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvalResult:
    """One offline-evaluation run, ready to append to metrics.csv."""

    run_at_utc: str            # ISO-8601 second-resolution
    git_sha: str | None
    holdout_days: int
    k_values: tuple[int, ...]
    n_sessions_total: int      # sessions in the holdout
    n_sessions_evaluable: int  # sessions with at least one click *and* a non-empty ranking
    n_sessions_skipped: int    # holdout-window sessions excluded
    aggregate: AggregateMetrics
    notes: str = ""


class RegressionAlert(RuntimeError):
    """NDCG@10 dropped beyond the configured threshold vs the previous
    run. Raise to abort a rerank before bad scores are written to
    data/*.json (rule E14, fail loud)."""


# ---------------------------------------------------------------------------
# Per-session ranking construction
# ---------------------------------------------------------------------------
def build_session_pairs(
    sessions: Iterable[Session],
    scores: dict[str, float],
    *,
    fill_with_global_top: int = 0,
) -> list[tuple[list[str], frozenset[str]]]:
    """For each session produce (ranking, clicked) suitable for
    lib.replay.aggregate_sessions.

    The candidate set per session is `clicks ∪ impressions ∪ <top-N
    of the global ranking>`. Without position-rank logging (Phase 2,
    Ra3 in the audit), we don't know what the user actually saw beyond
    "they clicked or it appeared in the impression beacon", so we use
    the candidates the user interacted with as a lower bound.

    `fill_with_global_top` lets the caller pad the candidate set with
    the top-N items by global score so NDCG@10 has 10 slots even when
    the session only saw a few items. Set to 0 to disable.
    """
    if not isinstance(scores, dict):
        raise TypeError(f"scores must be dict, got {type(scores).__name__}")
    # Pre-compute global top once (sorted, descending)
    global_top: list[str] = []
    if fill_with_global_top > 0:
        global_top = [
            name for name, _ in sorted(
                scores.items(), key=lambda kv: kv[1], reverse=True
            )[:fill_with_global_top]
        ]

    pairs: list[tuple[list[str], frozenset[str]]] = []
    for sess in sessions:
        candidates: set[str] = set(sess.clicked_names)
        candidates.update(sess.viewed_names)
        if global_top:
            candidates.update(global_top)
        # Sort candidates by score (desc); items missing a score get 0.
        ranking = sorted(
            candidates,
            key=lambda name: scores.get(name, 0.0),
            reverse=True,
        )
        pairs.append((ranking, sess.clicked_names))
    return pairs


# ---------------------------------------------------------------------------
# Run + report
# ---------------------------------------------------------------------------
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_evaluation(
    scores: dict[str, float],
    sessions: list[Session],
    *,
    holdout_days: int,
    k_values: tuple[int, ...] = (5, 10),
    git_sha: str | None = None,
    now: datetime | None = None,
    fill_with_global_top: int = 0,
    notes: str = "",
) -> EvalResult:
    """Score the held-out sessions and produce an EvalResult."""
    if not isinstance(k_values, tuple):
        k_values = tuple(k_values)
    if not k_values:
        raise ValueError("k_values must not be empty")

    pairs = build_session_pairs(sessions, scores, fill_with_global_top=fill_with_global_top)
    aggregate = aggregate_sessions(pairs, k_values=k_values)

    # n_sessions_evaluable = sessions with ranking AND clicks AND >= 1
    # clicked-in-ranking. aggregate_sessions already counts skipped
    # for "no clicks". A session whose clicks were filtered out (eg.
    # the user clicked an item we don't have a score for *and* didn't
    # see an impression of) is still counted as evaluable: 0 score,
    # which is the honest signal.
    if now is None:
        run_at = _utc_now_iso()
    else:
        run_at = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return EvalResult(
        run_at_utc=run_at,
        git_sha=git_sha,
        holdout_days=holdout_days,
        k_values=k_values,
        n_sessions_total=len(sessions),
        n_sessions_evaluable=aggregate.n_sessions - aggregate.n_skipped,
        n_sessions_skipped=aggregate.n_skipped,
        aggregate=aggregate,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# CSV format (reports/metrics.csv)
# ---------------------------------------------------------------------------
# A stable column order. New columns are appended at the end so the
# CSV stays readable as a time series and reading old rows still works.
_BASE_COLUMNS: tuple[str, ...] = (
    "run_at_utc",
    "git_sha",
    "holdout_days",
    "n_sessions_total",
    "n_sessions_evaluable",
    "n_sessions_skipped",
    "mean_average_precision",
    "notes",
)


def _per_k_columns(k_values: Iterable[int]) -> list[str]:
    cols: list[str] = []
    for k in k_values:
        cols.append(f"ndcg_at_{k}")
        cols.append(f"precision_at_{k}")
        cols.append(f"recall_at_{k}")
        cols.append(f"hit_rate_at_{k}")
    return cols


def header_columns(k_values: Iterable[int]) -> list[str]:
    """The CSV header. Stable across runs as long as k_values match."""
    return list(_BASE_COLUMNS) + _per_k_columns(k_values)


def format_metrics_row(result: EvalResult) -> dict[str, Any]:
    """Convert an EvalResult to a flat dict suitable for csv.DictWriter."""
    row: dict[str, Any] = {
        "run_at_utc": result.run_at_utc,
        "git_sha": result.git_sha or "",
        "holdout_days": result.holdout_days,
        "n_sessions_total": result.n_sessions_total,
        "n_sessions_evaluable": result.n_sessions_evaluable,
        "n_sessions_skipped": result.n_sessions_skipped,
        "mean_average_precision": _round(result.aggregate.mean_average_precision),
        "notes": result.notes,
    }
    for k in result.k_values:
        row[f"ndcg_at_{k}"] = _round(result.aggregate.ndcg_at_k.get(k, 0.0))
        row[f"precision_at_{k}"] = _round(result.aggregate.precision_at_k.get(k, 0.0))
        row[f"recall_at_{k}"] = _round(result.aggregate.recall_at_k.get(k, 0.0))
        row[f"hit_rate_at_{k}"] = _round(result.aggregate.hit_rate_at_k.get(k, 0.0))
    return row


def _round(x: float) -> float:
    return round(float(x), 6)


def write_metrics_row(
    path: str | Path,
    result: EvalResult,
) -> None:
    """Append a row to `path`, creating the file with a header if it
    does not exist. Atomic: writes to <path>.tmp then os.replace.

    Note: CSV append is sequential by nature, so 'atomic' here means
    'we never leave a half-written file' -- not 'concurrent writers
    are safe'. The eval pipeline runs once per rerank; there's only
    one writer.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    columns = header_columns(result.k_values)
    new_row = format_metrics_row(result)

    # Read existing content (if any), validate header alignment.
    existing_text = ""
    if p.exists():
        existing_text = p.read_text(encoding="utf-8")
        if existing_text:
            existing_header = existing_text.splitlines()[0]
            new_header_str = ",".join(columns)
            if existing_header != new_header_str:
                # Header drift -- happens if k_values changed across
                # runs. Don't silently corrupt the time series; require
                # the operator to migrate the file.
                raise ValueError(
                    f"{p} header mismatch.\n"
                    f"  on disk: {existing_header}\n"
                    f"  this run: {new_header_str}\n"
                    "  Either restore the old k_values or move the old "
                    "metrics.csv aside and start fresh."
                )

    # Build the new file content in memory then atomic-replace.
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    if not existing_text:
        writer.writeheader()
    else:
        # preserve everything that was there
        # writer.writeheader would re-emit; just write the body.
        buf.write(existing_text)
        if not existing_text.endswith("\n"):
            buf.write("\n")
    writer.writerow(new_row)

    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
        os.replace(tmp, p)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_last_metrics_row(path: str | Path) -> dict[str, str] | None:
    """Return the last row of `path` as a dict, or None if the file
    does not exist or has only a header.

    Values are strings (csv.DictReader); callers cast as needed."""
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return None
    return rows[-1]


# ---------------------------------------------------------------------------
# Replay history (reports/replays.csv): side-by-side baseline vs candidate
# ---------------------------------------------------------------------------
_REPLAY_BASE_COLUMNS: tuple[str, ...] = (
    "run_at_utc",
    "git_sha",
    "baseline_path",
    "candidate_path",
    "n_sessions",
    "n_evaluable",
    "regression_metric",
    "regression_threshold",
    "verdict",            # "ok" | "regressed"
    "notes",
)


def _replay_per_k_columns(k_values: Iterable[int]) -> list[str]:
    cols: list[str] = []
    for k in k_values:
        for prefix in ("baseline", "candidate", "delta"):
            cols.append(f"{prefix}_ndcg_at_{k}")
        for prefix in ("baseline", "candidate", "delta"):
            cols.append(f"{prefix}_hit_rate_at_{k}")
    cols.append("baseline_map")
    cols.append("candidate_map")
    cols.append("delta_map")
    return cols


def replay_header_columns(k_values: Iterable[int]) -> list[str]:
    return list(_REPLAY_BASE_COLUMNS) + _replay_per_k_columns(k_values)


def format_replay_row(
    *,
    baseline: EvalResult,
    candidate: EvalResult,
    baseline_path: str,
    candidate_path: str,
    regression_metric: str,
    regression_threshold: float,
    verdict: str,
    notes: str = "",
) -> dict[str, Any]:
    """Flatten a baseline/candidate pair into one CSV row."""
    if baseline.k_values != candidate.k_values:
        raise ValueError(
            f"k_values mismatch: baseline={baseline.k_values} candidate={candidate.k_values}"
        )
    row: dict[str, Any] = {
        "run_at_utc": candidate.run_at_utc,
        "git_sha": candidate.git_sha or "",
        "baseline_path": baseline_path,
        "candidate_path": candidate_path,
        "n_sessions": candidate.n_sessions_total,
        "n_evaluable": candidate.n_sessions_evaluable,
        "regression_metric": regression_metric,
        "regression_threshold": _round(regression_threshold),
        "verdict": verdict,
        "notes": notes,
    }
    for k in baseline.k_values:
        b_n = baseline.aggregate.ndcg_at_k.get(k, 0.0)
        c_n = candidate.aggregate.ndcg_at_k.get(k, 0.0)
        row[f"baseline_ndcg_at_{k}"] = _round(b_n)
        row[f"candidate_ndcg_at_{k}"] = _round(c_n)
        row[f"delta_ndcg_at_{k}"] = _round(c_n - b_n)
        b_h = baseline.aggregate.hit_rate_at_k.get(k, 0.0)
        c_h = candidate.aggregate.hit_rate_at_k.get(k, 0.0)
        row[f"baseline_hit_rate_at_{k}"] = _round(b_h)
        row[f"candidate_hit_rate_at_{k}"] = _round(c_h)
        row[f"delta_hit_rate_at_{k}"] = _round(c_h - b_h)
    b_m = baseline.aggregate.mean_average_precision
    c_m = candidate.aggregate.mean_average_precision
    row["baseline_map"] = _round(b_m)
    row["candidate_map"] = _round(c_m)
    row["delta_map"] = _round(c_m - b_m)
    return row


def write_replay_row(
    path: str | Path,
    *,
    baseline: EvalResult,
    candidate: EvalResult,
    baseline_path: str,
    candidate_path: str,
    regression_metric: str,
    regression_threshold: float,
    verdict: str,
    notes: str = "",
) -> None:
    """Append a row to `path` (default reports/replays.csv). Atomic via
    tmp + os.replace; same header-drift guard as write_metrics_row."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    columns = replay_header_columns(baseline.k_values)
    row = format_replay_row(
        baseline=baseline,
        candidate=candidate,
        baseline_path=baseline_path,
        candidate_path=candidate_path,
        regression_metric=regression_metric,
        regression_threshold=regression_threshold,
        verdict=verdict,
        notes=notes,
    )

    existing_text = p.read_text(encoding="utf-8") if p.exists() else ""
    if existing_text:
        existing_header = existing_text.splitlines()[0]
        new_header_str = ",".join(columns)
        if existing_header != new_header_str:
            raise ValueError(
                f"{p} header mismatch.\n"
                f"  on disk: {existing_header}\n"
                f"  this run: {new_header_str}\n"
                "  Either restore the old k_values or move the old "
                "replays.csv aside and start fresh."
            )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    if not existing_text:
        writer.writeheader()
    else:
        buf.write(existing_text)
        if not existing_text.endswith("\n"):
            buf.write("\n")
    writer.writerow(row)

    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
        os.replace(tmp, p)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def check_regression(
    new: EvalResult,
    previous_row: dict[str, str] | None,
    *,
    threshold: float,
    metric: str = "ndcg_at_10",
) -> None:
    """Raise RegressionAlert if `new` has dropped beyond `threshold`
    on the named metric vs `previous_row`. No-ops when:
      - there is no previous row (first run)
      - the previous row lacks the metric column (k_values changed)
      - the previous row's holdout_days disagree with the new run's
        (different windows -> different session populations -> not a
        fair apples-to-apples comparison; eg. the seed run used a
        60-day window because of the analytics blackout, and the next
        run reverts to the configured default of 14 days)
    """
    if previous_row is None:
        return
    prev_str = previous_row.get(metric)
    if prev_str is None or prev_str == "":
        return
    try:
        prev_value = float(prev_str)
    except ValueError:
        return  # malformed prior row -- can't compare honestly

    # Window-mismatch guard: a 14-day rerun would always look like
    # it regressed against a 60-day baseline simply because the
    # session populations differ. Skip the comparison and let the
    # caller write a fresh row at the new window.
    prev_window = previous_row.get("holdout_days")
    if prev_window is not None and prev_window != "":
        try:
            if int(prev_window) != int(new.holdout_days):
                return
        except ValueError:
            return  # malformed window -- skip rather than crash

    # Resolve new value from EvalResult
    if metric.startswith("ndcg_at_"):
        k = int(metric.removeprefix("ndcg_at_"))
        new_value = new.aggregate.ndcg_at_k.get(k, 0.0)
    elif metric.startswith("precision_at_"):
        k = int(metric.removeprefix("precision_at_"))
        new_value = new.aggregate.precision_at_k.get(k, 0.0)
    elif metric.startswith("hit_rate_at_"):
        k = int(metric.removeprefix("hit_rate_at_"))
        new_value = new.aggregate.hit_rate_at_k.get(k, 0.0)
    elif metric == "mean_average_precision":
        new_value = new.aggregate.mean_average_precision
    else:
        raise ValueError(f"unsupported metric for regression check: {metric!r}")

    if prev_value <= 0:
        return  # nothing to drop from
    drop = (prev_value - new_value) / prev_value
    if drop > threshold:
        raise RegressionAlert(
            f"{metric} regressed from {prev_value:.4f} to {new_value:.4f} "
            f"({drop * 100:.1f}% drop, threshold {threshold * 100:.1f}%). "
            "Aborting rerank to protect production scores. "
            "Investigate before re-running, or pass --skip-regression-check "
            "if the drop is expected (eg. you changed k_values)."
        )
