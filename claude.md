# Core Rules

**Always follow these rules:**

1. **Always `git push` when done** - Push changes after completing work
2. **Never remove content** - Content removed is content lost
   - If something seems outdated, find a new home for it
   - Archive to `data/archive/` rather than delete
3. **Use `template.txt`** for content schemas when adding new entries
4. **Update `CHANGELOG.md`** after making changes - 1-2 line summary per day

---

# Project Overview

**tech-econ.com** is a curated directory of resources for tech economists, data scientists, and applied researchers.

**High-Level Objectives:**
- Aggregate and organize tools, datasets, papers, and learning resources
- Help researchers discover relevant content through search, browsing, and recommendations
- Maintain quality through ML-based ranking and curation
- Provide learning paths and career guidance

**Current Content:**
- 188 Python/R packages | 243 datasets | 111 learning resources
- 50 talks/podcasts | 13 career guides | 63 conferences
- Academic papers organized by research topic

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

# Tech Stack Quick Reference

- **Static Site**: Hugo
- **Search**: Fuse.js (client), Pagefind (index), bge-large-en-v1.5 (embeddings)
- **Ranking**: LightGBM-Tweedie model
- **Backend**: Cloudflare Workers + D1 Database
- **Frontend**: Vanilla JS, Leaflet maps, AOS animations
