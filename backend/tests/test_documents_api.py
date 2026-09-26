import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from docduel.db import get_session
from docduel.main import app
from docduel.routes.documents import get_ocr
from docduel.settings import Settings, get_settings


@pytest.fixture
def client(tmp_path, cached_ocr):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_ocr] = lambda: cached_ocr
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _post(client, fixture_bytes, name):
    return client.post("/api/documents", files={"file": (name, fixture_bytes(name))})


def test_upload_text_pdf(client, fixture_bytes, tmp_path):
    r = _post(client, fixture_bytes, "receipt_text.pdf")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "pdf_text"
    assert body["pages"] == 1
    assert "BLUE FIG CAFE" in body["text_preview"]
    assert body["is_test_document"] is False
    assert len(list((tmp_path / "uploads").iterdir())) == 1  # kept in dev


def test_upload_same_scan_twice_reuses_result(client, fixture_bytes, fake_provider):
    first = _post(client, fixture_bytes, "receipt_scan.pdf").json()
    second = _post(client, fixture_bytes, "receipt_scan.pdf").json()
    assert first["kind"] == "pdf_scan"
    assert second["document_id"] == first["document_id"]
    assert second["already_ingested"] is True
    assert fake_provider.calls == 1


def test_upload_errors_are_json(client, fixture_bytes):
    r = _post(client, fixture_bytes, "fake.pdf")
    assert r.status_code == 415
    assert r.json()["error_code"] == "file_type_mismatch"
    r = _post(client, fixture_bytes, "transactions_bad.csv")  # any CSV is accepted now
    assert r.status_code == 200 and r.json()["kind"] == "csv"


def test_photo_upload_is_ready_for_describe(client, fixture_bytes):
    from docduel.runs import image_store

    image_store.clear()
    body = _post(client, fixture_bytes, "receipt_photo.jpg").json()
    assert body["kind"] == "image" and body["can_describe"] is True
    assert _post(client, fixture_bytes, "receipt_text.pdf").json()["can_describe"] is False
    image_store.clear()
