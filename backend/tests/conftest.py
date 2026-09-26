from pathlib import Path

import pytest

from docduel.ingest.cache import OcrCache
from docduel.ingest.ocr_azure import CachedOcr

FIXTURES = Path(__file__).parent / "fixtures"


class FakeOcr:
    """Stands in for Azure: counts calls and returns fixed text."""

    name = "fake-ocr"

    def __init__(self, text: str = "BLUE FIG CAFE\nTOTAL AUD 32.90") -> None:
        self.text = text
        self.calls = 0

    def read(self, image: bytes, mime: str) -> str:
        assert image, "OCR received empty image bytes"
        self.calls += 1
        return self.text


@pytest.fixture
def fixture_bytes():
    return lambda name: (FIXTURES / name).read_bytes()


@pytest.fixture
def fake_provider() -> FakeOcr:
    return FakeOcr()


@pytest.fixture
def cached_ocr(tmp_path, fake_provider) -> CachedOcr:
    return CachedOcr(fake_provider, OcrCache(tmp_path / "ocr"))
