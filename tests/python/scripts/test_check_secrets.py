"""Tests for scripts/check_secrets.py.

Pure-function coverage for parse_keys + diff_keys, plus end-to-end
main() runs against synthetic template/env files in tmp_path. We
never read or write the real .claude/secrets.env in tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "check_secrets.py"
_spec = importlib.util.spec_from_file_location("check_secrets", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_secrets"] = mod
_spec.loader.exec_module(mod)


# --------------------------------------------------------------------------- #
# parse_keys
# --------------------------------------------------------------------------- #


class TestParseKeys:
    def test_returns_empty_for_missing_file(self, tmp_path):
        assert mod.parse_keys(tmp_path / "nope.env") == set()

    def test_extracts_simple_keys(self, tmp_path):
        p = tmp_path / "x.env"
        p.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert mod.parse_keys(p) == {"FOO", "BAZ"}

    def test_skips_comments_and_blanks(self, tmp_path):
        p = tmp_path / "x.env"
        p.write_text(
            "# comment\n"
            "\n"
            "FOO=bar\n"
            "  # indented comment\n"
            "BAZ=qux\n",
            encoding="utf-8",
        )
        assert mod.parse_keys(p) == {"FOO", "BAZ"}

    def test_handles_export_prefix(self, tmp_path):
        p = tmp_path / "x.env"
        p.write_text("export FOO=bar\nBAZ=qux\n", encoding="utf-8")
        assert mod.parse_keys(p) == {"FOO", "BAZ"}

    def test_ignores_lowercase_or_invalid_keys(self, tmp_path):
        p = tmp_path / "x.env"
        p.write_text(
            "VALID=1\n"
            "lowercase=2\n"
            "1STARTS_WITH_DIGIT=3\n"
            "ALSO_VALID=4\n",
            encoding="utf-8",
        )
        # We only accept UPPER_SNAKE_CASE starting with a letter.
        assert mod.parse_keys(p) == {"VALID", "ALSO_VALID"}

    def test_does_not_capture_values(self, tmp_path):
        # parse_keys must never expose values — security-sensitive files.
        # We assert by checking the return type only contains key names.
        p = tmp_path / "x.env"
        p.write_text("ADMIN_KEY=super-secret-value\n", encoding="utf-8")
        keys = mod.parse_keys(p)
        assert keys == {"ADMIN_KEY"}
        # And the secret value never appears in the set
        assert all("super-secret" not in k for k in keys)


# --------------------------------------------------------------------------- #
# diff_keys
# --------------------------------------------------------------------------- #


class TestDiffKeys:
    def test_missing_in_env(self):
        out = mod.diff_keys({"A", "B", "C"}, {"A"})
        assert out["missing_in_env"] == ["B", "C"]
        assert out["extra_in_env"] == []

    def test_extra_in_env(self):
        out = mod.diff_keys({"A"}, {"A", "B"})
        assert out["missing_in_env"] == []
        assert out["extra_in_env"] == ["B"]

    def test_both_directions(self):
        out = mod.diff_keys({"A", "B"}, {"A", "C"})
        assert out["missing_in_env"] == ["B"]
        assert out["extra_in_env"] == ["C"]

    def test_perfect_match(self):
        out = mod.diff_keys({"A", "B"}, {"A", "B"})
        assert out == {"missing_in_env": [], "extra_in_env": []}

    def test_results_are_sorted(self):
        out = mod.diff_keys({"Z", "A", "M"}, {"A"})
        assert out["missing_in_env"] == ["M", "Z"]


# --------------------------------------------------------------------------- #
# main(): end-to-end
# --------------------------------------------------------------------------- #


def _write(p: Path, content: str) -> None:
    p.write_text(content, encoding="utf-8")


class TestMain:
    def test_template_missing_returns_2(self, tmp_path, capsys):
        rc = mod.main([
            "--template", str(tmp_path / "no.template"),
            "--env", str(tmp_path / "env"),
        ])
        assert rc == 2
        assert "template not found" in capsys.readouterr().out

    def test_env_missing_returns_1_with_helpful_message(self, tmp_path, capsys):
        template = tmp_path / "template"
        _write(template, "FOO=xxx\n")
        rc = mod.main([
            "--template", str(template),
            "--env", str(tmp_path / "no.env"),
        ])
        assert rc == 1
        out = capsys.readouterr().out
        assert "does not exist" in out
        assert "Copy from" in out

    def test_missing_keys_lists_them_and_exits_1(self, tmp_path, capsys):
        template = tmp_path / "template"
        env = tmp_path / "env"
        _write(template, "FOO=xxx\nBAR=xxx\nBAZ=xxx\n")
        _write(env, "FOO=real-value\n")
        rc = mod.main(["--template", str(template), "--env", str(env)])
        assert rc == 1
        out = capsys.readouterr().out
        assert "2 key(s) declared in template but missing" in out
        assert "BAR" in out
        assert "BAZ" in out
        # Must NOT echo any value, even from env
        assert "real-value" not in out

    def test_perfect_match_returns_0(self, tmp_path, capsys):
        template = tmp_path / "template"
        env = tmp_path / "env"
        _write(template, "FOO=xxx\nBAR=xxx\n")
        _write(env, "FOO=v1\nBAR=v2\n")
        rc = mod.main(["--template", str(template), "--env", str(env)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "OK" in out
        assert "2 key(s) match" in out

    def test_extra_keys_are_informational_only(self, tmp_path, capsys):
        template = tmp_path / "template"
        env = tmp_path / "env"
        _write(template, "FOO=xxx\n")
        _write(env, "FOO=v1\nEXTRA_LOCAL=v2\n")
        rc = mod.main(["--template", str(template), "--env", str(env)])
        assert rc == 0  # extras don't fail the check
        out = capsys.readouterr().out
        assert "informational" in out
        assert "EXTRA_LOCAL" in out

    def test_quiet_suppresses_stdout(self, tmp_path, capsys):
        template = tmp_path / "template"
        env = tmp_path / "env"
        _write(template, "FOO=xxx\nMISSING=xxx\n")
        _write(env, "FOO=v1\n")
        rc = mod.main([
            "--template", str(template),
            "--env", str(env),
            "--quiet",
        ])
        assert rc == 1
        assert capsys.readouterr().out == ""
