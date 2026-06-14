# Handoff — 2026-06-14 — stream-t-ci-reliability

## Where we left off

/end pass complete. Branch has 6 commits ahead of main, tree is clean, tests are green (JS 714/714, Python 1950/1950). Blocked on two human sign-offs before anything meaningful can advance.

## Active streams (clustered)

**[A] Experimental loop**
- A.3 MMR wiring done; experiment stays `draft` until A.4 HITL clears.
- **A.4 HITL** (BLOCKING): run `python3 scripts/analyze_experiments.py --experiment harness_aa_v2`, review per-variant CTR + confidence intervals, declare win/loss/inconclusive. This is the chokepoint for the whole stream.
- A.7 fresh-agent audit follows A.4.

**[B] Homepage Editorial**
- **B.5 HITL** (BLOCKING): eyeball the live site — hero image, type-tinted cards, Inter Display font. No visual check has happened. B.6 audit follows.

**[C] /site + /dashboard** — complete. Stream M (slides) now unblocked.

**[N] Card images** — scoped only; can start in parallel while waiting on A.4/B.5.

**[T] CI/CD** — T.1-T.5 done. T.6 audit window opens ~2026-06-28 (needs 14 rolling days of clean CI).

## Decisions made this session

- /system reconcile pass executed: STATUS-BOARD markers added to claude.md, SYSTEM.md scaffolded (copied from delivery), decisions.md created, T.1-T.5 marked ✅, C.4 resolved via HITL + passing build.
- Learned rule added: scaffold files must be copied from sibling projects, not drafted from scratch.
- 6 tracked .pyc files removed from git tracking.

## Open questions

- Start Stream N while waiting on A.4 + B.5 HITLs?
- 13 stale local branches (phase-*, autoresearch/*) — prune?
- PR to merge stream-t-ci-reliability → main (needs RecsysGate: PR + 4 CI checks + bypass token).

## Landmines / gotchas

- **A.3 must stay `draft`** until A.4 HITL clears — flipping `exp_re1_mmr_v1` to `active` before that poisons the A/A baseline.
- **B.5 still not eyeballed** — hero + type-tinted cards + font change are live in the branch but no human has looked at the rendered page.
- **3 Python test collection errors** are pre-existing missing optional deps (`aiohttp`, `hdbscan`, and one more) — not regressions, but worth tracking in requirements-dev.txt if those scripts get used.

## Suggested next move

A.4: `python3 scripts/analyze_experiments.py --experiment harness_aa_v2` — gives the CTR numbers needed to unblock the entire experimental loop.
