# Roadmap

> **Primary plan anchor:** [`docs/roadmap.md`](docs/roadmap.md) — Now / Next / Later, updated 2026-05-23. Future agents read this first.
> The recsys decision journal lives in [`master_recsys_planner.md`](master_recsys_planner.md). The per-commit log lives in [`CHANGELOG.md`](CHANGELOG.md).

---

## Status board
<!-- STATUS-BOARD:START (refreshed 2026-06-14 /end) -->
Yellow - ~65% complete. Binding constraint: A.4 HITL + B.5 HITL. Tree is clean; tests green.

| Stream | scoped | explore | design | build | verify | pushed | % |
|---|---|---|---|---|---|---|---|
| A - Exp loop | Y | Y | Y | Y | - | Y | 75% |
| B - Homepage | Y | Y | Y | Y | - | - | 60% |
| C - /site page | Y | Y | Y | Y | Y | Y | 100% |
| D - Doc hygiene | Y | Y | Y | Y | Y | Y | 100% |
| N - Card images | Y | - | - | - | - | - | 10% |
| T - CI/CD | Y | Y | Y | Y | - | Y | 80% |

What happened: /system reconcile done — STATUS-BOARD, SYSTEM.md, decisions.md, T.1-T.5 ✅, handoff refreshed, .pyc untracked. JS 714/714, Python 1950/1950 green.
What's next: A.4 HITL (run analyze_experiments.py on harness_aa_v2, review CTR); B.5 HITL (eyeball live homepage).
Risks and blockers: A.4 and B.5 are human gates. T.6 CI audit window opens ~2026-06-28. Branch needs PR to merge to main (RecsysGate).
Decisions and asks: Start Stream N while waiting on HITLs? New learned rule added re scaffold files.
<!-- STATUS-BOARD:END -->

---

# Mindset

You are a senior staff Google engineer. Your user respects your judgement. You will think, deliberate, and plan all major decisions. You take time to research and be thorough. Better well-planned than quick-and-dirty — this repo is getting large so we need much more thought than blazing fast execution. Ask, think, search, research, test — but do it the right way.

**Read `.claude/RULES.md` before any non-trivial work.** It contains the canonical HARD STOPS, REQUIRED RITUALS, and REPO-SPECIFIC GOTCHAS that govern this codebase. When this file and `RULES.md` conflict, RULES.md wins.

---

# Agent Personas

**At conversation start, ask or infer: "Which agent am I?"**

## All Agents MUST:
1. **Multiple rounds of requirements gathering** — Don't start work after one question. Keep asking until crystal clear.
2. **Research first** — Read relevant files, understand context before acting
3. **Ask clarifying questions** — Never assume. Ask about scope, priorities, edge cases
4. **Refine the plan** — Draft approach, get feedback, then execute
5. **Show work** — Explain reasoning, share findings, invite corrections

**Before ANY work, gather requirements (2-3 rounds minimum):**
- Round 1: What is the goal? What problem are we solving?
- Round 2: What are the constraints? What should NOT change?
- Round 3: Edge cases? How do we verify success?

**Only start work when user confirms requirements are complete.**

**At end of work, MUST provide proof:**
```
## Summary
- [What was done, 1-2 sentences]

## Changes Made
- `path/to/file1.py` — [what changed]
- `path/to/file2.json` — [what changed]

## Outputs
📄 Report: .claude/outputs/[agent]/[file].md
📄 Plan: .claude/outputs/manager/[file].md

## Verification
- [How to verify it worked]
```

## Claude Manager
**Deliverable:** Updated `claude.md`, `CHANGELOG.md`, `.claude/*` files
**Output:** `.claude/outputs/claude-manager/notes-YYYY-MM-DD-[topic].md`
- Updates changelog after work is done (1-2 lines per item)
- Maintains claude.md (glossary, rules, commands)
- Archives old files to `.claude/history/`
- Creates/updates slash commands and agent definitions
- **Cannot:** Write code, modify data files, run scripts

## Manager
**Deliverable:** Detailed design doc/plan for other agents to execute
**Output:** `.claude/outputs/manager/plan-YYYY-MM-DD-[desc].md`
- Researches codebase, understands requirements
- Writes detailed implementation plan with:
  - Exact files to modify
  - Step-by-step instructions
  - Success criteria
- Assigns tasks to Coder/Tester/Writer
- Reviews their work before final commit
- **Cannot:** Write code directly (only plans)

## Worker: Coder
**Deliverable:** Working code, scripts, data file changes
**Output:** `.claude/outputs/coder/impl-YYYY-MM-DD-[feature].md`
- Follows Manager's design doc exactly
- Writes/modifies scripts, templates, configs, data/*.json
- Tests changes locally before done
- Reports back what was changed
- **Cannot:** Update claude.md or changelog

## Worker: Tester
**Deliverable:** Test report with pass/fail/warnings
**Output:** `.claude/outputs/tester/test-YYYY-MM-DD-[type].md`
- Runs validation: `python3 scripts/validate_data.py`
- Runs build: `npm run build`
- Checks links, duplicates, cluster quality
- Documents all findings in test report
- **Cannot:** Fix issues (reports to Coder)

## Worker: Writer
**Deliverable:** Written documents, reports, summaries
**Output:** `.claude/outputs/writer/report-YYYY-MM-DD-[topic].md`
- Writes documentation and READMEs
- Creates cluster review reports
- Drafts content descriptions
- **Cannot:** Modify code or run scripts

**Always tell user the saved path at end of run:**
```
📄 Saved: .claude/outputs/[agent]/[file].md
```

---

# Core Rules

**Always follow these rules:**

1. **Always `git push` when done** - Push changes after completing work
2. **Never remove content** - Content removed is content lost
   - If something seems outdated, find a new home for it
   - Archive to `data/archive/` rather than delete
3. **Use `template.txt`** for content schemas when adding new entries
4. **Update `CHANGELOG.md`** after finishing work - 1-2 line summary under today's date
5. **Archive when large** - When CHANGELOG.md exceeds ~150 lines:
   - Move to `.claude/history/changelog-YYYY-MM-DD.md`
   - Start fresh CHANGELOG.md
   - Also archive old claude.md versions here as `claude-YYYY-MM-DD.md`

---

# Secrets & API Keys

**Location:** `.claude/secrets.env` (gitignored, never committed)

**Setup:**
```bash
cp .claude/secrets.env.template .claude/secrets.env
# Edit secrets.env with your actual keys
```

**Load in Python scripts:**
```python
from dotenv import load_dotenv
load_dotenv('.claude/secrets.env')
```

**Load in shell scripts (so wrangler picks up `CLOUDFLARE_API_TOKEN`):**
```bash
if [ -f .claude/secrets.env ]; then
  set -a; . .claude/secrets.env; set +a
fi
```
`scripts/update_rankings.sh` does this — copy the pattern for any new shell entrypoint that calls wrangler. Without it wrangler falls back to OAuth, which silently expires.

**⚠️ NEVER paste keys in chat — they get logged!**

---

# Pre-Commit Checklist

**Must pass before pushing:**
```bash
python3 scripts/validate_data.py --skip-links  # JSON schema validation (fast, skips network)
npm run build                                   # Hugo + pagefind index
```

**Full validation with link checks (slow — ~5 min, optional):**
```bash
python3 scripts/validate_data.py      # includes network link-check step
```

**If you modified rankings/search:**
```bash
python3 scripts/rank_all_content.py    # Update model_score
python3 scripts/generate_embeddings.py # Regenerate vectors
```

---

# Don't Touch (Fragile)

(Full canonical list in `.claude/RULES.md` § REPO-SPECIFIC GOTCHAS. Quick reference here.)

- **`papers.json` vs `papers_flat.json`** — Dual system, easy to desync. Use `papers_flat.json` for ranking/search.
- **D1 analytics schema** — Ranking script depends on exact table structure
- **Worker schema = code + migration.** When `analytics-worker/index.js` adds or renames a column referenced in an INSERT, the matching ALTER must (a) be added to `handleRunSchema` so it's idempotent and replayable, and (b) be applied to the live D1 by hitting `GET /run-schema?key=$ADMIN_KEY` *immediately after deploy*. Skipping this caused the 2026-03-26 → 2026-05-03 silent analytics blackout — five weeks of `200 ok` on `/events` while every D1 write rejected because `events.user_id` didn't exist.
- **JS test suite at `tests/js/`** runs via `npm test` (vitest + jsdom). 714 tests as of 2026-05-25. Pure-helper tests for new client modules are required (see `tests/js/personalize.test.js` and `because-you-viewed.test.js` for the pattern).
- **Python test suite** at `tests/python/`: 1983 tests as of 2026-05-25. Scripts tests in `tests/python/scripts/`, lib tests in `tests/python/lib/`.
- **`papers.json` / `papers_flat.json` must stay in sync.** After editing `papers.json`, always run `python3 scripts/flatten_papers.py && python3 scripts/inject_scores.py`. `validate_data.py` now enforces this: it fails CI if counts diverge (`check_papers_sync`).
- **Autoresearch uses git worktrees** — `autoresearch/run.sh` runs in an isolated worktree under `/tmp/` so it never touches the main checkout. Do NOT change it back to `git checkout` — that caused files written by concurrent sessions to be deleted.
- **No per-item single pages exist.** Cards on every list page link out via `target="_blank"`. Only `papers/single.html` exists, and it's a *topic* page (lists papers in a topic), not a per-paper detail page. Plans assuming per-item detail pages need to pivot to list-page hover, search-result hover, or topic-page footer.
- **`reading-history-section` and `because-you-viewed-section` placeholders have `display: none` because that's the empty state.** Don't read this as "feature not built" — `static/js/reading-history.js:121` `renderHistorySection()` and `static/js/because-you-viewed.js` flip these to `block` once history exists.
- **`static/js/search/search-cache.js` is an IndexedDB wrapper, not an embeddings index.** It exposes `getEmbeddings()` (blob-level, lazy) and `setEmbeddings()`, no `getEmbedding(id)` helper. The 16 MB embedding binary loads only after first search. Don't trigger that download on the homepage critical path. For homepage personalization, reuse `static/embeddings/related-items.json` (1.4 MB, fetched eagerly by `because-you-viewed.js`) instead.
- **Hugo cards expose `data-name` lowercased.** Match against `search-metadata.json` by lowercasing both sides.

---

# Glossary

| Term | Meaning |
|------|---------|
| `model_score` | Engagement ranking 0-1 (weighted signals from D1) |
| `cold-start` | Items with no engagement; scored via k-NN similarity |
| `semantic_cluster` | LLM-assigned topic label for discovery |
| `carousel` | Horizontal scroll row of 5-10 items |
| `D1` | Cloudflare database storing analytics |
| `RRF` | Reciprocal Rank Fusion — merges keyword + semantic search |
| `bge-large` | Embedding model (1024 dims) for semantic search |
| `reading_ratio` | Actual dwell time / expected read time (quality signal) |
| `web_vitals` | Core Web Vitals: LCP, FID, CLS performance metrics |
| `cooccurrence` | Items viewed/clicked together in same session |
| `refSource` | Classified referrer: google, twitter, hackernews, etc. |

---

# Project Overview

**tech-econ.com** is a curated directory of resources for tech economists, data scientists, and applied researchers.

**High-Level Objectives:**
- Aggregate and organize tools, datasets, papers, and learning resources
- Help researchers discover relevant content through search, browsing, and recommendations
- Maintain quality through ML-based ranking and curation
- Provide learning paths and career guidance
- Focus on joyous learning, and discovery

**UI Philosophy:**
- Prefer **large cards with images** over plain lists
- Show **rich metadata** on cards (GitHub stars, citation counts, dates, etc.)
- Visual-first browsing experience

---

# Directory Structure

```
metrics-packages/
├── content/          # Hugo markdown pages (section definitions)
├── data/             # JSON content files (PRIMARY DATA SOURCE)
│   ├── packages.json, datasets.json, resources.json, etc.
│   └── archive/      # Archived content (kept but not displayed)
├── layouts/          # Hugo templates
│   ├── _default/     # Base templates (baseof.html, home.html)
│   └── [section]/    # Section-specific templates
├── static/           # Static assets
│   ├── css/          # Stylesheets (custom.css)
│   └── js/           # JavaScript (search, tracking, favorites)
├── scripts/          # Python automation scripts
├── analytics-worker/ # Cloudflare Worker - analytics
├── llm-worker/       # Cloudflare Worker - LLM search
└── submit-worker/    # Cloudflare Worker - submissions
```

---

# Content Types & Data Files

| Type      | File                  | Use For                            |
|-----------|-----------------------|------------------------------------|
| Package   | `data/packages.json`  | Libraries, tools, frameworks       |
| Dataset   | `data/datasets.json`  | Data collections, benchmarks       |
| Resource  | `data/resources.json` | Blogs, tutorials, courses          |
| Book      | `data/books.json`     | Published books                    |
| Talk      | `data/talks.json`     | Videos, podcasts, interviews       |
| Paper     | `data/papers.json`    | Academic papers (nested by topic)  |
| Career    | `data/career.json`    | Career guides, industry insights   |
| Community | `data/community.json` | Conferences, meetups, events       |

**See `template.txt` for complete field schemas and examples.**

---

# Common Workflows

## Adding Content
1. Identify content type from table above
2. Copy template from `template.txt`
3. Add entry to appropriate `data/*.json` file
4. Validate JSON syntax
5. Build and test: `hugo server`

## Full Build
```bash
hugo --gc --minify              # Build static site
npx pagefind --site public      # Generate search index
# Or combined:
npm run build
```

## Regenerate Rankings/Embeddings
```bash
python3 scripts/generate_embeddings.py   # Vector search index
python3 scripts/rank_all_content.py      # ML-based rankings
python3 scripts/enrich_metadata.py       # LLM-enriched fields
```

## Check the Recsys Scoreboard
**Source of truth for "is the ranker getting better?"**

```bash
python3 scripts/scoreboard_status.py     # one-screen view of metrics.csv + replays.csv
```
Reads `reports/metrics.csv` (one row per rerank-with-eval) + `reports/replays.csv` (baseline-vs-candidate replays from `replay_eval.py`). Prints:
- row count + latest NDCG@10 / Hit-Rate@10 / MAP / @5 metrics
- delta vs prior comparable row (same `holdout_days` only — cross-window deltas are skipped per the eval gate)
- WARNING when rows mix `holdout_days` windows
- replay-history tail
- **decision-readiness guard**: RED/YELLOW/GREEN based on row density. Don't flip a ranker default (e.g., Ra2 `knn-bge`) until GREEN — that requires ≥3 rows at the same `holdout_days`.

## Check Analytics

**Worker:** `tech-econ-analytics-v2.pp712.workers.dev` (D1 DB: `1515d5fb`)
**Old worker:** `tech-econ-analytics.rawat-pranjal010.workers.dev` (read-only rollback)

```bash
# Quick check via API (no auth needed)
WORKER="https://tech-econ-analytics-v2.pp712.workers.dev"
curl -s "$WORKER/stats" | python3 -m json.tool           # Dashboard summary
curl -s "$WORKER/clicks?limit=20"                         # Top clicks
curl -s "$WORKER/searches?limit=20"                       # Top searches
curl -s "$WORKER/timeseries?days=7"                       # Daily timeseries
curl -s "$WORKER/clicks-by-country"                       # Clicks by country
curl -s "$WORKER/clicks-by-country?country=US"            # Clicks for specific country
curl -s "$WORKER/health"                                  # Health check

# Direct D1 queries via wrangler (from analytics-worker/ dir)
cd analytics-worker
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT name, section, click_count, last_clicked FROM content_clicks ORDER BY last_clicked DESC LIMIT 20"

npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT * FROM search_queries ORDER BY last_searched DESC LIMIT 10"

npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT country, SUM(click_count) as clicks FROM clicks_by_country GROUP BY country ORDER BY clicks DESC"
```

## Analytics health & runbook

**Quick check (no auth):**
```bash
curl -s https://tech-econ-analytics-v2.pp712.workers.dev/health | python3 -m json.tool
```
Healthy: `status=ok`, `last_write_age_seconds < 3600`, `write_errors_today=0`, `events_24h > 0`.
Degraded: `status=degraded` flips when last write is older than 24h or any write errors recorded today.

**Symptoms of a broken pipeline:**
- `/timeseries?days=N` returns nothing past a certain date
- All `last_clicked` timestamps in `/clicks` are stale
- `/health` → `status=degraded` (or `last_write_age_seconds` is null/huge)
- The reranker reports `Items with engagement: 0` and falls back to `weighted` scoring
- `python3 scripts/rank_all_content.py --source api` aborts with "REFUSING TO RERANK" (the staleness guard)

**Recovery (in order):**
1. **Backup first.** Never skip this step.
   ```bash
   cd analytics-worker && mkdir -p backups
   npx wrangler d1 export tech-econ-analytics-db --remote \
     --output=backups/$(date +%F)-pre-recovery.sql
   ```
2. **Re-run schema.** Idempotent — safe to call repeatedly.
   ```bash
   curl "https://tech-econ-analytics-v2.pp712.workers.dev/run-schema?key=$ADMIN_KEY"
   ```
3. **Smoke test** with a uniquely-named click:
   ```bash
   UNIQ="diag_$(date +%s)"
   curl -s -X POST https://tech-econ-analytics-v2.pp712.workers.dev/events \
     -H "Content-Type: application/json" -H "Origin: https://tech-econ.com" \
     --data "{\"v\":2,\"events\":[{\"t\":\"click\",\"sid\":\"diag\",\"p\":\"/diag\",\"ts\":$(date +%s)000,\"d\":{\"type\":\"card\",\"name\":\"$UNIQ\",\"section\":\"diag\"}}]}"
   sleep 3
   curl -s "https://tech-econ-analytics-v2.pp712.workers.dev/clicks?limit=200" | grep "$UNIQ"
   ```
4. **Re-check** `/health` → `last_write_age_seconds` should now be small.
5. If `/health` shows `last_error`, that's the actual D1 error (not just a generic failure).

`backups/` is gitignored — D1 dumps contain IPs and weak user IDs, never commit them.

**Configuration:**
- `hugo.toml` - Hugo site config (baseURL: tech-econ.com)
- `package.json` - npm dependencies and scripts

**Core Templates:**
- `layouts/_default/baseof.html` - Master layout
- `layouts/_default/home.html` - Homepage
- `layouts/[section]/list.html` - Section listing pages

**Automation Scripts:**
- `scripts/generate_embeddings.py` - Vector embeddings (bge-large-en-v1.5)
- `scripts/rank_all_content.py` - LightGBM ranking model
- `scripts/enrich_metadata.py` - LLM metadata enrichment
- `scripts/validate_data.py` - Data validation

**Styling:**
- `static/css/custom.css` - Main styles
- `static/js/tracker.js` - Analytics tracking

---

# ML Pipeline

## 1. Ranking Model (`scripts/rank_all_content.py`)
**Goal:** Create `model_score` to rank content everywhere on the site.

LightGBM-Tweedie model trained on engagement signals from D1 analytics:
| Signal | Weight | Description |
|--------|--------|-------------|
| Clicks | ×5.0 | Outbound link clicks |
| Impressions | ×0.5 | Card views |
| Viewability | ×0.1 | Per second visible (IAB 50%+) |
| Dwell | ×1.0 | Per minute on page |
| Scroll 90% | ×2.0 | Deep read indicator |
| Search clicks | ×3.0 | High-intent signal |
| Rage clicks | ×-2.0 | Frustration (negative) |
| Quick bounce | ×-1.0 | Left quickly (negative) |
| Reading ratio | ×0.5 | Actual vs expected read time (quality) |
| High-imp no-click | ×-1.0 | Impressions ≥10 with 0 clicks (irrelevant) |
| Co-view | ×0.1 | Viewed with other engaged items |
| Co-click | ×0.3 | Clicked with other engaged items |
| Deep session | ×1.5 | Part of high-engagement session |

**Cold-start:** Uses sentence-BERT similarity to propagate scores from similar engaged items.

## 2. Semantic Search (`scripts/generate_embeddings.py`)
**Goal:** Make search better and more contextual.

Hybrid keyword + vector search with RRF (Reciprocal Rank Fusion):
- **Embeddings:** bge-large-en-v1.5 (1024 dimensions)
- **Keyword:** MiniSearch (client-side)
- **Output:** `static/embeddings/search-*.json|bin`

## 3. Clustering & Carousels (`scripts/cluster_resources.py`)
**Goal:** Netflix-style exploratory discovery within sections.

Clustering happens within rigid sections (e.g., Talks → Videos → clusters). Each cluster becomes a carousel:
- **5-10 items per carousel** (target: 7)
- **Carousels ranked by score** (best clusters surface first)
- **Items within carousels ranked by score**
- **Carousels grouped into categories** for user filtering
- **Niche & interesting** — aids discovery, not just popular content

## 4. Discovery / Hero Topics
**Goal:** Even more niche topic pages with one "hero" item and related content trailing.

Used for deep-dive topic pages where one standout item leads, followed by related resources.

## 5. LLM Enrichment (`scripts/enrich_metadata.py`)
**Goal:** Create rich metadata and tags to power embeddings and search.

Uses Claude API to generate:
- Tags and categories
- Short descriptions
- "Best for" use cases
- Semantic cluster labels

Run enrichment **before** generating embeddings.

## 6. ALS Collaborative Filtering (`scripts/build_als_model.py`)
**Goal:** User-based recommendations (future).

Not currently useful — requires more user interaction data. When ready:
- **Library:** implicit (ALS)
- **Input:** Session-level interactions
- **Output:** User-item and item-item similarity matrices

## 7. A/B Testing Harness (`static/js/experiments.js` + `data/experiments.json`)
**Goal:** Measure ranker / re-ranker / surface changes before global rollout.

**Client-side bucketing (shipped, PR #18):**
- `data/experiments.json` declares experiments with `id`, `status`, `variants[]`
- Inlined into every page via `baseof.html` (`<script id="experiments-config">`); pipe `jsonify` through `safeJS` to avoid Hugo's html/template double-encoding (see RULES.md).
- `window.Experiments.getVariant('exp_id')` returns `"control" | "treatment" | null` deterministically per `(te_uid, experiment_id)` cookie hash.
- Pause an experiment by flipping `status` to `"paused"`; deterministic mapping persists.

**Tracker logging (shipped, PR #42):**
- `static/js/tracker.js:track()` reads `window.Experiments.getAllAssignments()` and attaches the result as `event.exp = {experiment_id: variant_id, ...}` to every payload when non-empty.

**Server-side ingestion (shipped, PR #46):**
- `analytics-worker/index.js`: `events.experiments` column added; INSERT path stores per-event variant assignments. Schema migration applied via `/run-schema` per RULES.md F15.

**Analysis script (shipped, PR #47):**
- `scripts/analyze_experiments.py`: per-variant CTR + statistical significance. Run as `python3 scripts/analyze_experiments.py --experiment <id>`.

**First experiment running (shipped, PR #48):**
- `harness_aa_v1` — A/A test (control_a vs control_b, 50/50). Validates pipeline health before any real treatment. Live since 2026-05-04.

**Open items:** See [`docs/roadmap.md`](docs/roadmap.md) Stream A — run analysis on `harness_aa_v1`, seed `replays.csv`, ship first real treatment (Re1 MMR vs baseline).

## 8. `lib/` toolkit (Phase 2 extractions)
Reusable modules pulled out of `scripts/rank_all_content.py` so they can be tested independently and re-used by future scripts:

| Module | Purpose | Use it from |
|---|---|---|
| `lib/freshness.py` | Exponential decay boost based on `first_seen` | `rank_all_content.py:calculate_freshness_scores` (now a thin wrapper) |
| `lib/d1_client.py` | HTTP wrapper around the analytics worker (read-only typed endpoints) | `scripts/evaluate_recsys.py`, future replays |
| `lib/diversity.py` | MMR re-ranking | `select_diverse_trending`, search-side `mmr.js` mirror |
| `lib/eval_runner.py` | Offline NDCG/Hit-Rate gate; appends `metrics.csv` | `scripts/evaluate_recsys.py`, eval-gate in `rank_all_content.py` |
| `lib/replay.py` | Baseline-vs-candidate replay | `scripts/replay_eval.py` |
| `lib/recsys_config.py` | Typed loader for `data/recsys_config.json` | All ranker tunables; `from lib.recsys_config import load` |
| `lib/cold_start.py` | k-NN cold-start propagation (TF-IDF / BGE) | `rank_all_content.py:propagate_cold_start_scores` |
| `lib/sample_weights.py` | Dwell-weighted positive samples (Ra1) | `rank_all_content.py` LightGBM training |
| `lib/model_cache.py` | Persist/load LightGBM booster (Ra7) | `rank_all_content.py:_save_model_artifact` |
| `lib/d1_sessions.py` | Group D1 events into sessions | `lib/eval_runner.py` |
| `lib/holdout.py` | Temporal split for offline eval | `lib/eval_runner.py` |
| `lib/metrics.py` | NDCG / Hit-Rate / MAP / Precision implementations | `lib/eval_runner.py` |
| `lib/score_combiner.py` | Blend engagement + predictions + freshness + citations → final score | `rank_all_content.py:combine_scores` |
| `lib/trending.py` | Select trending candidates + MMR rerank + build embedding lookup | `rank_all_content.py:select_trending` |
| `lib/data_io.py` | Atomic JSON read/write with output metadata stamping | All scripts writing data/*.json |
| `lib/schemas.py` | TypedDicts for all JSON shapes in the recsys pipeline | Static typing + runtime sanity checks |

---

# Slash Commands

## `/rerank`
Refresh content rankings with latest engagement data.
1. Fetch clicks, impressions, dwell, scroll depth from D1
2. Run `python3 scripts/rank_all_content.py`
3. Updates `model_score` in all data/*.json files
4. Cold-start items get scores via similarity propagation
5. Commit and report: items updated, top gainers, cold-start count

## `/review-clusters`
Quality check clustering and carousels.
1. Load `data/resource_clusters.json` (or other cluster files)
2. Review each cluster: label accuracy, item coherence, size (5-10)
3. Log issues to `scripts/cluster_assignments_review.csv`
4. Columns: item_name, current_cluster, suggested_cluster, issue, notes
5. Issue types: miscategorized, orphan, bad_label, too_small, too_large
6. Summarize findings and recommend re-clustering if needed

## `/enrich`
Add LLM-generated metadata to new or poor items.
1. Find items missing: tags, description, best_for, semantic_cluster
2. Run `python3 scripts/enrich_metadata.py`
3. Regenerate embeddings: `python3 scripts/generate_embeddings.py`
4. Commit and report: items enriched, failures, manual review needed

---

---

# Learned Rules

**Scaffold files are shared — copy, don't invent.**
Portable skeleton files (`SYSTEM.md`, `decisions.md`, `docs/chunks/`, `plan.md`) exist in sibling projects (`~/Code/delivery/`, `~/Code/econirl/`). Before creating any scaffold file, `cp` the sibling version.
- Wrong: drafting `SYSTEM.md` from scratch.
- Right: `cp ~/Code/delivery/SYSTEM.md .`

---

# Tech Stack Quick Reference

- **Static Site**: Hugo
- **Search**: Hybrid keyword (MiniSearch) + semantic (bge-large-en-v1.5) with RRF fusion
- **Ranking**: LightGBM-Tweedie → `model_score`
- **Recommendations**: ALS collaborative filtering
- **Clustering**: K-means on bge embeddings
- **Backend**: Cloudflare Workers + D1 Database
- **Frontend**: Vanilla JS, Leaflet maps, AOS animations
