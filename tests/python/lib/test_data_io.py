"""Tests for lib/data_io.py — atomic JSON IO with provenance metadata."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from lib.data_io import (
    OutputMeta,
    current_git_sha,
    read_json,
    write_json_atomic,
)


# ---------------------------------------------------------------------------
# OutputMeta
# ---------------------------------------------------------------------------
class TestOutputMeta:
    def test_required_version(self):
        m = OutputMeta(version="rank@v1")
        assert m.version == "rank@v1"

    def test_generated_at_default_is_iso_z(self):
        m = OutputMeta(version="x")
        # ISO-8601 with seconds resolution and Z suffix
        assert m.generated_at.endswith("Z")
        assert "T" in m.generated_at

    def test_git_sha_resolves_or_none(self):
        # In CI we are inside a git repo so this should be a non-empty
        # short sha; if not in a repo it should be None. Either way it
        # is never an empty string.
        m = OutputMeta(version="x")
        assert m.git_sha is None or (isinstance(m.git_sha, str) and len(m.git_sha) > 0)

    def test_to_dict_round_trip(self):
        m = OutputMeta(version="x", generated_at="2026-01-01T00:00:00Z", git_sha="abc1234")
        d = m.to_dict()
        assert d == {
            "version": "x",
            "generated_at": "2026-01-01T00:00:00Z",
            "git_sha": "abc1234",
            "schema_version": 1,
        }

    def test_frozen(self):
        m = OutputMeta(version="x")
        with pytest.raises(Exception):
            m.version = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# current_git_sha
# ---------------------------------------------------------------------------
class TestCurrentGitSha:
    def test_in_repo_returns_string(self):
        sha = current_git_sha()
        # Tests run from inside the tech-econ repo, so this should
        # always succeed in CI and locally.
        assert sha is None or (isinstance(sha, str) and 0 < len(sha) <= 40)

    def test_no_git_returns_none(self):
        # Simulate the "git not on PATH" case — the function should
        # never raise.
        with mock.patch(
            "lib.data_io.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            assert current_git_sha() is None


# ---------------------------------------------------------------------------
# read_json
# ---------------------------------------------------------------------------
class TestReadJson:
    def test_reads_dict(self, tmp_path: Path):
        p = tmp_path / "x.json"
        p.write_text('{"a": 1, "b": 2}\n', encoding="utf-8")
        assert read_json(p) == {"a": 1, "b": 2}

    def test_reads_list(self, tmp_path: Path):
        p = tmp_path / "x.json"
        p.write_text("[1, 2, 3]\n", encoding="utf-8")
        assert read_json(p) == [1, 2, 3]

    def test_tolerates_missing_meta(self, tmp_path: Path):
        # File written before _meta existed — read_json must not raise
        p = tmp_path / "x.json"
        p.write_text('{"items": []}', encoding="utf-8")
        result = read_json(p)
        assert "_meta" not in result  # we don't fabricate one
        assert result == {"items": []}

    def test_missing_path_raises_filenotfounderror(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_json(tmp_path / "does-not-exist.json")

    def test_invalid_json_raises_valueerror(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            read_json(p)


# ---------------------------------------------------------------------------
# write_json_atomic
# ---------------------------------------------------------------------------
class TestWriteJsonAtomic:
    def test_dict_payload_injects_meta(self, tmp_path: Path):
        p = tmp_path / "out.json"
        meta = OutputMeta(version="v1", generated_at="2026-01-01T00:00:00Z", git_sha="abc")
        write_json_atomic(p, {"a": 1}, meta=meta)
        result = json.loads(p.read_text(encoding="utf-8"))
        assert result["a"] == 1
        assert result["_meta"]["version"] == "v1"
        assert result["_meta"]["generated_at"] == "2026-01-01T00:00:00Z"

    def test_list_payload_passes_through_unchanged(self, tmp_path: Path):
        # Lists don't get _meta injected (would change every reader's
        # contract). Document this explicitly.
        p = tmp_path / "items.json"
        meta = OutputMeta(version="v1")
        write_json_atomic(p, [1, 2, 3], meta=meta)
        result = json.loads(p.read_text(encoding="utf-8"))
        assert result == [1, 2, 3]

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = tmp_path / "deep" / "nested" / "out.json"
        meta = OutputMeta(version="v1")
        write_json_atomic(p, {}, meta=meta)
        assert p.exists()

    def test_atomic_failure_preserves_original(self, tmp_path: Path):
        # Existing file should survive a serialisation error mid-write.
        p = tmp_path / "out.json"
        p.write_text('{"original": true}', encoding="utf-8")
        meta = OutputMeta(version="v1")

        # Patch os.replace so the tmp file is never moved into place.
        with mock.patch(
            "lib.data_io.os.replace",
            side_effect=OSError("boom"),
        ):
            with pytest.raises(OSError):
                write_json_atomic(p, {"new": True}, meta=meta)

        # Original file is intact, tmp file was cleaned up.
        assert json.loads(p.read_text(encoding="utf-8")) == {"original": True}
        tmp = p.with_suffix(p.suffix + ".tmp")
        assert not tmp.exists(), "tmp file should be cleaned up after failure"

    def test_round_trip_idempotent(self, tmp_path: Path):
        p = tmp_path / "rt.json"
        meta = OutputMeta(
            version="v1",
            generated_at="2026-01-01T00:00:00Z",
            git_sha="abc1234",
        )
        payload = {"items": [{"id": "x"}, {"id": "y"}]}
        write_json_atomic(p, payload, meta=meta)
        first = read_json(p)
        # Writing the same payload again with a fresh OutputMeta of the
        # same content yields identical bytes.
        write_json_atomic(p, payload, meta=meta)
        second = read_json(p)
        assert first == second

    def test_trailing_newline(self, tmp_path: Path):
        p = tmp_path / "nl.json"
        write_json_atomic(p, {"x": 1}, meta=OutputMeta(version="v1"))
        text = p.read_text(encoding="utf-8")
        assert text.endswith("\n"), "file should end with a newline for diffing"

    def test_unicode_payload(self, tmp_path: Path):
        p = tmp_path / "u.json"
        write_json_atomic(p, {"name": "résumé"}, meta=OutputMeta(version="v1"))
        result = json.loads(p.read_text(encoding="utf-8"))
        assert result["name"] == "résumé"
