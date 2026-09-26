"""Opt-in test against real Azure. Run with:  $env:RUN_LIVE_AZURE="1"; uv run pytest -m live -s"""

import os

import pytest

from docduel.ingest import ingest_bytes
from docduel.ingest.factory import build_ocr
from docduel.settings import Settings

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("RUN_LIVE_AZURE") != "1", reason="set RUN_LIVE_AZURE=1 to run")
def test_real_azure_reads_scan_and_caches(fixture_bytes, tmp_path):
    settings = Settings(data_dir=tmp_path)
    ocr = build_ocr(settings)
    assert ocr is not None, "Azure is not configured in backend/.env"
    data = fixture_bytes("receipt_scan.pdf")
    first = ingest_bytes(data, "receipt_scan.pdf", ocr)
    second = ingest_bytes(data, "receipt_scan.pdf", ocr)
    assert first.kind == "pdf_scan"
    assert "BLUE FIG" in first.text.upper()
    assert "32.90" in first.text
    assert ocr.calls == 1, "second read should come from the cache"
    assert second.ocr_cache_hits == 1
    print("\n--- Azure OCR text ---\n" + first.text)
