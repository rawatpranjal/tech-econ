"""Bullshit tests for autoresearch/checks/check_deep_metadata.py.

Exercises the validation logic via main() with synthetic packages.json.
Uses pytest.raises(SystemExit) since main() calls sys.exit() on completion.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "autoresearch" / "checks" / "check_deep_metadata.py"

_spec = importlib.util.spec_from_file_location("check_deep_metadata", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_deep_metadata"] = mod
_spec.loader.exec_module(mod)

main = mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(monkeypatch, tmp_path):
    """Run main() with sys.argv pointing to tmp_path, return exit code."""
    monkeypatch.setattr(sys, "argv", [
        "check_deep_metadata.py",
        "--project-root", str(tmp_path),
        "--log-prefix", str(tmp_path / "log"),
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    return exc.value.code


def _write_packages(tmp_path, packages):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "packages.json").write_text(json.dumps(packages))


def _good_dm():
    return {
        "schema_version": 1,
        "math_level": "basic-stats",
        "confidence": "high",
        "methods": [{"name": "OLS", "description": "Ordinary least squares"}],
        "relationships": [],
        "strengths": ["fast", "flexible"],
        "limitations": ["requires stationarity"],
        "key_concepts": [{"name": "IV", "description": "Instrumental Variable"}],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckDeepMetadata:
    def test_valid_package_passes(self, tmp_path, monkeypatch):
        _write_packages(tmp_path, [
            {"name": "DoubleML", "deep_metadata": _good_dm()}
        ])
        assert _run(monkeypatch, tmp_path) == 0

    def test_packages_json_missing_fails(self, tmp_path, monkeypatch):
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        # don't write packages.json
        assert _run(monkeypatch, tmp_path) == 1

    def test_packages_not_a_list_fails(self, tmp_path, monkeypatch):
        _write_packages(tmp_path, {"items": []})
        assert _run(monkeypatch, tmp_path) == 1

    def test_missing_schema_version_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        del dm["schema_version"]
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_invalid_math_level_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["math_level"] = "rocket-science"
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_invalid_confidence_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["confidence"] = "very-high"
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_invalid_relationship_type_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["relationships"] = [{"type": "copied-from", "target": "Other"}]
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_valid_relationship_type_passes(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["relationships"] = [{"type": "alternative-to", "target": "Pkg2"}]
        _write_packages(tmp_path, [
            {"name": "Pkg", "deep_metadata": dm},
            {"name": "Pkg2"},
        ])
        assert _run(monkeypatch, tmp_path) == 0

    def test_method_missing_name_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["methods"] = [{"description": "No name field"}]
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_key_concept_missing_description_fails(self, tmp_path, monkeypatch):
        dm = _good_dm()
        dm["key_concepts"] = [{"name": "IV"}]  # missing description
        _write_packages(tmp_path, [{"name": "Pkg", "deep_metadata": dm}])
        assert _run(monkeypatch, tmp_path) == 1

    def test_regression_guard_fires_when_enriched_drops(self, tmp_path, monkeypatch):
        # First run: 2 enriched packages
        _write_packages(tmp_path, [
            {"name": "A", "deep_metadata": _good_dm()},
            {"name": "B", "deep_metadata": _good_dm()},
        ])
        _run(monkeypatch, tmp_path)  # writes baseline
        # Second run: only 1 enriched → regression
        _write_packages(tmp_path, [
            {"name": "A", "deep_metadata": _good_dm()},
            {"name": "B"},  # deep_metadata removed
        ])
        assert _run(monkeypatch, tmp_path) == 1

    def test_no_deep_metadata_packages_passes(self, tmp_path, monkeypatch):
        # Packages with no deep_metadata are silently skipped
        _write_packages(tmp_path, [
            {"name": "Bare", "url": "https://example.com"}
        ])
        assert _run(monkeypatch, tmp_path) == 0
