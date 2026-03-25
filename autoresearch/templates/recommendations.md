# Improve Ranking Model

## Objective
Improve the content ranking system in `scripts/rank_all_content.py` to produce
better model_score values that surface high-quality content.

## Current State
- LightGBM-Tweedie model trained on engagement signals from D1 analytics
- 13 weighted signals (clicks, impressions, dwell, scroll, rage clicks, etc.)
- Cold-start items scored via sentence-BERT similarity propagation
- Scores stored as `model_score` field in all data/*.json files

## Areas to Improve
Pick ONE of these per session (start with whichever seems most impactful):

1. **Cold-start scoring**: ~60% of items have zero engagement. Current k-NN
   similarity approach uses all-MiniLM-L6-v2. Explore:
   - Using content features (citations, GitHub stars, tags) as auxiliary signals
   - Bayesian prior from category-level engagement rates
   - Better neighbor selection (weight by recency, not just similarity)

2. **Feature engineering**: Add new features to the LightGBM model:
   - Item age (days since added)
   - Category-level average engagement
   - Tag frequency (popular vs niche tags)
   - Description length / quality signals

3. **Score calibration**: Ensure scores are well-distributed:
   - Currently many items cluster at 0.0-0.1
   - Explore quantile normalization or isotonic calibration
   - Ensure diverse content surfaces (not just popular items)

4. **Modular refactor**: The script is 1400+ lines and monolithic. Break it into:
   - `scripts/ranking/signals.py` — engagement signal weights, fetching from D1 API
   - `scripts/ranking/features.py` — feature engineering (BERT embeddings, TF-IDF, categorical encoding)
   - `scripts/ranking/cold_start.py` — k-NN score propagation for items without engagement
   - `scripts/ranking/calibration.py` — score normalization, freshness boost, section weights
   - `scripts/rank_all_content.py` — thin orchestrator that imports and calls the above
   - Each module should be independently testable
   - Preserve all existing behavior (same inputs, same outputs)

## Constraints
- Do NOT change the D1 schema or analytics worker
- Do NOT change the data file format (model_score must remain a float in [0,1])
- The script must still work without D1 access (graceful fallback)
- When refactoring, create a `scripts/ranking/` package with `__init__.py`

## Verification
After changes, run:
```bash
python3 scripts/validate_data.py
hugo --gc --minify
```

## Success Criteria
- All items have model_score in [0,1]
- Score distribution is more uniform (less clustering at 0)
- Cold-start items get reasonable scores (not all the same)
- Hugo build passes
- validate_data.py passes
