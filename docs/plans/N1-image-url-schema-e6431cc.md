---
chunk_id: "N1-image-url-schema"
builder: "sonnet"
verifier: "opus"
status: "verified"
strike_count: 0
criteria_fingerprint: "sha256:023a52b07df8cb50b93d22f52f74810a4c80e087dbd1c65a2aa8e2806141dac1"
branch: "feat/N1-image-url-schema"
archived_commit: "e6431cc2019b7758bf46bfdfcac0415139c7b0c0"
---

# Chunk N.1 — Schema-add image_url to books and career

## Goal
Add `image_url` field to every entry in `data/books.json` (102 entries) and
`data/career.json` (639 entries). Update the validator. Write tests.

This is the schema step: all entries get `image_url: ""` as a baseline. Later N.2–N.4
chunks will backfill real URLs. We do NOT add `image_url` to REQUIRED_FIELDS yet (it's
still being backfilled across content types site-wide).

## Acceptance criteria

1. **books.json coverage**: `len([b for b in books if 'image_url' in b]) == len(books)` — every
   one of the 102 book entries has an `image_url` key. Entries without a natural image get `""`.
2. **career.json coverage**: `len([c for c in career if 'image_url' in c]) == len(career)` — every
   one of the 639 career entries has an `image_url` key. Entries without a natural image get `""`.
3. **No data loss**: entry count is unchanged. books.json still has 102 entries; career.json still
   has 639 entries. All other fields on every entry are untouched.
4. **Validator passes**: `python3 scripts/validate_data.py --skip-links` exits 0 with no errors
   on books.json or career.json.
5. **Format check added**: `validate_data.py` gains a function `check_image_url_format(files)`
   that validates: when `image_url` is present and non-empty, it must be either a relative path
   starting with `/` or an absolute URL starting with `http`. Returns a list of errors.
6. **Tests added**: `tests/python/scripts/test_validate_data.py` gains ≥5 new test cases covering:
   - books.json entries WITH `image_url` pass the format check
   - career.json entries WITH `image_url` pass the format check
   - an entry with a malformed `image_url` (e.g. `"not-a-url"`) fails the format check
   - an entry with `image_url: ""` (empty string) passes (empty is allowed)
   - an entry with `image_url: "https://example.com/img.png"` passes
7. **JS suite unchanged**: `npm test` stays at 714/714 green.
8. **Python suite stable or grows**: `python3 -m pytest tests/python/ -q` exits 0, count ≥ 1950.

## Tasks

1. Write a one-off migration script (or inline Python) to add `"image_url": ""` to every entry
   in `data/books.json` and `data/career.json`. Use atomic write via `lib/data_io.py` if possible;
   otherwise write-then-rename.
2. Add `check_image_url_format(files)` to `scripts/validate_data.py`. Wire it into `main()` so
   it runs alongside `validate_required_fields`.
3. Add ≥5 test cases to `tests/python/scripts/test_validate_data.py` covering criterion 6 above.
4. Run `python3 scripts/validate_data.py --skip-links` to confirm criterion 4.
5. Run `python3 -m pytest tests/python/ -q` and `npm test` to confirm criteria 7–8.
6. Set `status: pending_verification` in this file when done.

## Verdict

**VERIFIED 2026-06-14** — Opus fresh-agent adversarial check. All 8 criteria pass.

Per-criterion: books 102/102 ✅, career 639/639 ✅, no data loss ✅, validator exits 0 ✅,
format check added + wired ✅, 11 new tests ✅, JS 714/714 ✅, Python 2029 passed ✅.

Community.json out-of-scope fix (eurocim-icon.gif → "") was REQUIRED — new format check
would have tripped CI without it. Correct call.

Advisory (no fix required for sign-off): non-string image_url raises AttributeError instead of
clean error. Cannot be triggered by current data. Candidate for hardening in N.2.
