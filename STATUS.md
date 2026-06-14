# Status: tech-econ — 2026-05-29

## This month (north-star)
We are making tech-econ.com discover and rank content better, and look better doing it. The headline goal for May–June is to close the loop on controlled experiments: ship the first *real* A/B treatment (a new content-ordering method called MMR) with a logged decision, so future ranking changes can be measured rather than guessed. Alongside that, two visible upgrades are in flight — a magazine-style "Editorial" homepage, and a plain-language "how this site works" page. Everything else (multi-channel retrieval, deep-learning rankers, more homepage directions) is explicitly queued behind these.

## Active streams
This repo tracks work as lettered streams in `docs/roadmap.md`, not `docs/chunks/`. Now-horizon streams:

| Stream | What | Phase | State |
|:---|:---|:---|:---|
| **A** — Experimental loop | First real A/B treatment (Re1 MMR) | code / blocked | A.1/2/5/6 shipped. A.3 MMR registered as **draft**; architecture = Option A (dual-render) per saved memory. Blocked on deploy + 48h clean A/A data + wiring PR. Audit A.7 pending. |
| **B** — Editorial homepage | Magazine-like Direction 1 | awaiting sign-off | B.1–B.4 shipped (PR #56). **B.5 visual sign-off never actually eyeballed.** B.6 audit pending (sequential). |
| **C** — `/site` transparency page | Explain the site in plain language | mostly done | Tabs 1–6 shipped. Tabs 7–8 (Performance, Experiments) need SVG design direction. C.4 fresh-agent audit pending. |
| **D** — Stale-doc cleanup | Docs match code | ✅ done | Closed 2026-05-24, all 5 items. |
| **N** — Image fill on cards | Every card has a real/generated/favicon image | not started | Mechanical, parallel, unblocked. Books/career have no images; datasets ~66%. |
| **T** — CI/CD reliability | No silent workflow failures | not started | Mechanical, parallel, unblocked. 5 workflow fixes staged. |

Next/Later streams (E–T, I–S) are all sequenced behind A, B, C, or T and need no action now.

## Needs your attention (ranked)
1. **Deploy to Cloudflare** — the single biggest unblock. Until the recent tracker + dashboard + `/site` changes go live, the A/A experiment can't collect clean data, which is the chokepoint for the headline MMR treatment. This is a you-action (likely needs your auth). *(Action: yours.)*
2. **Eyeball the homepage** — B.5 sign-off was treated as implicit when PR #56 shipped, but no one actually looked at the live hero / type-tinted cards. If they look wrong in production, this is why. *(Decision: yours.)*
3. **Uncommitted working tree** — 34 modified + ~45 untracked files are sitting in the tree (largely auto-generated test files from background autorun iterations 31–44). The 2026-05-25 handoff said "nothing in flight / synced," so this is drift worth a commit-or-triage decision. *(Decision: yours.)*
4. **Tabs 7–8 SVG design direction** (Stream C) — needs a design call from you; non-blocking. *(Decision: yours.)*
5. **Pending fresh-agent audits** — A.7, B.6, C.4. Mechanical; can be delegated to subagents now. *(Mechanical.)*

## Shipped in last 7 days
- PR #57 — end-of-session housekeeping (handoff, test count, stash rule)
- PR #56 — homepage polish 2: row reorder, type-tint cards, hero image script, featured.json
- PR #55 — C4 follow-ups: scoreboard rebuild, SVG 13px floor, dark-mode tints, per-tab dashboard retry
- PR #54 — A.3 draft: registered Re1 MMR experiment + design doc
- PR #53 — C4 audit: dashboard build + worker schema + papers count
- Test suite grew: 714 JS tests, 1983 Python tests

## Recent commits (7 days)
```
7ea5f9d chore: end-of-session housekeeping (handoff, test count, stash rule) (#57)
02f426e feat(stream-b): homepage polish 2 — row reorder, type-tint cards, hero, featured.json (#56)
e71187c fix(c4-followups): scoreboard rebuild + SVG floor + dark-mode tints + dashboard retry (#55)
7990c0c feat(ab): A.3 draft — register Re1 MMR experiment + design doc (#54)
5251917 fix(c4-audit): dashboard build + worker schema + papers count (#53)
```

## Open questions / landmines
- **A.3 architecture is actually decided** (Option A, dual-render — saved memory), contradicting the handoff's "open question." Treat it as settled; remaining A.3 blockers are deploy + data + wiring, not the design call.
- **B.5 was never visually verified** (handoff landmine). Risk is purely cosmetic but live.
- **Eval gate is RED** — `reports/metrics.csv` has 1 row; need ≥3 at the same holdout window before flipping any ranker default (e.g. Stream F's k-NN flip). Blocked on more A/A data → blocked on deploy.
- **Offline scoreboard last ran 2026-05-03**: NDCG@10 0.419, Hit-Rate@10 0.80 (15 evaluable sessions). One data point only.

## Suggested next move
Deploy to Cloudflare — one action, biggest unblock; it starts clean A/A data collection, the chokepoint for the headline MMR treatment. While that 48h window fills, the leveraged subagent work is the parallel mechanical streams (N image-fill, T CI fixes) and the three pending audits — run one at a time.

## TLDR
The website project is in good shape and moving fast — six chunks of work shipped in the past week, including a refreshed homepage and a new "how this site works" page. The big push this month is setting up a proper experiment so we can measure whether a new way of ordering content actually performs better, instead of guessing. That experiment is ready but can't start gathering real data until the latest changes are published to the hosting service — and that publish step is the one thing waiting on you. A smaller open item: the new homepage shipped without anyone actually looking at it live, so it's worth a quick visual check. Once the changes are published, there's plenty of independent cleanup work (filling in missing images, fixing automated maintenance jobs, and a few quality reviews) that can run in the background, one task at a time.
