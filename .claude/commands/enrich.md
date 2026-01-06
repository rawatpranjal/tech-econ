---
description: Run LLM enrichment on items missing tags/descriptions
---

Run LLM enrichment on items missing tags/descriptions.

1. Find items in data/*.json without tags or description
2. Run `python3 scripts/enrich_metadata.py`
3. Run `python3 scripts/generate_embeddings.py`
4. Commit changes
5. Report: items enriched, failures
