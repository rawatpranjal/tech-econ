# Review Clustering & Carousels

Manually inspect cluster quality and document issues.

## Steps

1. **Load cluster data:**
   ```bash
   cat data/resource_clusters.json | python3 -m json.tool | head -200
   ```

2. **For each section with clusters, review:**
   - Are cluster labels descriptive and accurate?
   - Do items in each cluster belong together semantically?
   - Are cluster sizes appropriate (5-10 items)?
   - Are there orphan items that should be clustered?
   - Are there items miscategorized?

3. **Check carousel categories:**
   - Do category groupings make sense?
   - Are categories balanced in size?
   - Would a user understand the category names?

4. **Document issues in a review file:**
   Create/update `scripts/cluster_assignments_review.csv` with columns:
   - `item_name`, `current_cluster`, `suggested_cluster`, `issue_type`, `notes`

   Issue types: `miscategorized`, `orphan`, `bad_label`, `cluster_too_small`, `cluster_too_large`

5. **Summarize findings:**
   - Total clusters reviewed
   - Number of issues found by type
   - Recommendations for re-clustering

After review, consider running `python3 scripts/cluster_resources.py` with adjusted parameters if needed.
