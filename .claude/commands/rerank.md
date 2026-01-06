# Rerank Content

Fetch latest engagement data from D1 and update all content scores.

## Steps

1. **Fetch analytics from D1:**
   ```bash
   cd analytics-worker
   npx wrangler d1 execute tech-econ-analytics-db --remote --command \
     "SELECT * FROM content_clicks" --json > /tmp/clicks.json
   npx wrangler d1 execute tech-econ-analytics-db --remote --command \
     "SELECT * FROM content_impressions" --json > /tmp/impressions.json
   npx wrangler d1 execute tech-econ-analytics-db --remote --command \
     "SELECT * FROM content_dwell" --json > /tmp/dwell.json
   ```

2. **Run ranking script:**
   ```bash
   python3 scripts/rank_all_content.py
   ```

3. **Verify score updates:**
   - Check that `model_score` fields are updated in data/*.json files
   - Look for any items with score = 0 (cold start candidates)

4. **Commit changes:**
   ```bash
   git add data/*.json
   git commit -m "Update model_score rankings with new engagement data"
   git push
   ```

Report: How many items were updated, top 5 gainers, any cold-start items identified.
