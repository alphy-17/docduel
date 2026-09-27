# Evaluation: openai on test-v1 (categorise_v1)

- Model: `gpt-6-luna` (reasoning: medium)
- Documents: 5 scored of 5
- Created: 2026-09-27T00:36:15+00:00

| Metric | Value (95% interval) |
|---|---|
| accuracy | 100.0% (100.0-100.0) |
| macro f1 | 100.0% (100.0-100.0) |
| schema validity | 100.0% (100.0-100.0) |
| p50 / p95 latency | 1946 / 2394 ms |
| cost per 1,000 docs | $0.3167 |
| total cost of this run | $0.001584 |

Notes:
- A missing or extra row_id counts as wrong for that row.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
