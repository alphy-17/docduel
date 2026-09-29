# Evaluation: small-ft-r1 on hard-holdout (extract_v1)

- Model: `small-ft-r1` (reasoning: None)
- Documents: 20 scored of 20
- Created: 2026-09-29T06:13:24+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 74.5% (60.9-85.2) |
| line item f1 | 75.3% (54.5-91.9) |
| perfect document rate | 10.0% (0.0-25.0) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 74.5% |
| line item precision | 76.3% |
| line item recall | 74.4% |
| p50 / p95 latency | 8399 / 11309 ms |
| cost per 1,000 docs | $1.8129 |
| total cost of this run | $0.036258 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 20 | 90.0% | 90.0% |
| document_date | 20 | 20.0% | 20.0% |
| document_number | 20 | 85.0% | 85.0% |
| currency | 20 | 85.0% | 85.0% |
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
