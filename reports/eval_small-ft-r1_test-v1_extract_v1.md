# Evaluation: small-ft-r1 on test-v1 (extract_v1)

- Model: `small-ft-r1` (reasoning: None)
- Documents: 63 scored of 63
- Created: 2026-09-28T10:21:59+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 96.3% (94.0-98.5) |
| line item f1 | 90.5% (83.2-96.7) |
| perfect document rate | 74.6% (63.5-84.2) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 95.1% |
| line item precision | 91.4% |
| line item recall | 89.6% |
| p50 / p95 latency | 5970 / 10929 ms |
| cost per 1,000 docs | $1.4124 |
| total cost of this run | $0.088981 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 23 | 95.7% | 78.3% |
| document_date | 23 | 100.0% | 100.0% |
| document_number | 23 | 91.3% | 91.3% |
| currency | 63 | 100.0% | 100.0% |
| subtotal | 42 | 95.2% | 95.2% |
| tax | 37 | 97.3% | 97.3% |
| service_charge | 5 | 100.0% | 100.0% |
| discount | 6 | 50.0% | 50.0% |
| total | 60 | 96.7% | 96.7% |
| payment_method | 46 | 97.8% | 97.8% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
