# LLM Enrichment

Run Claude API enrichment on new or poor-quality items.

## Steps

1. **Identify items needing enrichment:**

   New items (missing enriched fields):
   ```bash
   # Find items without tags, description, or best_for
   python3 -c "
   import json
   for f in ['packages', 'datasets', 'resources', 'talks', 'books']:
       data = json.load(open(f'data/{f}.json'))
       items = data if isinstance(data, list) else data.get('items', data.values())
       for item in items if isinstance(items, list) else []:
           if not item.get('tags') or not item.get('description'):
               print(f'{f}: {item.get(\"name\", item.get(\"title\", \"unknown\"))}')
   "
   ```

2. **Run enrichment script:**

   For all unenriched:
   ```bash
   python3 scripts/enrich_metadata.py
   ```

   For specific items (edit script or pass args):
   ```bash
   python3 scripts/enrich_metadata.py --items "item1,item2,item3"
   ```

3. **Review enriched fields:**
   - Check generated tags are relevant
   - Verify descriptions are accurate
   - Confirm "best_for" suggestions make sense

4. **Re-generate embeddings** (enrichment changes text):
   ```bash
   python3 scripts/generate_embeddings.py
   ```

5. **Commit changes:**
   ```bash
   git add data/*.json static/embeddings/
   git commit -m "LLM enrichment: add metadata for new items"
   git push
   ```

Report: Items enriched, any failures, suggested manual review items.
