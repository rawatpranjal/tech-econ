---
chunk_id: "N4-career-community-images"
builder: "sonnet"
verifier: "opus"
status: "verified"
strike_count: 0
criteria_fingerprint: "sha256:f08c01089622fad2fe5db6ce779295ac8d52fb77f7beaaf54a983ae8deaa054c"
branch: "feat/N4-career-community-images"
archived_commit: "3664fb620fa62ef4e5de93ea0abbd373270fb1ae"
---

# Chunk N.4 — Career + Community image backfill (Google favicon CDN)

## Goal
Fill `image_url` for career.json (639 items, all `""`) and community.json (452 items,
307 already have images, 131 missing key, 14 have `""`).

Strategy: Google favicon CDN URL — `https://www.google.com/s2/favicons?domain={domain}&sz=128`.
No HTTP requests needed in the script (pure URL derivation from the entry's `url` field).
Reliable (Google always returns an icon; uses brand favicon), fast, no local storage needed.

This is the same pattern as N.3 (derive CDN URL from entry field, no download).

Community.json also needs the `image_url` key added to 131 entries that lack it.

## Acceptance criteria

1. **Script exists**: `scripts/fetch_career_community_images.py` present and importable.
   Has two helpers: `extract_domain(url: str | None) -> str | None` (returns the
   netloc from a URL, e.g. `"https://instacart.careers/"` → `"instacart.careers"`;
   strips leading `www.`; returns None for None/empty/unparseable input) and
   `build_favicon_url(domain: str) -> str` (returns
   `f"https://www.google.com/s2/favicons?domain={domain}&sz=128"`).
2. **CLI flags**: `--dry-run` (no writes, exit 0), `--limit N`, `--skip-existing`.
3. **community.json schema fix**: all 452 `community.json` entries have an `image_url`
   key after the run (131 were missing it; 307 already had non-empty values which must
   be left untouched by `--skip-existing` logic).
4. **career.json coverage**: ≥ 580 of 639 career.json entries have non-empty `image_url`
   after the run (entries whose `url` field yields a parseable domain; entries with
   None/empty/malformed URL stay `""`).
5. **community.json coverage**: ≥ 400 of 452 community.json entries have non-empty
   `image_url` after the run (307 pre-existing + ≥ 93 of the 145 newly filled).
6. **Format**: every new non-empty `image_url` added by this script starts with
   `https://www.google.com/s2/favicons?domain=` and passes `check_image_url_format()`.
   Pre-existing community.json values (which start with `/images/` or `https://`) must
   be left untouched.
7. **No data loss**: career.json stays at 639 entries; community.json stays at 452. All
   non-`image_url` fields untouched.
8. **Atomic write**: both files written with `os.replace`.
9. **Validator**: `python3 scripts/validate_data.py --skip-links` exits 0.
10. **Unit tests**: `tests/python/scripts/test_fetch_career_community_images.py` ≥ 7
    tests covering: `extract_domain` parses correctly; strips `www.`; returns None for
    None/empty/bad input; `build_favicon_url` correct format; `--dry-run` no writes;
    coverage ≥ 580 on real career.json; pre-existing community.json images are preserved.
11. **Python suite**: CI-mirror venv (python3.11 + requirements-dev.txt) exits 0, ≥ 2071.
12. **JS suite**: `npm test` 714/714.

## Tasks

1. Write `scripts/fetch_career_community_images.py` with `extract_domain`,
   `build_favicon_url`, and `main()` with argparse. Use `--skip-existing` to preserve
   the 307 community.json entries that already have non-empty `image_url`.
2. Write `tests/python/scripts/test_fetch_career_community_images.py` ≥ 7 tests.
   Follow the repo pattern: `sys.modules.setdefault("requests", MagicMock())` if needed.
3. Run `python3 scripts/fetch_career_community_images.py --dry-run` → exits 0.
4. Run `python3 scripts/fetch_career_community_images.py` → fast (no HTTP in script).
5. Verify coverage: count non-empty image_url in both files.
6. Run `validate_data.py --skip-links`, pytest, npm test.
7. Commit everything.

## Verdict

**VERIFIED 2026-06-14** — Opus adversarial check, first pass. All 12 criteria pass.

Coverage: career 639/639, community 452/452. All NEW values are favicon CDN URLs.
307 pre-existing community images bit-for-bit preserved. 55 tests. Python 2126, JS 714/714.

Advisory: re-running without `--skip-existing` overwrites the 307 curated community images.
Always use `--skip-existing` for future runs.
