"""Generate the six Phase 1 test fixtures. Deterministic; all data is invented.

Run from backend/:  uv run python tests/fixtures/make_fixtures.py
"""

import io
import random
from pathlib import Path

import pypdfium2 as pdfium
from fpdf import FPDF
from PIL import Image, ImageFilter

OUT = Path(__file__).parent
RECEIPT_LINES = [
    "BLUE FIG CAFE",
    "12 Example Street, Geelong VIC 3220",
    "ABN 00 000 000 000",
    "Tax invoice no. INV-20417      Date: 14/08/2026",
    "",
    "2 x Flat white           @ 5.20      10.40",
    "1 x Banana bread         @ 6.50       6.50",
    "1 x Avocado toast        @ 16.00     16.00",
    "",
    "Subtotal                            32.90",
    "GST included                         2.99",
    "TOTAL                        AUD    32.90",
    "Paid by card (VISA ****0000)",
    "Thank you!",
]


def text_pdf() -> bytes:
    pdf = FPDF(format=(100 * 2.83465, 90 * 2.83465), unit="pt")  # 100 x 90 mm receipt
    pdf.set_creation_date(__import__("datetime").datetime(2026, 1, 1))
    pdf.add_page()
    pdf.set_font("Courier", size=7.5)
    for line in RECEIPT_LINES:
        pdf.cell(0, 11, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def raster(pdf_bytes: bytes, scale: float = 2.5) -> Image.Image:
    doc = pdfium.PdfDocument(pdf_bytes)
    img = doc[0].render(scale=scale).to_pil().convert("L")
    doc.close()
    return img


def degrade(img: Image.Image, angle: float, seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = img.rotate(angle, expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.6))
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 60):  # light salt-and-pepper noise
        x, y = rng.randrange(w), rng.randrange(h)
        px[x, y] = rng.choice((40, 220))
    return img


def main() -> None:
    base = text_pdf()
    (OUT / "receipt_text.pdf").write_bytes(base)

    scan = degrade(raster(base), angle=1.2, seed=1)
    buf = io.BytesIO()
    scan.save(buf, format="PDF", resolution=180)  # image-only PDF: no text layer
    (OUT / "receipt_scan.pdf").write_bytes(buf.getvalue())

    photo = degrade(raster(base, 3.0), angle=-2.5, seed=2).convert("RGB")
    photo.save(OUT / "receipt_photo.jpg", format="JPEG", quality=85)

    (OUT / "transactions_good.csv").write_text(
        "Date,Description,Amount\n"
        "2026-08-01,SQ *BLUE FIG CAFE 4411 GEELONG,-10.40\n"
        "2026-08-02,WOOLWORTHS 3321 BELMONT,-86.15\n"
        "2026-08-03,MYKI TOPUP VIC,-20.00\n"
        "2026-08-05,ORIGIN ENERGY BILL,-142.60\n",
        encoding="utf-8",
    )
    (OUT / "transactions_bad.csv").write_text(
        "when,what\n2026-08-01,SQ *BLUE FIG CAFE\n2026-08-02,WOOLWORTHS\n", encoding="utf-8"
    )
    (OUT / "fake.pdf").write_bytes(b"This is plain text pretending to be a PDF.\n")
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
