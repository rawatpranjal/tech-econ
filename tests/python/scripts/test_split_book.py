"""Bullshit tests for split_book.py pure functions.

Covers: slugify, pick_split_level, detect_chapter_boundaries, split_chapters
All pure text processing — no filesystem.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "split_book", _REPO_ROOT / "scripts" / "split_book.py"
)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
sys.modules["split_book"] = mod
_spec.loader.exec_module(mod)

slugify = mod.slugify
pick_split_level = mod.pick_split_level
detect_chapter_boundaries = mod.detect_chapter_boundaries
split_chapters = mod.split_chapters


# ──────────────────────────────────────────────
# slugify
# ──────────────────────────────────────────────

class TestSlugify:
    def test_basic_title(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_become_hyphens(self):
        result = slugify("Causal Inference & ML")
        assert "causal" in result
        assert "inference" in result
        assert " " not in result

    def test_max_len_truncated(self):
        long = "A " * 50  # 100 chars
        result = slugify(long, max_len=20)
        assert len(result) <= 20

    def test_empty_string_returns_untitled(self):
        assert slugify("") == "untitled"

    def test_no_trailing_hyphen(self):
        result = slugify("A " * 10, max_len=10)
        assert not result.endswith("-")

    def test_lowercases(self):
        assert slugify("UPPER CASE") == "upper-case"

    def test_digits_preserved(self):
        assert slugify("Chapter 1") == "chapter-1"


# ──────────────────────────────────────────────
# pick_split_level
# ──────────────────────────────────────────────

class TestPickSplitLevel:
    def test_5_h1_headers_picks_level_1(self):
        text = "# Section\n\n" * 5
        assert pick_split_level(text) == 1

    def test_fewer_than_5_h1_but_5_h2_picks_level_2(self):
        text = "# Only One\n\n" + "## Sub\n\n" * 5
        assert pick_split_level(text) == 2

    def test_no_headers_falls_back_to_1(self):
        assert pick_split_level("Just plain text, no headers.") == 1

    def test_h1_beats_h2_when_both_sufficient(self):
        text = "# H1\n\n" * 6 + "## H2\n\n" * 6
        # H1 detected first and is >= 5 → return 1
        assert pick_split_level(text) == 1

    def test_exactly_5_h1_is_sufficient(self):
        text = "# A\n\n# B\n\n# C\n\n# D\n\n# E\n\n"
        assert pick_split_level(text) == 1

    def test_4_h1_insufficient_falls_to_h2_check(self):
        text = "# A\n\n# B\n\n# C\n\n# D\n\n## Sub\n\n" * 2
        # 4 H1 < 5, but 2*1=2 H2 < 5 → fallback 1
        assert pick_split_level(text) == 1


# ──────────────────────────────────────────────
# detect_chapter_boundaries
# ──────────────────────────────────────────────

class TestDetectChapterBoundaries:
    def _make_book(self, n_chapters=3, front_matter=""):
        parts = [front_matter] if front_matter.strip() else []
        for i in range(1, n_chapters + 1):
            parts.append(f"# Chapter {i}. The Title\n\nContent of chapter {i}.\n")
        return "\n".join(parts)

    def test_3_chapters_detected(self):
        text = self._make_book(3)
        result = detect_chapter_boundaries(text)
        assert len(result) >= 3

    def test_chapter_titles_extracted(self):
        text = self._make_book(3)
        result = detect_chapter_boundaries(text)
        titles = [t for t, _ in result]
        assert any("Chapter 1" in t for t in titles)

    def test_fewer_than_3_chapters_returns_empty(self):
        text = self._make_book(2)
        assert detect_chapter_boundaries(text) == []

    def test_front_matter_captured(self):
        text = self._make_book(3, front_matter="# Preface\n\nIntroduction text.\n")
        result = detect_chapter_boundaries(text)
        titles = [t for t, _ in result]
        assert any("Front" in t or "Matter" in t for t in titles)

    def test_chapter_2_and_3_detected_not_just_chapter_1(self):
        # Regression: without re.MULTILINE, ^ only matches start-of-string.
        # Chapters 2+ were silently skipped because their headings appear
        # after a newline, not at the very start of the combined string.
        text = self._make_book(3)
        result = detect_chapter_boundaries(text)
        titles = [t for t, _ in result]
        assert any("Chapter 2" in t for t in titles), "Chapter 2 was not detected"
        assert any("Chapter 3" in t for t in titles), "Chapter 3 was not detected"

    def test_multiline_chapter_headings_all_found(self):
        # Each chapter starts mid-string (after newlines), not at position 0.
        # The CHAPTER_PATTERN must use re.MULTILINE so ^ matches line-starts.
        text = "Intro\n\n# Chapter 1\nBody 1.\n\n# Chapter 2\nBody 2.\n\n# Chapter 3\nBody 3.\n"
        result = detect_chapter_boundaries(text)
        assert len(result) >= 3

    def test_no_chapter_markers_returns_empty(self):
        text = "# Regular Header\n\n## Sub Section\n\n# Another Header\n\n"
        assert detect_chapter_boundaries(text) == []


# ──────────────────────────────────────────────
# split_chapters
# ──────────────────────────────────────────────

class TestSplitChapters:
    def test_h1_split(self):
        text = "# Introduction\n\nIntro text.\n\n# Methods\n\nMethods text.\n"
        result = split_chapters(text, level=1)
        assert len(result) == 2
        titles = [t for t, _ in result]
        assert "Introduction" in titles
        assert "Methods" in titles

    def test_h2_split(self):
        text = "## Background\n\nBg.\n\n## Results\n\nRes.\n"
        result = split_chapters(text, level=2)
        assert len(result) == 2

    def test_body_contains_heading(self):
        text = "# Section One\n\nContent here.\n# Section Two\n\nMore.\n"
        result = split_chapters(text, level=1)
        # Body should start with the heading line
        assert result[0][1].startswith("# Section One")

    def test_content_before_first_heading_becomes_front_matter(self):
        text = "Preamble text\n\n# First Section\n\nContent.\n"
        result = split_chapters(text, level=1)
        assert len(result) == 2
        titles = [t for t, _ in result]
        assert "Front Matter" in titles

    def test_empty_text_returns_empty(self):
        assert split_chapters("", level=1) == []

    def test_no_headings_at_level_returns_single_front_matter(self):
        text = "Just some content\nwith no headings.\n"
        result = split_chapters(text, level=1)
        assert len(result) == 1
        assert result[0][0] == "Front Matter"

    def test_sub_heading_not_split(self):
        # H3 should NOT split when level=1
        text = "# Top\n\n### Sub\n\nSub content.\n# Another\n\nMore.\n"
        result = split_chapters(text, level=1)
        assert len(result) == 2
