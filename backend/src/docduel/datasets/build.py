"""Build dataset inventory, run OCR once (cached), write splits, review sheet and frozen manifest.

  uv run --group data python -m docduel.datasets.build inventory
  uv run --group data python -m docduel.datasets.build ocr-plan
  uv run --group data python -m docduel.datasets.build ocr [--workers 4] [--limit N]
  uv run --group data python -m docduel.datasets.build splits
  uv run --group data python -m docduel.datasets.build review
  uv run --group data python -m docduel.datasets.build freeze

Splits follow Plan Section 12 ("Data splits used throughout").
"""

import argparse
import base64
import hashlib
import html
import io
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import yaml

from docduel.settings import get_settings

DATASET_VERSION = "test-v1"
CORD_TEST_SEED = 2026
CORD_TEST_COUNT = 40
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def data_dir() -> Path:
    return get_settings().data_dir


def splits_dir() -> Path:
    return data_dir() / "splits"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(data_dir()).as_posix()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _needs_ocr(path: Path) -> bool:
    if path.suffix.lower() in IMAGE_EXT:
        return True
    if path.suffix.lower() == ".pdf":
        from docduel.ingest.pdf import read_text_layer

        return any(p.needs_ocr for p in read_text_layer(path.read_bytes()))
    return False


# ------------------------------------------------------------------ inventory


def inventory() -> list[dict]:
    d = data_dir()
    rows: list[dict] = []

    # CORD: train -> train, validation -> dev, test -> 40 sampled test + 60 reserve
    cord = d / "raw" / "cord"
    test_ids: set[int] = set()
    test_labels = _read_jsonl(cord / "test" / "labels.jsonl")
    if test_labels:
        ids = sorted(r["image_id"] for r in test_labels)
        test_ids = set(random.Random(CORD_TEST_SEED).sample(ids, CORD_TEST_COUNT))
    for src_split, split in (("train", "train"), ("validation", "dev"), ("test", None)):
        for r in _read_jsonl(cord / src_split / "labels.jsonl"):
            path = cord / src_split / r["file"]
            s = split or ("test" if r["image_id"] in test_ids else "reserve")
            rows.append(
                {
                    "id": f"cord_{src_split}_{r['image_id']:04d}",
                    "source": "cord",
                    "task": "extract",
                    "split": s,
                    "path": _rel(path),
                    "sha256": sha256_file(path),
                    "label": r["label"],
                }
            )

    # Synthetic invoices and transactions (splits decided at generation time)
    syn = d / "synthetic" / "output"
    for split in ("train", "dev", "test", "hard"):
        for r in _read_jsonl(syn / "invoices" / split / "labels.jsonl"):
            path = syn / "invoices" / split / r["file"]
            rows.append(
                {
                    "id": r["file"].removesuffix(".pdf"),
                    "source": "synthetic_invoice",
                    "task": "extract",
                    "split": split,
                    "path": _rel(path),
                    "sha256": sha256_file(path),
                    "template": r["template"],
                    "rendered_as": r["rendered_as"],
                    "label": r["label"],
                }
            )
        for r in _read_jsonl(syn / "transactions" / split / "labels.jsonl"):
            path = syn / "transactions" / split / r["file"]
            rows.append(
                {
                    "id": r["file"].removesuffix(".csv"),
                    "source": "synthetic_transactions",
                    "task": "categorise",
                    "split": split,
                    "path": _rel(path),
                    "sha256": sha256_file(path),
                    "merchants": r["merchants"],
                    "label": r["label"],
                }
            )

    # Owner receipts (redacted copies only) -> all in test
    owner_labels = d / "test" / "owner_labels.json"
    if owner_labels.exists():
        labels = json.loads(owner_labels.read_text(encoding="utf-8"))["labels"]
        for name, label in sorted(labels.items()):
            path = d / "owner_receipts_redacted" / name
            if not path.exists():
                sys.exit(f"missing redacted owner receipt: {path}")
            stem = hashlib.sha1(name.encode()).hexdigest()[:8]
            rows.append(
                {
                    "id": f"owner_{stem}",
                    "source": "owner",
                    "task": "extract",
                    "split": "test",
                    "path": _rel(path),
                    "sha256": sha256_file(path),
                    "label": label,
                }
            )

    for r in rows:
        r["needs_ocr"] = r["task"] == "extract" and _needs_ocr(d / r["path"])
    _write_jsonl(splits_dir() / "inventory.jsonl", rows)
    return rows


def _load_inventory() -> list[dict]:
    rows = _read_jsonl(splits_dir() / "inventory.jsonl")
    if not rows:
        sys.exit("no inventory yet - run: python -m docduel.datasets.build inventory")
    return rows


def summary(rows: list[dict]) -> dict:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        key = f"{r['source']}:{r['task']}"
        out.setdefault(r["split"], {}).setdefault(key, 0)
        out[r["split"]][key] += 1
    return out


# ------------------------------------------------------------------ OCR


def _pages_needing_ocr(r: dict) -> int:
    path = data_dir() / r["path"]
    if path.suffix.lower() in IMAGE_EXT:
        return 1
    from docduel.ingest.pdf import read_text_layer

    return sum(p.needs_ocr for p in read_text_layer(path.read_bytes()))


def _is_cached(r: dict) -> bool:
    from docduel.ingest.ocr_azure import OCR_FORMAT_VERSION

    cache = get_settings().ocr_cache_dir
    if (data_dir() / r["path"]).suffix.lower() in IMAGE_EXT:
        return (cache / f"{r['sha256']}_v{OCR_FORMAT_VERSION}.json").exists()
    return (cache / f"{r['sha256']}_p0_v{OCR_FORMAT_VERSION}.json").exists()


def ocr_plan() -> dict:
    rows = [r for r in _load_inventory() if r["needs_ocr"] and r["split"] != "reserve"]
    pages = {s: 0 for s in ("train", "dev", "test", "hard")}
    cached = 0
    for r in rows:
        if _is_cached(r):
            cached += 1
            continue
        pages[r["split"]] += _pages_needing_ocr(r)
    total = sum(pages.values())
    pricing = yaml.safe_load((get_settings().config_dir / "pricing.yaml").read_text())
    per_1000 = pricing["azure_document_intelligence"]["per_1000_pages_0_to_1m"]
    free = pricing["azure_document_intelligence"]["free_tier_F0_pages_per_month"]
    return {
        "pages_by_split": pages,
        "total_pages": total,
        "already_cached_docs": cached,
        "s0_cost_usd": round(total * per_1000 / 1000, 2),
        "f0_free_pages_per_month": free,
    }


def run_ocr(workers: int = 4, limit: int | None = None, splits=("train", "dev", "test")) -> None:
    from docduel.ingest import IngestError, ingest_bytes
    from docduel.ingest.factory import build_ocr

    ocr = build_ocr(get_settings())
    if ocr is None:
        sys.exit("Azure OCR is not configured in backend/.env")
    todo = [r for r in _load_inventory() if r["split"] in splits and r["task"] == "extract"]
    todo = [r for r in todo if not (r["needs_ocr"] and _is_cached(r))] if limit else todo
    if limit:
        todo = [r for r in todo if r["needs_ocr"]][:limit]
    text_dir = splits_dir() / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    failures, done, t0 = [], 0, time.time()

    def work(r: dict) -> tuple[dict, str | None]:
        path = data_dir() / r["path"]
        try:
            doc = ingest_bytes(path.read_bytes(), path.name, ocr)
        except IngestError as exc:
            return r, f"{exc.error_code}: {exc.message}"
        (text_dir / f"{r['sha256']}.txt").write_text(doc.text, encoding="utf-8")
        return r, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(work, r) for r in todo]):
            r, err = fut.result()
            done += 1
            if err:
                failures.append({"id": r["id"], "error": err})
            if done % 25 == 0 or done == len(todo):
                print(
                    f"{done}/{len(todo)} docs  azure_calls={ocr.calls}  "
                    f"failures={len(failures)}  {time.time() - t0:.0f}s",
                    flush=True,
                )
    _write_jsonl(splits_dir() / "ocr_failures.jsonl", failures)
    print(f"Azure calls made: {ocr.calls}. Failures: {len(failures)}")


# ------------------------------------------------------------------ splits


def build_splits(splits=("train", "dev", "test")) -> dict:
    rows = _load_inventory()
    text_dir = splits_dir() / "text"
    counts = {}
    for split in splits:
        out = []
        for r in rows:
            if r["split"] != split:
                continue
            rec = dict(r)
            if r["task"] == "extract":
                t = text_dir / f"{r['sha256']}.txt"
                if not t.exists() and split == "hard":  # unreadable heavy scan: leave it out
                    print(f"skipped {r['id']}: OCR found no text")
                    continue
                if not t.exists():
                    sys.exit(f"no extracted text for {r['id']} - run the ocr step first")
                rec["text"] = t.read_text(encoding="utf-8")
            else:
                from docduel.ingest.csv import parse_transactions, render_for_prompt

                rec["text"] = render_for_prompt(
                    parse_transactions((data_dir() / r["path"]).read_bytes())
                )
            out.append(rec)
        _write_jsonl(splits_dir() / f"{split}.jsonl", out)
        counts[split] = len(out)
    return counts


# ------------------------------------------------------------------ review sheet


def _thumb(path: Path) -> str:
    from PIL import Image

    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        img = pdfium.PdfDocument(path)[0].render(scale=1.6).to_pil()
    else:
        img = Image.open(path)
    img = img.convert("RGB")
    img.thumbnail((900, 1400))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def review_sheet() -> Path:
    rows = [r for r in _load_inventory() if r["split"] == "test"]
    rng = random.Random(7)
    owner = [r for r in rows if r["source"] == "owner"]
    cord = rng.sample([r for r in rows if r["source"] == "cord"], 8)
    inv = rng.sample([r for r in rows if r["source"] == "synthetic_invoice"], 4)
    tx = [r for r in rows if r["source"] == "synthetic_transactions"][:1]
    picks = owner + cord + inv
    esc = html.escape
    parts = [
        "<!doctype html><meta charset=utf-8><title>DocDuel test-v1 label review</title>",
        "<style>body{font:14px system-ui;margin:24px;max-width:1500px}.doc{display:flex;"
        "gap:24px;border-top:2px solid #ccc;padding:18px 0}img{max-width:560px;border:1px solid "
        "#ddd}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:3px 7px;"
        "text-align:left;vertical-align:top}.null{color:#aaa}</style>",
        f"<h1>Label review - {len(picks)} test documents + transaction sample</h1>",
        "<p>Check every value against the image. Null = not printed / not labelled. Note the "
        "number of any row that is wrong.</p>",
    ]
    for n, r in enumerate(picks, 1):
        lab = r["label"]
        fields = "".join(
            f"<tr><th>{k}</th><td class={'null' if v is None else ''}>{esc(str(v))}</td></tr>"
            for k, v in lab.items()
            if k != "line_items"
        )
        items = "".join(
            f"<tr><td>{esc(i['description'])}</td><td>{i['quantity']}</td><td>{i['unit_price']}</td>"
            f"<td>{i['amount']}</td></tr>"
            for i in lab["line_items"]
        )
        parts.append(
            f"<div class=doc><img src='data:image/jpeg;base64,{_thumb(data_dir() / r['path'])}'>"
            f"<div><h2>#{n} {esc(r['id'])} <small>({r['source']})</small></h2>"
            f"<table>{fields}</table>"
            f"<h3>Line items</h3><table><tr><th>description</th><th>qty</th><th>unit</th>"
            f"<th>amount</th></tr>{items}</table></div></div>"
        )
    for r in tx:
        from docduel.ingest.csv import parse_transactions

        df = parse_transactions((data_dir() / r["path"]).read_bytes())
        cats = {i["row_id"]: i["category"] for i in r["label"]["items"]}
        body = "".join(
            f"<tr><td>{x.row_id}</td><td>{esc(x.description)}</td><td>{x.amount}</td>"
            f"<td>{cats[x.row_id]}</td></tr>"
            for x in df.itertuples()
        )
        parts.append(
            f"<h2>#T {esc(r['id'])} (categorise)</h2><table><tr><th>row</th>"
            f"<th>description</th><th>amount</th><th>category</th></tr>{body}</table>"
        )
    out = splits_dir() / "review.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# ------------------------------------------------------------------ freeze


def freeze() -> Path:
    from docduel.datasets.leakage import check_from_disk

    problems = check_from_disk()
    if problems:
        sys.exit("leakage check failed - not freezing:\n" + "\n".join(problems))
    rows = [r for r in _load_inventory() if r["split"] == "test"]
    docs = [
        {k: r[k] for k in ("id", "source", "task", "path", "sha256", "label") if k in r}
        | {k: r[k] for k in ("template", "rendered_as", "merchants") if k in r}
        for r in sorted(rows, key=lambda r: r["id"])
    ]
    manifest = {
        "dataset_version": DATASET_VERSION,
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": summary(rows)["test"],
        "notes": "Raw files are not committed. CORD fields vendor_name, document_date and "
        "document_number are null (not labelled in CORD) and are not scored.",
        "documents": docs,
    }
    out = data_dir() / "test" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m docduel.datasets.build")
    ap.add_argument("step", choices=["inventory", "ocr-plan", "ocr", "splits", "review", "freeze"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--splits", default="train,dev,test", help="comma list, e.g. dev,test")
    a = ap.parse_args(argv)
    if a.step == "inventory":
        print(json.dumps(summary(inventory()), indent=2))
    elif a.step == "ocr-plan":
        print(json.dumps(ocr_plan(), indent=2))
    elif a.step == "ocr":
        run_ocr(a.workers, a.limit, tuple(a.splits.split(",")))
    elif a.step == "splits":
        print(json.dumps(build_splits(tuple(a.splits.split(","))), indent=2))
    elif a.step == "review":
        print("review sheet:", review_sheet())
    else:
        print("frozen:", freeze())


if __name__ == "__main__":
    main()
