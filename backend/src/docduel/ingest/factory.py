from docduel.ingest.cache import OcrCache
from docduel.ingest.errors import IngestError
from docduel.ingest.ocr_azure import AzureReadProvider, CachedOcr
from docduel.settings import Settings


def build_ocr(settings: Settings) -> CachedOcr | None:
    """Real Azure OCR behind the disk cache, or None when Azure isn't configured."""
    try:
        provider = AzureReadProvider(
            settings.azure_di_endpoint, settings.azure_di_key.get_secret_value()
        )
    except IngestError:
        return None
    return CachedOcr(provider, OcrCache(settings.ocr_cache_dir))
