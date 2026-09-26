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
