# Plan — A.3 Re1 MMR vs baseline (first real treatment)

**Date:** 2026-05-24
**Stream:** A (Close the experimental loop)
**Status:** experiment registered as `status: "draft"`. Wiring + activation deferred to next PR.
**Owner:** Manager (this doc); Coder (next PR); Pranjal (HITL sign-off + launch)

## Goalpost

Ship the first real treatment experiment end-to-end:

- Detect a real shift in homepage CTR (positive or negative) at p<0.05 with ≥100 clicks per variant.
- Stream A's success criterion (b) requires "at least one real treatment experiment with a decision (win/loss/inconclusive)." This is that one.

A clean inconclusive verdict counts. Detecting nothing real after enough power is shipped is a valid outcome and closes the stream.

## Variant semantics

| Variant | Behaviour | What user sees |
|---|---|---|
| `control` (50%) | Today's homepage rendering — items per row ordered by `model_score` descending (with the existing ad-hoc "max-2-per-type" filter) | Status quo |
| `treatment` (50%) | Same items, reordered by MMR with `lambda=0.7` using BGE embeddings | Same row labels; items appear in a diversity-aware order |

Same item set per row both arms. Only the *within-row order* differs. Cross-row composition unchanged.

## Why MMR specifically

- Already coded in `lib/diversity.py` (Python build-time) and `static/js/search/mmr.js` (JS for search-side rerank). Parallel suites confirm the math matches.
- `lambda=0.7` matches the JS default — same knob, no tuning surprise.
- Cheap: O(n²) over ≤10 items per row.
- Interpretable: variant assignment is observable in DOM via `data-variant`; the reordering can be inspected per-user.
- It's the principled upgrade over the current ad-hoc "max-2-per-type" filter (per the recsys audit's Re6).

## Launch gate (must pass before flipping `status: "draft"` → `"active"`)

1. **`harness_aa_v2` shows a clean A/A** — run `python3 scripts/analyze_experiments.py --experiment harness_aa_v2` after ≥48 hours of post-2026-05-24 data. CTR_A and CTR_B must be statistically indistinguishable (p>0.10) with ≥500 impressions per arm. If this fails the harness is still broken and we don't trust any treatment result.
2. **Tracker.js fix deployed to Cloudflare** — `static/js/tracker.js` cookie-timing fix from PR #51 must be live in production. Verify by hitting prod, opening DevTools, confirming `te_uid` cookie is set on first pageview before any click.
3. **MMR wiring lands in a follow-up PR** — see Architecture below.
4. **HITL** — Pranjal signs off on the wiring approach and the launch gate result.

## Architecture (the decision next session needs to make)

Three options to deliver per-variant ordering on a statically-rendered Hugo page:

### Option A — Server-side: pre-compute both orderings at build time

- `scripts/generate_homepage_rows.py` writes both `items` (control) and `items_mmr` (treatment) per row to `data/homepage_rows.json`.
- `layouts/_default/home.html` renders both inside the same row container with `data-variant="control"` / `data-variant="treatment"`.
- New tiny JS module (`static/js/homepage-mmr-experiment.js`) calls `window.Experiments.getVariant('exp_re1_mmr_v1')` and toggles `display: block` / `display: none` on the right pair.
- **Pros:** deterministic, debuggable (just View Source), no per-page-load compute, no client embedding dependency.
- **Cons:** ~2× HTML payload for the rows region (negligible — homepage rows are ~30 KB; doubling is ~30 KB extra gzipped to ~8 KB).

### Option B — Client-side: ship one ordering, reorder in browser

- Build script writes single ordering as today.
- Client loads `static/embeddings/related-items.json` (already fetched eagerly for `because-you-viewed`) and runs `mmr.js` on the visible items if in treatment.
- **Pros:** no payload growth; single source of truth at build time.
- **Cons:** depends on the related-items embedding file containing every homepage item (it doesn't today — it's the related-items subset); client-side reorder = DOM jank on slow devices; harder to debug.

### Option C — Hybrid: server-side variant pre-render but ship as JSON, build DOM client-side

- Like A but the items list is a JSON blob the client reads and constructs DOM from.
- **Pros / Cons:** all the cons of Option B for debuggability with all the cons of A for payload, plus extra runtime cost. Skip.

**Recommendation: Option A.** Lowest risk for a *first* real treatment. Once we trust the harness, B becomes attractive for future experiments where payload matters.

## Implementation plan (next PR)

Concrete steps for the wiring PR, assuming Option A:

1. **`scripts/generate_homepage_rows.py`** — call `mmr_rerank` per row, write `items_mmr` alongside `items`. Embedding lookup: load `static/embeddings/related-items.json` (or a dedicated build-time embedding file if related-items doesn't cover the homepage corpus — verify first by inspecting the file).
2. **`layouts/_default/home.html`** — wrap each row's `{{ range .items }}` block in a `<div data-variant="control">…</div>` and add a sibling `<div data-variant="treatment" hidden>` ranging over `.items_mmr`. The `hidden` attribute keeps the page visually identical to today by default.
3. **`static/js/homepage-mmr-experiment.js`** — new module, ~30 lines. On `DOMContentLoaded`: read `window.Experiments.getVariant('exp_re1_mmr_v1')`; if `"treatment"`, swap which sibling shows. Reuses existing `experiments.js`.
4. **`layouts/_default/baseof.html`** — add `<script src="/js/homepage-mmr-experiment.js" defer></script>`.
5. **Tracker logging** — already shipped (PR #42). `tracker.js` reads `window.Experiments.getAllAssignments()` and attaches `event.exp = {exp_re1_mmr_v1: "control"|"treatment"}`. No change needed.
6. **Flip `status: "draft"` → `"active"` in `data/experiments.json`.**
7. **Tests** — new `tests/js/homepage-mmr-experiment.test.js` covering: control variant leaves DOM untouched; treatment variant hides control DOM and shows treatment DOM; unknown variant (null) falls back to control. Pure-helper test in `tests/python/scripts/test_generate_homepage_rows.py` covering: `items_mmr` exists per row; same length as `items`; differs in order (statistically — pick a row where MMR provably reorders).
8. **CI**: `python3 scripts/validate_data.py && npm run build && npm test`.

## Measurement plan

- **Primary metric:** `ctr_homepage` — clicks on `.explore-card` from `/` (homepage path) divided by impressions on the same selector, per variant. Same query shape `analyze_experiments.py` already uses; new metric requires no script change beyond filtering by path.
- **Secondary metrics:** click-position depth (does MMR shift clicks deeper into rows?), time-to-first-click, total clicks per session on `/`.
- **Power:** harness_aa_v2 traffic indicates ~X impressions/day. Project the time-to-detect against an MDE of ±10% relative CTR. If we'd need >30 days to power, lower the MDE we care about *before* launch — don't move goalposts after seeing data.
- **Stopping rule:** check daily. Declare at first day where (a) p<0.05 AND (b) clicks-per-variant ≥100 AND (c) at least 7 days have elapsed. The 7-day floor prevents weekday-of-week confounds.

## Failure modes / rollback

- **MMR causes a CTR drop:** flip `status: "active"` → `"paused"`. Existing users who saw treatment will revert immediately. No data loss.
- **MMR produces identical ordering to control** (e.g., embeddings missing for most homepage items): the experiment is a hidden A/A. Detect at launch: in dev, log per-row "did MMR change anything?" If most rows answer no, the experiment is uninformative — fix embedding coverage before launching.
- **Tracker bug recurs:** `tracker-cookie-timing.test.js` regression suite (added in PR #51) catches it. CI gates merges.

## Out of scope for this prep PR

- Wiring (next PR).
- Adding the experiment to `tests/js/aa-experiment-config.test.js` — that test asserts A/A behaviour specifically; a non-A/A draft experiment doesn't belong there. A new `tests/js/exp-re1-mmr-config.test.js` will land with the wiring PR.
- Activating the experiment — gated on the launch gate above.

## Refs

- `data/experiments.json` — registration (this PR).
- `lib/diversity.py` — MMR implementation (already shipped).
- `static/js/search/mmr.js` — JS twin (already shipped, used by search rerank).
- `static/js/experiments.js` — bucketing harness (already shipped).
- `scripts/analyze_experiments.py` — per-variant CTR + significance (already shipped, PR #47).
- `docs/roadmap.md` Stream A.3 — goalpost.
- `master_recsys_planner.md` — append a Status entry once this PR lands.
