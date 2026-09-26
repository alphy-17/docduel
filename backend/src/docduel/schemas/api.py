from pydantic import BaseModel


class DocumentOut(BaseModel):
    document_id: str
    kind: str
    pages: int
    text_preview: str
    ocr_ms: int
    is_test_document: bool
    already_ingested: bool = False


class ErrorOut(BaseModel):
    error_code: str
    message: str
