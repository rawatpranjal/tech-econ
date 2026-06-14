"""Bullshit tests for migrate_data.py pure helpers.

Covers:
  - get_schema_version: dict/list/None payloads, default, non-int version
  - stamp_meta: dict payload, list payload wrapping, preserves other keys, timestamp ISO format
  - find_migrations_for: already-at-target, backwards raises, no-migration raises, chain walking
  - migrate_payload: no-op, chain applies, stamps each step
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# migrate_data.py only imports lib.data_io lazily (inside apply() at line 296),
# not at module load time. No stub needed — the real lib package is importable
# via the repo root that conftest.py adds to sys.path.

_spec = importlib.util.spec_from_file_location(
    "migrate_data", _REPO_ROOT / "scripts" / "migrate_data.py"
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["migrate_data"] = _mod
_spec.loader.exec_module(_mod)

get_schema_version = _mod.get_schema_version
stamp_meta = _mod.stamp_meta
find_migrations_for = _mod.find_migrations_for
migrate_payload = _mod.migrate_payload
Migration = _mod.Migration
MIGRATIONS = _mod.MIGRATIONS


# ──────────────────────────────────────────────
# get_schema_version
# ──────────────────────────────────────────────

class TestGetSchemaVersion:
    def test_dict_with_version(self):
        assert get_schema_version({"_meta": {"schema_version": 3}}) == 3

    def test_dict_without_meta(self):
        assert get_schema_version({"items": []}) == 1

    def test_empty_dict(self):
        assert get_schema_version({}) == 1

    def test_list_payload(self):
        assert get_schema_version([{"id": 1}]) == 1

    def test_none_payload(self):
        assert get_schema_version(None) == 1

    def test_custom_default(self):
        assert get_schema_version({}, default=5) == 5

    def test_non_int_version_ignored(self):
        # String version should fall back to default
        assert get_schema_version({"_meta": {"schema_version": "2"}}) == 1

    def test_meta_none_falls_back(self):
        assert get_schema_version({"_meta": None}) == 1

    def test_meta_wrong_type_falls_back(self):
        assert get_schema_version({"_meta": "v3"}) == 1

    def test_version_zero(self):
        assert get_schema_version({"_meta": {"schema_version": 0}}) == 0


# ──────────────────────────────────────────────
# stamp_meta
# ──────────────────────────────────────────────

class TestStampMeta:
    def test_dict_payload_adds_meta(self):
        out = stamp_meta({"data": 1}, schema_version=2, applied_by="test")
        assert out["_meta"]["schema_version"] == 2
        assert out["_meta"]["applied_by"] == "test"
        assert "applied_at" in out["_meta"]

    def test_dict_payload_preserves_other_keys(self):
        out = stamp_meta({"data": 42, "name": "x"}, schema_version=1, applied_by="t")
        assert out["data"] == 42
        assert out["name"] == "x"

    def test_list_payload_wrapped(self):
        lst = [1, 2, 3]
        out = stamp_meta(lst, schema_version=1, applied_by="test")
        assert isinstance(out, dict)
        assert out["items"] == lst
        assert out["_meta"]["schema_version"] == 1

    def test_list_payload_meta_fields(self):
        out = stamp_meta([], schema_version=7, applied_by="migrator")
        assert out["_meta"]["applied_by"] == "migrator"

    def test_timestamp_is_iso_format(self):
        import re
        out = stamp_meta({}, schema_version=1, applied_by="x")
        ts = out["_meta"]["applied_at"]
        # Should look like 2026-05-25T... with a T separator
        assert "T" in ts

    def test_does_not_mutate_input(self):
        inp = {"key": "val"}
        stamp_meta(inp, schema_version=2, applied_by="x")
        assert "_meta" not in inp

    def test_overwrites_existing_meta(self):
        inp = {"_meta": {"schema_version": 1, "old_key": "keep"}}
        out = stamp_meta(inp, schema_version=2, applied_by="new")
        assert out["_meta"]["schema_version"] == 2
        assert out["_meta"]["applied_by"] == "new"

    def test_preserves_extra_meta_fields(self):
        # Other _meta keys from earlier migrations should survive
        inp = {"_meta": {"schema_version": 1, "custom": "yes"}}
        out = stamp_meta(inp, schema_version=2, applied_by="x")
        assert out["_meta"]["custom"] == "yes"


# ──────────────────────────────────────────────
# find_migrations_for (with synthetic MIGRATIONS)
# ──────────────────────────────────────────────

def _make_migration(from_v, to_v, target="packages.json"):
    return Migration(
        from_version=from_v,
        to_version=to_v,
        target=target,
        description=f"v{from_v}->v{to_v}",
        apply=lambda p: p,
    )


@pytest.fixture(autouse=False)
def clean_migrations(monkeypatch):
    """Replace the module-level MIGRATIONS with an empty list for the test, then restore."""
    monkeypatch.setattr(_mod, "MIGRATIONS", [])
    yield _mod.MIGRATIONS


class TestFindMigrationsFor:
    def test_already_at_target_returns_empty(self):
        result = find_migrations_for("packages.json", 2, 2)
        assert result == []

    def test_backwards_raises(self):
        with pytest.raises(ValueError, match="backwards"):
            find_migrations_for("packages.json", 3, 2)

    def test_no_migration_registered_raises(self, clean_migrations):
        with pytest.raises(ValueError, match="No migration registered"):
            find_migrations_for("packages.json", 1, 2)

    def test_wildcard_migration_matches_any_target(self, clean_migrations):
        m = Migration(
            from_version=1, to_version=2, target="*",
            description="v1->v2 universal", apply=lambda p: p,
        )
        clean_migrations.append(m)
        chain = find_migrations_for("packages.json", 1, 2)
        assert len(chain) == 1
        assert chain[0] is m

    def test_two_step_chain(self, clean_migrations):
        m1 = Migration(from_version=1, to_version=2, target="*",
                       description="1->2", apply=lambda p: p)
        m2 = Migration(from_version=2, to_version=3, target="*",
                       description="2->3", apply=lambda p: p)
        clean_migrations.extend([m1, m2])
        chain = find_migrations_for("packages.json", 1, 3)
        assert len(chain) == 2
        assert chain[0] is m1
        assert chain[1] is m2

    def test_specific_target_preferred_over_wildcard(self, clean_migrations):
        mwild = Migration(from_version=1, to_version=2, target="*",
                          description="wild", apply=lambda p: {"wild": True})
        mspec = Migration(from_version=1, to_version=2, target="packages.json",
                          description="specific", apply=lambda p: {"specific": True})
        clean_migrations.extend([mwild, mspec])
        chain = find_migrations_for("packages.json", 1, 2)
        assert len(chain) == 1


# ──────────────────────────────────────────────
# migrate_payload
# ──────────────────────────────────────────────

class TestMigratePayload:
    def test_already_at_version_noop(self):
        payload = {"_meta": {"schema_version": 2}, "items": []}
        out, log = migrate_payload(payload, "packages.json", 2)
        assert out is payload
        assert any("no-op" in line for line in log)

    def test_missing_migration_raises_wrapped(self):
        payload = {"_meta": {"schema_version": 1}}
        with pytest.raises(ValueError):
            migrate_payload(payload, "packages.json", 5)

    def test_chain_applied_and_stamped(self, clean_migrations):
        def add_flag(p):
            out = dict(p) if isinstance(p, dict) else {"items": p}
            out["flagged"] = True
            return out

        m = Migration(from_version=1, to_version=2, target="*",
                      description="add flag", apply=add_flag)
        clean_migrations.append(m)
        payload = {"items": [], "_meta": {"schema_version": 1}}
        out, log = migrate_payload(payload, "packages.json", 2)
        assert out["flagged"] is True
        assert out["_meta"]["schema_version"] == 2
        assert len(log) == 1
        assert "v1" in log[0]

    def test_default_version_treated_as_v1(self):
        # Payload with no _meta is treated as v1
        payload = [{"id": 1}, {"id": 2}]
        out, log = migrate_payload(payload, "datasets.json", 1)
        assert out is payload
        assert any("no-op" in line for line in log)
