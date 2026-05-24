# impl-2026-05-24-stream-c8-perf-tabs

Stream C.8 — /site Tabs 7 (Performance) + 8 (Experiments)
Created: 2026-05-24

## Files created / modified

- `scripts/build_site_scoreboard.py` — NEW. Reads metrics.csv, replays.csv, experiments.json, per-experiment markdown reports; writes data/site_scoreboard.json atomically via .tmp rename. Docstring has Inputs/Outputs/Side effects/Reproducibility per guardrail pattern.
- `tests/python/scripts/test_build_site_scoreboard.py` — NEW. 16 pytest cases: metrics parsing, graceful missing replays, experiment markdown parsing, atomic JSON write, end-to-end main().
- `data/site_scoreboard.json` — NEW. Generated output consumed by Hugo templates. 1 metrics row, 1 replay, 2 experiments (harness_aa_v1 paused with results, harness_aa_v2 active without results).
- `layouts/site/list.html` — MODIFIED. Nav extended from 6 to 8 buttons (Performance + Experiments). Tab 7 and Tab 8 content panels added before closing </div>/<script>. Reads site.Data.site_scoreboard via Hugo data templates.
- `static/css/custom.css` — MODIFIED. Added ~250 lines of new CSS at end: .scoreboard-card, .scoreboard-grid, .scoreboard-sparkline, .experiment-card, .experiment-card-header, .experiment-results-grid, .experiment-result-cell, .status-pill (.status-active/.status-paused/.status-ended/.status-broken), .active-experiment-callout, .next-experiments-callout, .experiment-timeline. Dark mode overrides + mobile breakpoints included.
- `CHANGELOG.md` — MODIFIED. 1-line C.8 entry prepended under 2026-05-24.
- `docs/roadmap.md` — MODIFIED. C.8 line added under Stream C.

## Pipeline script

- Inputs read: reports/metrics.csv, reports/replays.csv, data/experiments.json, reports/experiments/<id>-YYYY-MM-DD.md (glob, most-recent per id)
- Output: data/site_scoreboard.json with 1 metrics rows, 1 replays, 2 experiments
- Tests: 16 (all passing)

## Tab 7 (Performance)

- Word count: ~560 words prose
- Visual elements: 4 scoreboard-card stat cards (NDCG@10 primary, Hit-Rate@10, MAP, Sessions evaluated), inline SVG sparkline (dots + polyline when 2+ points, Y-axis guides at 0.2/0.4/0.6/0.8, date labels), history table (site-content-types style)
- Headline number: NDCG@10 = 0.419 (from 2026-05-03 eval run)
- Replay section rendered inline via Hugo if block (shows latest replay numbers)

## Tab 8 (Experiments)

- Word count: ~500 words prose
- Experiments table rows: 2 (harness_aa_v1 paused/broken, harness_aa_v2 active)
- Detail cards: 2 (harness_aa_v1 shows per-variant CTR numbers + CI; harness_aa_v2 shows "collecting data")
- Timeline SVG: yes, horizontal bars positioned by conceptual date range, color-coded (red=broken, green=active)
- Active-experiment callout: green pill callout for harness_aa_v2
- Next-experiments callout: blue-tinted block describing diversity experiment + personalization experiment planned

## Em-dash check

- grep result: 0 (confirmed with `grep -c $'\xe2\x80\x94' layouts/site/list.html`)

## Verification

- script runs: pass (writes data/site_scoreboard.json, 1 metrics rows, 1 replays, 2 experiments)
- validate_data.py: pass
- hugo build: pass (106 pages, 0 new warnings, no new pages)
- npm test: pass (185/185)
- pytest: 16/16 new tests pass; 467 existing pass; 7 pre-existing d1_sessions stub failures unrelated to this work

## Open issues

- Hugo sparkline uses range arithmetic via `add`/`sub`/`mul`/`div`/`float` template functions. Hugo's standard math functions require care with int vs float. Build passes cleanly, but with only 1 history row the sparkline renders as a single dot -- this is the correct behavior and will naturally become a line as more eval runs accumulate.
- The 7 pre-existing failures in tests/python/lib/test_d1_sessions.py (TestFetchEventsViaApi stub issue) predate this task and are unrelated.
- Tab nav has 8 buttons on mobile. The existing site-tabs CSS uses overflow-x: auto so horizontal scrolling handles it without any new mobile CSS needed.
