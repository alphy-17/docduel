# Evaluation: small-ft-r2 on hard-holdout (extract_v1)

- Model: `small-ft-r2` (reasoning: None)
- Documents: 20 scored of 20
- Created: 2026-09-29T06:30:01+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 85.6% (71.8-96.7) |
| line item f1 | 73.9% (53.4-91.7) |
| perfect document rate | 70.0% (50.0-90.0) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 85.6% |
| line item precision | 73.4% |
| line item recall | 74.4% |
| p50 / p95 latency | 8555 / 11009 ms |
| cost per 1,000 docs | $1.8647 |
| total cost of this run | $0.037294 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 20 | 90.0% | 90.0% |
| document_date | 20 | 90.0% | 90.0% |
| document_number | 20 | 85.0% | 85.0% |
| currency | 20 | 100.0% | 100.0% |
| subtotal | 20 | 80.0% | 80.0% |
| tax | 20 | 80.0% | 80.0% |
| discount | 3 | 66.7% | 66.7% |
| total | 20 | 75.0% | 75.0% |
| payment_method | 10 | 90.0% | 90.0% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
