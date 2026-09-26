"""API errors returned as JSON {error_code, message} (Plan 9.5)."""


class ApiError(Exception):
    def __init__(self, error_code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status = status
