# Content Ranking System

**Status**: Complete (Dec 31, 2025)

ML-powered content ranking for tech-econ.com using engagement data + content similarity.

## Quick Start

```bash
python scripts/rank_all_content.py
```

Output: `data/global_rankings.json`

## How It Works

### 1. Data Sources

| Source | Data | Weight |
|--------|------|--------|
| D1 clicks | Click counts per item | 3.0x |
| D1 impressions | View counts | 0.5x |
| D1 dwell | Time spent (ms) | 1.0x per minute |
| Paper citations | Academic impact | 0.3x (log-scaled) |

### 2. Algorithm

**For items with engagement data (114 items):**
```
score = clicks * 3.0 + impressions * 0.5 + dwell_minutes * 1.0
```

**For cold start items (3,164 items):**
- Build TF-IDF vectors from 22 metadata fields
- Find k=5 nearest neighbors among observed items
- Weighted average of neighbor scores

**For papers:**
- Add log(citations) boost (normalized to 0.3 max)

### 3. Metadata Fields Used

| Field | Source | Purpose |
|-------|--------|---------|
| name, description, summary | All | Core text |
| tags, topic_tags | All | Categories |
| synthetic_questions | All (except papers) | LLM search queries |
| use_cases | All | Applications |
| citations | Papers | Quality signal |
| domain_tags | Datasets | Domain categories |
| key_insights | Talks | Takeaways |
| language | Packages | Programming language |
| + 10 more fields | Various | Content similarity |

## Output Format

```json
{
  "updated": "2025-12-31T21:00:00Z",
  "algorithm": "enhanced_knn_with_citations_boost",
  "total_items": 3278,
  "observed_items": 114,
  "cold_start_items": 3164,
  "rankings": [
    {
      "name": "Causal Inference for the Brave and True",
      "type": "package",
      "category": "...",
      "score": 0.700,
      "rank": 1,
      "cold_start": false,
      "signals": {"clicks": 3, "impressions": 3, "dwell_ms": 0}
    }
  ]
}
```

## Current Top Rankings

### By Engagement (real clicks)
| Rank | Item | Clicks |
|------|------|--------|
| 1 | Causal Inference for the Brave and True | 3 |
| 2 | spaCy | 3 |
| 3 | JD.com 2020 (MSOM-20) | 3 |
| 4 | BestBuy | 3 |

### By Citations (papers)
| Rank | Paper | Citations |
|------|-------|-----------|
| 389 | ResNet | 156,789 |
| 49 | FDR Control (Benjamini-Hochberg) | 103,590 |
| 5 | Matrix Factorization for RecSys | 11,142 |

### By Type
| Type | Top Item | Score |
|------|----------|-------|
| Package | Causal Inference for the Brave and True | 0.700 |
| Dataset | JD.com 2020 | 0.600 |
| Paper | Matrix Factorization | 0.590 |
| Career | Care.com | 0.519 |
| Resource | Google Research Market Algorithms | 0.433 |

## Files

| File | Purpose |
|------|---------|
| `scripts/rank_all_content.py` | Main ranking script |
| `scripts/rank_content.py` | Simple engagement-only ranking |
| `data/global_rankings.json` | Full rankings output |
| `data/content_rankings.json` | Simple rankings output |

## Future Improvements

- [ ] Add Web Analytics page views as signal
- [ ] Implement true ALS when more session data available
- [ ] Add time decay for older engagement
- [ ] Personalization based on user interests
