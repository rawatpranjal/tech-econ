# Experiment report: `harness_aa_v1`

- **status:** `active`
- **primary metric:** `ctr`
- **started:** `2026-05-04`
- **generated:** `2026-05-24T03:35:33.138673+00:00`

## Per-variant counts + CTR

| variant | impressions | clicks | CTR | 95% CI |
|---|---:|---:|---:|---|
| `control_a` | 8,071 | 322 | 0.0399 | [0.0358, 0.0444] |
| `control_b` | 10,205 | 237 | 0.0232 | [0.0205, 0.0263] |

_(No `control` variant present — skipping pairwise tests.)_
## Provenance

Counts derived from one D1 query per experiment over the `events` table; `events.experiments` stores `{experiment_id: variant_id}` as JSON (PR #46). Re-derive with:
```sql
SELECT json_extract(experiments, '$.harness_aa_v1') AS variant,
       SUM(CASE WHEN type IN ('impression','pageview') THEN 1 ELSE 0 END) AS impressions,
       SUM(CASE WHEN type='click' THEN 1 ELSE 0 END) AS clicks
  FROM events
 WHERE json_extract(experiments, '$.harness_aa_v1') IS NOT NULL
 GROUP BY variant
```
