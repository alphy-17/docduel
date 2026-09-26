import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from sqlmodel import Session, select

from docduel.db import Document, get_session
from docduel.ingest import IngestError, ingest_bytes
from docduel.ingest.factory import build_ocr
from docduel.ingest.limits import MAX_FILE_BYTES
from docduel.ingest.ocr_azure import CachedOcr
from docduel.schemas.api import DocumentOut
from docduel.settings import Settings, get_settings
from docduel.testset import is_test_document

router = APIRouter(prefix="/api")

_EXT = {"pdf": "pdf", "png": "png", "jpeg": "jpg", "webp": "webp", "csv": "csv"}


def get_ocr() -> CachedOcr | None:
    return build_ocr(get_settings())


def _out(doc: Document, already: bool) -> DocumentOut:
    return DocumentOut(
        document_id=doc.id,
        kind=doc.kind,
        pages=doc.pages,
        text_preview=doc.text[:500],
        ocr_ms=doc.ocr_ms,
        is_test_document=is_test_document(doc.sha256),
        already_ingested=already,
    )


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    session: Annotated[Session, Depends(get_session)],
    ocr: Annotated[CachedOcr | None, Depends(get_ocr)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentOut:
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise IngestError("file_too_large", "The file is larger than the 10 MB limit.", 413)

    # Same bytes uploaded before: reuse the stored result (no extraction, no OCR cost).
    from docduel.ingest.service import sha256_hex

    existing = session.exec(select(Document).where(Document.sha256 == sha256_hex(data))).first()
    if existing:
        return _out(existing, already=True)

    doc = await asyncio.to_thread(ingest_bytes, data, file.filename, ocr)
    if settings.keep_uploads:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        (settings.upload_dir / f"{doc.sha256}.{_EXT[doc.file_type]}").write_bytes(data)

    row = Document(
        sha256=doc.sha256,
        kind=doc.kind,
        filename=doc.filename,
        text=doc.text,
        pages=doc.pages,
        ocr_provider=doc.ocr_provider,
        ocr_ms=doc.ocr_ms,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _out(row, already=False)
