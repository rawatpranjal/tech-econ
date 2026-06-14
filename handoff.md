# Handoff — 2026-06-14 — stream-t-ci-reliability

## Where we left off

/system reconcile pass completed. Branch `stream-t-ci-reliability` has CI fixes (fcae03f) plus the reconcile housekeeping commit. Open work is gated on two human sign-offs: A.4 (per-variant CTR review) and B.5 (visual homepage check).

## Active streams

**[A] Experimental loop**
- A.1, A.2, A.5, A.6 shipped. A.3 MMR wiring done (homepage-mmr-experiment.js, dual-render in home.html). Experiment stays `draft` pending A.4 HITL.
- A.4 HITL: run `python3 scripts/analyze_experiments.py --experiment harness_aa_v2`, review per-variant CTR + confidence intervals, declare win/loss/inconclusive.
- A.7 fresh-agent audit still pending (requires A.4 decision first).

**[B] Homepage Editorial**
- B.1-B.4 shipped (PR #56). B.5 HITL pending: eyeball the live site (hero, type-tinted cards, font change). No hugo server check was done before prior PR.
- B.6 audit pending.

**[C] /site + /dashboard**
- C.1-C.11 complete. C.4 audit gate resolved (HITL C.5 + passing build served as combined gate). Stream M (slides) now unblocked.

**[D] Doc hygiene**
- Fully closed 2026-05-24.

**[N] Card images**
- Not started. Scoped only. Can run in parallel with A/B wait.

**[T] CI/CD reliability**
- T.1-T.5 shipped (fcae03f, 2026-05-29). T.6 audit window opens ~2026-06-28 (need 14 rolling days of clean CI).

## Decisions made this pass
- C.4 marked satisfied via HITL C.5 + passing build (logged in decisions.md).
- T.1-T.5 marked ✅ retrospectively against fcae03f.
- STATUS-BOARD markers added to claude.md; decisions.md created as /system scaffold.

## Open questions
- Start Stream N while waiting on A.4 + B.5 HITLs?
- Branch pruning: 13 stale local branches (phase-*, autoresearch/*) — still open from prior session.
- T.6 audit: calendar it for ~2026-06-28.

## Landmines / gotchas
- **B.5 still not eyeballed**: homepage has type-tinted cards + hero image + Inter Display font. Needs live visual check before B is declared done.
- **A.3 stays draft**: `exp_re1_mmr_v1` must not flip to `active` until A.4 HITL clears.
- **~95 untracked test files**: committed in housekeeping pass. Run `npm test` + `pytest` to confirm all green after the commit.

## Suggested next move
A.4 analysis: `python3 scripts/analyze_experiments.py --experiment harness_aa_v2` — gives the per-variant CTR numbers needed for the HITL decision.
