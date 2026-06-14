"""Bullshit tests for check_secrets.py pure helpers.

Covers: parse_keys (extracts UPPER_SNAKE_CASE, skips comments/blanks,
        handles export prefix, returns empty for nonexistent file),
        diff_keys (missing/extra keys logic).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "check_secrets.py"

_spec = importlib.util.spec_from_file_location("check_secrets", _SCRIPT_PATH)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_secrets"] = mod
_spec.loader.exec_module(mod)

parse_keys = mod.parse_keys
diff_keys = mod.diff_keys


class TestParseKeys:
    def test_extracts_simple_key(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("MY_KEY=value\n")
        assert parse_keys(f) == {"MY_KEY"}

    def test_skips_comment_lines(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("# this is a comment\nREAL_KEY=value\n")
        assert parse_keys(f) == {"REAL_KEY"}

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("\n\nKEY_ONE=a\n\nKEY_TWO=b\n\n")
        assert parse_keys(f) == {"KEY_ONE", "KEY_TWO"}

    def test_handles_export_prefix(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("export EXPORTED_KEY=value\n")
        assert parse_keys(f) == {"EXPORTED_KEY"}

    def test_handles_leading_whitespace(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("  INDENTED_KEY=value\n")
        assert parse_keys(f) == {"INDENTED_KEY"}

    def test_nonexistent_file_returns_empty(self, tmp_path):
        assert parse_keys(tmp_path / "nonexistent.txt") == set()

    def test_multiple_keys(self, tmp_path):
        f = tmp_path / "env.txt"
        f.write_text("KEY_A=1\nKEY_B=2\nKEY_C=3\n")
        assert parse_keys(f) == {"KEY_A", "KEY_B", "KEY_C"}

    def test_ignores_lowercase_assignments(self, tmp_path):
        # Lowercase variable names don't match the UPPER_SNAKE_CASE pattern
        f = tmp_path / "env.txt"
        f.write_text("lowercase_key=value\nUPPER_KEY=value\n")
        result = parse_keys(f)
        assert "UPPER_KEY" in result
        assert "lowercase_key" not in result


class TestDiffKeys:
    def test_missing_in_env(self):
        result = diff_keys({"A", "B"}, {"B"})
        assert result["missing_in_env"] == ["A"]

    def test_extra_in_env(self):
        result = diff_keys({"A"}, {"A", "EXTRA"})
        assert result["extra_in_env"] == ["EXTRA"]

    def test_identical_sets_no_diff(self):
        result = diff_keys({"A", "B"}, {"A", "B"})
        assert result["missing_in_env"] == []
        assert result["extra_in_env"] == []

    def test_completely_disjoint(self):
        result = diff_keys({"TMPL_KEY"}, {"ENV_KEY"})
        assert "TMPL_KEY" in result["missing_in_env"]
        assert "ENV_KEY" in result["extra_in_env"]

    def test_missing_sorted_alphabetically(self):
        result = diff_keys({"Z", "A", "M"}, set())
        assert result["missing_in_env"] == ["A", "M", "Z"]

    def test_empty_template_no_missing(self):
        result = diff_keys(set(), {"ENV_KEY"})
        assert result["missing_in_env"] == []
        assert result["extra_in_env"] == ["ENV_KEY"]
