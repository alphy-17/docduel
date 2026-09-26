"""Document ingestion: bytes in, clean text out."""

from docduel.ingest.errors import IngestError
from docduel.ingest.service import IngestedDocument, ingest_bytes

__all__ = ["IngestError", "IngestedDocument", "ingest_bytes"]
