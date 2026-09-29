# Evaluation: small-ft-r1 on dev (extract_v1)

- Model: `small-ft-r1` (reasoning: None)
- Documents: 150 scored of 150
- Created: 2026-09-28T10:16:34+00:00

| Metric | Value (95% interval) |
|---|---|
| field accuracy | 97.9% (96.5-99.1) |
| line item f1 | 92.4% (88.4-95.7) |
| perfect document rate | 82.7% (76.0-88.0) |
| schema validity | 100.0% (100.0-100.0) |
| field accuracy exact | 97.8% |
| line item precision | 93.0% |
| line item recall | 91.8% |
| p50 / p95 latency | 5961 / 10935 ms |
| cost per 1,000 docs | $1.4677 |
| total cost of this run | $0.220154 |

| Field | Scored | Accuracy | Exact |
|---|---|---|---|
| vendor_name | 50 | 100.0% | 98.0% |
| document_date | 50 | 100.0% | 100.0% |
| document_number | 50 | 98.0% | 98.0% |
| currency | 150 | 99.3% | 99.3% |
| subtotal | 117 | 97.4% | 97.4% |
| tax | 97 | 97.9% | 97.9% |
| service_charge | 15 | 93.3% | 93.3% |
| discount | 13 | 76.9% | 76.9% |
| total | 148 | 97.3% | 97.3% |
| payment_method | 111 | 98.2% | 98.2% |

Notes:
- Only fields with non-null ground truth are scored (CORD has no vendor or date).
- Short strings: headline uses fuzzy match (token_set_ratio >= 90); exact also given.
- Zero-priced line items (modifiers, free extras) are ignored on both sides.
- A line item with a blank true amount only needs a matching description.
- Perfect document = every scored field and every priced line item right.
- 95% intervals: 1,000 bootstrap resamples of documents, seed 2026.
