#!/usr/bin/env python3
"""Split a docling-produced book markdown into per-chapter files.

Usage:
    python3 scripts/split_book.py books/deep-learning-recsys/

Reads the largest .md in the directory, splits on top-level H1 headings
(falls back to H2 if H1 is too sparse), writes chapters/NN-slug.md and a
README.md with the table of contents.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SLUG_RE = re.compile(r"[^a-z0-9]+")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)


def slugify(title: str, max_len: int = 60) -> str:
    s = SLUG_RE.sub("-", title.lower()).strip("-")
    return s[:max_len].rstrip("-") or "untitled"


def find_source_md(book_dir: Path) -> Path:
    candidates = sorted(
        (p for p in book_dir.glob("*.md") if p.name.lower() not in {"readme.md", "crosswalk.md"}),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidates:
        sys.exit(f"No source markdown found in {book_dir}")
    return candidates[0]


CHAPTER_PATTERN = re.compile(r"^#{1,3}\s+Chapter\s+\d+", re.IGNORECASE)


def pick_split_level(text: str) -> int:
    """Choose H1 if it appears at least 5 times; else H2."""
    h1 = len(re.findall(r"^# [^#]", text, re.MULTILINE))
    if h1 >= 5:
        return 1
    h2 = len(re.findall(r"^## [^#]", text, re.MULTILINE))
    if h2 >= 5:
        return 2
    return 1  # last resort


def detect_chapter_boundaries(text: str) -> list[tuple[str, str]]:
    """If the doc explicitly names 'Chapter N. ...' headings, split there.

    Returns [(title, body), ...] or [] if no chapter markers found.
    """
    matches = list(CHAPTER_PATTERN.finditer(text))
    if len(matches) < 3:
        return []

    chapters: list[tuple[str, str]] = []
    front = text[: matches[0].start()].strip()
    if front:
        chapters.append(("00 Front Matter", front + "\n"))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end]
        first_line = body.split("\n", 1)[0]
        title = re.sub(r"^#+\s+", "", first_line).strip()
        chapters.append((title, body))

    return chapters


def split_chapters(text: str, level: int) -> list[tuple[str, str]]:
    """Return list of (title, body) pairs."""
    prefix = "#" * level + " "
    lines = text.splitlines(keepends=True)
    chapters: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith(prefix) and not line.startswith(prefix + "#"):
            if current_title is not None:
                chapters.append((current_title, current_lines))
            current_title = line[len(prefix):].strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_title is not None:
        chapters.append((current_title, current_lines))
    elif current_lines:
        chapters.append(("Front Matter", current_lines))

    return [(t, "".join(ls)) for t, ls in chapters]


def write_chapters(book_dir: Path, chapters: list[tuple[str, str]]) -> list[Path]:
    out_dir = book_dir / "chapters"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()

    paths: list[Path] = []
    width = max(2, len(str(len(chapters))))
    for i, (title, body) in enumerate(chapters, start=1):
        slug = slugify(title)
        filename = f"{str(i).zfill(width)}-{slug}.md"
        path = out_dir / filename
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    return paths


def write_toc(book_dir: Path, source_md: Path, chapters: list[tuple[str, str]], paths: list[Path]) -> None:
    total_words = sum(len(b.split()) for _, b in chapters)
    lines = [
        f"# {book_dir.name}",
        "",
        f"Source: `{source_md.name}` ({source_md.stat().st_size // 1024} KB)",
        f"Chapters: {len(chapters)} | Total words: {total_words:,}",
        "",
        "## Table of Contents",
        "",
    ]
    for (title, body), path in zip(chapters, paths):
        words = len(body.split())
        rel = path.relative_to(book_dir)
        lines.append(f"- [{title}]({rel}) — {words:,} words")
    lines.append("")
    (book_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book_dir", type=Path, help="Directory containing the docling .md output")
    parser.add_argument("--level", type=int, choices=(1, 2, 3), help="Heading level to split on")
    args = parser.parse_args()

    book_dir: Path = args.book_dir.resolve()
    if not book_dir.is_dir():
        sys.exit(f"Not a directory: {book_dir}")

    source_md = find_source_md(book_dir)
    text = source_md.read_text(encoding="utf-8")

    chapters = detect_chapter_boundaries(text)
    used_strategy = "Chapter-N pattern"

    if not chapters:
        level = args.level or pick_split_level(text)
        chapters = split_chapters(text, level)
        if len(chapters) <= 2 and level == 1:
            chapters = split_chapters(text, 2)
            level = 2
        used_strategy = f"H{level} headings"

    paths = write_chapters(book_dir, chapters)
    write_toc(book_dir, source_md, chapters, paths)

    print(f"Strategy: {used_strategy}")
    print(f"Chapters: {len(paths)}")
    print(f"Output: {book_dir / 'chapters'}")
    print(f"TOC: {book_dir / 'README.md'}")


if __name__ == "__main__":
    main()
