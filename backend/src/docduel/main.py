import os
from contextlib import asynccontextmanager

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from docduel.db import init_db
from docduel.ingest.errors import IngestError
from docduel.routes import documents
from docduel.settings import BACKEND_DIR, get_settings

load_dotenv(BACKEND_DIR / ".env")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="DocDuel API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)


@app.exception_handler(IngestError)
async def ingest_error_handler(_: Request, exc: IngestError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status, content={"error_code": exc.error_code, "message": exc.message}
    )


def _model_status() -> dict[str, dict[str, object]]:
    """Report which models are configured. Never returns key values."""
    data = yaml.safe_load((settings.config_dir / "models.yaml").read_text(encoding="utf-8"))
    out: dict[str, dict[str, object]] = {}
    for key, cfg in data["models"].items():
        key_env = cfg.get("api_key_env")
        out[key] = {
            "model_id": cfg.get("model_id"),
            "status": cfg.get("status", "active"),
            "key_present": bool(key_env and os.getenv(key_env)),
        }
    return out


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "live_mode_enabled": settings.live_mode_enabled,
        "ocr_configured": bool(
            settings.azure_di_endpoint and settings.azure_di_key.get_secret_value()
        ),
        "models": _model_status(),
    }
