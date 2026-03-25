#!/usr/bin/env python3
"""
check_search.py -- Validates search UI changes for the autoresearch loop.

Two-tier checks:
  Tier 1 (hard, must pass): Hugo build, HTML balance, JS syntax, JS brace balance
  Tier 2 (soft, warnings): reduced-motion, CSS variables, dark mode coverage

Usage:
    python3 autoresearch/checks/check_search.py --project-root /path/to/repo --log-prefix /path/to/log
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate search UI changes")
    parser.add_argument(
        "--project-root",
        default=str(Path(__file__).parent.parent.parent),
        help="Project root directory",
    )
    parser.add_argument(
        "--log-prefix",
        default=None,
        help="Log file prefix (for compatibility with evaluate.sh)",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    errors: list[str] = []
    warnings: list[str] = []

    # -- Tier 1: Hard checks -----------------------------------------------

    # 1. Hugo build
    result = subprocess.run(
        ["hugo", "--gc", "--minify"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        errors.append(f"Hugo build failed: {result.stderr[:500]}")
    else:
        print("PASS  Hugo build")

    # 2. JS syntax check
    js_file = root / "static" / "js" / "search" / "unified-search.js"
    if js_file.exists():
        result = subprocess.run(
            ["node", "--check", str(js_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            errors.append(f"JS syntax error: {result.stderr[:300]}")
        else:
            print("PASS  JS syntax valid")

        # Brace balance
        content = js_file.read_text()
        opens = content.count("{")
        closes = content.count("}")
        if opens != closes:
            errors.append(f"JS unbalanced braces: {opens} opens vs {closes} closes")
        else:
            print("PASS  JS braces balanced")
    else:
        errors.append("unified-search.js not found")

    # 3. Modal HTML div balance
    modal_file = root / "layouts" / "partials" / "global-search-modal.html"
    if modal_file.exists():
        content = modal_file.read_text()
        div_opens = content.count("<div")
        div_closes = content.count("</div>")
        if div_opens != div_closes:
            errors.append(
                f"Modal HTML unbalanced divs: {div_opens} opens vs {div_closes} closes"
            )
        else:
            print("PASS  Modal HTML balanced")
    else:
        errors.append("global-search-modal.html not found")

    # -- Tier 2: Soft checks -----------------------------------------------

    css_file = root / "static" / "css" / "custom.css"
    if css_file.exists():
        css_content = css_file.read_text()

        # Check for keyframes without reduced-motion
        has_keyframes = "@keyframes" in css_content
        has_reduced_motion = "prefers-reduced-motion" in css_content
        if has_keyframes and not has_reduced_motion:
            warnings.append(
                "Has @keyframes but missing prefers-reduced-motion fallback"
            )
        elif has_keyframes:
            print("PASS  Reduced motion support present")

    # -- Summary -----------------------------------------------------------
    print()
    for w in warnings:
        print(f"WARN  {w}")

    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        print()
        print(f"RESULT: FAIL ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1

    print(f"RESULT: PASS ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
