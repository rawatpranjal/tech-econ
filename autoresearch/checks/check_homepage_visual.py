#!/usr/bin/env python3
"""
check_homepage_visual.py -- Validates CSS and template integrity for homepage visual improvements.

Checks:
  - CSS file exists, balanced braces, no catastrophic size regression
  - All homepage partial templates exist with expected markers
  - Hugo build passes
  - Screenshots captured (non-blocking if hugo server not running)

Usage:
    python3 autoresearch/checks/check_homepage_visual.py --project-root /path --log-prefix /path/iter-001
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

SHOT_SCRAPER = "/Library/Frameworks/Python.framework/Versions/3.11/bin/shot-scraper"

TEMPLATE_CHECKS = {
    "layouts/_default/home.html": ["explore-scroller"],
    "layouts/partials/homepage/row-standard.html": ["explore-card"],
    "layouts/partials/homepage/row-hero.html": ["explore-card-hero"],
    "layouts/partials/homepage/row-narrative.html": ["hero-card"],
    "layouts/partials/homepage/row-compact.html": ["explore-card-compact"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--log-prefix", required=True)
    args = parser.parse_args()

    root = Path(args.project_root)
    log_prefix = args.log_prefix
    failures = []
    warnings = []

    # -- 1. CSS syntax validation --
    css_file = root / "static" / "css" / "custom.css"
    css_lines = 0
    css_size = 0
    if not css_file.exists():
        failures.append("static/css/custom.css not found")
    else:
        css_text = css_file.read_text()
        css_lines = len(css_text.splitlines())
        css_size = len(css_text)

        open_braces = css_text.count("{")
        close_braces = css_text.count("}")
        if open_braces != close_braces:
            failures.append(
                f"CSS brace mismatch: {open_braces} open vs {close_braces} close"
            )
        else:
            print(f"PASS  CSS braces balanced ({open_braces} pairs)")

        if css_size < 1000:
            failures.append(f"CSS file suspiciously small ({css_size} bytes)")
        else:
            print(f"PASS  CSS file size OK ({css_size} bytes, {css_lines} lines)")

    # -- 2. Template integrity --
    for tmpl_path, markers in TEMPLATE_CHECKS.items():
        full_path = root / tmpl_path
        if not full_path.exists():
            failures.append(f"Template missing: {tmpl_path}")
            continue
        content = full_path.read_text()
        for marker in markers:
            if marker not in content:
                failures.append(
                    f"Template {tmpl_path} missing expected marker: '{marker}'"
                )
            else:
                print(f"PASS  {tmpl_path} contains '{marker}'")

    # -- 3. Hugo build --
    try:
        result = subprocess.run(
            ["hugo", "--gc", "--minify"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            failures.append(f"Hugo build failed: {result.stderr[:500]}")
        else:
            print("PASS  Hugo build succeeded")
    except Exception as e:
        failures.append(f"Hugo build error: {e}")

    # -- 4. Screenshots (non-blocking) --
    try:
        urllib.request.urlopen("http://localhost:1313/", timeout=3)
        hugo_running = True
    except (urllib.error.URLError, OSError):
        hugo_running = False
        warnings.append(
            "Hugo server not running at localhost:1313 - skipping screenshots"
        )

    if hugo_running:
        for suffix, extra_args in [
            ("screenshot-after.png", ["--width", "1400", "--height", "900"]),
            ("screenshot-full.png", ["--width", "1400"]),
        ]:
            out_path = f"{log_prefix}-{suffix}"
            try:
                subprocess.run(
                    [SHOT_SCRAPER, "http://localhost:1313/", "-o", out_path]
                    + extra_args,
                    capture_output=True,
                    timeout=30,
                )
                print(f"PASS  Screenshot saved: {out_path}")
            except Exception as e:
                warnings.append(f"Screenshot failed ({suffix}): {e}")

    # -- 5. Baseline regression check --
    baseline_path = root / "autoresearch" / ".visual_baseline.json"
    if css_file.exists():
        current_metrics = {"css_lines": css_lines, "css_size": css_size}

        if baseline_path.exists():
            try:
                baseline = json.loads(baseline_path.read_text())
                if current_metrics["css_lines"] < baseline.get("css_lines", 0) - 500:
                    failures.append(
                        f"CSS regression: {current_metrics['css_lines']} lines "
                        f"(baseline: {baseline['css_lines']})"
                    )
            except Exception:
                pass

        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(current_metrics, indent=2))

    # -- Summary --
    print()
    for w in warnings:
        print(f"WARN  {w}")
    for f in failures:
        print(f"FAIL  {f}")

    if failures:
        print(
            f"\nRESULT: FAIL ({len(failures)} error(s), {len(warnings)} warning(s))"
        )
        return 1

    print(f"RESULT: PASS ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
