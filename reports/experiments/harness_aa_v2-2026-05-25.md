# Experiment report: `harness_aa_v2`

- **status:** `active`
- **primary metric:** `ctr`
- **started:** `2026-05-24`
- **generated:** `2026-05-25T17:05:54.735320+00:00`

## Per-variant counts + CTR

| variant | impressions | clicks | CTR | 95% CI |
|---|---:|---:|---:|---|
| `control_a` | 15 | 0 | 0.0000 | [-0.0000, 0.2039] |
| `control_b` | 33 | 0 | 0.0000 | [0.0000, 0.1043] |

_(No `control` variant present — skipping pairwise tests.)_
## Provenance

Counts derived from one D1 query per experiment over the `events` table; `events.experiments` stores `{experiment_id: variant_id}` as JSON (PR #46). Re-derive with:
```sql
SELECT json_extract(experiments, '$.harness_aa_v2') AS variant,
       SUM(CASE WHEN type IN ('impression','pageview') THEN 1 ELSE 0 END) AS impressions,
       SUM(CASE WHEN type='click' THEN 1 ELSE 0 END) AS clicks
  FROM events
 WHERE json_extract(experiments, '$.harness_aa_v2') IS NOT NULL
 GROUP BY variant
```
