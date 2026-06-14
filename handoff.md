# Handoff — 2026-06-14 — stream-t-ci-reliability

## Where we left off
Stream N fully closed (N.1–N.7 + N.6b). Tree is clean, branch up to date with remote. 2126 Python / 714 JS green. All remaining Now-horizon work is blocked on human gates or time.

## Active streams (clustered)

**Blocked on user (HITL):**
- **A.4** — Run `python3 scripts/analyze_experiments.py --experiment harness_aa_v2`, review per-variant CTR + 95% CI, declare win/loss. This unblocks Re1 MMR flip and closes Stream A.
- **B.5** — Eyeball the live homepage (hero + type-tinted cards + Inter Display font). No human has looked at it. Sign-off unblocks B.6 audit.

**Time-gated:**
- **T.6** — CI audit window opens 2026-06-28. Check 14-day rolling success rate of T.1–T.5 workflow fixes.

**Needs PR to main:**
- Branch is 20+ commits ahead of main (all Stream T + Stream N work). RecsysGate: PR + 4 CI checks + bypass token required. See `memory/project_stream_t_ci_fix.md`.

**Done this session:**
- Stream N (N.1–N.7 + N.6b): image_url populated across all content types; templates wired; 65 book covers; datasets 150-card initials gap closed with favicon step.

## Decisions made this session
- Resources/learning template NOT updated — stored image_url values are OG blog images, not favicons; would look bad at 20px. Needs a card redesign. Deferred intentionally.
- `hugo_stats.json` gitignored (was tracked as build artifact).
- Directory Structure label in docs fixed (`metrics-packages/` → `tech-econ/`).

## Open questions
- **A.4 result:** Is harness_aa_v2 A/A statistically clean? Determines whether Re1 MMR goes active.
- **PR to main:** Ready to open when you want. Needs bypass token or PAT in secrets.

## Landmines / gotchas
- **`--skip-existing` on community:** Re-running `fetch_career_community_images.py` without `--skip-existing` overwrites 307 curated community images. Always use the flag.
- **A.3 stays `draft`** until A.4 HITL clears — flipping `exp_re1_mmr_v1` to `active` before that corrupts the A/A baseline.
- **Eval gate RED:** `reports/metrics.csv` has 1 row; need ≥3 at same holdout_days before flipping any ranker default.

## Suggested next move
A.4 — run the A/A analysis. If clean, flip Re1 MMR from draft to active and Stream A closes.
