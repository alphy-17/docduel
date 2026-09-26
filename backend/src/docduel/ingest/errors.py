class IngestError(Exception):
    """A user-facing ingestion error with a stable code and an HTTP status."""

    def __init__(self, error_code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status = status
