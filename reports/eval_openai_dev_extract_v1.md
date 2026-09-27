# Evaluation: openai on dev (extract_v1)

- Model: `gpt-6-luna` (reasoning: medium)
- Documents: 5 scored of 5
- Created: 2026-09-27T00:35:07+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 85.0% (70.8-100.0) |
| line item f1 | 100.0% (100.0-100.0) |
| perfect document rate | 60.0% (20.0-100.0) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 85.0% |
| line item precision | 100.0% |
| line item recall | 100.0% |
| p50 / p95 latency | 3206 / 6423 ms |
| cost per 1,000 docs | $0.3711 |
| total cost of this run | $0.001856 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| currency | 5 | 100.0% | 100.0% |
| subtotal | 3 | 33.3% | 33.3% |
| tax | 2 | 100.0% | 100.0% |
| total | 5 | 80.0% | 80.0% |
| payment_method | 5 | 100.0% | 100.0% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
