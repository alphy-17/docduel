import io

import pytest
from fpdf import FPDF

from docduel.ingest import IngestError, ingest_bytes
from docduel.ingest.filetype import detect

# --- the six fixtures (acceptance: four succeed, two are rejected) ---


def test_text_pdf_uses_text_layer_without_ocr(fixture_bytes, cached_ocr, fake_provider):
    doc = ingest_bytes(fixture_bytes("receipt_text.pdf"), "receipt_text.pdf", cached_ocr)
    assert doc.kind == "pdf_text"
    assert doc.pages == 1
    assert "BLUE FIG CAFE" in doc.text and "32.90" in doc.text
    assert fake_provider.calls == 0
    assert doc.ocr_provider is None


def test_scanned_pdf_goes_through_ocr(fixture_bytes, cached_ocr, fake_provider):
    doc = ingest_bytes(fixture_bytes("receipt_scan.pdf"), "receipt_scan.pdf", cached_ocr)
    assert doc.kind == "pdf_scan"
    assert doc.ocr_pages == [0]
    assert fake_provider.calls == 1
    assert "BLUE FIG CAFE" in doc.text


def test_photo_goes_through_ocr(fixture_bytes, cached_ocr, fake_provider):
    doc = ingest_bytes(fixture_bytes("receipt_photo.jpg"), "receipt_photo.jpg", cached_ocr)
    assert doc.kind == "image"
    assert fake_provider.calls == 1


def test_good_csv(fixture_bytes):
    doc = ingest_bytes(fixture_bytes("transactions_good.csv"), "transactions_good.csv")
    assert doc.kind == "csv"
    assert doc.csv_rows == 4
    lines = doc.text.splitlines()
    assert lines[0] == "row_id | date | description | amount"
    assert lines[1] == "1 | 2026-08-01 | SQ *BLUE FIG CAFE 4411 GEELONG | -10.40"


def test_bad_csv_is_rejected(fixture_bytes):
    with pytest.raises(IngestError) as err:
        ingest_bytes(fixture_bytes("transactions_bad.csv"), "transactions_bad.csv")
    assert err.value.error_code == "csv_missing_columns"
    assert "amount" in err.value.message


def test_fake_pdf_is_rejected(fixture_bytes):
    with pytest.raises(IngestError) as err:
        ingest_bytes(fixture_bytes("fake.pdf"), "fake.pdf")
    assert err.value.error_code == "file_type_mismatch"
    assert err.value.status == 415


# --- cache: the same scan twice makes one provider call ---


def test_same_scan_twice_calls_ocr_once(fixture_bytes, cached_ocr, fake_provider):
    data = fixture_bytes("receipt_scan.pdf")
    first = ingest_bytes(data, "a.pdf", cached_ocr)
    second = ingest_bytes(data, "b.pdf", cached_ocr)
    assert fake_provider.calls == 1
    assert first.ocr_cache_hits == 0 and second.ocr_cache_hits == 1
    assert first.text == second.text


# --- type detection is by bytes, not name ---


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.7 ...", "pdf"),
        (b"\x89PNG\r\n\x1a\n....", "png"),
        (b"\xff\xd8\xff\xe0....", "jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
        (b"date,description,amount\n1,2,3\n", "csv"),
    ],
)
def test_detect_by_bytes(data, expected):
    assert detect(data, None) == expected


def test_real_pdf_with_wrong_name_is_detected_by_bytes(fixture_bytes):
    with pytest.raises(IngestError) as err:
        ingest_bytes(fixture_bytes("receipt_text.pdf"), "receipt.png")
    assert err.value.error_code == "file_type_mismatch"


def test_unsupported_type():
    with pytest.raises(IngestError) as err:
        ingest_bytes(b"GIF89a\x00\x00binary", "x.gif")
    assert err.value.error_code == "unsupported_file_type"
    assert err.value.status == 415


def test_empty_file():
    with pytest.raises(IngestError) as err:
        ingest_bytes(b"", "empty.pdf")
    assert err.value.status == 400


# --- limits ---


def test_file_too_large():
    with pytest.raises(IngestError) as err:
        ingest_bytes(b"%PDF-" + b"0" * (10 * 1024 * 1024), "big.pdf")
    assert err.value.error_code == "file_too_large"
    assert err.value.status == 413


def test_pdf_over_three_pages_rejected():
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for i in range(4):
        pdf.add_page()
        pdf.cell(0, 10, f"Page {i + 1} with enough text to count as a text layer page")
    with pytest.raises(IngestError) as err:
        ingest_bytes(bytes(pdf.output()), "four.pdf")
    assert err.value.error_code == "too_many_pages"


def test_csv_over_200_rows_rejected():
    rows = "\n".join(f"2026-08-01,SHOP {i},-1.00" for i in range(201))
    with pytest.raises(IngestError) as err:
        ingest_bytes(f"date,description,amount\n{rows}\n".encode(), "big.csv")
    assert err.value.error_code == "too_many_rows"


def test_csv_columns_are_case_insensitive_and_semicolons_work():
    data = b"DATE;Description; AMOUNT\n2026-08-01;SHOP;-1.00\n"
    doc = ingest_bytes(data, "semi.csv")
    assert doc.csv_rows == 1


def test_scan_without_ocr_configured_is_a_clear_error(fixture_bytes):
    with pytest.raises(IngestError) as err:
        ingest_bytes(fixture_bytes("receipt_scan.pdf"), "scan.pdf", None)
    assert err.value.error_code == "ocr_not_configured"
    assert err.value.status == 503


def test_webp_is_converted_before_ocr(cached_ocr, fake_provider):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, format="WEBP")
    doc = ingest_bytes(buf.getvalue(), "x.webp", cached_ocr)
    assert doc.kind == "image"
    assert fake_provider.calls == 1


def test_azure_lines_are_joined_one_per_line():
    from types import SimpleNamespace as NS

    from docduel.ingest.ocr_azure import lines_text

    result = NS(
        content="A B C",
        pages=[NS(lines=[NS(content="BLUE FIG CAFE"), NS(content="TOTAL 32.90")])],
    )
    assert lines_text(result) == "BLUE FIG CAFE\nTOTAL 32.90"
    assert lines_text(NS(content=" plain ", pages=[])) == "plain"
