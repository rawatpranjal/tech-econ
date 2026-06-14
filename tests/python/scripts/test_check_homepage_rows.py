"""Bullshit tests for autoresearch/checks/check_homepage_rows.py.

Exercises the validation logic via main() with synthetic JSON files.
No network or real data needed.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "autoresearch" / "checks" / "check_homepage_rows.py"

_spec = importlib.util.spec_from_file_location("check_homepage_rows", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_homepage_rows"] = mod
_spec.loader.exec_module(mod)

main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(row_id, n_items=5, item_type="package"):
    items = [
        {"name": f"{row_id}-item-{i}", "type": item_type, "url": f"https://example.com/{i}"}
        for i in range(n_items)
    ]
    return {"id": row_id, "row_type": "standard", "title": row_id.title(),
            "template": "row-standard", "items": items}


def _write_rows(tmp_path, rows_data):
    f = tmp_path / "data" / "homepage_rows.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows_data))
    return tmp_path


def _run(monkeypatch, tmp_path):
    """Run main() with --project-root pointing to tmp_path."""
    monkeypatch.setattr(sys, "argv", ["check_homepage_rows.py", "--project-root", str(tmp_path)])
    return main()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckHomepageRows:
    def test_valid_data_passes(self, tmp_path, monkeypatch):
        rows = [
            _make_row("packages", item_type="package"),
            _make_row("datasets", item_type="dataset"),
            _make_row("resources", item_type="resource"),
            _make_row("talks", item_type="talk"),
            _make_row("books", item_type="book"),
        ]
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 0

    def test_missing_rows_key_fails(self, tmp_path, monkeypatch):
        _write_rows(tmp_path, {"items": []})
        assert _run(monkeypatch, tmp_path) == 1

    def test_file_missing_fails(self, tmp_path, monkeypatch):
        assert _run(monkeypatch, tmp_path) == 1

    def test_invalid_json_fails(self, tmp_path, monkeypatch):
        f = tmp_path / "data" / "homepage_rows.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{not valid json")
        assert _run(monkeypatch, tmp_path) == 1

    def test_too_few_rows_fails(self, tmp_path, monkeypatch):
        # Only 2 rows — below MIN_ROWS=5
        rows = [_make_row(f"r{i}", item_type="package") for i in range(2)]
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 1

    def test_row_missing_required_field_fails(self, tmp_path, monkeypatch):
        row = _make_row("pkgs")
        del row["template"]  # remove required field
        rows = [row] + [
            _make_row(f"r{i}", item_type=["package", "dataset", "resource", "talk"][i % 4])
            for i in range(4)
        ]
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 1

    def test_too_many_duplicates_fails(self, tmp_path, monkeypatch):
        # Same item name appears in 6 rows — exceeds MAX_ALLOWED_DUPLICATES=5
        rows = []
        for i in range(6):
            row = _make_row(f"row{i}", item_type="package")
            row["items"][0]["name"] = "DuplicateItem"
            rows.append(row)
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 1

    def test_missing_expected_types_fails(self, tmp_path, monkeypatch):
        # Only packages — missing dataset, resource, talk
        rows = [_make_row(f"r{i}", item_type="package") for i in range(5)]
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 1

    def test_items_mmr_field_not_required(self, tmp_path, monkeypatch):
        # items_mmr is optional — rows without it should still pass
        rows = [
            _make_row("packages", item_type="package"),
            _make_row("datasets", item_type="dataset"),
            _make_row("resources", item_type="resource"),
            _make_row("talks", item_type="talk"),
            _make_row("books", item_type="book"),
        ]
        _write_rows(tmp_path, {"rows": rows})
        assert _run(monkeypatch, tmp_path) == 0
