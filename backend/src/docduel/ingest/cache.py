"""On-disk OCR cache so the same page is never sent to Azure twice."""

import json
from datetime import UTC, datetime
from pathlib import Path


class OcrCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))["content"]

    def put(self, key: str, content: str, provider: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "provider": provider,
            "content": content,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._path(key).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
