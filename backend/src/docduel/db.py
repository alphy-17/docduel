"""SQLModel tables and session helpers (Plan Section 9.7)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine

from docduel.settings import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    sha256: str = Field(index=True, unique=True)
    kind: str
    source: str = "upload"  # upload | cord | synthetic
    filename: str | None = None
    text: str
    pages: int
    ocr_provider: str | None = None
    ocr_ms: int = 0
    created_at: datetime = Field(default_factory=_now)


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    task: str
    instructions: str | None = None
    prompt_version: str
    created_at: datetime = Field(default_factory=_now)


class ModelResult(SQLModel, table=True):
    __tablename__ = "model_results"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    run_id: str = Field(foreign_key="runs.id", index=True)
    model_key: str
    model_id: str | None = None
    raw_output: str = ""
    parsed_json: str | None = None  # JSON text, only when schema-valid
    schema_valid: bool | None = None  # None = task has no schema (custom, describe)
    ttft_ms: float | None = None
    latency_ms: float | None = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float | None = None
    cold_start: bool = False
    error_code: str | None = None
    error: str | None = None


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=args)


def init_db(engine: Engine | None = None) -> None:
    SQLModel.metadata.create_all(engine or get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
