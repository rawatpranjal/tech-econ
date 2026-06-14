#!/usr/bin/env python3
"""human_metrics.py -- one-screen human-engagement health check.

Reports the three human-centric metrics from the roadmap (Stream A metrics):

    1. Clicks per session   -- mean of D1 click_count / session_count over
                               rolling 7d  (target ≥ 1.5)
    2. Return rate          -- fraction of users with session_count > 1
                               (target: trending up; reports current value)
    3. Top-10 content       -- current all-time top-10 clicked items
                               (churn tracked manually across runs)

Reads from the analytics worker API (no wrangler, no local DB access).
Requires network access to the deployed worker.

Usage:
    python3 scripts/human_metrics.py
    python3 scripts/human_metrics.py --days 14   # wider window for clicks/session
    python3 scripts/human_metrics.py --json       # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.d1_client import D1Client, D1ClientError  # noqa: E402

# ANSI colours (stripped when stdout is not a terminal)
def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
YELLOW = lambda t: _c("33", t)
RED    = lambda t: _c("31", t)
BOLD   = lambda t: _c("1",  t)
DIM    = lambda t: _c("2",  t)


# ─── targets from roadmap ────────────────────────────────────────────────────

CLICKS_PER_SESSION_TARGET = 1.5   # ≥ this is green


def _status(value: float | None, target: float, higher_is_better: bool = True) -> str:
    """Return GREEN/YELLOW/RED label for a metric."""
    if value is None:
        return YELLOW("?")
    if higher_is_better:
        if value >= target:
            return GREEN(f"{value:.3f}")
        if value >= target * 0.8:
            return YELLOW(f"{value:.3f}")
        return RED(f"{value:.3f}")
    else:
        if value <= target:
            return GREEN(f"{value:.3f}")
        return YELLOW(f"{value:.3f}")


# ─── metric computation ───────────────────────────────────────────────────────

def clicks_per_session(client: D1Client, days: int) -> float | None:
    """Compute sum(clicks) / sum(sessions) over rolling `days` window."""
    try:
        rows = client.timeseries(days=days)
    except D1ClientError:
        return None
    if not rows:
        return None
    total_clicks = sum(int(r.get("clicks", 0) or 0) for r in rows)
    total_sessions = sum(int(r.get("sessions", 0) or 0) for r in rows)
    if total_sessions == 0:
        return None
    return total_clicks / total_sessions


def return_rate(client: D1Client) -> float | None:
    """Fraction of users who have made more than one visit."""
    try:
        data = client.get("/users").payload
    except D1ClientError:
        return None
    rr = data.get("returning_rate")
    if rr is None:
        return None
    return float(rr)


def top_content(client: D1Client, limit: int = 10) -> list[dict]:
    """Top clicked content items."""
    try:
        items = client.clicks(limit=limit)
    except D1ClientError:
        return []
    return items[:limit]


# ─── printing ─────────────────────────────────────────────────────────────────

def print_report(cps: float | None, rr: float | None, top: list[dict], days: int) -> None:
    print()
    print(BOLD("─── Human Metrics ──────────────────────────────────"))
    print()

    # Metric 1: clicks / session
    cps_label = _status(cps, CLICKS_PER_SESSION_TARGET)
    target_str = DIM(f"(target ≥ {CLICKS_PER_SESSION_TARGET})")
    print(f"  Clicks / session  [{days}d window]  {cps_label}  {target_str}")

    # Metric 2: return rate
    rr_pct = f"{rr*100:.1f}%" if rr is not None else "?"
    if rr is None:
        rr_str = YELLOW("?")
    elif rr >= 0.30:
        rr_str = GREEN(rr_pct)
    elif rr >= 0.15:
        rr_str = YELLOW(rr_pct)
    else:
        rr_str = RED(rr_pct)
    print(f"  Return rate                        {rr_str}  {DIM('(target: trending up)')}")

    print()
    print(BOLD("─── Top-10 Content (all-time clicks) ────────────────"))
    if not top:
        print(f"  {YELLOW('No data')}")
    else:
        for i, item in enumerate(top, 1):
            name    = item.get("name", "?")[:50]
            section = item.get("section", "?")
            count   = item.get("count", item.get("click_count", "?"))
            print(f"  {i:2d}. {name:<50}  {DIM(section):<15}  {count} clicks")

    print()
    print(DIM("  Note: top-10 churn requires comparing two runs over time."))
    print(DIM("        Save outputs and diff to track monthly turnover."))
    print()


def build_json_report(cps: float | None, rr: float | None, top: list[dict], days: int) -> dict:
    return {
        "clicks_per_session": {"value": cps, "days": days, "target": CLICKS_PER_SESSION_TARGET},
        "return_rate": {"value": rr},
        "top_10": top,
    }


# ─── entry point ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Human engagement metrics from D1.")
    parser.add_argument("--days", type=int, default=7, help="Rolling window for clicks/session (default: 7)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    client = D1Client()

    cps = clicks_per_session(client, args.days)
    rr  = return_rate(client)
    top = top_content(client, limit=10)

    if args.json:
        print(json.dumps(build_json_report(cps, rr, top, args.days), indent=2))
        return 0

    print_report(cps, rr, top, args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
