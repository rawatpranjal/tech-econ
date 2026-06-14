"""Bullshit tests for autoresearch/checks/check_homepage_visual.py.

Exercises CSS validation, template marker checks, and baseline regression guard
via main() with synthetic files. Hugo build is monkeypatched to avoid subprocess.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "autoresearch" / "checks" / "check_homepage_visual.py"

_spec = importlib.util.spec_from_file_location("check_homepage_visual", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_homepage_visual"] = mod
_spec.loader.exec_module(mod)

main = mod.main

_TEMPLATE_CHECKS = mod.TEMPLATE_CHECKS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CSS = "body { margin: 0; }\n" * 100  # ~1800 bytes, balanced braces


def _write_css(tmp_path, content=None):
    css_dir = tmp_path / "static" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "custom.css").write_text(content if content is not None else _VALID_CSS)


def _write_templates(tmp_path):
    for tmpl_rel, markers in _TEMPLATE_CHECKS.items():
        full = tmp_path / tmpl_rel
        full.parent.mkdir(parents=True, exist_ok=True)
        # Write all required markers into the file
        full.write_text("\n".join(markers) + "\n")


def _run(monkeypatch, tmp_path, mock_hugo=True):
    monkeypatch.setattr(sys, "argv", [
        "check_homepage_visual.py",
        "--project-root", str(tmp_path),
        "--log-prefix", str(tmp_path / "log"),
    ])
    if mock_hugo:
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: SimpleNamespace(returncode=0, stderr="", stdout=""),
        )
    return main()


# ---------------------------------------------------------------------------
# CSS validation tests
# ---------------------------------------------------------------------------

class TestCSSValidation:
    def test_valid_css_passes(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 0

    def test_missing_css_file_fails(self, tmp_path, monkeypatch):
        _write_templates(tmp_path)
        # no CSS file written
        assert _run(monkeypatch, tmp_path) == 1

    def test_css_too_small_fails(self, tmp_path, monkeypatch):
        _write_css(tmp_path, content="body { }")  # < 1000 bytes
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 1

    def test_brace_mismatch_fails(self, tmp_path, monkeypatch):
        # Extra open brace — unbalanced
        bad_css = "body { margin: 0; }\n" * 50 + "div {\n"
        _write_css(tmp_path, content=bad_css)
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 1

    def test_balanced_braces_passes(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        result = _run(monkeypatch, tmp_path)
        assert result == 0


# ---------------------------------------------------------------------------
# Template integrity tests
# ---------------------------------------------------------------------------

class TestTemplateIntegrity:
    def test_missing_template_fails(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        # Remove one template
        first_tmpl = list(_TEMPLATE_CHECKS.keys())[0]
        (tmp_path / first_tmpl).unlink()
        assert _run(monkeypatch, tmp_path) == 1

    def test_missing_marker_in_template_fails(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        # Overwrite first template with content missing its required marker
        first_tmpl = list(_TEMPLATE_CHECKS.keys())[0]
        (tmp_path / first_tmpl).write_text("<!-- no markers here -->")
        assert _run(monkeypatch, tmp_path) == 1

    def test_all_templates_present_passes(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 0


# ---------------------------------------------------------------------------
# Hugo build tests
# ---------------------------------------------------------------------------

class TestHugoBuild:
    def test_hugo_failure_fails(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: SimpleNamespace(returncode=1, stderr="build error", stdout=""),
        )
        monkeypatch.setattr(sys, "argv", [
            "check_homepage_visual.py",
            "--project-root", str(tmp_path),
            "--log-prefix", str(tmp_path / "log"),
        ])
        assert main() == 1

    def test_hugo_exception_fails(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)

        def _raise(*a, **kw):
            raise FileNotFoundError("hugo not found")

        monkeypatch.setattr(subprocess, "run", _raise)
        monkeypatch.setattr(sys, "argv", [
            "check_homepage_visual.py",
            "--project-root", str(tmp_path),
            "--log-prefix", str(tmp_path / "log"),
        ])
        assert main() == 1


# ---------------------------------------------------------------------------
# Baseline regression guard tests
# ---------------------------------------------------------------------------

class TestBaselineRegression:
    def _write_baseline(self, tmp_path, css_lines):
        baseline_dir = tmp_path / "autoresearch"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        (baseline_dir / ".visual_baseline.json").write_text(
            json.dumps({"css_lines": css_lines, "css_size": 9999})
        )

    def test_regression_guard_fires_when_css_shrinks_drastically(self, tmp_path, monkeypatch):
        # Baseline: 2000 lines; current: 100 lines → drop of 1900 > 500 → FAIL
        big_css = "body { margin: 0; }\n" * 2000  # 2000 lines
        self._write_baseline(tmp_path, css_lines=2000)
        _write_css(tmp_path, content="body { margin: 0; }\n" * 100)
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 1

    def test_small_css_change_within_threshold_passes(self, tmp_path, monkeypatch):
        # Baseline: 200 lines; current: 100 lines → drop of 100 ≤ 500 → PASS
        self._write_baseline(tmp_path, css_lines=200)
        _write_css(tmp_path, content="body { margin: 0; }\n" * 100)
        _write_templates(tmp_path)
        assert _run(monkeypatch, tmp_path) == 0

    def test_no_baseline_creates_one(self, tmp_path, monkeypatch):
        _write_css(tmp_path)
        _write_templates(tmp_path)
        # No .visual_baseline.json exists yet
        baseline_path = tmp_path / "autoresearch" / ".visual_baseline.json"
        assert not baseline_path.exists()
        _run(monkeypatch, tmp_path)
        assert baseline_path.exists()
        data = json.loads(baseline_path.read_text())
        assert "css_lines" in data
        assert "css_size" in data
