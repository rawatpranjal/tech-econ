#!/usr/bin/env python3
"""build_site_scoreboard.py -- compile recsys metrics + experiment results into
a single JSON file consumed by the /site transparency page (Tabs 7 and 8).

Inputs:
    reports/metrics.csv           -- one row per rerank-with-eval run
                                     (NDCG@10, Hit-Rate@10, MAP, holdout_days, ...)
    reports/replays.csv           -- one row per replay_eval comparison
                                     (baseline vs candidate scoring approaches)
    data/experiments.json         -- experiment registry (ids, statuses, variants)
    reports/experiments/<id>-YYYY-MM-DD.md
                                  -- per-experiment markdown reports written by
                                     analyze_experiments.py; most-recent per id

Outputs:
    data/site_scoreboard.json     -- compiled snapshot for Hugo site templates

Side effects:
    Writes data/site_scoreboard.json atomically (writes to .tmp file, then renames).
    Safe to re-run at any time; output is deterministic given the same inputs.

Reproducibility:
    Pure read + write. No randomness. No network. No subprocess.
    Re-running produces identical output for the same input files.

Usage:
    python3 scripts/build_site_scoreboard.py
    python3 scripts/build_site_scoreboard.py --repo-root /path/to/repo
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of dicts. Returns [] if missing or empty."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def _try_float(s: str | None, default: float | None = None) -> float | None:
    """Parse a string to float; return default if empty or unparseable."""
    if not s or not s.strip():
        return default
    try:
        return float(s.strip())
    except ValueError:
        return default


def _try_int(s: str | None, default: int | None = None) -> int | None:
    """Parse a string to int; return default if empty or unparseable."""
    if not s or not s.strip():
        return default
    try:
        return int(s.strip())
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Metrics parsing
# --------------------------------------------------------------------------- #


def _parse_metrics_row(row: dict[str, str]) -> dict[str, Any]:
    """Convert one row from metrics.csv into a typed dict."""
    return {
        "date": (row.get("run_at_utc") or "")[:10],
        "run_at_utc": (row.get("run_at_utc") or "").strip(),
        "git_sha": (row.get("git_sha") or "").strip()[:7],
        "holdout_days": _try_int(row.get("holdout_days")),
        "n_sessions_total": _try_int(row.get("n_sessions_total")),
        "n_evaluable_sessions": _try_int(row.get("n_sessions_evaluable")),
        "n_sessions_skipped": _try_int(row.get("n_sessions_skipped")),
        "ndcg_at_5": _try_float(row.get("ndcg_at_5")),
        "ndcg_at_10": _try_float(row.get("ndcg_at_10")),
        "hit_rate_at_5": _try_float(row.get("hit_rate_at_5")),
        "hit_rate_at_10": _try_float(row.get("hit_rate_at_10")),
        "map_at_10": _try_float(row.get("mean_average_precision")),
        "precision_at_10": _try_float(row.get("precision_at_10")),
        "notes": (row.get("notes") or "").strip(),
    }


def build_metrics(metrics_csv: Path) -> dict[str, Any]:
    """Parse metrics.csv and return {latest, history} structure."""
    rows = _load_csv(metrics_csv)
    if not rows:
        return {"latest": None, "history": []}

    parsed = [_parse_metrics_row(r) for r in rows]
    return {
        "latest": parsed[-1],
        "history": parsed,
    }


# --------------------------------------------------------------------------- #
# Replays parsing
# --------------------------------------------------------------------------- #


def _shorten_path(p: str) -> str:
    """Return just the filename stem of a path (no directory, no extension)."""
    if not p:
        return ""
    stem = Path(p).stem
    return stem or p


def _parse_replay_row(row: dict[str, str]) -> dict[str, Any]:
    """Convert one row from replays.csv into a typed dict."""
    return {
        "date": (row.get("run_at_utc") or "")[:10],
        "run_at_utc": (row.get("run_at_utc") or "").strip(),
        "git_sha": (row.get("git_sha") or "").strip()[:7],
        "baseline_label": _shorten_path(row.get("baseline_path") or ""),
        "candidate_label": _shorten_path(row.get("candidate_path") or ""),
        "n_sessions": _try_int(row.get("n_sessions")),
        "n_evaluable": _try_int(row.get("n_evaluable")),
        "verdict": (row.get("verdict") or "").strip(),
        "notes": (row.get("notes") or "").strip(),
        "baseline_ndcg_at_10": _try_float(row.get("baseline_ndcg_at_10")),
        "candidate_ndcg_at_10": _try_float(row.get("candidate_ndcg_at_10")),
        "delta_ndcg_at_10": _try_float(row.get("delta_ndcg_at_10")),
        "baseline_hit_rate_at_10": _try_float(row.get("baseline_hit_rate_at_10")),
        "candidate_hit_rate_at_10": _try_float(row.get("candidate_hit_rate_at_10")),
        "delta_hit_rate_at_10": _try_float(row.get("delta_hit_rate_at_10")),
    }


def build_replays(replays_csv: Path) -> dict[str, Any]:
    """Parse replays.csv and return {latest, history} structure."""
    rows = _load_csv(replays_csv)
    if not rows:
        return {"latest": None, "history": []}

    parsed = [_parse_replay_row(r) for r in rows]
    return {
        "latest": parsed[-1],
        "history": parsed,
    }


# --------------------------------------------------------------------------- #
# Experiment markdown report parsing
# --------------------------------------------------------------------------- #


def _find_latest_experiment_report(
    reports_dir: Path, experiment_id: str
) -> Path | None:
    """Return the most-recent markdown file for the given experiment id.

    Files are named <experiment_id>-YYYY-MM-DD.md; lexicographic sort picks
    the latest date.
    """
    if not reports_dir.exists():
        return None
    candidates = sorted(
        reports_dir.glob(f"{experiment_id}-????-??-??.md"), reverse=True
    )
    return candidates[0] if candidates else None


def _parse_experiment_report(md_path: Path) -> dict[str, Any] | None:
    """Parse per-variant counts + CTR from an experiment markdown report.

    Expected table rows look like:
        | `control_a` | 8,071 | 322 | 0.0399 | [0.0358, 0.0444] |

    Returns a dict keyed by variant_id or None if parsing fails.
    """
    if not md_path or not md_path.exists():
        return None

    text = md_path.read_text(encoding="utf-8")

    # Pattern: | `variant` | impressions | clicks | CTR | [ci_low, ci_high] |
    # Commas in numbers are stripped; backticks are stripped from variant names.
    row_pattern = re.compile(
        r"\|\s*`?([^`|]+?)`?\s*\|"          # variant id
        r"\s*([\d,]+)\s*\|"                  # impressions
        r"\s*([\d,]+)\s*\|"                  # clicks
        r"\s*([\d.]+)\s*\|"                  # CTR
        r"\s*\[([\d.]+),\s*([\d.]+)\]\s*\|"  # CI [low, high]
    )

    results: dict[str, Any] = {}
    for m in row_pattern.finditer(text):
        variant = m.group(1).strip()
        impressions = int(m.group(2).replace(",", ""))
        clicks = int(m.group(3).replace(",", ""))
        ctr = float(m.group(4))
        ci_low = float(m.group(5))
        ci_high = float(m.group(6))
        results[variant] = {
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }

    return results if results else None


# --------------------------------------------------------------------------- #
# Experiments
# --------------------------------------------------------------------------- #


# Human-readable verdicts for known experiments. These are populated from the
# narrative we have on record. New experiments default to "collecting data".
_KNOWN_VERDICTS: dict[str, str] = {
    "harness_aa_v1": (
        "broken -- cookie-timing bug caused 57 users to appear in both variants; "
        "19 days of data were contaminated. Bug fixed; harness_aa_v2 started."
    ),
    "harness_aa_v2": "collecting data",
}

_KNOWN_SUMMARIES: dict[str, str] = {
    "harness_aa_v1": (
        "A/A sanity test to validate the end-to-end experiment harness. "
        "Discovered a bucketing contamination bug: the anonymous user ID cookie "
        "was written too late, so the first-impression bucketing used a different "
        "ID than later events. Fixed before restarting as v2."
    ),
    "harness_aa_v2": (
        "A/A sanity re-run after the cookie-timing fix. Both variants see the "
        "same experience. If CTR is balanced, the harness is validated and real "
        "treatment experiments can begin."
    ),
}


def build_experiments(
    experiments_json: Path, reports_dir: Path
) -> list[dict[str, Any]]:
    """Read experiments.json and enrich each non-draft experiment with report data."""
    if not experiments_json.exists():
        return []

    with experiments_json.open("r", encoding="utf-8") as f:
        data = json.load(f)

    output: list[dict[str, Any]] = []
    for exp in data.get("experiments", []):
        exp_id = exp.get("id", "")
        status = exp.get("status", "draft")

        # Skip placeholder/draft experiments that are not real.
        if status == "draft" or exp_id.startswith("_"):
            continue

        kind = "A/A sanity" if "aa" in exp_id else "treatment"
        summary = _KNOWN_SUMMARIES.get(exp_id, "")
        verdict = _KNOWN_VERDICTS.get(exp_id, "collecting data")

        # Try to load per-variant results from the latest report file.
        report_path = _find_latest_experiment_report(reports_dir, exp_id)
        results = _parse_experiment_report(report_path)

        # For v1, override verdict to reflect contaminated status even if
        # results were parsed successfully.
        if exp_id == "harness_aa_v1" and results:
            verdict = _KNOWN_VERDICTS["harness_aa_v1"]

        output.append(
            {
                "id": exp_id,
                "status": status,
                "started_at": exp.get("started_at") or "",
                "ended_at": exp.get("ended_at") or None,
                "kind": kind,
                "summary": summary,
                "results": results,
                "verdict": verdict,
            }
        )

    return output


# --------------------------------------------------------------------------- #
# Main assembler
# --------------------------------------------------------------------------- #


def build_scoreboard(repo_root: Path) -> dict[str, Any]:
    """Assemble the full scoreboard dict from all source files."""
    metrics = build_metrics(repo_root / "reports" / "metrics.csv")
    replays = build_replays(repo_root / "reports" / "replays.csv")
    experiments = build_experiments(
        repo_root / "data" / "experiments.json",
        repo_root / "reports" / "experiments",
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "replays": replays,
        "experiments": experiments,
    }


def write_scoreboard(scoreboard: dict[str, Any], output_path: Path) -> None:
    """Write the scoreboard JSON atomically via a .tmp rename."""
    tmp = output_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(scoreboard, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--repo-root",
        default=str(_REPO_ROOT),
        help="Path to repository root (default: parent of this script)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: <repo_root>/data/site_scoreboard.json)",
    )
    args = parser.parse_args(argv)

    root = Path(args.repo_root).resolve()
    output = Path(args.output) if args.output else root / "data" / "site_scoreboard.json"

    scoreboard = build_scoreboard(root)
    write_scoreboard(scoreboard, output)

    n_metrics = len(scoreboard["metrics"].get("history", []))
    n_replays = len(scoreboard["replays"].get("history", []))
    n_exp = len(scoreboard["experiments"])
    print(
        f"wrote {output}  "
        f"[{n_metrics} metrics rows, {n_replays} replays, {n_exp} experiments]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
