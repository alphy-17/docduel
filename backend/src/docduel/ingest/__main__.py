"""Debug CLI: uv run python -m docduel.ingest <path> [<path> ...]"""

import argparse
import logging
import sys
from pathlib import Path

from docduel.ingest.errors import IngestError
from docduel.ingest.factory import build_ocr
from docduel.ingest.service import ingest_bytes
from docduel.settings import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m docduel.ingest")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--chars", type=int, default=500, help="characters of text to print")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)  # hide SDK request/response logs

    ocr = build_ocr(get_settings())
    status = 0
    for path in args.paths:
        print(f"\n=== {path.name}")
        try:
            doc = ingest_bytes(path.read_bytes(), path.name, ocr)
        except IngestError as exc:
            print(f"REJECTED [{exc.error_code}] (HTTP {exc.status}): {exc.message}")
            status = 1
            continue
        print(f"kind={doc.kind} pages={doc.pages} sha256={doc.sha256[:12]}...")
        print(
            f"extract_ms={doc.extract_ms} ocr_ms={doc.ocr_ms} ocr_pages={doc.ocr_pages} "
            f"ocr_cache_hits={doc.ocr_cache_hits} provider={doc.ocr_provider}"
        )
        print("-" * 40)
        print(doc.text[: args.chars])
    if ocr is not None:
        print(f"\nAzure calls made in this run: {ocr.calls}")
    return status


if __name__ == "__main__":
    sys.exit(main())
