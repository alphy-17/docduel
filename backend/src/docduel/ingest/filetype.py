"""Detect a file's real type from its bytes, never from its name."""

from typing import Literal

from docduel.ingest.errors import IngestError

FileType = Literal["pdf", "png", "jpeg", "webp", "csv"]

_EXTENSIONS: dict[str, FileType] = {
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".webp": "webp",
    ".csv": "csv",
}


def sniff(data: bytes) -> FileType | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if _looks_like_csv(data):
        return "csv"
    return None


def _looks_like_csv(data: bytes) -> bool:
    head = data[:4096]
    if b"\x00" in head:
        return False
    try:
        text = head.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = head.decode("cp1252")
        except UnicodeDecodeError:
            return False
    first_line = text.splitlines()[0] if text.strip() else ""
    return "," in first_line or ";" in first_line


def detect(data: bytes, filename: str | None = None) -> FileType:
    if not data:
        raise IngestError("empty_file", "The file is empty.", 400)
    kind = sniff(data)
    claimed = _claimed_type(filename)
    if kind is None:
        if claimed:
            raise IngestError(
                "file_type_mismatch",
                f"The file is named '{filename}' but its contents are not a valid "
                f"{claimed.upper()}.",
                415,
            )
        raise IngestError(
            "unsupported_file_type",
            "Unsupported file type. Use PDF, PNG, JPG, WEBP or CSV.",
            415,
        )
    if claimed and claimed != kind:
        raise IngestError(
            "file_type_mismatch",
            f"The file is named '{filename}' but its contents look like {kind.upper()}.",
            415,
        )
    return kind


def _claimed_type(filename: str | None) -> FileType | None:
    if not filename or "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return _EXTENSIONS.get(ext)
