# CI Failure Debug Report

**Date:** 2026-01-05
**Agent:** Tester

## Summary

Investigated CI failures causing email spam. Found and fixed 2 issues.

## Issues Found

### 1. Validate Data Failures (ALREADY FIXED)

- **Cause:** 113 duplicate URLs failing validation
- **Fix:** Commit d83b7e9 - updated validator to use URL+category composite key
- **Status:** Passing since Jan 6, 04:17:49

### 2. Generate Weekly Highlight Failure (FIXED NOW)

- **Cause:** `KeyError: 'title'` - resources use `name` field, not `title`
- **File:** `scripts/generate-highlight.py`
- **Lines fixed:** 89, 108
- **Fix:** Commit ffbef0d - changed `r['title']` to `r.get('name', '')`
- **Status:** Fixed, pushed to main

### 3. Deploy Cancellations (NO ACTION)

- **Cause:** Concurrent runs cancel each other (normal behavior)
- **Status:** Not sending failure emails

## Verification

```
$ gh run list --limit 5
completed  success  Fix 24 duplicate URL validation errors  Validate Data  main  push
```

Validate Data now passing. Weekly Highlight will be tested next Sunday (scheduled).

## Files Modified

- `scripts/generate-highlight.py` (2 lines changed)

## Recommendations

1. **Rotate API keys** - User exposed keys in conversation (OpenAI, Cloudflare, GitHub)
2. **Monitor next Sunday** - Verify weekly-highlight runs successfully
