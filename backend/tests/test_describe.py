"""Describe task (Plan 3.9): image prep, in-memory store, API checks."""

import io

import pytest
from PIL import Image

from docduel.ingest.vision import MAX_SIDE, prepare_for_model
from docduel.runs import image_store


def _big_png(w: int = 3000, h: int = 2000) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def test_images_are_capped_and_jpeg() -> None:
    out = prepare_for_model(_big_png(), "png")
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "JPEG" and max(img.size) == MAX_SIDE
        assert img.size == (1536, 1024)  # aspect ratio kept


def test_small_images_are_not_enlarged() -> None:
    with Image.open(io.BytesIO(prepare_for_model(_big_png(400, 300), "png"))) as img:
        assert img.size == (400, 300)


def test_scanned_pdf_page_one_is_rendered(fixture_bytes) -> None:
    out = prepare_for_model(fixture_bytes("receipt_scan.pdf"), "pdf")
    with Image.open(io.BytesIO(out)) as img:
        assert max(img.size) == MAX_SIDE


def test_image_store_expires_after_ttl() -> None:
    image_store.clear()
    image_store.put("doc1", b"jpeg", now=0)
    assert image_store.get("doc1", now=image_store.TTL_S - 1) == b"jpeg"
    assert image_store.get("doc1", now=image_store.TTL_S + 1) is None


def test_image_store_drops_oldest_when_full() -> None:
    image_store.clear()
    for i in range(image_store.MAX_ITEMS + 1):
        image_store.put(f"d{i}", b"x", now=0)
    assert image_store.get("d0", now=0) is None
    assert image_store.get(f"d{image_store.MAX_ITEMS}", now=0) == b"x"


@pytest.fixture(autouse=True)
def _clean_store():
    image_store.clear()
    yield
    image_store.clear()
