"""OCR via Azure AI Document Intelligence (prebuilt-read), wrapped in a disk cache."""

import io
import logging
import time
from typing import Protocol

from docduel.ingest.cache import OcrCache
from docduel.ingest.errors import IngestError

log = logging.getLogger("docduel.ocr")

PROVIDER_NAME = "azure-prebuilt-read"
# Bump when the stored OCR text format changes, so old cache entries are not reused.
OCR_FORMAT_VERSION = 2


class OcrProvider(Protocol):
    name: str

    def read(self, image: bytes, mime: str) -> str: ...


class AzureReadProvider:
    name = PROVIDER_NAME

    def __init__(self, endpoint: str, key: str) -> None:
        if not endpoint or not key:
            raise IngestError(
                "ocr_not_configured",
                "OCR is not configured (AZURE_DI_ENDPOINT / AZURE_DI_KEY missing).",
                503,
            )
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        self._client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    def read(self, image: bytes, mime: str) -> str:
        from azure.core.exceptions import AzureError

        try:
            poller = self._client.begin_analyze_document(
                "prebuilt-read", body=io.BytesIO(image), content_type="application/octet-stream"
            )
            result = poller.result()
        except AzureError as exc:
            raise IngestError(
                "ocr_failed", f"Azure OCR failed: {exc.__class__.__name__}", 502
            ) from exc
        return lines_text(result)


def lines_text(result) -> str:
    """One OCR line per text line, pages separated by a blank line (keeps reading order)."""
    pages = getattr(result, "pages", None) or []
    if not pages:
        return (getattr(result, "content", "") or "").strip()
    blocks = ["\n".join(line.content for line in (page.lines or [])) for page in pages]
    return "\n\n".join(b for b in blocks if b).strip()


class CachedOcr:
    """Checks the cache first; only calls the provider on a miss."""

    def __init__(self, provider: OcrProvider, cache: OcrCache) -> None:
        self.provider = provider
        self.cache = cache
        self.calls = 0  # provider calls made through this instance

    @property
    def name(self) -> str:
        return self.provider.name

    def read(self, key: str, image: bytes, mime: str) -> tuple[str, bool]:
        """Return (text, from_cache)."""
        key = f"{key}_v{OCR_FORMAT_VERSION}"
        cached = self.cache.get(key)
        if cached is not None:
            log.info("ocr cache hit key=%s", key)
            return cached, True
        start = time.perf_counter()
        text = self.provider.read(image, mime)
        self.calls += 1
        log.info(
            "ocr provider call provider=%s key=%s ms=%d",
            self.provider.name,
            key,
            (time.perf_counter() - start) * 1000,
        )
        self.cache.put(key, text, self.provider.name)
        return text, False
