# Homepage: Simplify & Automate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 14-row manually-curated homepage with 5 fully-algorithmic rows, add a weekly GitHub Actions auto-refresh, and add a Playwright screenshot dev tool for fast visual iteration.

**Architecture:** `generate_homepage_rows.py` is rewritten from ~1238 lines to ~200, building 5 rows (Trending/New/Packages/Datasets/Talks) entirely from `global_rankings.json` and the content JSON files — no manual input files needed. A new GitHub Actions workflow runs the script weekly (Monday 3am UTC) and commits the result before the existing Monday 8am deploy. A `scripts/screenshot-homepage.js` Playwright script enables screenshot-driven visual iteration.

**Tech Stack:** Python 3.11 (stdlib only), GitHub Actions, Playwright (Node.js), Hugo

**Spec:** `docs/superpowers/specs/2026-04-05-homepage-simplify-automate-design.md`

---

## Task 1: Update validator thresholds

The existing `autoresearch/checks/check_homepage_rows.py` expects 10–15 rows, 7 content types, and 60+ unique items. Our new design produces 5 rows and ~40 items. Update thresholds before rewriting the generator so the validator acts as a passing test target.

**Files:**
- Modify: `autoresearch/checks/check_homepage_rows.py:28-34`

- [ ] **Step 1: Run validator against current output to confirm baseline**

```bash
python3 autoresearch/checks/check_homepage_rows.py
```

Expected: PASS (current 14-row output satisfies existing thresholds).

- [ ] **Step 2: Update thresholds**

In `autoresearch/checks/check_homepage_rows.py`, replace lines 28–34:

```python
# Thresholds
MIN_ROWS = 10
MAX_ROWS = 15
MIN_ITEMS_PER_ROW = 3
MAX_ITEMS_PER_ROW = 12
MAX_ALLOWED_DUPLICATES = 5
EXPECTED_TYPES = {"package", "dataset", "resource", "paper", "talk", "career", "community"}
MIN_UNIQUE_ITEMS = 60
```

With:

```python
# Thresholds
MIN_ROWS = 5
MAX_ROWS = 7
MIN_ITEMS_PER_ROW = 3
MAX_ITEMS_PER_ROW = 12
MAX_ALLOWED_DUPLICATES = 5
EXPECTED_TYPES = {"package", "dataset", "resource", "talk"}
MIN_UNIQUE_ITEMS = 30
```

Rationale: 5 fixed rows; `package`/`dataset`/`talk` are guaranteed by dedicated rows; `resource` appears in Trending/New; `career`/`community` are no longer surfaced on the homepage; ~40 unique items across 5×8 rows satisfies the 30 floor.

- [ ] **Step 3: Run validator again — it should now fail on current 14-row output (too many rows)**

```bash
python3 autoresearch/checks/check_homepage_rows.py
```

Expected: `FAIL  Row count 14 within [5, 7]`

This confirms the validator is wired to our new target. It will pass again after Task 3.

- [ ] **Step 4: Commit**

```bash
git add autoresearch/checks/check_homepage_rows.py
git commit -m "chore: update homepage validator thresholds for 5-row design"
```

---

## Task 2: Rewrite generate_homepage_rows.py

Replace the 1238-line script with a ~200-line version that builds exactly 5 algorithmic rows. The output schema (`generated_at`, `stats`, `rows[]`) is **unchanged** — templates require zero modifications.

**Files:**
- Modify: `scripts/generate_homepage_rows.py` (full rewrite)

- [ ] **Step 1: Replace the entire file with the new implementation**

```python
#!/usr/bin/env python3
"""
Homepage Row Generator — Simplified
Generates 5 algorithmic rows. Zero manual curation required.

Rows:
  0. Trending Now  (hero template)    — top engaged non-cold-start, type-diverse
  1. New This Month (standard)        — impressions > 0, deep_sessions < 5
  2. Top Packages   (standard)        — packages.json sorted by model_score
  3. Top Datasets   (standard)        — datasets.json sorted by model_score
  4. Talks Worth Watching (standard)  — talks.json sorted by model_score

Usage:
    python3 scripts/generate_homepage_rows.py
    python3 scripts/generate_homepage_rows.py --output data/homepage_rows.json
"""

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


DATA_DIR = Path(__file__).parent.parent / "data"

TEMPLATE_HERO = "hero"
TEMPLATE_STANDARD = "standard"

MAX_SAME_TYPE_PER_ROW = 3
ROW_ITEMS = 8  # target items per non-hero row
HERO_ITEMS = 10  # target items for hero/trending row


def load_json(path: Path) -> dict | list | None:
    """Load a JSON file, return None if missing or invalid."""
    if not path.exists():
        print(f"  Warning: {path.name} not found, skipping")
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Warning: Failed to load {path.name}: {e}")
        return None


def load_content_lookup(data_dir: Path) -> dict[str, dict]:
    """Build name -> metadata dict from all content files."""
    lookup: dict[str, dict] = {}
    content_files = {
        "packages.json": "package",
        "datasets.json": "dataset",
        "resources.json": "resource",
        "papers_flat.json": "paper",
        "talks.json": "talk",
        "career.json": "career",
        "community.json": "community",
        "books.json": "book",
    }
    for filename, content_type in content_files.items():
        data = load_json(data_dir / filename)
        if data is None:
            continue
        items = data if isinstance(data, list) else []
        for item in items:
            name = item.get("name") or item.get("title", "")
            if not name:
                continue
            url = (
                item.get("url")
                or item.get("github_url")
                or item.get("docs_url")
                or ""
            )
            image_url = item.get("image_url", "")
            if not image_url:
                if content_type == "package":
                    github_url = item.get("github_url") or ""
                    if "github.com/" in github_url:
                        owner = github_url.split("github.com/")[1].split("/")[0]
                        image_url = f"https://github.com/{owner}.png?size=128"
                elif content_type == "book":
                    isbn = item.get("isbn") or ""
                    if isbn:
                        image_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
            key = name.lower().strip()
            lookup[key] = {
                "name": name,
                "type": content_type,
                "category": item.get("category", ""),
                "description": item.get("description") or item.get("summary", ""),
                "url": url,
                "image_url": image_url,
                "tags": item.get("tags", []),
                "model_score": item.get("model_score", 0.0),
            }
    return lookup


def build_score_lookup(rankings: list[dict]) -> dict[str, float]:
    """Build name -> score lookup from global_rankings."""
    return {r["name"].lower().strip(): r.get("score", 0.0) for r in rankings}


def make_item(ranking_entry: dict, content_lookup: dict) -> dict:
    """Build a normalized item dict from a ranking entry + content metadata."""
    name = ranking_entry.get("name", "")
    key = name.lower().strip()
    meta = content_lookup.get(key, {})
    return {
        "name": name,
        "type": ranking_entry.get("type", meta.get("type", "unknown")),
        "category": ranking_entry.get("category", meta.get("category", "")),
        "description": ranking_entry.get("description", meta.get("description", "")),
        "url": ranking_entry.get("url", meta.get("url", "")),
        "image_url": ranking_entry.get("image_url", meta.get("image_url", "")),
        "score": ranking_entry.get("score", 0.0),
        "cold_start": ranking_entry.get("cold_start", True),
        "signals": ranking_entry.get("signals", {}),
    }


def make_item_from_meta(meta: dict, score_lookup: dict) -> dict:
    """Build a normalized item dict from content metadata, with score from rankings."""
    name = meta.get("name", "")
    key = name.lower().strip()
    # Prefer engagement-based score from rankings; fall back to model_score from content file
    score = score_lookup[key] if key in score_lookup else meta.get("model_score", 0.0)
    return {
        "name": name,
        "type": meta.get("type", "unknown"),
        "category": meta.get("category", ""),
        "description": meta.get("description", ""),
        "url": meta.get("url", ""),
        "image_url": meta.get("image_url", ""),
        "score": score,
        "cold_start": key not in score_lookup,
        "signals": {},
    }


def apply_type_cap(items: list[dict], max_same_type: int) -> list[dict]:
    """Cap items to max_same_type per content type."""
    type_counts: dict[str, int] = defaultdict(int)
    result = []
    for item in items:
        t = item.get("type", "unknown")
        if type_counts[t] < max_same_type:
            type_counts[t] += 1
            result.append(item)
    return result


def dedup_against_used(items: list[dict], used: set[str]) -> list[dict]:
    """Remove items already in the used set."""
    return [i for i in items if i["name"].lower().strip() not in used]


def mark_used(items: list[dict], used: set[str]) -> None:
    """Record item names as used."""
    for item in items:
        used.add(item["name"].lower().strip())


def build_trending_now(
    rankings: list[dict], content_lookup: dict, used: set[str]
) -> dict:
    """Row 0: top engaged non-cold-start items, max 3 per type."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if not r.get("cold_start", True)
    ]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    items = candidates[:HERO_ITEMS]
    mark_used(items, used)
    return {
        "id": "trending-now",
        "row_type": "trending",
        "title": "Trending Now",
        "description": "What the community is reading and clicking most",
        "template": TEMPLATE_HERO,
        "items": items,
    }


def build_new_this_month(
    rankings: list[dict], content_lookup: dict, used: set[str]
) -> dict:
    """Row 1: items with some impressions but few deep sessions (recently discovered)."""
    candidates = [
        make_item(r, content_lookup)
        for r in rankings
        if r.get("signals", {}).get("impressions", 0) > 0
        and r.get("signals", {}).get("deep_sessions", 0) < 5
    ]
    candidates = dedup_against_used(candidates, used)
    candidates = apply_type_cap(candidates, MAX_SAME_TYPE_PER_ROW)
    candidates.sort(
        key=lambda x: x.get("signals", {}).get("impressions", 0), reverse=True
    )
    items = candidates[:ROW_ITEMS]
    mark_used(items, used)
    return {
        "id": "new-this-month",
        "row_type": "new_this_month",
        "title": "New This Month",
        "description": "Recently surfaced — getting noticed but not yet deep-dived",
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def build_type_row(
    type_filter: str,
    row_id: str,
    title: str,
    description: str,
    content_lookup: dict,
    score_lookup: dict,
    used: set[str],
) -> dict:
    """Generic row: filter by type, sort by score, take top ROW_ITEMS."""
    candidates = [
        make_item_from_meta(meta, score_lookup)
        for meta in content_lookup.values()
        if meta.get("type") == type_filter
    ]
    candidates = dedup_against_used(candidates, used)
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    items = candidates[:ROW_ITEMS]
    mark_used(items, used)
    return {
        "id": row_id,
        "row_type": type_filter,
        "title": title,
        "description": description,
        "template": TEMPLATE_STANDARD,
        "items": items,
    }


def generate_rows(data_dir: Path) -> dict:
    """Build all 5 rows and return the homepage_rows.json payload."""
    rankings_data = load_json(data_dir / "global_rankings.json") or {}
    rankings: list[dict] = rankings_data.get("rankings", [])

    content_lookup = load_content_lookup(data_dir)
    score_lookup = build_score_lookup(rankings)

    used: set[str] = set()
    rows = [
        build_trending_now(rankings, content_lookup, used),
        build_new_this_month(rankings, content_lookup, used),
        build_type_row(
            "package", "top-packages", "Top Packages",
            "The most-used tools and libraries in the tech-econ stack",
            content_lookup, score_lookup, used,
        ),
        build_type_row(
            "dataset", "top-datasets", "Top Datasets",
            "Datasets researchers keep coming back to",
            content_lookup, score_lookup, used,
        ),
        build_type_row(
            "talk", "talks-worth-watching", "Talks Worth Watching",
            "Lectures, interviews, and keynotes worth your time",
            content_lookup, score_lookup, used,
        ),
    ]

    total_items = sum(len(r["items"]) for r in rows)
    unique_types: set[str] = set(
        item.get("type", "unknown")
        for row in rows
        for item in row["items"]
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_rows": len(rows),
            "total_items": total_items,
            "unique_types": sorted(unique_types),
            "type_count": len(unique_types),
            "critique_iterations": 0,
        },
        "critique_log": [],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate homepage rows (5 algorithmic rows, zero manual curation)"
    )
    parser.add_argument(
        "--output",
        default="data/homepage_rows.json",
        help="Output file path (default: data/homepage_rows.json)",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    output_path = Path(__file__).parent.parent / args.output

    print("Homepage Row Generator")
    print("=" * 50)
    result = generate_rows(data_dir)

    print(f"\nWriting {len(result['rows'])} rows to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"\nDone.")
    print(f"  Rows:   {result['stats']['total_rows']}")
    print(f"  Items:  {result['stats']['total_items']}")
    print(f"  Types:  {', '.join(result['stats']['unique_types'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/generate_homepage_rows.py
git commit -m "feat: rewrite generate_homepage_rows.py — 5 algorithmic rows, zero manual curation"
```

---

## Task 3: Run script, validate, and rebuild

Confirm the new script produces valid output, the validator passes, and the site builds cleanly.

**Files:**
- Output: `data/homepage_rows.json` (regenerated)

- [ ] **Step 1: Run the generator**

```bash
python3 scripts/generate_homepage_rows.py
```

Expected output:
```
Homepage Row Generator
==================================================

Writing 5 rows to .../data/homepage_rows.json...

Done.
  Rows:   5
  Items:  ~42
  Types:  dataset, package, resource, talk, ...
```

If you see `Warning: X not found, skipping`, that's fine — it means a content file is missing, not an error.

- [ ] **Step 2: Run validator — should PASS**

```bash
python3 autoresearch/checks/check_homepage_rows.py
```

Expected:
```
PASS  Row count 5 within [5, 7]
PASS  Row 'trending-now' item count N within [3, 12]
...
RESULT: PASS (0 warning(s))
```

If it fails on `EXPECTED_TYPES`, check what types your Trending/New rows actually contain:
```bash
python3 -c "
import json
with open('data/homepage_rows.json') as f:
    d = json.load(f)
types = set(item['type'] for row in d['rows'] for item in row['items'])
print('Types found:', sorted(types))
"
```

If `resource` is missing, it means `global_rankings.json` has no non-cold-start resources. In that case, update `EXPECTED_TYPES` in `autoresearch/checks/check_homepage_rows.py` to remove `"resource"` (it's a best-effort check, not a hard requirement).

- [ ] **Step 3: Build the site**

```bash
npm run build
```

Expected: Hugo builds without errors. Pagefind indexes successfully.

- [ ] **Step 4: Commit the regenerated data**

```bash
git add data/homepage_rows.json
git commit -m "data: regenerate homepage_rows.json — 5 algorithmic rows"
```

---

## Task 4: Add GitHub Actions weekly refresh workflow

New workflow runs Monday 3am UTC — 5 hours before the existing deploy at Monday 8am. It regenerates `homepage_rows.json` and commits it. The deploy job picks up the fresh file automatically.

**Files:**
- Create: `.github/workflows/refresh-homepage.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
name: Refresh Homepage Rows

on:
  schedule:
    - cron: '0 3 * * 1'  # Monday 3am UTC (before the 8am deploy)
  workflow_dispatch:      # Allow manual trigger via GitHub UI

permissions:
  contents: write

jobs:
  refresh:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Generate homepage rows
        run: python3 scripts/generate_homepage_rows.py

      - name: Validate output
        run: python3 autoresearch/checks/check_homepage_rows.py

      - name: Commit and push if changed
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git diff --quiet data/homepage_rows.json || (
            git add data/homepage_rows.json &&
            git commit -m "Auto-refresh homepage rows ($(date +%Y-%m-%d))" &&
            git push
          )
```

- [ ] **Step 2: Verify the workflow appears in GitHub**

```bash
git add .github/workflows/refresh-homepage.yml
git commit -m "ci: add weekly homepage rows refresh workflow"
git push
```

Then open `https://github.com/rawatpranjal/tech-econ/actions` and confirm the workflow `Refresh Homepage Rows` appears. Trigger it manually via "Run workflow" to smoke-test before the first scheduled run.

---

## Task 5: Add Playwright screenshot dev tool

Installs Playwright as a devDependency and adds a `scripts/screenshot-homepage.js` script. Enables a tight visual iteration loop: change template/CSS → screenshot → read image → repeat.

**Files:**
- Modify: `package.json` (add devDependency + screenshot script)
- Create: `scripts/screenshot-homepage.js`

- [ ] **Step 1: Install Playwright**

```bash
npm install --save-dev playwright
npx playwright install chromium
```

Expected: `node_modules/playwright` created, Chromium browser downloaded (~150MB).

- [ ] **Step 2: Create the screenshot script**

Create `scripts/screenshot-homepage.js`:

```javascript
#!/usr/bin/env node
/**
 * screenshot-homepage.js
 * Takes full-page and above-the-fold screenshots of the Hugo dev server.
 *
 * Usage:
 *   node scripts/screenshot-homepage.js
 *   node scripts/screenshot-homepage.js --port 1313 --out /tmp/homepage.png
 *
 * Output:
 *   /tmp/homepage.png       — full page
 *   /tmp/homepage-fold.png  — above the fold (1440×900 viewport)
 */

const { chromium } = require('playwright');

async function main() {
  const args = process.argv.slice(2);

  const portIdx = args.indexOf('--port');
  const port = portIdx !== -1 ? args[portIdx + 1] : '1313';

  const outIdx = args.indexOf('--out');
  const out = outIdx !== -1 ? args[outIdx + 1] : '/tmp/homepage.png';
  const foldOut = out.replace(/\.png$/, '-fold.png');

  const url = `http://localhost:${port}`;
  console.log(`Screenshotting ${url} ...`);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
  } catch (e) {
    console.error(`Could not reach ${url} — is hugo server running?`);
    console.error(`Start it with: hugo server --port ${port} &`);
    await browser.close();
    process.exit(1);
  }

  // Full page
  await page.screenshot({ path: out, fullPage: true });
  console.log(`Full page  → ${out}`);

  // Above the fold only
  await page.screenshot({ path: foldOut, fullPage: false });
  console.log(`Above fold → ${foldOut}`);

  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
```

- [ ] **Step 3: Add npm script for convenience**

In `package.json`, add `"screenshot"` to the scripts section:

```json
{
  "scripts": {
    "build": "hugo --gc --minify && npx pagefind --site public",
    "pagefind": "npx pagefind --site public",
    "screenshot": "node scripts/screenshot-homepage.js",
    "test": "echo \"Error: no test specified\" && exit 1"
  }
}
```

- [ ] **Step 4: Test the screenshot loop**

In one terminal:
```bash
hugo server --port 1313
```

In another:
```bash
node scripts/screenshot-homepage.js
```

Expected:
```
Screenshotting http://localhost:1313 ...
Full page  → /tmp/homepage.png
Above fold → /tmp/homepage-fold.png
```

Confirm both PNG files exist and are non-zero:
```bash
ls -lh /tmp/homepage.png /tmp/homepage-fold.png
```

- [ ] **Step 5: Commit**

```bash
git add package.json scripts/screenshot-homepage.js
git commit -m "feat: add Playwright screenshot tool for visual dev loop"
git push
```

---

## Verification Checklist

After all tasks complete:

- [ ] `python3 scripts/generate_homepage_rows.py` produces exactly 5 rows
- [ ] `python3 autoresearch/checks/check_homepage_rows.py` → `RESULT: PASS`
- [ ] `npm run build` exits 0
- [ ] `.github/workflows/refresh-homepage.yml` visible in GitHub Actions; manual trigger succeeds
- [ ] `node scripts/screenshot-homepage.js` produces `/tmp/homepage.png` and `/tmp/homepage-fold.png`
- [ ] No items appear in more than one row (confirmed by validator duplicate check)
- [ ] Trending row contains ≥3 different content types

---

## Post-Implementation: Visual Iteration Loop

With the screenshot tool in place, use this loop during any future CSS/template changes:

```bash
# Terminal 1 — leave running
hugo server --port 1313

# Terminal 2 — run after each change
node scripts/screenshot-homepage.js
# Then ask Claude to read /tmp/homepage.png and give feedback
```

## Phase 2 (Future): Full Pipeline Automation

To also auto-refresh engagement rankings (not just homepage rows), add these secrets to GitHub repo settings:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_D1_DB_ID`  
- `CLOUDFLARE_API_TOKEN`

Then prepend to the `refresh` job in `refresh-homepage.yml`:
```yaml
- name: Refresh engagement rankings
  env:
    CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    CLOUDFLARE_D1_DB_ID: ${{ secrets.CLOUDFLARE_D1_DB_ID }}
    CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
  run: python3 scripts/rank_all_content.py

- name: Stage updated rankings
  run: git add data/global_rankings.json
```
