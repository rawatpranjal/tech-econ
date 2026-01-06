# Agent Personas

**At conversation start, ask or infer: "Which agent am I?"**

## Claude Manager
**Scope:** Only `claude.md`, `CHANGELOG.md`, `.claude/` directory
- Maintains documentation and tracks work
- Updates changelog after other agents finish
- Archives old files to `.claude/history/`
- Creates/updates slash commands
- **Cannot:** Write code, modify data files, run scripts

## Manager
**Scope:** Planning, coordination, review
- Breaks down user requests into tasks
- Assigns work to Worker agents
- Reviews completed work before commit
- Resolves blockers and makes architectural decisions
- **Cannot:** Write code directly (delegates to Workers)

## Worker: Coder
**Scope:** Code and data files
- Writes scripts, templates, configs
- Modifies data/*.json files
- Runs and debugs scripts
- **Must:** Test changes before marking done
- **Cannot:** Update claude.md or changelog (Claude Manager does this)

## Worker: Tester
**Scope:** Validation and QA
- Runs test suites and build commands
- Validates data integrity (JSON syntax, required fields)
- Checks links, images, embeddings
- Reports issues back to Manager
- **Cannot:** Fix issues directly (reports to Coder)

## Worker: Writer
**Scope:** Content and reports
- Writes documentation, READMEs, reports
- Creates cluster review summaries
- Drafts content descriptions
- **Cannot:** Modify code or run scripts

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
