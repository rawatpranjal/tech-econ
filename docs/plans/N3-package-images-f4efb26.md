---
chunk_id: "N3-package-images"
builder: "sonnet"
verifier: "opus"
status: "verified"
strike_count: 0
criteria_fingerprint: "sha256:e6bb8d4a852c9fb8e823dea544f003a6eab16b6ee5eb7ea6eea5563e82f26080"
branch: "feat/N3-package-images"
archived_commit: "f4efb26e193b8dd26c95d8ff5027e5c2e87ff09e"
---

# Chunk N.3 — Package images (GitHub org avatar)

## Goal
Write `scripts/fetch_package_images.py`, run it, and populate `image_url` for all
551 packages in `packages.json`. 471 have a GitHub URL (in `github_url` or `url`
field); for these, set `image_url` to `https://github.com/{owner}.png?size=128` (the
org/user avatar CDN URL — always resolves, no HTTP needed). The 80 non-GitHub packages
(mostly CRAN) get `image_url: ""`.

Packages.json currently has NO `image_url` field at all. This chunk adds the field AND
populates it.

Pattern already in codebase: `generate_homepage_rows.py:153` uses
`f"https://github.com/{owner}.png?size=128"` for the same purpose.

## Acceptance criteria

1. **Script exists**: `scripts/fetch_package_images.py` present and importable. Has two
   callable helpers: `parse_github_owner(url: str | None) -> str | None` (extracts the
   first path segment from a GitHub URL, e.g. `"https://github.com/DoubleML/foo"` →
   `"DoubleML"`; returns None if URL is not a GitHub URL or is None/empty) and
   `build_avatar_url(owner: str) -> str` (returns
   `f"https://github.com/{owner}.png?size=128"`).
2. **CLI flags**: `--dry-run` (print what would change, exit 0, no writes), `--limit N`
   (process N packages only), `--skip-existing` (skip entries where `image_url` is
   already non-empty).
3. **Precedence**: the script checks `github_url` field first, then `url` field.
   `parse_github_owner` is called on `github_url`; if None, called on `url`.
4. **image_url field added**: after running with no flags, all 551 `packages.json` entries
   have an `image_url` key. Entries without a resolvable GitHub owner get `""`.
5. **Coverage**: ≥ 450 of 551 entries have non-empty `image_url` (≥ 95% of the 471 with
   GitHub URLs — a few may have malformed URLs that parse to None).
6. **Format**: every non-empty `image_url` in `packages.json` matches
   `https://github.com/{owner}.png?size=128` and passes `check_image_url_format()`.
7. **No data loss**: `packages.json` entry count stays at 551; all other fields untouched.
8. **Atomic write**: packages.json written atomically (write to temp, then `os.replace`).
9. **Validator**: `python3 scripts/validate_data.py --skip-links` exits 0.
10. **Unit tests**: `tests/python/scripts/test_fetch_package_images.py` has ≥ 6 tests with
    mocked requests (if any) or pure-logic tests covering: `parse_github_owner` extracts
    owner correctly; returns None for non-GitHub URL; returns None for None input;
    `build_avatar_url` produces correct format; `--dry-run` makes no writes; coverage
    count is ≥ 450 after running against the real `packages.json`.
11. **Python suite**: `python3 -m pytest tests/python/ -q` in CI-mirror venv (python3.11 +
    requirements-dev.txt) exits 0, count ≥ 2047.
12. **JS suite**: `npm test` exits 0, 714/714.

## Tasks

1. Write `scripts/fetch_package_images.py` with `parse_github_owner`, `build_avatar_url`,
   and `main()` with argparse. Follow the same stub pattern as N.2 if `requests` is
   imported (this script may not need requests at all since avatar URLs need no HTTP).
2. Write `tests/python/scripts/test_fetch_package_images.py` with ≥ 6 tests. Follow the
   repo-standard stub pattern for any optional imports.
3. Run `python3 scripts/fetch_package_images.py --dry-run` — verify exits 0.
4. Run `python3 scripts/fetch_package_images.py` — populates 471 image_url fields, fast
   (no HTTP).
5. Verify coverage: count non-empty `image_url` in packages.json (criterion 5).
6. Run `python3 scripts/validate_data.py --skip-links`, pytest, npm test.
7. Commit everything: script, tests, updated packages.json.
8. Set `status: pending_verification`.

## Verdict

**VERIFIED 2026-06-14** — Opus adversarial check, first pass. All 12 criteria pass.

Coverage: 471/551 packages have non-empty image_url (all https://github.com/{owner}.png?size=128).
80 CRAN/non-GitHub entries get "". 24 tests. Python 2071/2071, JS 714/714.

Builder correctly applied the N.2 lesson: requests stub at line 17 of test file before module load.

Advisory (pre-existing, not N.3's fault): test_validate_data.py relies on alphabetical collection
order for the requests MagicMock stub — a pytest-randomly or isolated run would break it. Fix:
add `requests` to requirements-dev.txt.
