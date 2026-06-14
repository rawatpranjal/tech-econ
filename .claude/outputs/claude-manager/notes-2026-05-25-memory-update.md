# Memory Update — 2026-05-25

## What was updated
`/Users/pranjal/.claude/projects/-Users-pranjal-Code-tech-econ/memory/MEMORY.md`

## Changes made
Added a new bullet entry capturing three learned bug-fix patterns from the bullshit/integration test session, plus updated test counts.

## Bug patterns added to memory
1. `re.MULTILINE` omission — `^` matches only string start without it; multi-chapter splits silently failed in `split_book.py`
2. `str.rstrip(suffix)` character-set stripping — does NOT strip literal suffix strings; use `str.removesuffix()` instead; broke repo name parsing in `update_stars.py`
3. `re.split()` discards pre-match content — preamble before first heading was silently dropped in `split_book.py`; always capture it separately

## Test counts (current as of this session)
- JS: 487 tests (`tests/js/`)
- Python: 1048 tests (`tests/python/`)

## No entries removed
Existing entries (Homepage Visual Critique, Re1 MMR Wiring) remain unchanged and are still current.
