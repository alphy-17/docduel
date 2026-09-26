"""Turn any supported file into an IngestedDocument."""

import hashlib
import time
from typing import Literal

from pydantic import BaseModel

from docduel.ingest import csv as csv_ingest
from docduel.ingest import filetype, images, pdf
from docduel.ingest.errors import IngestError
from docduel.ingest.limits import MAX_FILE_BYTES
from docduel.ingest.ocr_azure import CachedOcr

DocKind = Literal["pdf_text", "pdf_scan", "image", "csv"]


class IngestedDocument(BaseModel):
    sha256: str
    filename: str | None = None
    file_type: filetype.FileType
    kind: DocKind
    pages: int
    text: str
    ocr_provider: str | None = None
    ocr_pages: list[int] = []
    ocr_cache_hits: int = 0
    ocr_ms: int = 0  # time spent in OCR (cache hits are ~0)
    extract_ms: int = 0  # total ingestion time including OCR
    csv_rows: int | None = None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ingest_bytes(
    data: bytes, filename: str | None = None, ocr: CachedOcr | None = None
) -> IngestedDocument:
    start = time.perf_counter()
    if len(data) > MAX_FILE_BYTES:
        raise IngestError(
            "file_too_large",
            f"The file is {len(data) / 1_048_576:.1f} MB; the limit is 10 MB.",
            413,
        )
    ftype = filetype.detect(data, filename)
    digest = sha256_hex(data)
    doc = IngestedDocument(
        sha256=digest, filename=filename, file_type=ftype, kind="pdf_text", pages=1, text=""
    )

    if ftype == "csv":
        df = csv_ingest.parse_transactions(data)
        doc.kind, doc.text, doc.csv_rows = "csv", csv_ingest.render_for_prompt(df), len(df)

    elif ftype == "pdf":
        pages = pdf.read_text_layer(data)
        doc.pages = len(pages)
        texts = []
        for page in pages:
            if not page.needs_ocr:
                texts.append(page.text)
                continue
            ocr_client = _require(ocr)
            png = pdf.render_page_png(data, page.index)
            t0 = time.perf_counter()
            text, hit = ocr_client.read(f"{digest}_p{page.index}", png, "image/png")
            doc.ocr_ms += int((time.perf_counter() - t0) * 1000)
            doc.ocr_pages.append(page.index)
            doc.ocr_cache_hits += int(hit)
            doc.ocr_provider = ocr_client.name
            texts.append(text)
        doc.kind = "pdf_scan" if doc.ocr_pages else "pdf_text"
        doc.text = "\n\n".join(t for t in texts if t)

    else:  # png / jpeg / webp
        images.validate_image(data)
        ocr_client = _require(ocr)
        image, mime = images.prepare_for_ocr(data, ftype)
        t0 = time.perf_counter()
        text, hit = ocr_client.read(digest, image, mime)
        doc.ocr_ms = int((time.perf_counter() - t0) * 1000)
        doc.kind, doc.text, doc.ocr_pages = "image", text, [0]
        doc.ocr_cache_hits = int(hit)
        doc.ocr_provider = ocr_client.name

    if not doc.text.strip():
        raise IngestError("no_text_found", "No readable text was found in this document.")
    doc.extract_ms = int((time.perf_counter() - start) * 1000)
    return doc


def _require(ocr: CachedOcr | None) -> CachedOcr:
    if ocr is None:
        raise IngestError(
            "ocr_not_configured", "This document needs OCR, but OCR is not configured.", 503
        )
    return ocr
