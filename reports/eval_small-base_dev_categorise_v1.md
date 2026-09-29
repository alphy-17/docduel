# Evaluation: small-base on dev (categorise_v1)

- Model: `small-base` (reasoning: None)
- Documents: 5 scored of 5
- Created: 2026-09-28T09:49:26+00:00

| Metric | Value (95% interval) |
|---|---|
| accuracy | 91.5% (89.0-93.5) |
| macro f1 | 92.3% (89.2-94.5) |
| schema validity | 100.0% (100.0-100.0) |
| p50 / p95 latency | 16247 / 16348 ms |
| cost per 1,000 docs | $3.5048 |
| total cost of this run | $0.017524 |

Notes:
- A missing or extra row_id counts as wrong for that row.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
