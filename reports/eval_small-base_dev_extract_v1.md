# Evaluation: small-base on dev (extract_v1)

- Model: `small-base` (reasoning: None)
- Documents: 150 scored of 150
- Created: 2026-09-28T10:12:17+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 86.4% (83.2-89.3) |
| line item f1 | 82.0% (76.3-86.9) |
| perfect document rate | 43.3% (35.3-51.3) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 86.3% |
| line item precision | 82.8% |
| line item recall | 81.1% |
| p50 / p95 latency | 5813 / 9960 ms |
| cost per 1,000 docs | $1.3705 |
| total cost of this run | $0.205574 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 50 | 98.0% | 96.0% |
| document_date | 50 | 98.0% | 98.0% |
| document_number | 50 | 98.0% | 98.0% |
| currency | 150 | 96.7% | 96.7% |
| subtotal | 117 | 83.8% | 83.8% |
| tax | 97 | 81.4% | 81.4% |
| service_charge | 15 | 73.3% | 73.3% |
| discount | 13 | 84.6% | 84.6% |
| total | 148 | 81.1% | 81.1% |
| payment_method | 111 | 73.0% | 73.0% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
