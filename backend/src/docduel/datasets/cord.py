"""CORD v2 receipts: download, convert ground truth to ReceiptExtraction, export images.

  uv run --group data python -m docduel.datasets.cord download   # parquet files -> data/raw/cord
  uv run --group data python -m docduel.datasets.cord export     # images + labels per split

CORD (CC-BY-4.0) removed store names and dates for privacy, so vendor_name, document_date and
document_number are always null here and are not scored on CORD documents (Plan 10.1).
"""

import io
import json
import sys
from pathlib import Path

from docduel.schemas.extraction import LineItem, ReceiptExtraction
from docduel.scoring.normalise import parse_amount, parse_quantity, to_float
from docduel.settings import get_settings

REPO_ID = "naver-clova-ix/cord-v2"
SPLITS = {"train": "train", "validation": "validation", "test": "test"}


def raw_dir() -> Path:
    return get_settings().data_dir / "raw" / "cord"


def _as_list(v: object) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _scalar(v: object) -> str | None:
    """CORD sometimes stores a field as a list; if the values disagree we treat it as unknown."""
    if isinstance(v, list):
        vals = {str(x) for x in v if x not in (None, "")}
        return vals.pop() if len(vals) == 1 else None
    return v if v not in ("",) else None


def _name(v: object) -> str:
    return " ".join(str(x) for x in _as_list(v)).strip()


def _item(d: dict) -> LineItem | None:
    desc = _name(d.get("nm"))
    amount = parse_amount(_scalar(d.get("price")))
    if not desc and amount is None:
        return None
    return LineItem(
        description=desc,
        quantity=to_float(parse_quantity(_scalar(d.get("cnt")))),
        unit_price=to_float(parse_amount(_scalar(d.get("unitprice")))),
        amount=to_float(amount),
    )


def to_schema(gt_parse: dict) -> ReceiptExtraction:
    items: list[LineItem] = []
    for menu in _as_list(gt_parse.get("menu")):
        if not isinstance(menu, dict):
            continue
        if (it := _item(menu)) is not None:
            items.append(it)
        # Modifiers ("sub") only become line items when they carry their own price.
        for sub in _as_list(menu.get("sub")):
            if isinstance(sub, dict) and sub.get("price") and (it := _item(sub)) is not None:
                items.append(it)
    sub_total = gt_parse.get("sub_total") or {}
    total = gt_parse.get("total") or {}
    sub_total = sub_total if isinstance(sub_total, dict) else {}
    total = total if isinstance(total, dict) else {}

    discount = parse_amount(_scalar(sub_total.get("discount_price")))
    payment = None
    if total.get("creditcardprice"):
        payment = "card"
    elif total.get("emoneyprice"):
        payment = "e-money"
    elif total.get("cashprice"):
        payment = "cash"

    return ReceiptExtraction(
        vendor_name=None,
        document_date=None,
        document_number=None,
        currency="IDR",
        line_items=items,
        subtotal=to_float(parse_amount(_scalar(sub_total.get("subtotal_price")))),
        tax=to_float(parse_amount(_scalar(sub_total.get("tax_price")))),
        service_charge=to_float(parse_amount(_scalar(sub_total.get("service_price")))),
        discount=to_float(abs(discount)) if discount is not None else None,
        total=to_float(parse_amount(_scalar(total.get("total_price")))),
        payment_method=payment,
    )


def download() -> list[Path]:
    from huggingface_hub import HfApi, hf_hub_download

    out = raw_dir() / "parquet"
    out.mkdir(parents=True, exist_ok=True)
    files = [
        f
        for f in HfApi().list_repo_files(
            REPO_ID, repo_type="dataset", revision="refs/convert/parquet"
        )
        if f.endswith(".parquet")
    ]
    paths = []
    for f in sorted(files):
        print("downloading", f, flush=True)
        paths.append(
            Path(
                hf_hub_download(
                    REPO_ID, f, repo_type="dataset", revision="refs/convert/parquet", local_dir=out
                )
            )
        )
    return paths


def _ext(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpg"
    from PIL import Image

    return (Image.open(io.BytesIO(data)).format or "bin").lower()


MAX_IMAGE_BYTES = 4 * 1024 * 1024  # Azure F0 file limit; also well under our 10 MB upload limit


def _shrink(data: bytes) -> bytes:
    """Re-encode very large photos as JPEG so every receipt can be uploaded and OCR'd."""
    if len(data) <= MAX_IMAGE_BYTES:
        return data
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    quality, scale = 92, 1.0
    while True:
        cand = (
            img if scale == 1.0 else img.resize((int(img.width * scale), int(img.height * scale)))
        )
        buf = io.BytesIO()
        cand.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= MAX_IMAGE_BYTES or scale < 0.3:
            return buf.getvalue()
        scale *= 0.85


def export() -> None:
    """Write data/raw/cord/<split>/<image_id>.<ext> and labels.jsonl per split."""
    import pandas as pd

    base = raw_dir()
    for split in SPLITS:
        files = sorted((base / "parquet").rglob(f"*{split}*/*.parquet")) or sorted(
            (base / "parquet").rglob(f"{split}*.parquet")
        )
        if not files:
            print(f"WARNING: no parquet files for split {split!r} under {base / 'parquet'}")
            continue
        out = base / split
        out.mkdir(parents=True, exist_ok=True)
        n = 0
        with (out / "labels.jsonl").open("w", encoding="utf-8") as fh:
            for f in files:
                for row in pd.read_parquet(f).itertuples():
                    gt = json.loads(row.ground_truth)
                    image_id = gt["meta"]["image_id"]
                    data = _shrink(row.image["bytes"])
                    name = f"{image_id:04d}.{_ext(data)}"
                    (out / name).write_bytes(data)
                    label = to_schema(gt["gt_parse"]).model_dump()
                    rec = {"file": name, "image_id": image_id, "split": split, "label": label}
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
        print(f"{split}: {n} receipts -> {out}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "download":
        download()
    elif cmd == "export":
        export()
    else:
        sys.exit("usage: python -m docduel.datasets.cord [download|export]")
