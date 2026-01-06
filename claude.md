# Core Rules

**Always follow these rules:**

1. **Always `git push` when done** - Push changes after completing work
2. **Never remove content** - Content removed is content lost
   - If something seems outdated, find a new home for it
   - Archive to `data/archive/` rather than delete
3. **Use `template.txt`** for content schemas when adding new entries
4. **Update `CHANGELOG.md`** after making changes - 1-2 line summary per day
5. When changelog.md gets too large, dump into claude_history 

---

# Project Overview

**tech-econ.com** is a curated directory of resources for tech economists, data scientists, and applied researchers.

**High-Level Objectives:**
- Aggregate and organize tools, datasets, papers, and learning resources
- Help researchers discover relevant content through search, browsing, and recommendations
- Maintain quality through ML-based ranking and curation
- Provide learning paths and career guidance
- Focus on joyous learning, and discovery

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

## Ranking Model (`scripts/rank_all_content.py`)
LightGBM-Tweedie model trained on engagement data. Outputs `model_score` field.

**Engagement signals (from D1 analytics):**
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

**Cold-start handling:** Uses sentence-BERT similarity (all-MiniLM-L6-v2) to propagate scores from similar engaged items.

## Semantic Search (`scripts/generate_embeddings.py`)
Hybrid keyword + vector search with RRF (Reciprocal Rank Fusion).

- **Embeddings:** bge-large-en-v1.5 (1024 dimensions)
- **Keyword:** MiniSearch (client-side)
- **Output files:**
  - `static/embeddings/search-metadata.json` - Item data
  - `static/embeddings/search-embeddings.bin` - Binary Float32 vectors

## Topic Clustering (`scripts/cluster_resources.py`)
Creates Netflix-style carousels by grouping semantically similar items.

- **Algorithm:** K-means on embeddings
- **Cluster size:** 4-10 items (target: 7)
- **Output:** `data/resource_clusters.json`

## Collaborative Filtering (`scripts/build_als_model.py`)
ALS (Alternating Least Squares) for item-item recommendations.

- **Library:** implicit
- **Input:** Session-level interactions (dwell, clicks, search queries)
- **Output:** Item similarity matrix for "related items"

## LLM Enrichment (`scripts/enrich_metadata.py`)
Uses Claude API to generate:
- Tags and categories
- Short descriptions
- "Best for" use cases
- Semantic cluster labels

---

# Tech Stack Quick Reference

- **Static Site**: Hugo
- **Search**: Hybrid keyword (MiniSearch) + semantic (bge-large-en-v1.5) with RRF fusion
- **Ranking**: LightGBM-Tweedie → `model_score`
- **Recommendations**: ALS collaborative filtering
- **Clustering**: K-means on bge embeddings
- **Backend**: Cloudflare Workers + D1 Database
- **Frontend**: Vanilla JS, Leaflet maps, AOS animations
