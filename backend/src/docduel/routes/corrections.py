"""Corrections page API (Plan 8.2, 8.3).

The Owner checks our model's answer for each hard-pool document against the page image, fixes
mistakes and saves. Pre-fill comes from our fine-tuned model's saved eval answers, never from
OpenAI (rule R3). Test-set documents can never be saved as corrections (rule R4).
"""

import io
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session, select

from docduel.datasets.build import _read_jsonl, splits_dir
from docduel.db import Correction, get_session
from docduel.errors import ApiError
from docduel.schemas.extraction import ReceiptExtraction
from docduel.settings import REPO_DIR, get_settings
from docduel.testset import is_test_document

router = APIRouter(prefix="/api")
PREFILL_MODEL = "small-ft-r1"
SessionDep = Annotated[Session, Depends(get_session)]
FIELDS = [f for f in ReceiptExtraction.model_fields if f != "line_items"]


def pool() -> dict[str, dict]:
    rows = _read_jsonl(splits_dir() / "hard_correct.jsonl")
    return {r["id"]: r for r in sorted(rows, key=lambda r: r["id"])}


def prefill_path() -> Path:
    return REPO_DIR / "reports" / f"eval_{PREFILL_MODEL}_hard-correct_extract_v1.json"


def prefills() -> dict[str, dict | None]:
    path = prefill_path()
    if not path.exists():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        o["id"]: (o.get("parsed") if o.get("schema_valid") else None) for o in report["outputs"]
    }


def empty_answer() -> dict[str, Any]:
    return {**{f: None for f in FIELDS}, "line_items": []}


def changed_fields(before: dict | None, after: dict) -> int:
    """How many top-level fields (line items count as one) differ from the pre-fill."""
    before = before or empty_answer()
    keys = [*FIELDS, "line_items"]
    return sum(before.get(k) != after.get(k) for k in keys)


def _doc(doc_id: str) -> dict:
    doc = pool().get(doc_id)
    if doc is None:
        raise ApiError("not_found", f"{doc_id} is not in the corrections pool", 404)
    return doc


@router.get("/corrections")
def list_corrections(session: SessionDep) -> dict[str, Any]:
    docs = pool()
    saved = {c.doc_id: c for c in session.exec(select(Correction))}
    items = [
        {
            "id": d,
            "verified": d in saved,
            "changed_fields": saved[d].changed_fields if d in saved else None,
        }
        for d in docs
    ]
    return {
        "total": len(docs),
        "verified": sum(i["verified"] for i in items),
        "prefill_model": PREFILL_MODEL,
        "prefill_ready": prefill_path().exists(),
        "items": items,
    }


@router.get("/corrections/{doc_id}")
def get_correction(doc_id: str, session: SessionDep) -> dict[str, Any]:
    _doc(doc_id)
    pre = prefills().get(doc_id)
    saved = session.exec(select(Correction).where(Correction.doc_id == doc_id)).first()
    return {
        "id": doc_id,
        "prefill_model": PREFILL_MODEL,
        "prefill_valid": pre is not None,
        "prefill": pre or empty_answer(),
        "saved": json.loads(saved.payload_json) if saved else None,
        "verified": saved is not None,
    }


@lru_cache(maxsize=64)
def _page_png(path: str) -> bytes:
    """Page 1 at high resolution, cropped to the printed area so small text is readable."""
    import pypdfium2 as pdfium
    from PIL import ImageFilter

    img = pdfium.PdfDocument(path)[0].render(scale=3.0).to_pil().convert("RGB")
    ink = (
        img.convert("L").filter(ImageFilter.MedianFilter(5)).point(lambda v: 255 if v < 150 else 0)
    )
    box = ink.getbbox()  # the median filter removes scan speckle, so this finds real text
    if box:
        pad = 40
        x0, y0, x1, y1 = box
        img = img.crop(
            (
                max(x0 - pad, 0),
                max(y0 - pad, 0),
                min(x1 + pad, img.width),
                min(y1 + pad, img.height),
            )
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.get("/corrections/{doc_id}/image")
def correction_image(doc_id: str) -> Response:
    doc = _doc(doc_id)
    png = _page_png(str(get_settings().data_dir / doc["path"]))
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.put("/corrections/{doc_id}")
def save_correction(doc_id: str, answer: ReceiptExtraction, session: SessionDep) -> dict[str, Any]:
    doc = _doc(doc_id)
    if is_test_document(doc["sha256"]):
        raise ApiError("test_document", "Test-set documents can never become training data", 409)
    payload = answer.model_dump(mode="json")
    changed = changed_fields(prefills().get(doc_id), payload)
    row = session.exec(select(Correction).where(Correction.doc_id == doc_id)).first()
    if row is None:
        row = Correction(
            doc_id=doc_id,
            document_sha256=doc["sha256"],
            payload_json="",
            prefill_model=PREFILL_MODEL,
        )
    if row.used_in_round is not None:
        raise ApiError("locked", f"Already used in round {row.used_in_round}; not editable", 409)
    row.payload_json = json.dumps(payload)
    row.changed_fields = changed
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    total = len(pool())
    verified = len(session.exec(select(Correction)).all())
    return {"id": doc_id, "changed_fields": changed, "verified": verified, "total": total}
