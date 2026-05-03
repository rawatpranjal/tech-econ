"""Tests for scripts/migrate_data.py.

The registry is empty by design — no migration is needed yet. These
tests cover the SCAFFOLD: that the framework itself works correctly
once a migration is appended. Real migrations get their own per-test
files in this directory once they exist.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make `scripts/` importable without conflicting with `lib/`.
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


@pytest.fixture
def md():
    """Import scripts/migrate_data.py once per test for isolation
    (the module-level MIGRATIONS list is mutable in some tests via
    `patch.object`)."""
    if "migrate_data" in sys.modules:
        return importlib.reload(sys.modules["migrate_data"])
    return importlib.import_module("migrate_data")


# ---------------------------------------------------------------------------
# get_schema_version
# ---------------------------------------------------------------------------
class TestGetSchemaVersion:
    def test_default_for_pre_meta_payload(self, md):
        assert md.get_schema_version([]) == 1
        assert md.get_schema_version({"items": []}) == 1
        assert md.get_schema_version({"_meta": {}}) == 1

    def test_reads_from_meta(self, md):
        assert md.get_schema_version({"_meta": {"schema_version": 5}}) == 5

    def test_non_int_falls_back_to_default(self, md):
        assert md.get_schema_version({"_meta": {"schema_version": "five"}}) == 1

    def test_custom_default(self, md):
        assert md.get_schema_version([], default=99) == 99


# ---------------------------------------------------------------------------
# stamp_meta
# ---------------------------------------------------------------------------
class TestStampMeta:
    def test_wraps_list_payload(self, md):
        out = md.stamp_meta([1, 2, 3], schema_version=2, applied_by="test")
        assert isinstance(out, dict)
        assert out["items"] == [1, 2, 3]
        assert out["_meta"]["schema_version"] == 2
        assert out["_meta"]["applied_by"] == "test"
        assert "applied_at" in out["_meta"]

    def test_updates_existing_meta(self, md):
        out = md.stamp_meta(
            {"_meta": {"schema_version": 1, "extra": "preserved"}, "items": []},
            schema_version=2,
            applied_by="test",
        )
        assert out["_meta"]["schema_version"] == 2
        # Extra fields are preserved
        assert out["_meta"]["extra"] == "preserved"

    def test_does_not_mutate_input(self, md):
        original = {"_meta": {"schema_version": 1}, "items": []}
        md.stamp_meta(original, schema_version=2, applied_by="test")
        assert original["_meta"]["schema_version"] == 1


# ---------------------------------------------------------------------------
# find_migrations_for
# ---------------------------------------------------------------------------
class TestFindMigrations:
    def test_same_version_returns_empty(self, md):
        assert md.find_migrations_for("anything.json", 3, 3) == []

    def test_backwards_raises(self, md):
        with pytest.raises(ValueError, match="Cannot migrate backwards"):
            md.find_migrations_for("x.json", 5, 3)

    def test_no_path_raises(self, md):
        with pytest.raises(ValueError, match="No migration registered from v1"):
            md.find_migrations_for("x.json", 1, 2)

    def test_finds_chain(self, md):
        m12 = md.Migration(1, 2, "x.json", "step a", lambda p: p)
        m23 = md.Migration(2, 3, "x.json", "step b", lambda p: p)
        with patch.object(md, "MIGRATIONS", [m12, m23]):
            chain = md.find_migrations_for("x.json", 1, 3)
            assert [(m.from_version, m.to_version) for m in chain] == [(1, 2), (2, 3)]

    def test_wildcard_target_matches(self, md):
        wild = md.Migration(1, 2, "*", "global step", lambda p: p)
        with patch.object(md, "MIGRATIONS", [wild]):
            chain = md.find_migrations_for("anything.json", 1, 2)
            assert len(chain) == 1
            assert chain[0].target == "*"


# ---------------------------------------------------------------------------
# migrate_payload
# ---------------------------------------------------------------------------
class TestMigratePayload:
    def test_no_op_when_already_at_target_version(self, md):
        payload = {"_meta": {"schema_version": 2}, "items": []}
        out, log = md.migrate_payload(payload, "x.json", 2)
        assert out is payload  # exact identity preserved
        assert any("no-op" in line for line in log)

    def test_applies_single_migration(self, md):
        def add_field(p):
            new = dict(p)
            new["new_field"] = True
            return new

        m = md.Migration(1, 2, "x.json", "add new_field", add_field)
        with patch.object(md, "MIGRATIONS", [m]):
            payload = {"_meta": {"schema_version": 1}, "items": []}
            out, log = md.migrate_payload(payload, "x.json", 2)
        assert out["new_field"] is True
        assert out["_meta"]["schema_version"] == 2
        assert any("v1 -> v2" in line for line in log)

    def test_applies_chained_migrations(self, md):
        def step1(p):
            new = dict(p)
            new["step1"] = True
            return new

        def step2(p):
            new = dict(p)
            new["step2"] = True
            return new

        m12 = md.Migration(1, 2, "x.json", "step 1", step1)
        m23 = md.Migration(2, 3, "x.json", "step 2", step2)
        with patch.object(md, "MIGRATIONS", [m12, m23]):
            payload = {"_meta": {"schema_version": 1}, "items": []}
            out, _ = md.migrate_payload(payload, "x.json", 3)
        assert out["step1"] is True
        assert out["step2"] is True
        assert out["_meta"]["schema_version"] == 3


# ---------------------------------------------------------------------------
# Registry sanity (catches bad commits to MIGRATIONS list)
# ---------------------------------------------------------------------------
class TestRegistry:
    def test_no_duplicate_from_to_pairs_per_target(self, md):
        """If two migrations claim the same (from, to, target), the
        chain-finder will be ambiguous. Catch it now."""
        seen: set[tuple[int, int, str]] = set()
        for m in md.MIGRATIONS:
            key = (m.from_version, m.to_version, m.target)
            assert key not in seen, f"Duplicate migration entry: {key}"
            seen.add(key)

    def test_each_migration_increments_version(self, md):
        for m in md.MIGRATIONS:
            assert m.from_version < m.to_version, (
                f"Migration {m.target} v{m.from_version}->v{m.to_version} "
                "must be strictly forward; add a separate reverse entry "
                "for downgrades."
            )

    def test_apply_callables_are_callable(self, md):
        for m in md.MIGRATIONS:
            assert callable(m.apply), f"Migration {m.target} apply isn't callable"


# ---------------------------------------------------------------------------
# CLI driver smoke
# ---------------------------------------------------------------------------
class TestCliDriver:
    def test_list_with_empty_registry(self, md, capsys):
        rc = md.list_migrations()
        assert rc == 0
        out = capsys.readouterr().out
        assert "No migrations registered" in out

    def test_list_with_non_empty_registry(self, md, capsys):
        m = md.Migration(1, 2, "x.json", "test", lambda p: p)
        with patch.object(md, "MIGRATIONS", [m]):
            rc = md.list_migrations()
        out = capsys.readouterr().out
        assert rc == 0
        assert "v1 -> v2" in out
        assert "x.json" in out

    def test_main_returns_2_when_args_missing(self, md):
        # main() requires --target and --to-version unless --list
        rc = md.main([])
        assert rc == 2

    def test_main_handles_missing_target_file(self, md, tmp_path):
        rc = md.main(["--target", "does-not-exist.json", "--to-version", "2"])
        assert rc == 2

    def test_main_dry_run_does_not_write(self, md, tmp_path, capsys):
        # Write a real data file under a temp data dir, then point the
        # script at it via --target. Since the script resolves data_dir
        # from REPO_ROOT, we can't fully isolate without monkey-patching.
        # Workaround: place the file in the actual data/ dir under a
        # temp name; verify dry-run does not modify it.
        data_dir = Path(__file__).resolve().parents[3] / "data"
        test_file = data_dir / ".test_migrate_smoke.json"
        try:
            payload = {"_meta": {"schema_version": 1}, "items": [{"x": 1}]}
            test_file.write_text(json.dumps(payload), encoding="utf-8")
            mtime_before = test_file.stat().st_mtime
            rc = md.main([
                "--target", ".test_migrate_smoke.json",
                "--to-version", "1",  # already at v1, no-op
                "--dry-run",
            ])
            assert rc == 0
            mtime_after = test_file.stat().st_mtime
            assert mtime_before == mtime_after, "dry-run wrote the file"
        finally:
            if test_file.exists():
                test_file.unlink()
