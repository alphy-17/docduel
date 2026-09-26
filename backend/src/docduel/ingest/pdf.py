"""PDF text extraction and page rasterisation with pypdfium2."""

import io
from dataclasses import dataclass

import pypdfium2 as pdfium

from docduel.ingest.errors import IngestError
from docduel.ingest.limits import MAX_PAGES, MIN_TEXT_CHARS_PER_PAGE

RENDER_SCALE = 3.0  # 72 dpi * 3 = 216 dpi, enough for OCR


@dataclass
class PdfPageText:
    index: int
    text: str

    @property
    def meaningful_chars(self) -> int:
        return sum(ch.isalnum() for ch in self.text)

    @property
    def needs_ocr(self) -> bool:
        return self.meaningful_chars < MIN_TEXT_CHARS_PER_PAGE


def _open(data: bytes) -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise IngestError(
            "pdf_unreadable", "The PDF could not be opened (it may be damaged or encrypted)."
        ) from exc


def read_text_layer(data: bytes) -> list[PdfPageText]:
    pdf = _open(data)
    try:
        n = len(pdf)
        if n == 0:
            raise IngestError("pdf_empty", "The PDF has no pages.")
        if n > MAX_PAGES:
            raise IngestError("too_many_pages", f"The PDF has {n} pages; the limit is {MAX_PAGES}.")
        pages = []
        for i in range(n):
            page = pdf[i]
            textpage = page.get_textpage()
            text = textpage.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            pages.append(PdfPageText(index=i, text=text.strip()))
            textpage.close()
            page.close()
        return pages
    finally:
        pdf.close()


def render_page_png(data: bytes, index: int, scale: float = RENDER_SCALE) -> bytes:
    pdf = _open(data)
    try:
        page = pdf[index]
        image = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        page.close()
        return buf.getvalue()
    finally:
        pdf.close()
