# Evaluation: small-ft-r1 on hard-correct (extract_v1)

- Model: `small-ft-r1` (reasoning: None)
- Documents: 40 scored of 40
- Created: 2026-09-29T04:31:24+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 64.4% (52.2-75.2) |
| line item f1 | 56.4% (38.7-72.5) |
| perfect document rate | 20.0% (7.5-32.5) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 64.0% |
| line item precision | 66.0% |
| line item recall | 49.3% |
| p50 / p95 latency | 6130 / 10441 ms |
| cost per 1,000 docs | $1.4324 |
| total cost of this run | $0.057294 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 40 | 75.0% | 72.5% |
| document_date | 40 | 32.5% | 32.5% |
| document_number | 40 | 65.0% | 65.0% |
| currency | 40 | 80.0% | 80.0% |
| subtotal | 40 | 60.0% | 60.0% |
| tax | 40 | 62.5% | 62.5% |
| discount | 9 | 77.8% | 77.8% |
| total | 40 | 62.5% | 62.5% |
| payment_method | 28 | 78.6% | 78.6% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
