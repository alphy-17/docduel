# Evaluation: small-ft-r2 on test-v1 (extract_v1)

- Model: `small-ft-r2` (reasoning: None)
- Documents: 63 scored of 63
- Created: 2026-09-29T06:39:30+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 95.1% (92.1-97.6) |
| line item f1 | 85.5% (78.1-93.0) |
| perfect document rate | 65.1% (54.0-76.2) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 93.6% |
| line item precision | 86.7% |
| line item recall | 84.4% |
| p50 / p95 latency | 5993 / 10817 ms |
| cost per 1,000 docs | $1.425 |
| total cost of this run | $0.089776 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 23 | 95.7% | 73.9% |
| document_date | 23 | 100.0% | 100.0% |
| document_number | 23 | 91.3% | 91.3% |
| currency | 63 | 96.8% | 96.8% |
| subtotal | 42 | 92.9% | 92.9% |
| tax | 37 | 94.6% | 94.6% |
| service_charge | 5 | 80.0% | 80.0% |
| discount | 6 | 66.7% | 66.7% |
| total | 60 | 95.0% | 95.0% |
| payment_method | 46 | 100.0% | 100.0% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
