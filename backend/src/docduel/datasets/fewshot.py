"""Pick few-shot examples for the prompts, from the TRAIN split only (Plan 3.1, rule R4).

Run once:  uv run python -m docduel.datasets.fewshot
Writes backend/prompts/fewshot/{extract,categorise}_v1.json (committed, reviewed by the Owner).
Extract: 2 CORD receipts (free-tier OCR, cached; payment label must be visible in the text)
+ 1 text-layer synthetic invoice.
Categorise: 3 short slices (8 rows each) of different training CSVs.
"""

import json
import random
import sys
from pathlib import Path

from docduel.datasets.build import _load_inventory, data_dir
from docduel.settings import BACKEND_DIR, get_settings
from docduel.testset import is_test_document

SEED = 2026
FEWSHOT_DIR = BACKEND_DIR / "prompts" / "fewshot"
CSV_ROWS = 8


def _pick(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    rows = sorted(rows, key=lambda r: r["id"])
    if len(rows) < n:
        sys.exit(f"not enough candidates: need {n}, found {len(rows)}")
    return rng.sample(rows, n)


def _check_train(r: dict) -> None:
    if r["split"] != "train" or is_test_document(r["sha256"]):
        sys.exit(f"LEAK: {r['id']} is not a training document")


# CORD sometimes labels a payment method the receipt text never shows. A few-shot example
# like that would teach guessing, so only accept one whose text supports its label.
PAYMENT_EVIDENCE = {
    "cash": ("cash", "tunai"),
    "card": ("card", "credit", "debit", "visa", "master", "bca", "edc"),
    "e-money": ("ovo", "gopay", "emoney", "e-money", "dana", "shopeepay"),
}


def _text(r: dict, ocr) -> str:
    from docduel.ingest import ingest_bytes

    path = data_dir() / r["path"]
    return ingest_bytes(path.read_bytes(), path.name, ocr).text


def _pick_cord_with_evidence(rows: list[dict], n: int, rng: random.Random, ocr) -> list[dict]:
    rows = sorted(rows, key=lambda r: r["id"])
    rng.shuffle(rows)
    chosen = []
    for r in rows:
        pay = r["label"]["payment_method"]
        text = _text(r, ocr).lower()
        if pay is None or any(w in text for w in PAYMENT_EVIDENCE.get(pay, (pay,))):
            chosen.append(r)
        else:
            print(f"skipped {r['id']}: label says {pay!r} but the text does not show it")
        if len(chosen) == n:
            return chosen
    sys.exit(f"not enough CORD candidates with payment evidence (need {n})")


def build(seed: int = SEED) -> dict[str, int]:
    from docduel.ingest.csv import parse_transactions, render_for_prompt
    from docduel.ingest.factory import build_ocr

    rng = random.Random(seed)
    train = [r for r in _load_inventory() if r["split"] == "train"]

    cord = [
        r
        for r in train
        if r["source"] == "cord"
        and r["label"]["total"] is not None
        and 3 <= len(r["label"]["line_items"]) <= 8
    ]
    invoices = [
        r for r in train if r["source"] == "synthetic_invoice" and r["rendered_as"] == "text_pdf"
    ]
    csvs = [r for r in train if r["source"] == "synthetic_transactions"]

    ocr = build_ocr(get_settings())
    if ocr is None:
        sys.exit("Azure OCR is not configured in backend/.env")

    extract = []
    for r in _pick_cord_with_evidence(cord, 2, rng, ocr) + _pick(invoices, 1, rng):
        _check_train(r)
        extract.append(
            {"id": r["id"], "sha256": r["sha256"], "text": _text(r, ocr), "output": r["label"]}
        )

    categorise = []
    for r in _pick(csvs, 3, rng):
        _check_train(r)
        df = parse_transactions((data_dir() / r["path"]).read_bytes()).head(CSV_ROWS)
        items = [i for i in r["label"]["items"] if i["row_id"] <= CSV_ROWS]
        categorise.append(
            {
                "id": r["id"],
                "sha256": r["sha256"],
                "text": render_for_prompt(df),
                "output": {"items": items},
            }
        )

    FEWSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for name, examples in (("extract_v1", extract), ("categorise_v1", categorise)):
        path = FEWSHOT_DIR / f"{name}.json"
        payload = {"source_split": "train", "seed": seed, "examples": examples}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(BACKEND_DIR)}: {[e['id'] for e in examples]}")
    print(f"Azure calls made: {ocr.calls}")
    return {"extract": len(extract), "categorise": len(categorise)}


def fewshot_path(name: str) -> Path:
    return FEWSHOT_DIR / f"{name}.json"


if __name__ == "__main__":
    build()
