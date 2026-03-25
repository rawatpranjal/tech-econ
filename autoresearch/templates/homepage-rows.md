# Task: Homepage Rows — Critique and Improve

You are an expert editorial curator and software engineer reviewing the homepage content rows for tech-econ.com. Your job is to make the homepage feel like a Netflix-quality discovery experience: every row tells a story, every item belongs, and a researcher scrolling the page would find at least 5 rows compelling.

## Constraints

You MAY modify:
- `scripts/generate_homepage_rows.py` — the row generator logic
- `data/homepage_rows.json` — the generated output (only if regenerating is impractical)
- `data/staff_picks.json` — the hand-curated picks list

You MUST NOT modify:
- `layouts/` — Hugo templates
- `hugo.toml` — site config
- `analytics-worker/` — Cloudflare worker code
- `autoresearch/` — autoresearch infrastructure itself

## Step-by-Step Instructions

### Step 1: Generate rows with no auto-critique

```bash
python3 scripts/generate_homepage_rows.py --critique-iterations 0
```

### Step 2: Read every row in detail

READ `data/homepage_rows.json` completely. For every row, read:
- The row title
- The template type
- Every single item: name, type, category, description

Do not summarize or skip. You must see every item to critique effectively.

### Step 3: Critique each row like a harsh editor

For each row ask:
1. Does the title accurately describe what's in it?
2. Does every item actually belong? Flag any item that feels out of place.
3. Is there good type diversity? (Not all packages, not all papers)
4. Does this row offer something the others don't? Is it redundant?
5. Are there gaps — important content types missing from the whole homepage?
6. Would a researcher browsing the site find this row interesting or skip it?

Write down your critique findings before making any changes.

### Step 4: Fix the generator

Based on your critique, modify `scripts/generate_homepage_rows.py` to fix:
- Selection logic that pulls wrong items
- Type diversity constraints that are too loose or strict
- Rows that are conceptually redundant
- Missing fallback logic for sparse sections

### Step 5: Regenerate with critique loop

```bash
python3 scripts/generate_homepage_rows.py --critique-iterations 3
```

### Step 6: Validate with Hugo build

```bash
cd /Users/pranjal/Code/tech-econ && hugo --gc --minify
```

Fix any build errors before proceeding.

### Step 7: Final review

Read `data/homepage_rows.json` again. Ask yourself:
- Does the homepage feel like Netflix? (Multiple distinct story threads)
- Is each row genuinely useful to a tech economist or data scientist?
- Are there at least 10 rows with 5+ items each?
- Are all 8 content types (package, dataset, resource, paper, talk, career, community, book) represented somewhere?

## Success Criteria

- 10-15 rows in `data/homepage_rows.json`
- Each row has 5-12 items
- No item appears in more than one row
- All 8 content types present across all rows
- Total unique items >= 60
- Each row title matches its contents
- No obviously misplaced items (e.g., a career portal in the "Foundational Papers" row)
- Hugo build passes: `hugo --gc --minify`

## Quality Bar

A good homepage row makes a researcher think "oh, I didn't know about half of these — I should explore." A bad row feels like a random sample from a database query. The difference is curation: choosing items that form a coherent set with a clear theme.
