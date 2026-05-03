"""Atomic, versioned JSON IO with provenance metadata.

Inputs:
    - paths to read / write data/*.json files
    - payload to serialise (dict or list)
    - OutputMeta describing the write (version, generated_at, git_sha)

Outputs:
    - On disk: the JSON file, written atomically (tmp + os.replace)
    - In memory: deserialised JSON for read_json()

Side effects:
    - write_json_atomic() writes a temp file alongside the target then
      atomically replaces it. A crash mid-write leaves the previous
      file intact.

Reproducibility:
    - read_json + write_json_atomic are deterministic
    - current_git_sha() is process-side only — falls back to None when
      we're not in a git repo

Architecture rules enforced
    - B6: every JSON we emit carries a _meta block (version,
      generated_at, git_sha)
    - C8: read_json tolerates files that pre-date _meta — never raises
      on missing fields
    - D12: atomic writes (tmp + os.replace) so a crash never leaves a
      half-written JSON

Usage
    from lib.data_io import OutputMeta, write_json_atomic, read_json
    write_json_atomic(
        "data/papers_flat.json",
        items,
        meta=OutputMeta(version="rank-pipeline@v3.2"),
    )
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
def _utc_now_iso() -> str:
    """ISO-8601 timestamp in UTC, second-resolution. Stable for tests."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def current_git_sha() -> str | None:
    """Return the short git SHA of HEAD, or None if not in a repo.

    Never raises — failures (no git, no repo, command not found) all
    yield None so writers can include the field unconditionally.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


@dataclass(frozen=True)
class OutputMeta:
    """Provenance block stamped onto every JSON we own.

    `version` is required — the calling pipeline names itself
    (e.g. "rank-pipeline@v3.2") so readers can branch on it.

    `generated_at` defaults to current UTC at construction time, which
    is fine because OutputMeta is meant to be built once per write.

    `git_sha` resolves to the short HEAD on construction; pass an
    explicit value to override (useful for tests).
    """

    version: str
    generated_at: str = field(default_factory=_utc_now_iso)
    git_sha: str | None = field(default_factory=current_git_sha)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        # asdict gives us a fresh dict every time so callers can mutate
        return asdict(self)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def read_json(path: str | Path) -> Any:
    """Read JSON from a file. Tolerates missing _meta block (rule C8).

    Returns whatever the file contains — typically a dict (carouseled
    output) or a list (papers_flat-style flat array).

    Raises FileNotFoundError if path doesn't exist (callers usually want
    that explicit) and ValueError on malformed JSON.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{p} is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def _inject_meta(payload: Any, meta: OutputMeta) -> Any:
    """Return `payload` with a `_meta` field at the top level.

    For dict payloads we add (or overwrite) the `_meta` key. For lists
    or scalars we leave the structure untouched — wrapping a list would
    silently change every reader's contract. Callers who want metadata
    on a list-shaped file should wrap it in a dict themselves
    (`{"items": [...], "_meta": ...}`) before passing it in.
    """
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out["_meta"] = meta.to_dict()
    return out


def write_json_atomic(
    path: str | Path,
    payload: Any,
    *,
    meta: OutputMeta,
    indent: int | None = 2,
) -> None:
    """Atomically serialise `payload` to `path`.

    Writes to `<path>.tmp` first, then `os.replace`s onto the target.
    A crash before `os.replace` leaves the original file untouched
    (rule D12). The tmp file is removed on serialisation error so we
    don't leave debris behind.

    `meta` is mandatory — every JSON we write must carry provenance
    (rule B6). For dict payloads it's injected at the top level. For
    list payloads `meta` is currently ignored (see _inject_meta) but
    still required so callers don't accidentally write metadata-less
    files.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = _inject_meta(payload, meta)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=indent, ensure_ascii=False, sort_keys=False)
            f.write("\n")  # trailing newline for nicer diffs
        os.replace(tmp, p)
    except Exception:
        # Best-effort cleanup; never mask the original error.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


__all__ = [
    "OutputMeta",
    "current_git_sha",
    "read_json",
    "write_json_atomic",
]
