# Homepage: Simplify & Automate — Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Problem:** Homepage has 14 manually-curated rows that drift stale, require editorial effort, and have visual inconsistencies after the Netflix redesign attempt.
**Goal:** 5 algorithmic rows, zero manual curation, weekly auto-refresh via GitHub Actions, Playwright screenshot loop for fast visual iteration.

---

## 1. Row Structure

5 fixed rows. All 100% algorithmic — no `staff_picks.json`, `narrative_carousels.json`, or cluster files required.

| # | ID | Title | Template | Data Source | Items |
|---|---|-------|----------|-------------|-------|
| 0 | `trending-now` | Trending Now | `hero` | `global_rankings.json` — top engaged, type-diverse | 8–10 |
| 1 | `new-this-month` | New This Month | `standard` | All content files, `date_added` last 60 days, sorted by recency | 6–10 |
| 2 | `top-packages` | Top Packages | `standard` | `packages.json` sorted by `model_score` | 8 |
| 3 | `top-datasets` | Top Datasets | `standard` | `datasets.json` sorted by `model_score` | 8 |
| 4 | `talks-worth-watching` | Talks Worth Watching | `standard` | `talks.json` sorted by `model_score` | 8 |

**Retired rows** (data stays in files, just not surfaced on homepage):
- Staff Picks, Most Clicked This Week, narrative deep-dives (Pat Bajari, Deep Dive, Learning Path, Foundational Papers), Essential DiD Toolkit, If You Like AEA, Hidden Gems, Datasets to Explore (replaced by Top Datasets), Community & Events, Career Corner

**Hero carousel unchanged** — still rotates through first 5 items of the Trending row with type-specific gradients.

**Dedup rule** — an item can appear in at most one row. Trending row has first claim; subsequent rows skip already-used items.

---

## 2. Script Rewrite — `generate_homepage_rows.py`

Reduce from ~1238 lines to ~200. Schema of `homepage_rows.json` is **unchanged** so all templates work as-is.

### What's removed
- All narrative carousel logic + `narrative_carousels.json` dependency
- Staff picks builder + `staff_picks.json` dependency
- Cluster file dependencies (`package_clusters.json`, `dataset_clusters.json`, `talk_clusters.json`)
- 3-iteration critique loop
- `hidden_gems`, `community`, `career`, `coengagement` builders
- `homepage_trending.json` fallback (no longer needed)

### What stays
- `load_json()` / `load_content_lookup()` helpers
- Dedup tracking via `used_names` set
- Type diversity constraint on Trending row (max 3 of same type)
- Output format: `{ generated_at, stats, rows[] }` — identical schema

### New builder functions

```python
def build_trending_row(rankings, content_lookup, used_names):
    """Top 10 from global_rankings.json, max 3 same type, skip cold_start."""

def build_new_row(content_lookup, used_names, days=60):
    """Items with date_added in last N days, sorted by date descending."""

def build_type_row(type_filter, row_id, title, content_lookup, rankings_index, used_names, n=8):
    """Generic: filter by type, sort by model_score, take top N."""
```

### CLI unchanged
```bash
python3 scripts/generate_homepage_rows.py
python3 scripts/generate_homepage_rows.py --output data/homepage_rows.json
```

---

## 3. Automation — GitHub Actions

### Phase 1 (immediate, no new secrets)

New workflow: `.github/workflows/refresh-homepage.yml`

**Schedule:** Monday 3am UTC (5 hours before the existing deploy at 8am Monday)

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` (3.11)
3. `pip install` minimal deps (no sentence-transformers needed)
4. `python3 scripts/generate_homepage_rows.py`
5. `python3 autoresearch/checks/check_homepage_rows.py` — fail fast if invalid
6. `git diff --quiet data/homepage_rows.json || (git add data/homepage_rows.json && git commit -m "Auto-refresh homepage rows ($(date +%Y-%m-%d))" && git push)`

The existing `deploy.yml` at 8am Monday then picks up the fresh `homepage_rows.json` automatically.

### Phase 2 (later, needs D1 credentials)

Add `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_D1_DB_ID` + `CLOUDFLARE_API_TOKEN` to GH Secrets.

Before step 4, add:
```
python3 scripts/rank_all_content.py
git add data/global_rankings.json
```

Full pipeline: D1 engagement data → `global_rankings.json` → `homepage_rows.json` → committed → deployed.

**Manual trigger** — both phases support `workflow_dispatch` for on-demand runs.

---

## 4. Dev Tool — Playwright Screenshot Loop

**Purpose:** Visual test-iterate-develop loop. Enables seeing exact rendered output during template/CSS changes without opening a browser manually.

**Install (one-time):**
```bash
npm install --save-dev playwright
npx playwright install chromium
```

**Script:** `scripts/screenshot-homepage.js`

```javascript
// Usage: node scripts/screenshot-homepage.js [--port 1313] [--out /tmp/homepage.png]
// Takes full-page screenshot of homepage, plus a viewport-only crop for above-the-fold view.
```

**Saves two files:**
- `/tmp/homepage.png` — full page
- `/tmp/homepage-fold.png` — first 900px (above the fold)

**Dev loop:**
```bash
hugo server --port 1313 &          # start dev server
node scripts/screenshot-homepage.js # screenshot → /tmp/homepage.png
# Claude reads the image, gives feedback
# Edit layouts/ or static/css/custom.css
# Re-run screenshot → iterate
kill %1                             # stop server when done
```

Script is idempotent and fast (~2s per run). Saves to `/tmp/` to avoid cluttering the repo.

---

## 5. Files Changed

| File | Change |
|------|--------|
| `scripts/generate_homepage_rows.py` | Rewrite — 5 algorithmic rows, ~200 lines |
| `.github/workflows/refresh-homepage.yml` | New — weekly cron + manual trigger |
| `scripts/screenshot-homepage.js` | New — Playwright dev tool |
| `package.json` | Add `playwright` devDependency |
| `data/homepage_rows.json` | Regenerated output (auto-managed after this) |

**Not changed:** All HTML templates (`home.html`, `row-*.html`), all CSS, all other data files, `autoresearch/checks/check_homepage_rows.py`.

---

## 6. Success Criteria

- [ ] `generate_homepage_rows.py` produces exactly 5 rows with no manual input files required
- [ ] `check_homepage_rows.py` passes on the new output
- [ ] `npm run build` succeeds cleanly
- [ ] `refresh-homepage.yml` runs without error on `workflow_dispatch`
- [ ] `screenshot-homepage.js` produces readable PNG files
- [ ] No items appear in more than one row
- [ ] Trending row has ≥3 different content types
