"""Export the Benchmark page data as a static file for the public site (Plan 9.2).

  uv run python scripts/export_static.py

Writes frontend/public/demo/benchmark.json from exactly what GET /api/benchmark returns, so the
public page shows the same numbers (all from reports/*.json, rule R5) without the backend.
Run again after any new eval report.
"""

import json

from fastapi.testclient import TestClient

from docduel.main import app
from docduel.settings import REPO_DIR

OUT = REPO_DIR / "frontend" / "public" / "demo" / "benchmark.json"


def main() -> None:
    r = TestClient(app).get("/api/benchmark")
    r.raise_for_status()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r.json(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_DIR).as_posix()} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
