"""Orchestrator with fake model clients (Plan 3.8): success, invalid JSON, timeout, one fails."""

import asyncio
import json

from sqlmodel import Session, SQLModel, create_engine, select

from docduel.db import Document, ModelResult, Run
from docduel.models.client import Delta, Finished, ModelCallError
from docduel.models.registry import ModelSpec
from docduel.runs.orchestrator import run_duel
from docduel.runs.prompting import build_prompt
from docduel.runs.store import create_run, save_outcomes

LEFT = ModelSpec("left", "openai", "gpt-6-luna", None, "K", reasoning_effort="none")
RIGHT = ModelSpec("right", "openai", "gpt-6-luna", None, "K", reasoning_effort="low")
GOOD = json.dumps({"bullets": ["a", "b", "c"]})


class FakeClient:
    def __init__(self, text: str = GOOD, delay: float = 0.0, fail: str | None = None) -> None:
        self.text, self.delay, self.fail = text, delay, fail

    async def stream(self, messages, response_format=None):
        if self.fail:
            raise ModelCallError(self.fail, "broken on purpose")
        await asyncio.sleep(self.delay)
        half = len(self.text) // 2
        yield Delta(self.text[:half])
        yield Delta(self.text[half:])
        yield Finished(self.text, 1000, 400, 200, 50, 12.0, 30.0 + self.delay * 1000)


def _run(clients: dict[str, FakeClient], timeout_s: float = 5.0):
    events: list[tuple[str, dict]] = []

    async def emit(name: str, data: dict) -> None:
        events.append((name, data))

    prompt = build_prompt("summarise", text="doc")
    outcomes = asyncio.run(
        run_duel([LEFT, RIGHT], prompt, emit, lambda s: clients[s.key], timeout_s)
    )
    return {o.model_key: o for o in outcomes}, events


def test_both_succeed_with_cost_and_events() -> None:
    out, events = _run({"left": FakeClient(), "right": FakeClient()})
    for key in ("left", "right"):
        o = out[key]
        assert o.schema_valid is True and o.parsed == {"bullets": ["a", "b", "c"]}
        # 600 x 0.10 + 400 x 0.01 + 200 x 0.50 per 1M = 0.000164 (pricing.yaml luna)
        assert abs(o.cost_usd - 0.000164) < 1e-12
    names = [n for n, _ in events]
    assert names.count("model.delta") == 4 and names.count("model.completed") == 2
    deltas = "".join(
        d["text"] for n, d in events if n == "model.delta" and d["model_key"] == "left"
    )
    assert deltas == GOOD


def test_invalid_json_is_marked_invalid_not_crashed() -> None:
    out, _ = _run(
        {"left": FakeClient('{"bullets": ["only one"]}'), "right": FakeClient("not json")}
    )
    assert out["left"].schema_valid is False and out["left"].parsed is None
    assert out["right"].schema_valid is False
    assert out["right"].raw_output == "not json"


def test_timeout_on_one_model_does_not_block_the_other() -> None:
    out, events = _run({"left": FakeClient(delay=2.0), "right": FakeClient()}, timeout_s=0.3)
    assert out["left"].error_code == "timeout"
    assert out["right"].schema_valid is True
    assert ("model.error", {"model_key": "left", **_errfields(out["left"])}) in events


def test_broken_key_on_left_right_still_completes() -> None:
    out, events = _run({"left": FakeClient(fail="auth_failed"), "right": FakeClient()})
    assert out["left"].error_code == "auth_failed"
    assert out["right"].schema_valid is True
    assert [n for n, d in events if d["model_key"] == "left"] == ["model.error"]


def test_plain_text_task_has_no_schema() -> None:
    events: list = []

    async def emit(name, data):
        events.append(name)

    prompt = build_prompt("custom", text="doc", instructions="Who?")
    (o,) = asyncio.run(run_duel([LEFT], prompt, emit, lambda s: FakeClient("Acme Pty Ltd")))
    assert o.schema_valid is None and o.raw_output == "Acme Pty Ltd"


def test_results_are_stored(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    SQLModel.metadata.create_all(engine)
    out, _ = _run({"left": FakeClient(fail="timeout"), "right": FakeClient()})
    with Session(engine) as s:
        doc = Document(sha256="x", kind="pdf_text", text="doc", pages=1)
        s.add(doc)
        s.commit()
        run = create_run(s, doc.id, "summarise", "summarise_v1", None)
        save_outcomes(s, run.id, list(out.values()))
        rows = {r.model_key: r for r in s.exec(select(ModelResult)).all()}
        assert s.get(Run, run.id).prompt_version == "summarise_v1"
    assert rows["left"].error_code == "timeout" and rows["left"].parsed_json is None
    assert json.loads(rows["right"].parsed_json) == {"bullets": ["a", "b", "c"]}


def _errfields(o) -> dict:
    return {"error_code": o.error_code, "message": o.error}
