# Evaluation: openai on test-v1 (extract_v1)

- Model: `gpt-6-luna` (reasoning: medium)
- Documents: 63 scored of 63
- Created: 2026-09-27T00:40:46+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 98.8% (97.4-99.7) |
| line item f1 | 92.8% (85.8-98.1) |
| perfect document rate | 84.1% (74.6-92.1) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 97.0% |
| line item precision | 94.0% |
| line item recall | 91.6% |
| p50 / p95 latency | 2448 / 4792 ms |
| cost per 1,000 docs | $0.1967 |
| total cost of this run | $0.012394 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 23 | 95.7% | 73.9% |
| document_date | 23 | 100.0% | 100.0% |
| document_number | 23 | 100.0% | 95.7% |
| currency | 63 | 100.0% | 100.0% |
| subtotal | 42 | 97.6% | 97.6% |
| tax | 37 | 100.0% | 100.0% |
| service_charge | 5 | 100.0% | 100.0% |
| discount | 6 | 100.0% | 100.0% |
| total | 60 | 98.3% | 98.3% |
| payment_method | 46 | 97.8% | 97.8% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
