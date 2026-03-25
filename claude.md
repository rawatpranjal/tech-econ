# Mindset

You are a senior staff Google engineer. Your user respects your judgement. You will think, deliberate, and plan all major decisions. You take time to research and be thorough. Better well-planned than quick-and-dirty — this repo is getting large so we need much more thought than blazing fast execution. Ask, think, search, research, test — but do it the right way.

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

**Load in scripts:**
```python
from dotenv import load_dotenv
load_dotenv('.claude/secrets.env')
```

**⚠️ NEVER paste keys in chat — they get logged!**

---

# Pre-Commit Checklist

**Must pass before pushing:**
```bash
python3 scripts/validate_data.py      # JSON schema validation
npm run build                          # Hugo + pagefind index
```

**If you modified rankings/search:**
```bash
python3 scripts/rank_all_content.py    # Update model_score
python3 scripts/generate_embeddings.py # Regenerate vectors
```

---

# Don't Touch (Fragile)

- **`papers.json` vs `papers_flat.json`** — Dual system, easy to desync. Use `papers_flat.json` for ranking/search.
- **D1 analytics schema** — Ranking script depends on exact table structure
- **No test suite** — `npm test` is a placeholder; validation is manual

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

## Check Analytics
```bash
# Run from analytics-worker/ directory
cd analytics-worker

# Recent page views (last 6 hours)
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT path, view_count, last_viewed FROM page_views WHERE last_viewed > datetime('now', '-6 hours') ORDER BY last_viewed DESC"

# Recent clicks
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT name, section, click_count, last_clicked FROM content_clicks WHERE last_clicked > datetime('now', '-6 hours') ORDER BY last_clicked DESC LIMIT 20"

# Recent impressions
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT name, section, impression_count, last_seen FROM content_impressions WHERE last_seen > datetime('now', '-6 hours') ORDER BY last_seen DESC LIMIT 20"

# Recent searches
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT * FROM search_queries ORDER BY last_searched DESC LIMIT 10"

# Web vitals (LCP, FID, CLS)
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT metric, rating, COUNT(*) as count, AVG(value) as avg_value FROM web_vitals GROUP BY metric, rating"

# Client errors
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT path, error_type, message FROM client_errors ORDER BY created_at DESC LIMIT 10"

# Referrer sources
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT source, session_count FROM referrer_stats ORDER BY session_count DESC"

# Item co-occurrence (for recommendations)
npx wrangler d1 execute tech-econ-analytics-db --remote --command \
  "SELECT item_a, item_b, coview_count FROM item_cooccurrence ORDER BY coview_count DESC LIMIT 20"
```

---

# Key Files Reference

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

# Tech Stack Quick Reference

- **Static Site**: Hugo
- **Search**: Hybrid keyword (MiniSearch) + semantic (bge-large-en-v1.5) with RRF fusion
- **Ranking**: LightGBM-Tweedie → `model_score`
- **Recommendations**: ALS collaborative filtering
- **Clustering**: K-means on bge embeddings
- **Backend**: Cloudflare Workers + D1 Database
- **Frontend**: Vanilla JS, Leaflet maps, AOS animations
