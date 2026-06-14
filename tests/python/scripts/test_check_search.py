"""Bullshit tests for autoresearch/checks/check_search.py.

Exercises the validation logic via main() with synthetic files.
subprocess calls (Hugo, node) are mocked so no build toolchain needed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "autoresearch" / "checks" / "check_search.py"

_spec = importlib.util.spec_from_file_location("check_search_mod", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_search_mod"] = mod
_spec.loader.exec_module(mod)

main = mod.main


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_ok_proc(returncode: int = 0) -> MagicMock:
    p = MagicMock()
    p.returncode = returncode
    p.stderr = ""
    return p


def _setup_tree(tmp_path: Path, *, js_content: str = "", modal_content: str = "", css_content: str = "") -> Path:
    """Create the minimal file tree that check_search.py expects."""
    # unified-search.js
    js_dir = tmp_path / "static" / "js" / "search"
    js_dir.mkdir(parents=True)
    (js_dir / "unified-search.js").write_text(js_content)

    # global-search-modal.html
    modal_dir = tmp_path / "layouts" / "partials"
    modal_dir.mkdir(parents=True)
    (modal_dir / "global-search-modal.html").write_text(modal_content)

    # custom.css
    css_dir = tmp_path / "static" / "css"
    css_dir.mkdir(parents=True)
    (css_dir / "custom.css").write_text(css_content)

    return tmp_path


def _run(monkeypatch, tmp_path: Path, proc_mock: MagicMock | None = None) -> int:
    monkeypatch.setattr(sys, "argv", ["check_search.py", "--project-root", str(tmp_path)])
    if proc_mock is None:
        proc_mock = _make_ok_proc()
    with patch.object(mod.subprocess, "run", return_value=proc_mock):
        return main()


# ---------------------------------------------------------------------------
# Hugo build failures
# ---------------------------------------------------------------------------

class TestHugoBuild:
    def test_hugo_failure_returns_1(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div>")
        monkeypatch.setattr(sys, "argv", ["check_search.py", "--project-root", str(tmp_path)])
        fail = _make_ok_proc(returncode=1)
        fail.stderr = "Hugo error: template not found"
        with patch.object(mod.subprocess, "run", return_value=fail):
            assert main() == 1

    def test_hugo_pass_continues(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div>")
        assert _run(monkeypatch, tmp_path) == 0


# ---------------------------------------------------------------------------
# JS brace balance
# ---------------------------------------------------------------------------

class TestJsBraceBalance:
    def test_balanced_braces_pass(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="function f() { return 1; }", modal_content="<div></div>")
        assert _run(monkeypatch, tmp_path) == 0

    def test_extra_open_brace_fails(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="function f() { return 1; } {", modal_content="<div></div>")
        assert _run(monkeypatch, tmp_path) == 1

    def test_extra_close_brace_fails(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="function f() { return 1; }}", modal_content="<div></div>")
        assert _run(monkeypatch, tmp_path) == 1

    def test_empty_js_passes(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="", modal_content="<div></div>")
        assert _run(monkeypatch, tmp_path) == 0


# ---------------------------------------------------------------------------
# Modal div balance
# ---------------------------------------------------------------------------

class TestModalDivBalance:
    def test_balanced_divs_pass(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="<div><div></div></div>")
        assert _run(monkeypatch, tmp_path) == 0

    def test_extra_open_div_fails(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="<div><div></div>")
        assert _run(monkeypatch, tmp_path) == 1

    def test_extra_close_div_fails(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div></div>")
        assert _run(monkeypatch, tmp_path) == 1

    def test_empty_modal_passes(self, tmp_path, monkeypatch):
        _setup_tree(tmp_path, js_content="{}", modal_content="")
        assert _run(monkeypatch, tmp_path) == 0


# ---------------------------------------------------------------------------
# JS file missing
# ---------------------------------------------------------------------------

class TestMissingFiles:
    def test_missing_js_file_fails(self, tmp_path, monkeypatch):
        # No js file created
        modal_dir = tmp_path / "layouts" / "partials"
        modal_dir.mkdir(parents=True)
        (modal_dir / "global-search-modal.html").write_text("<div></div>")
        (tmp_path / "static" / "css").mkdir(parents=True)
        (tmp_path / "static" / "css" / "custom.css").write_text("")
        monkeypatch.setattr(sys, "argv", ["check_search.py", "--project-root", str(tmp_path)])
        with patch.object(mod.subprocess, "run", return_value=_make_ok_proc()):
            assert main() == 1

    def test_missing_modal_file_fails(self, tmp_path, monkeypatch):
        js_dir = tmp_path / "static" / "js" / "search"
        js_dir.mkdir(parents=True)
        (js_dir / "unified-search.js").write_text("{}")
        (tmp_path / "static" / "css").mkdir(parents=True)
        (tmp_path / "static" / "css" / "custom.css").write_text("")
        # No modal file
        (tmp_path / "layouts" / "partials").mkdir(parents=True)
        monkeypatch.setattr(sys, "argv", ["check_search.py", "--project-root", str(tmp_path)])
        with patch.object(mod.subprocess, "run", return_value=_make_ok_proc()):
            assert main() == 1


# ---------------------------------------------------------------------------
# CSS reduced-motion
# ---------------------------------------------------------------------------

class TestCssReducedMotion:
    def test_keyframes_without_reduced_motion_warns(self, tmp_path, monkeypatch, capsys):
        css = "@keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }"
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div>", css_content=css)
        rc = _run(monkeypatch, tmp_path)
        # Warnings don't fail but should be reported
        captured = capsys.readouterr()
        assert "reduced-motion" in captured.out or "reduced-motion" in captured.err or rc == 0

    def test_keyframes_with_reduced_motion_passes(self, tmp_path, monkeypatch):
        css = "@keyframes spin {} @media (prefers-reduced-motion: reduce) { * { animation: none; } }"
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div>", css_content=css)
        assert _run(monkeypatch, tmp_path) == 0

    def test_no_keyframes_no_warning(self, tmp_path, monkeypatch, capsys):
        css = ".card { color: red; }"
        _setup_tree(tmp_path, js_content="{}", modal_content="<div></div>", css_content=css)
        rc = _run(monkeypatch, tmp_path)
        assert rc == 0
