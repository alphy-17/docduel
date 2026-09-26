"""Truly redact words from text-layer PDFs: delete matching text objects and draw black boxes.

Terms are passed on the command line (never stored in the repo). Originals are never modified.

  uv run python scripts/redact_pdfs.py IN_DIR OUT_DIR --term Alice --term Smith

Photo/scanned PDFs (no text layer) are copied unchanged and reported, so they can be checked by eye.
To black out a region of a photo PDF, pass --box "FILE.pdf:x0,y0,x1,y1" with fractions of the page
(0,0 = top-left, 1,1 = bottom-right). The page is re-rendered as an image with the box painted in.
Exits non-zero if any term can still be found in an output file's text layer.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw

PAD = 1.5  # points of padding around each black box


def _matches(text: str, terms: list[str]) -> bool:
    """Whole-word, case-insensitive match (so 'Ann' does not hit 'Announcement')."""
    return any(re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE) for t in terms)


def redact_file(src: Path, dst: Path, terms: list[str]) -> tuple[int, bool]:
    pdf = pdfium.PdfDocument(src)
    removed, has_text = 0, False
    for i in range(len(pdf)):
        page = pdf[i]
        textpage = page.get_textpage()
        has_text |= bool(textpage.get_text_range().strip())
        boxes, targets = [], []
        for obj in page.get_objects(max_depth=15, textpage=textpage):
            if obj.type != raw.FPDF_PAGEOBJ_TEXT:
                continue
            try:
                text = obj.extract()
            except pdfium.PdfiumError:
                text = ""
            if text and _matches(text, terms):
                boxes.append(obj.get_bounds())
                targets.append(obj)
        textpage.close()
        for obj in targets:
            if obj.level == 0:
                page.remove_obj(obj)
            else:  # nested inside a form XObject: remove from its container
                raw.FPDFFormObj_RemoveObject(obj.container.raw, obj.raw)
            removed += 1
        for obj in targets:
            obj.close()  # detached objects are now ours to free
        for left, bottom, right, top in boxes:
            rect = raw.FPDFPageObj_CreateNewRect(
                left - PAD, bottom - PAD, right - left + 2 * PAD, top - bottom + 2 * PAD
            )
            raw.FPDFPageObj_SetFillColor(rect, 0, 0, 0, 255)
            raw.FPDFPath_SetDrawMode(rect, raw.FPDF_FILLMODE_WINDING, 0)
            raw.FPDFPage_InsertObject(page.raw, rect)
        page.gen_content()
        page.close()
    pdf.save(dst)
    pdf.close()
    return removed, has_text


def box_redact(src: Path, dst: Path, boxes: list[tuple[float, float, float, float]]) -> None:
    from PIL import ImageDraw

    pdf = pdfium.PdfDocument(src)
    images = []
    for i in range(len(pdf)):
        img = pdf[i].render(scale=3.0).to_pil().convert("RGB")
        draw = ImageDraw.Draw(img)
        for x0, y0, x1, y1 in boxes:
            w, h = img.size
            draw.rectangle((x0 * w, y0 * h, x1 * w, y1 * h), fill="black")
        images.append(img)
    pdf.close()
    images[0].save(dst, format="PDF", resolution=216, save_all=True, append_images=images[1:])


def leftover_terms(path: Path, terms: list[str]) -> list[str]:
    pdf = pdfium.PdfDocument(path)
    text = "\n".join(p.get_textpage().get_text_range() for p in pdf)
    pdf.close()
    return [t for t in terms if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--term", action="append", default=[], help="word to remove (repeatable)")
    ap.add_argument("--terms-file", type=Path, help="text file with one term per line")
    ap.add_argument("--box", action="append", default=[], help='"FILE.pdf:x0,y0,x1,y1" fractions')
    args = ap.parse_args()
    if args.terms_file:
        lines = args.terms_file.read_text(encoding="utf-8").splitlines()
        args.term += [t.strip() for t in lines if t.strip() and not t.startswith("#")]
    if not args.term:
        ap.error("give at least one --term or a --terms-file")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    boxes: dict[str, list[tuple[float, float, float, float]]] = {}
    for spec in args.box:
        name, coords = spec.rsplit(":", 1)
        x0, y0, x1, y1 = (float(v) for v in coords.split(","))
        boxes.setdefault(name, []).append((x0, y0, x1, y1))
    for src in sorted(args.in_dir.iterdir()):
        if src.suffix.lower() != ".pdf":
            continue
        dst = args.out_dir / src.name
        removed, has_text = redact_file(src, dst, args.term)
        if not has_text:
            if src.name in boxes:
                box_redact(src, dst, boxes[src.name])
                print(
                    f"{src.name:28s} photo - {len(boxes[src.name])} box(es) painted; check visually"
                )
            else:
                shutil.copyfile(src, dst)
                print(f"{src.name:28s} no text layer (photo/scan) - copied; check visually")
            continue
        left = leftover_terms(dst, args.term)
        status = "OK" if not left else f"FAILED, still contains {len(left)} term(s)"
        failed |= bool(left)
        print(f"{src.name:28s} removed {removed} text object(s) - {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
