#!/usr/bin/env python3
"""check_secrets.py -- compare .claude/secrets.env against the template.

Why this exists
    Today the user did `npx wrangler deploy` and then hit
    /run-schema?key=$ADMIN_KEY -- and got "Unauthorized" because
    ADMIN_KEY was in the template (.claude/secrets.env.template) but
    not in the actual secrets.env. The migration still landed (we
    routed around with `wrangler d1 execute` directly) but the gap
    cost time and could have caused a longer outage if the worker had
    needed an explicit /run-schema for a less-self-healing change.

    This helper closes the loop: run it from CI or pre-commit (or
    just manually) and it warns about every key the template declares
    that the actual env file is missing.

Inputs
    - .claude/secrets.env.template  (canonical list of names)
    - .claude/secrets.env           (the user's actual file)

Outputs
    - stdout: missing-keys report; exit 0 if all template keys are
      present, exit 1 if any are missing.

Side effects
    - None. Read-only on both files. Never prints values.

Reproducibility
    - Pure given the two files. Empty values count as set (we don't
      try to validate that the value is meaningful — only that the
      assignment exists).

Usage
    python3 scripts/check_secrets.py
    python3 scripts/check_secrets.py --template <path> --env <path>
    python3 scripts/check_secrets.py --quiet  # exit code only
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_TEMPLATE = _REPO_ROOT / ".claude" / "secrets.env.template"
_DEFAULT_ENV = _REPO_ROOT / ".claude" / "secrets.env"

# Match `KEY=...` lines (ignoring leading whitespace + optional `export `).
# We DON'T capture the value -- the template's value is literally `xxx` or
# `sk-xxx` placeholder text and we never want to touch it.
_KEY_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=")


def parse_keys(path: Path) -> set[str]:
    """Return the set of UPPER_SNAKE_CASE keys declared in `path`.

    Skips comments (`# ...`) and blank lines. Skips export prefixes.
    Returns empty set if `path` doesn't exist.
    """
    if not path.exists():
        return set()
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _KEY_LINE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def diff_keys(template_keys: set[str], env_keys: set[str]) -> dict[str, list[str]]:
    """Compute the per-side diff. Returns:
      missing_in_env: keys declared in the template but not in env
      extra_in_env:   keys in env that the template doesn't declare
                      (informational; not a blocker)
    """
    return {
        "missing_in_env": sorted(template_keys - env_keys),
        "extra_in_env": sorted(env_keys - template_keys),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--template",
        default=str(_DEFAULT_TEMPLATE),
        help="path to secrets.env.template (default: .claude/secrets.env.template)",
    )
    parser.add_argument(
        "--env",
        default=str(_DEFAULT_ENV),
        help="path to secrets.env (default: .claude/secrets.env)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="exit code only; suppress stdout",
    )
    args = parser.parse_args(argv)

    template_path = Path(args.template)
    env_path = Path(args.env)

    if not template_path.exists():
        if not args.quiet:
            print(f"check_secrets: template not found at {template_path}")
        return 2

    template_keys = parse_keys(template_path)
    env_keys = parse_keys(env_path)
    diff = diff_keys(template_keys, env_keys)

    missing = diff["missing_in_env"]
    extra = diff["extra_in_env"]

    if not env_path.exists():
        if not args.quiet:
            print(
                f"check_secrets: {env_path} does not exist. "
                f"Copy from {template_path} and fill in values."
            )
        return 1

    if missing:
        if not args.quiet:
            print(
                f"check_secrets: {len(missing)} key(s) declared in template "
                f"but missing from {env_path.name}:"
            )
            for k in missing:
                print(f"  - {k}")
            print(
                f"\n  Add the missing line(s) to {env_path}, then re-run. "
                f"Never paste values in chat or commit messages."
            )
        return 1

    if not args.quiet:
        print(f"check_secrets: OK — {len(template_keys)} key(s) match template.")
        if extra:
            print(
                f"  (informational: {len(extra)} extra key(s) in env not in template: "
                f"{', '.join(extra)})"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
