# impl-2026-03-26-rank-all-content-fixes

## Summary
Fixed hardcoded paths and added API-based data fetching to `scripts/rank_all_content.py`.

## Changes Made

- `scripts/rank_all_content.py` (Change 1, line ~1054) — `data_dir` now uses `Path(__file__).resolve().parent.parent / 'data'` instead of hardcoded `/Users/pranjal/metrics-packages/data`
- `scripts/rank_all_content.py` (Change 2, line ~76) — `fetch_d1_data` wrangler `cwd` now uses `Path(__file__).resolve().parent.parent / 'analytics-worker'` instead of hardcoded path
- `scripts/rank_all_content.py` (Change 3, line ~62) — Added `CITATION_WEIGHT = 0.3` constant after `FRESHNESS_HALF_LIFE_DAYS` (was used at line ~989 but never defined)
- `scripts/rank_all_content.py` (Change 4, line ~1050) — Added `--source` CLI argument with choices `['d1', 'api']`, default `'d1'`
- `scripts/rank_all_content.py` (Change 5, lines ~247-287) — Added `fetch_engagement_from_api()` function after `fetch_engagement_data()`; hits `ANALYTICS_API/ranking-export` and maps API field names to internal signal keys
- `scripts/rank_all_content.py` (Change 6, line ~1065) — `main()` now branches on `args.source`: calls `fetch_engagement_from_api()` for `api`, `fetch_engagement_data()` for `d1`
- `scripts/rank_all_content.py` (Change 7, line ~1317) — `output_path` now uses `Path(__file__).resolve().parent.parent / args.output` instead of `data_dir.parent / args.output`

## Verification

Run with default D1 source:
```bash
python3 scripts/rank_all_content.py
```

Run with API source:
```bash
python3 scripts/rank_all_content.py --source api
```
