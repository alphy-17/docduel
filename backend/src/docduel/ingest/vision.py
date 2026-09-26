"""Prepare the image both models see for the describe task (Plan 3.9).

Same pixels for both models = fair duel. Longest side capped at 1536 px, saved as JPEG.
Images: EXIF-rotated original. Scanned PDFs: page 1 rendered.
"""

import io

import pypdfium2 as pdfium
from PIL import Image, ImageOps

MAX_SIDE = 1536
JPEG_QUALITY = 85
DESCRIBE_KINDS = ("image", "pdf_scan")


def _to_jpeg(img: Image.Image) -> bytes:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)  # only ever shrinks
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def prepare_for_model(data: bytes, file_type: str) -> bytes:
    if file_type == "pdf":
        pdf = pdfium.PdfDocument(data)
        try:
            page = pdf[0]
            w, h = page.get_size()  # points (1/72 inch)
            bitmap = page.render(scale=MAX_SIDE / max(w, h))
            img = bitmap.to_pil().copy()
            bitmap.close()
            page.close()
        finally:
            pdf.close()
        return _to_jpeg(img)
    with Image.open(io.BytesIO(data)) as img:
        return _to_jpeg(img)
