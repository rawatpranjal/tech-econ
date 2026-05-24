# Stream A Analysis Run — 2026-05-23

## What this file contains
Coder-agent findings from Stream A.1 (analyze_experiments.py) and A.2 (replay_eval.py).
No code was modified. Read-only diagnostic run.

## D1 raw data (from successful manual wrangler query)
experiment: harness_aa_v1, all time since 2026-05-04

| variant   | impressions | clicks | CTR    |
|-----------|-------------|--------|--------|
| control_a | 8,071       | 322    | 3.99%  |
| control_b | 10,205      | 237    | 2.32%  |
| **total** | **18,276**  | **559**|        |

## A.1 script failure

Command: `python3 scripts/analyze_experiments.py --experiment harness_aa_v1`

Failure: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

Root cause: wrangler prints a preamble line to stdout before the JSON array:
```
Cloudflare agent skills are available for: Claude Code, Cursor, Codex, Windsurf. ...
```
`analyze_experiments.py:_wrangler_query` calls `json.loads(proc.stdout)` on the
combined stdout which starts with that text, not `[`. `rank_all_content.py` has the
same pattern but silently swallows `JSONDecodeError`. The fix (not done here) is to
strip non-JSON lines before parsing or redirect wrangler's preamble to stderr via
`--install-skills` suppression / env var, or parse with a `findall` for the JSON array.

## A.2 script failure

Command: `python3 scripts/replay_eval.py --candidate data/global_rankings.json`

Failure (partial): `SessionLoadError: Could not reach analytics API — SSL certificate verify failed`

Root cause: Python 3.11 on macOS does not use the system keychain by default.
The `load_sessions(source='api')` call hits `https://tech-econ-analytics-v2.pp712.workers.dev`
and SSL verification fails. Fix options: `python3 -m certifi` path injection, or
`--source wrangler` flag (which has the same wrangler preamble issue as above).

No rows were appended to `reports/replays.csv` (file does not exist). `reports/metrics.csv` unchanged at 1 row.

## Computed A/A statistics (from D1 data, using script-identical formulas)

Split: control_a=44.2%, control_b=55.8%  (delta: 5.8 pp from 50/50 — OUTSIDE ±3 pp threshold)

CTR:
- control_a: 3.99% (95% Wilson CI: [3.58%, 4.44%])
- control_b: 2.32% (95% Wilson CI: [2.05%, 2.63%])

Two-proportion z-test: z=-6.50, p≈0.000 (two-sided) — CIs do NOT overlap.

Impression ratio: control_b has 1.264x more impressions than control_a (expected ~1.0).

Verdict: SKEWED — both the bucketing split and the CTR show a significant, unexpected signal.
The A/A test is failing: an identical no-op experiment is producing p≈0.000.
