# Evaluation: small-base on test-v1 (extract_v1)

- Model: `small-base` (reasoning: None)
- Documents: 63 scored of 63
- Created: 2026-09-27T11:40:10+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 88.7% (84.7-92.1) |
| line item f1 | 70.8% (59.7-81.3) |
| perfect document rate | 31.7% (20.6-44.4) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 86.9% |
| line item precision | 71.5% |
| line item recall | 70.1% |
| p50 / p95 latency | 5545 / 10045 ms |
| cost per 1,000 docs | $1.3394 |
| total cost of this run | $0.084384 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 23 | 95.7% | 78.3% |
| document_date | 23 | 95.7% | 95.7% |
| document_number | 23 | 95.7% | 91.3% |
| currency | 63 | 98.4% | 98.4% |
| subtotal | 42 | 88.1% | 88.1% |
| tax | 37 | 89.2% | 89.2% |
| service_charge | 5 | 80.0% | 80.0% |
| discount | 6 | 66.7% | 66.7% |
| total | 60 | 86.7% | 86.7% |
| payment_method | 46 | 71.7% | 69.6% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
