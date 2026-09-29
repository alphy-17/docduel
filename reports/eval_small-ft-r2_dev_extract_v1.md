# Evaluation: small-ft-r2 on dev (extract_v1)

- Model: `small-ft-r2` (reasoning: None)
- Documents: 150 scored of 150
- Created: 2026-09-29T06:30:55+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 97.0% (94.8-98.5) |
| line item f1 | 90.4% (83.7-95.5) |
| perfect document rate | 80.7% (74.0-86.7) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 96.9% |
| line item precision | 90.5% |
| line item recall | 90.3% |
| p50 / p95 latency | 6017 / 10692 ms |
| cost per 1,000 docs | $1.4625 |
| total cost of this run | $0.219381 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 50 | 100.0% | 98.0% |
| document_date | 50 | 100.0% | 100.0% |
| document_number | 50 | 100.0% | 100.0% |
| currency | 150 | 98.0% | 98.0% |
| subtotal | 117 | 94.9% | 94.9% |
| tax | 97 | 95.9% | 95.9% |
| service_charge | 15 | 93.3% | 93.3% |
| discount | 13 | 84.6% | 84.6% |
| total | 148 | 94.6% | 94.6% |
| payment_method | 111 | 100.0% | 100.0% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
