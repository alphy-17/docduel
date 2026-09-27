"""POST /api/runs + SSE stream with fake models (no real API calls)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from docduel.db import Document, get_engine, get_session
from docduel.main import app
from docduel.models.client import Delta, Finished, ModelCallError
from docduel.routes.runs import get_client_factory

GOOD = json.dumps({"bullets": ["a", "b", "c"]})


class FakeClient:
    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.calls = 0

    async def stream(self, messages, response_format=None):
        self.calls += 1
        if self.fail:
            raise ModelCallError(self.fail, "broken on purpose")
        yield Delta(GOOD[:10])
        yield Delta(GOOD[10:])
        yield Finished(GOOD, 100, 0, 20, 0, 5.0, 9.0)


@pytest.fixture
def setup():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    clients = {"placeholder": FakeClient(), "openai": FakeClient()}

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_client_factory] = lambda: lambda spec: clients[spec.key]
    with Session(engine) as s:
        pdf = Document(sha256="a", kind="pdf_text", text="Invoice 1 total 10", pages=1)
        csv = Document(
            sha256="b",
            kind="csv",
            text="row_id | date | description | amount\n1 | x | y | 1",
            pages=1,
        )
        table = Document(sha256="c", kind="csv", text="name | score\nA | 1", pages=1)
        photo = Document(sha256="d", kind="image", text="OCR text", pages=1)
        s.add_all([pdf, csv, table, photo])
        s.commit()
        ids = {"pdf": pdf.id, "csv": csv.id, "table": table.id, "photo": photo.id}
    yield TestClient(app), clients, ids
    app.dependency_overrides.clear()


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        out.append((fields["event"], json.loads(fields["data"])))
    return out


def test_full_run_streams_and_stores(setup) -> None:
    client, clients, ids = setup
    r = client.post("/api/runs", json={"document_id": ids["pdf"], "task": "summarise"})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]

    stream = client.get(f"/api/runs/{run_id}/stream")
    assert stream.headers["content-type"].startswith("text/event-stream")
    events = _events(stream.text)
    names = [n for n, _ in events]
    assert names[0] == "run.started" and names[-1] == "run.completed"
    assert events[0][1]["placeholders"] == ["placeholder"]
    assert names.count("model.delta") == 4 and names.count("model.completed") == 2

    stored = client.get(f"/api/runs/{run_id}").json()
    assert stored["run"]["prompt_version"] == "summarise_v1"
    assert all(res["parsed"] == {"bullets": ["a", "b", "c"]} for res in stored["results"])

    # Opening the stream again replays stored results: no new model calls.
    again = [n for n, _ in _events(client.get(f"/api/runs/{run_id}/stream").text)]
    assert "model.delta" not in again and again.count("model.completed") == 2
    assert clients["openai"].calls == 1


def test_broken_left_key_right_still_completes(setup) -> None:
    client, clients, ids = setup
    clients["placeholder"] = FakeClient(fail="auth_failed")
    run_id = client.post("/api/runs", json={"document_id": ids["pdf"], "task": "summarise"}).json()[
        "run_id"
    ]
    events = _events(client.get(f"/api/runs/{run_id}/stream").text)
    by_model = {(n, d.get("model_key")) for n, d in events}
    assert ("model.error", "placeholder") in by_model
    assert ("model.completed", "openai") in by_model


@pytest.mark.parametrize(
    ("doc", "task", "extra", "code"),
    [
        ("pdf", "categorise", {}, "wrong_task"),
        ("csv", "extract", {}, "wrong_task"),
        ("pdf", "custom", {}, "instructions_required"),
        ("table", "categorise", {}, "wrong_task"),
        ("pdf", "describe", {}, "wrong_task"),
        ("photo", "describe", {}, "image_expired"),
        ("missing", "extract", {}, "document_not_found"),
    ],
)
def test_bad_requests(setup, doc, task, extra, code) -> None:
    client, _, ids = setup
    body = {"document_id": ids.get(doc, "nope"), "task": task, **extra}
    r = client.post("/api/runs", json=body)
    assert r.json()["error_code"] == code


def test_live_mode_needs_access_code(setup) -> None:
    from docduel.settings import Settings, get_settings

    client, _, ids = setup
    app.dependency_overrides[get_settings] = lambda: Settings(
        live_mode_enabled=True, access_code="letmein"
    )
    body = {"document_id": ids["pdf"], "task": "summarise"}
    assert client.post("/api/runs", json=body).status_code == 403
    ok = client.post("/api/runs", json=body, headers={"X-Access-Code": "letmein"})
    assert ok.status_code == 200


def test_stream_unknown_run_is_json_404(setup) -> None:
    client, _, _ = setup
    r = client.get("/api/runs/nope/stream")
    assert r.status_code == 404 and r.json()["error_code"] == "run_not_found"


def test_any_csv_can_be_summarised(setup) -> None:
    client, _, ids = setup
    r = client.post("/api/runs", json={"document_id": ids["table"], "task": "summarise"})
    assert r.status_code == 200


def test_describe_sends_the_image_to_both_models(setup) -> None:
    from docduel.runs import image_store

    client, clients, ids = setup
    seen = []

    class PlainClient(FakeClient):
        async def stream(self, messages, response_format=None):
            seen.append(messages[-1]["content"][1]["image_url"]["url"][:23])
            yield Delta("A red square.")
            yield Finished("A red square.", 900, 0, 5, 0, 5.0, 9.0)

    clients["placeholder"], clients["openai"] = PlainClient(), PlainClient()
    image_store.put(ids["photo"], b"\xff\xd8fakejpeg")
    run_id = client.post(
        "/api/runs", json={"document_id": ids["photo"], "task": "describe"}
    ).json()["run_id"]
    events = _events(client.get(f"/api/runs/{run_id}/stream").text)
    done = [d for n, d in events if n == "model.completed"]
    assert len(done) == 2 and all(d["output"] == "A red square." for d in done)
    assert seen == ["data:image/jpeg;base64,"] * 2
    image_store.clear()


class FixedClient:
    def __init__(self, text: str) -> None:
        self.text = text

    async def stream(self, messages, response_format=None):
        yield Delta(self.text)
        yield Finished(self.text, 100, 0, 20, 0, 5.0, 9.0)


LABEL = {
    "vendor_name": None,
    "document_date": None,
    "document_number": None,
    "currency": "AUD",
    "line_items": [{"description": "Coffee", "quantity": 1, "unit_price": None, "amount": 5.0}],
    "subtotal": None,
    "tax": None,
    "service_charge": None,
    "discount": None,
    "total": 5.0,
    "payment_method": None,
}


def test_test_document_gets_ground_truth_scores(setup, monkeypatch) -> None:
    """Plan 5.5: a frozen test document is scored right/wrong, also on replay."""
    from docduel.routes import runs as runs_route

    client, clients, ids = setup
    entry = {"id": "cord_test_9999", "task": "extract", "label": LABEL}
    monkeypatch.setattr(runs_route, "frozen_entry", lambda sha: entry if sha == "a" else None)
    clients["openai"] = FixedClient(json.dumps(LABEL))
    clients["placeholder"] = FixedClient(json.dumps(LABEL | {"total": 6.0, "line_items": []}))
    run_id = client.post("/api/runs", json={"document_id": ids["pdf"], "task": "extract"}).json()[
        "run_id"
    ]
    for _ in range(2):  # live, then replay
        events = dict(_events(client.get(f"/api/runs/{run_id}/stream").text))
        score = events["score.completed"]
        assert score["mode"] == "ground_truth" and score["test_document_id"] == "cord_test_9999"
        right, left = score["results"]["openai"], score["results"]["placeholder"]
        assert right["perfect"] and right["correct_items"] == [0]
        assert right["fields"] == {"currency": True, "total": True}
        assert left["fields"]["total"] is False and left["expected"]["total"] == 5.0
        assert left["items"] == {"tp": 0, "pred": 0, "gold": 1}


def test_other_documents_get_no_ground_truth(setup) -> None:
    client, _, ids = setup
    run_id = client.post("/api/runs", json={"document_id": ids["pdf"], "task": "summarise"}).json()[
        "run_id"
    ]
    names = [n for n, _ in _events(client.get(f"/api/runs/{run_id}/stream").text)]
    assert "score.completed" not in names
