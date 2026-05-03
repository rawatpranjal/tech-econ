#!/usr/bin/env python3
"""Forward/backward schema migrations for data/*.json.

Architecture rule C7 (master_recsys_planner.md):
    "Schema changes require a migration. scripts/migrate_data.py
     accumulates one function per migration. Old shape -> new shape,
     idempotent, reversible where possible."

This file is the registry. It starts empty: no migration is needed
yet because we haven't broken any schema. The point of shipping the
scaffold *now* is so the first migration is a 30-line addition rather
than a "let's design a migration framework" detour.

Inputs
    - CLI: --target {file or 'all'} --to-version {N}
    - data/<file>.json (read + atomic write)

Outputs
    - data/<file>.json updated in place via lib.data_io.write_json_atomic
    - stdout: migration log

Side effects
    - Atomic writes via lib.data_io.write_json_atomic
    - Reads recsys_config.json only to learn where data lives;
      never modifies config

Reproducibility
    - Each migration is a pure function of (old payload) -> new payload
    - --dry-run prints the diff summary without writing
    - The registry below is the only mutable state; bumping versions
      means appending entries, never editing existing ones

Architecture rules enforced
    A1: Inputs/Outputs/Side effects/Reproducibility documented
    B6: every migration writes a fresh _meta block with the new
        schema_version + applied_at timestamp
    C7: this IS the migration mechanism
    C8: missing fields tolerated; default values apply
    E14: unknown migration target raises rather than silently skipping
    G18/19: tested in tests/python/scripts/test_migrate_data.py

Usage
    python scripts/migrate_data.py --list
    python scripts/migrate_data.py --target packages.json --to-version 2 --dry-run
    python scripts/migrate_data.py --target all --to-version 2

Conventions for adding a new migration
    1. Bump SCHEMA_VERSION for the affected file in lib/schemas.py.
    2. Append a Migration() entry to MIGRATIONS at the bottom of
       this file. Each entry has a `from_version`, `to_version`,
       `target` (filename or '*'), and `apply` callable.
    3. Add a test in tests/python/scripts/test_migrate_data.py
       that constructs a v{N-1} dict, runs apply(), and asserts the
       v{N} shape.
    4. Document in CHANGELOG.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make `lib/` importable when running directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass(frozen=True)
class Migration:
    """One step from from_version -> to_version on a single target.

    `target` may be a specific filename ("packages.json") or "*"
    meaning "applies to every data/*.json".

    `apply` is a pure function: takes the old top-level payload and
    returns the new one. It MUST NOT mutate input. It MUST be
    idempotent — running it twice in a row should produce the same
    result as running it once.
    """
    from_version: int
    to_version: int
    target: str
    description: str
    apply: Callable[[Any], Any]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Append to this list, never edit existing entries.
MIGRATIONS: list[Migration] = [
    # No migrations yet. The scaffold is in place so the first one is
    # a small additive change, not a framework discussion.
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_schema_version(payload: Any, default: int = 1) -> int:
    """Read _meta.schema_version from a payload, defaulting to 1.

    Migrations that pre-date _meta blocks are treated as v1.
    """
    if isinstance(payload, dict):
        meta = payload.get("_meta") or {}
        if isinstance(meta, dict):
            v = meta.get("schema_version")
            if isinstance(v, int):
                return v
    return default


def stamp_meta(payload: Any, *, schema_version: int, applied_by: str) -> Any:
    """Stamp/update the _meta block on a payload (rule B6)."""
    if not isinstance(payload, dict):
        # List-shaped payload (papers_flat, packages, etc.) — wrap
        # under {_meta, items} on first migration. Subsequent migrations
        # see a dict.
        return {
            "_meta": {
                "schema_version": schema_version,
                "applied_by": applied_by,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
            "items": payload,
        }
    out = dict(payload)
    meta = dict(out.get("_meta") or {})
    meta["schema_version"] = schema_version
    meta["applied_by"] = applied_by
    meta["applied_at"] = datetime.now(timezone.utc).isoformat()
    out["_meta"] = meta
    return out


def find_migrations_for(target: str, current_version: int, target_version: int) -> list[Migration]:
    """Return the chain of migrations to apply to `target` from
    current_version up to target_version, in order.

    Raises ValueError if no path exists.
    """
    if current_version > target_version:
        raise ValueError(
            f"Cannot migrate backwards: current={current_version} > "
            f"target={target_version}. Add a reverse migration if needed."
        )
    if current_version == target_version:
        return []

    chain: list[Migration] = []
    cur = current_version
    while cur < target_version:
        candidates = [
            m for m in MIGRATIONS
            if (m.target == target or m.target == "*")
            and m.from_version == cur
        ]
        if not candidates:
            raise ValueError(
                f"No migration registered from v{cur} for target {target!r}. "
                f"Available: {[(m.from_version, m.to_version, m.target) for m in MIGRATIONS]}"
            )
        # Prefer the migration that gets us closest to target without overshoot
        candidates.sort(key=lambda m: m.to_version)
        chosen = next(
            (c for c in candidates if c.to_version <= target_version),
            candidates[0],
        )
        if chosen.to_version > target_version:
            raise ValueError(
                f"Only migration from v{cur} jumps to v{chosen.to_version}, "
                f"which overshoots target v{target_version}."
            )
        chain.append(chosen)
        cur = chosen.to_version
    return chain


def migrate_payload(payload: Any, target: str, target_version: int) -> tuple[Any, list[str]]:
    """Apply migrations to a payload. Returns (new_payload, log)."""
    log: list[str] = []
    current = get_schema_version(payload, default=1)
    if current == target_version:
        log.append(f"  {target}: already at v{target_version}; no-op")
        return payload, log

    chain = find_migrations_for(target, current, target_version)
    out = payload
    for m in chain:
        log.append(
            f"  {target}: v{m.from_version} -> v{m.to_version} ({m.description})"
        )
        out = m.apply(out)
        out = stamp_meta(
            out,
            schema_version=m.to_version,
            applied_by=f"migrate_data.py@{m.from_version}->{m.to_version}",
        )
    return out, log


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def list_migrations() -> int:
    if not MIGRATIONS:
        print("No migrations registered. Scaffold is in place; add to "
              "MIGRATIONS in scripts/migrate_data.py when needed.")
        return 0
    print(f"{len(MIGRATIONS)} migration(s) registered:\n")
    for m in MIGRATIONS:
        print(f"  v{m.from_version} -> v{m.to_version} | {m.target} | {m.description}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        help="Filename in data/ to migrate (or 'all' for every data/*.json).",
    )
    parser.add_argument(
        "--to-version",
        type=int,
        help="Schema version to migrate to.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the migration but don't write the result.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered migrations and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        return list_migrations()

    if not args.target or args.to_version is None:
        parser.print_help(sys.stderr)
        print(
            "\nError: --target and --to-version are required (or use --list).",
            file=sys.stderr,
        )
        return 2

    data_dir = _REPO_ROOT / "data"
    if args.target == "all":
        targets = sorted(p.name for p in data_dir.glob("*.json") if not p.name.startswith("."))
    else:
        targets = [args.target]
        if not (data_dir / args.target).exists():
            print(f"Error: {data_dir / args.target} does not exist.", file=sys.stderr)
            return 2

    print(f"Migrating {len(targets)} file(s) to v{args.to_version}"
          f"{' (dry-run)' if args.dry_run else ''}...\n")

    failures = 0
    for filename in targets:
        path = data_dir / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  {filename}: skip — {e}")
            failures += 1
            continue

        try:
            new_payload, log = migrate_payload(payload, filename, args.to_version)
        except ValueError as e:
            print(f"  {filename}: ERROR — {e}")
            failures += 1
            continue

        for line in log:
            print(line)

        if args.dry_run:
            continue

        if new_payload is payload:
            continue

        # Atomic write via lib.data_io if available; fall back to a
        # local tmp+rename so this script keeps working when data_io
        # isn't on main yet.
        try:
            from lib.data_io import write_json_atomic, OutputMeta  # noqa: WPS433
            write_json_atomic(
                path=str(path),
                payload=new_payload,
                meta=OutputMeta(
                    version=f"migrate_data@v{args.to_version}",
                    generated_at=datetime.now(timezone.utc).isoformat(),
                ),
            )
        except (ImportError, TypeError):
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(new_payload, indent=2), encoding="utf-8")
            tmp.replace(path)

    if failures:
        print(f"\n{failures} file(s) failed.", file=sys.stderr)
        return 1
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
