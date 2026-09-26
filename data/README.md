# Data

Everything here is rebuilt by scripts. Only the frozen test manifest and hand-made labels are
committed; raw downloads, generated files, OCR cache and splits are git-ignored.

| Dataset | Source | Licence | Used for |
|---|---|---|---|
| CORD v2 receipts | `naver-clova-ix/cord-v2` (Hugging Face) | CC-BY-4.0 | train 800 / dev 100 / test 40 (fixed seed) / reserve 60 |
| Synthetic invoices | `docduel.datasets.invoices` (seeded) | MIT (ours) | templates A-E train/dev, F held-out test, G hard cases (Phase 8) |
| Synthetic transactions | `docduel.datasets.transactions` (seeded) | MIT (ours) | train/dev use the training merchant list; test uses a held-out list |
| Owner receipts | contributed by the project owner, redacted | private | 8 in the test set; files never committed, only hashes + labels |

CORD citation: Park et al., "CORD: A Consolidated Receipt Dataset for Post-OCR Parsing", 2019.
CORD removed store names and dates, so `vendor_name`, `document_date` and `document_number` are
null for CORD and not scored. Very large CORD photos are re-encoded as JPEG (<= 4 MB) on export.

## Rebuild (from `backend/`)

```
uv run --group data python -m docduel.datasets.cord download
uv run --group data python -m docduel.datasets.cord export
uv run python -m docduel.datasets.invoices
uv run python -m docduel.datasets.transactions
uv run python -m docduel.datasets.build inventory
uv run python -m docduel.datasets.build ocr-plan      # Gate 2A: pages + cost
uv run python -m docduel.datasets.build ocr           # Azure, cached in data/cache/ocr
uv run python -m docduel.datasets.build splits
uv run python -m docduel.datasets.build review        # Gate 2B spot-check sheet
uv run python -m docduel.datasets.build freeze        # writes data/test/manifest.json
```

Owner receipts are redacted with `scripts/redact_pdfs.py` (text layer + visual) before use.
