"""Image validation and preparation for OCR."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from docduel.ingest.errors import IngestError
from docduel.ingest.limits import AZURE_MAX_IMAGE_BYTES


def validate_image(data: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise IngestError("image_unreadable", "The image could not be read.") from exc


def prepare_for_ocr(data: bytes, kind: str) -> tuple[bytes, str]:
    """Return (bytes, mime) Azure can read.

    Azure Read accepts PNG and JPEG but not WEBP, and the free tier caps files at 4 MB.
    WEBP or oversized images are re-encoded as JPEG (and downscaled if needed).
    """
    if kind in ("png", "jpeg") and len(data) <= AZURE_MAX_IMAGE_BYTES:
        return data, "image/png" if kind == "png" else "image/jpeg"
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        quality, scale = 90, 1.0
        while True:
            w, h = int(img.width * scale), int(img.height * scale)
            candidate = img if scale == 1.0 else img.resize((w, h), Image.LANCZOS)
            buf = io.BytesIO()
            candidate.save(buf, format="JPEG", quality=quality)
            out = buf.getvalue()
            if len(out) <= AZURE_MAX_IMAGE_BYTES or scale < 0.3:
                return out, "image/jpeg"
            scale *= 0.8
