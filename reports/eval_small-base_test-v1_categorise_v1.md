# Evaluation: small-base on test-v1 (categorise_v1)

- Model: `small-base` (reasoning: None)
- Documents: 5 scored of 5
- Created: 2026-09-27T11:47:13+00:00

| Metric | Value (95% interval) |
|---|---|
| accuracy | 88.0% (81.0-95.0) |
| macro f1 | 87.4% (77.6-95.1) |
| schema validity | 100.0% (100.0-100.0) |
| p50 / p95 latency | 8669 / 10584 ms |
| cost per 1,000 docs | $1.9692 |
| total cost of this run | $0.009846 |

Notes:
- A missing or extra row_id counts as wrong for that row.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
