#!/usr/bin/env python3
"""analyze_experiments.py -- per-variant CTR / engagement report for active A/B experiments.

Inputs
    - data/experiments.json: experiment registry (loaded by static/js/experiments.js;
      same file is the source of truth for what's active)
    - D1 `events` table via wrangler subprocess: events.experiments column
      stores {experiment_id: variant_id, ...} as JSON (added by PR #46);
      json_extract per variant gives us per-arm impression / click counts.

Outputs
    - stdout: terse one-line-per-variant table + verdicts
    - reports/experiments/<experiment_id>-YYYY-MM-DD.md: full markdown report
      with CIs, sample sizes, and the SQL the result came from. Future-us
      reading the report can rerun the query verbatim.

Side effects
    - Writes one .md file per non-draft experiment in reports/experiments/
    - Spawns wrangler subprocesses (read-only D1 queries)

Reproducibility
    - Pure given the same data/experiments.json + same D1 snapshot
    - All counts come from one SELECT per experiment + GROUP BY variant
    - Stats: standard two-proportion z-test for click-through vs control

What this is NOT (yet)
    - A real sequential test (mSPRT / Bayesian sequential). Today it
      computes per-snapshot z-stats; if you peek a lot the false-positive
      rate inflates. Move to sequential once we have actual experiments
      running for >1 day.
    - A multi-metric guardrail framework. Today it only reports CTR.
      Engagement / dwell / quick-bounce guardrails are a follow-up.

Usage
    python3 scripts/analyze_experiments.py
    python3 scripts/analyze_experiments.py --experiment homepage_row_mmr
    python3 scripts/analyze_experiments.py --since 2026-05-01 --until 2026-05-31
    python3 scripts/analyze_experiments.py --no-write   # stdout only
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKER_DIR = _REPO_ROOT / "analytics-worker"
_EXPERIMENTS_PATH = _REPO_ROOT / "data" / "experiments.json"
_REPORTS_DIR = _REPO_ROOT / "reports" / "experiments"


# --------------------------------------------------------------------------- #
# Stats: two-proportion z-test + Wilson 95% CI on a single proportion.
# Pure functions, no scipy dependency (keeps requirements-dev light).
# --------------------------------------------------------------------------- #


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion. More robust than
    normal-approximation when successes/trials is near 0 or 1."""
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    n = trials
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return ((centre - spread) / denom, (centre + spread) / denom)


def two_prop_z(s1: int, n1: int, s2: int, n2: int) -> tuple[float, float]:
    """Two-proportion z-stat + two-sided p-value. Returns (z, p).

    Pooled-variance form (standard): null is p1 == p2.
    p-value uses the standard-normal CDF approximation via erf;
    sufficient for rough significance reporting at our sample sizes.
    """
    if n1 <= 0 or n2 <= 0:
        return (0.0, 1.0)
    p1 = s1 / n1
    p2 = s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    var = p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)
    if var <= 0:
        return (0.0, 1.0)
    z = (p1 - p2) / math.sqrt(var)
    p_val = 2 * (1 - _phi(abs(z)))
    return (z, p_val)


def _phi(x: float) -> float:
    """Standard-normal CDF approximation via math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# D1 query: one SELECT per experiment, GROUP BY variant.
# Uses wrangler subprocess like scripts/rank_all_content.py:fetch_d1_data.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class VariantRow:
    """One row of per-variant aggregation. Frozen so callers can't
    accidentally mutate the result of a query."""
    variant: str
    impressions: int
    clicks: int

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0


def _wrangler_query(sql: str) -> list[dict[str, Any]]:
    """Run a SELECT against D1 via wrangler. Returns the parsed `results`
    list. Raises CalledProcessError on wrangler failure, raises ValueError
    on JSON parse failure.

    Wrangler 4.x prints a non-JSON preamble ("Cloudflare agent skills are
    available for ...") to stdout before the JSON array even when --json is
    passed. We extract the JSON array with a regex rather than trying to
    suppress the preamble (no reliable env var exists for it)."""
    proc = subprocess.run(
        [
            "npx", "wrangler", "d1", "execute",
            "tech-econ-analytics-db", "--remote", "--json",
            "--command", sql,
        ],
        cwd=_WORKER_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    # Strip the preamble: find the first '[' and take from there.
    # re.DOTALL so '.' matches newlines inside the JSON array.
    match = re.search(r'\[.*\]', proc.stdout, re.DOTALL)
    if not match:
        raise ValueError(
            f"wrangler stdout contained no JSON array.\n"
            f"stdout={proc.stdout[:400]!r}\nstderr={proc.stderr[:200]!r}"
        )
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"wrangler JSON parse failed: {exc}\n"
            f"raw stdout={proc.stdout[:400]!r}"
        ) from exc
    # wrangler --json format: list of one query result; results live under .results
    if not payload or not isinstance(payload, list):
        return []
    return payload[0].get("results") or []


def fetch_variant_counts(
    experiment_id: str, *, since: int | None = None, until: int | None = None
) -> list[VariantRow]:
    """Per-variant impression + click counts for one experiment.

    impression == event.t in ('impression', 'pageview')  -- we count both
    so the funnel-top is everything the user saw, not just card surfaces.
    click       == event.t == 'click'

    Filters:
      - experiments column contains the experiment_id
      - timestamp BETWEEN since/until (millis), if provided
    """
    where_time = ""
    if since:
        where_time += f" AND timestamp >= {since}"
    if until:
        where_time += f" AND timestamp <= {until}"

    # Single SELECT, two aggregations via FILTER. SQLite supports FILTER
    # clauses in D1 (SQLite >= 3.30, well within Cloudflare's version).
    # Json-extract the variant once; group by it.
    sql = (
        "SELECT json_extract(experiments, '$." + experiment_id + "') AS variant, "
        "SUM(CASE WHEN type IN ('impression','pageview') THEN 1 ELSE 0 END) AS impressions, "
        "SUM(CASE WHEN type='click' THEN 1 ELSE 0 END) AS clicks "
        "FROM events "
        "WHERE json_extract(experiments, '$." + experiment_id + "') IS NOT NULL"
        + where_time
        + " GROUP BY variant"
    )
    rows = _wrangler_query(sql)
    out: list[VariantRow] = []
    for r in rows:
        variant = r.get("variant")
        if not isinstance(variant, str):
            continue
        out.append(
            VariantRow(
                variant=variant,
                impressions=int(r.get("impressions") or 0),
                clicks=int(r.get("clicks") or 0),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def load_experiments(path: Path = _EXPERIMENTS_PATH) -> list[dict[str, Any]]:
    """Read data/experiments.json and return active+paused experiments.
    Drafts are skipped (per the schema convention)."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    items = cfg.get("experiments") or []
    return [
        e for e in items
        if isinstance(e, dict)
        and e.get("status") in ("active", "paused")
        and isinstance(e.get("id"), str)
    ]


def render_report(
    experiment: dict[str, Any], rows: list[VariantRow]
) -> str:
    """Markdown report for one experiment."""
    eid = experiment["id"]
    status = experiment.get("status", "unknown")
    primary = experiment.get("primary_metric", "ctr")
    started = experiment.get("started_at", "?")
    by_variant = {r.variant: r for r in rows}

    lines: list[str] = []
    lines.append(f"# Experiment report: `{eid}`")
    lines.append("")
    lines.append(f"- **status:** `{status}`")
    lines.append(f"- **primary metric:** `{primary}`")
    lines.append(f"- **started:** `{started}`")
    lines.append(f"- **generated:** `{datetime.now(timezone.utc).isoformat()}`")
    lines.append("")

    if not rows:
        lines.append(
            "**No data yet.** Either no traffic has arrived since the deploy, "
            "or no client has been bucketed into this experiment. Verify "
            "`data/experiments.json` has the experiment marked `active` and "
            "the worker has the `events.experiments` column populated."
        )
        return "\n".join(lines) + "\n"

    # Per-variant table
    lines.append("## Per-variant counts + CTR")
    lines.append("")
    lines.append("| variant | impressions | clicks | CTR | 95% CI |")
    lines.append("|---|---:|---:|---:|---|")
    for r in sorted(rows, key=lambda x: x.variant):
        lo, hi = wilson_ci(r.clicks, r.impressions)
        lines.append(
            f"| `{r.variant}` | {r.impressions:,} | {r.clicks:,} "
            f"| {r.ctr:.4f} | [{lo:.4f}, {hi:.4f}] |"
        )
    lines.append("")

    # Pairwise tests against control
    control = by_variant.get("control")
    if control is None:
        lines.append("_(No `control` variant present — skipping pairwise tests.)_")
    else:
        lines.append("## vs `control` (two-proportion z-test on CTR)")
        lines.append("")
        lines.append("| variant | Δ CTR | z | p (two-sided) | verdict |")
        lines.append("|---|---:|---:|---:|---|")
        for r in sorted(rows, key=lambda x: x.variant):
            if r.variant == "control":
                continue
            z, p = two_prop_z(r.clicks, r.impressions, control.clicks, control.impressions)
            d_ctr = r.ctr - control.ctr
            verdict = _verdict(p, d_ctr, r.impressions, control.impressions)
            lines.append(
                f"| `{r.variant}` | {d_ctr:+.4f} | {z:+.2f} | {p:.4f} | {verdict} |"
            )
        lines.append("")

    # Reproducibility footer
    lines.append("## Provenance")
    lines.append("")
    lines.append(
        "Counts derived from one D1 query per experiment over the `events` "
        "table; `events.experiments` stores `{experiment_id: variant_id}` as "
        "JSON (PR #46). Re-derive with:"
    )
    lines.append("```sql")
    lines.append(
        f"SELECT json_extract(experiments, '$.{eid}') AS variant,\n"
        f"       SUM(CASE WHEN type IN ('impression','pageview') THEN 1 ELSE 0 END) AS impressions,\n"
        f"       SUM(CASE WHEN type='click' THEN 1 ELSE 0 END) AS clicks\n"
        f"  FROM events\n"
        f" WHERE json_extract(experiments, '$.{eid}') IS NOT NULL\n"
        f" GROUP BY variant"
    )
    lines.append("```")
    return "\n".join(lines) + "\n"


def _verdict(p_value: float, delta: float, n1: int, n2: int) -> str:
    """Heuristic verdict string for the table. Conservative thresholds:
    p < 0.01 → significant; min sample of 100 per arm before declaring
    anything (pre-registered minimum from the audit's A6 funnel)."""
    min_n = min(n1, n2)
    if min_n < 100:
        return f"insufficient data (min n={min_n})"
    if p_value < 0.01:
        return "treatment-wins" if delta > 0 else "control-wins"
    if p_value < 0.05:
        return "weak signal"
    return "no effect"


def _stdout_summary(experiment: dict[str, Any], rows: list[VariantRow]) -> None:
    eid = experiment["id"]
    if not rows:
        print(f"  {eid}: no data")
        return
    parts = [f"  {eid}:"]
    for r in sorted(rows, key=lambda x: x.variant):
        parts.append(f"{r.variant}={r.ctr:.3f} (n={r.impressions:,})")
    print(" ".join(parts))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--experiment", help="only analyze this experiment id (default: all active+paused)"
    )
    parser.add_argument(
        "--since", help="ISO date / Unix-ms; lower bound on event timestamp"
    )
    parser.add_argument(
        "--until", help="ISO date / Unix-ms; upper bound on event timestamp"
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="don't write reports to disk; stdout only",
    )
    args = parser.parse_args(argv)

    since_ms = _coerce_ms(args.since) if args.since else None
    until_ms = _coerce_ms(args.until) if args.until else None

    experiments = load_experiments()
    if args.experiment:
        experiments = [e for e in experiments if e["id"] == args.experiment]

    if not experiments:
        print(
            "No active or paused experiments found. Edit data/experiments.json "
            "to mark one as 'active' first."
        )
        return 0

    if not args.no_write:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Analyzing {len(experiments)} experiment(s):")
    for exp in experiments:
        rows = fetch_variant_counts(
            exp["id"], since=since_ms, until=until_ms
        )
        _stdout_summary(exp, rows)
        if not args.no_write:
            report_path = _REPORTS_DIR / f"{exp['id']}-{today}.md"
            report_path.write_text(render_report(exp, rows), encoding="utf-8")
            print(f"  -> {report_path.relative_to(_REPO_ROOT)}")
    return 0


def _coerce_ms(s: str) -> int:
    """Accept either an ISO date / datetime, or a raw Unix-ms integer.
    Returns Unix-ms. Raises ValueError on garbage."""
    s = s.strip()
    if s.isdigit() and len(s) >= 10:
        # Unix seconds (10 digits) or millis (13)
        return int(s) if len(s) >= 13 else int(s) * 1000
    # Parse as ISO
    if "T" in s:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    else:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


if __name__ == "__main__":
    sys.exit(main())
