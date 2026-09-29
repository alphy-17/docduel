"""Corrections API (Plan 8.2, 8.3) and the hard-pool split (8.1)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from docduel.datasets import hard
from docduel.db import Correction, get_session
from docduel.main import app
from docduel.routes import corrections

ANSWER = {
    "vendor_name": "Blue Fig Cafe",
    "document_date": "2026-04-03",
    "document_number": "00123",
    "currency": "AUD",
    "line_items": [{"description": "Flat white", "quantity": 1, "unit_price": 5.5, "amount": 5.5}],
    "subtotal": 5.5,
    "tax": 0.5,
    "service_charge": None,
    "discount": None,
    "total": 5.5,
    "payment_method": "card",
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    pool = {
        "inv_G_1": {"id": "inv_G_1", "sha256": "h1", "path": "x.pdf"},
        "inv_G_2": {"id": "inv_G_2", "sha256": "TEST", "path": "y.pdf"},
    }
    monkeypatch.setattr(corrections, "pool", lambda: pool)
    monkeypatch.setattr(corrections, "prefills", lambda: {"inv_G_1": dict(ANSWER, total=9.9)})
    monkeypatch.setattr(corrections, "is_test_document", lambda h: h == "TEST")
    yield TestClient(app), engine
    app.dependency_overrides.clear()


def test_list_and_prefill_from_our_model(client):
    c, _ = client
    body = c.get("/api/corrections").json()
    assert body["total"] == 2 and body["verified"] == 0
    assert body["prefill_model"] == "small-ft-r1"
    one = c.get("/api/corrections/inv_G_1").json()
    assert one["prefill"]["total"] == 9.9 and one["prefill_valid"] and not one["verified"]
    two = c.get("/api/corrections/inv_G_2").json()
    assert two["prefill_valid"] is False and two["prefill"]["line_items"] == []


def test_save_counts_changes_and_marks_human_verified(client):
    c, engine = client
    r = c.put("/api/corrections/inv_G_1", json=ANSWER)
    assert r.status_code == 200
    assert r.json() == {"id": "inv_G_1", "changed_fields": 1, "verified": 1, "total": 2}
    with Session(engine) as s:
        row = s.exec(select(Correction)).one()
    assert row.verified_by_human and row.prefilled_from == "our_model"
    assert row.document_sha256 == "h1" and json.loads(row.payload_json)["total"] == 5.5
    # saving again updates the same row
    c.put("/api/corrections/inv_G_1", json=dict(ANSWER, total=5.6))
    assert c.get("/api/corrections").json()["verified"] == 1


def test_refuses_test_documents_unknown_ids_and_bad_shapes(client):
    c, _ = client
    assert c.put("/api/corrections/inv_G_2", json=ANSWER).json()["error_code"] == "test_document"
    assert c.put("/api/corrections/nope", json=ANSWER).status_code == 404
    assert c.put("/api/corrections/inv_G_1", json={"total": "abc"}).status_code == 422


def test_used_corrections_are_locked(client):
    c, engine = client
    c.put("/api/corrections/inv_G_1", json=ANSWER)
    with Session(engine) as s:
        row = s.exec(select(Correction)).one()
        row.used_in_round = 2
        s.add(row)
        s.commit()
    assert c.put("/api/corrections/inv_G_1", json=ANSWER).json()["error_code"] == "locked"


def test_hard_pool_split_is_fixed_and_disjoint():
    rows = [{"id": f"inv_G_{30000 + i}"} for i in range(60)]
    a1, h1 = hard.assign(rows)
    a2, h2 = hard.assign(list(reversed(rows)))
    assert len(a1) == 40 and len(h1) == 20
    assert [r["id"] for r in h1] == [r["id"] for r in h2]
    assert not {r["id"] for r in a1} & {r["id"] for r in h1}
