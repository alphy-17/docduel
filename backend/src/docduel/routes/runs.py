"""Duel endpoints (Plan 3.5 / 9.5): start a run, stream it live (SSE), fetch it later.

Flow: POST /api/runs creates the run -> the browser opens GET /api/runs/{id}/stream ->
both models run in parallel and every chunk is pushed to the browser as it arrives.
Opening the stream again after it finished replays the stored results (no new model calls).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session, select

from docduel.db import Document, ModelResult, Run, get_engine, get_session
from docduel.errors import ApiError
from docduel.models.client import client_for
from docduel.models.registry import duel_keys, load_models
from docduel.runs.orchestrator import ClientFactory, run_duel
from docduel.runs.prompting import build_prompt
from docduel.runs.store import create_run, save_outcomes
from docduel.settings import Settings, get_settings

router = APIRouter(prefix="/api")

Task = Literal["extract", "categorise", "summarise", "custom", "describe"]
_active: set[str] = set()  # runs currently streaming (stops double model calls)


class RunIn(BaseModel):
    document_id: str
    task: Task
    instructions: str | None = Field(default=None, max_length=2000)


class RunCreated(BaseModel):
    run_id: str


def get_client_factory() -> ClientFactory:
    return client_for


def _check_task(doc: Document, body: RunIn) -> None:
    if body.task == "describe":
        raise ApiError("not_implemented", "The describe task is added in step 3.9.", 501)
    if body.task == "categorise" and doc.kind != "csv":
        raise ApiError("wrong_task", "Categorise needs a CSV of transactions.", 422)
    if body.task == "extract" and doc.kind == "csv":
        raise ApiError("wrong_task", "Extract needs a receipt or invoice, not a CSV.", 422)
    if body.task == "custom" and not (body.instructions or "").strip():
        raise ApiError("instructions_required", "The custom task needs instructions.", 422)


@router.post("/runs", response_model=RunCreated)
def start_run(
    body: RunIn,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_access_code: Annotated[str | None, Header()] = None,
) -> RunCreated:
    if settings.live_mode_enabled:
        expected = settings.access_code.get_secret_value()
        if not expected or x_access_code != expected:
            raise ApiError("access_denied", "A valid access code is needed.", 403)
    doc = session.get(Document, body.document_id)
    if doc is None:
        raise ApiError("document_not_found", "No document with that id.", 404)
    _check_task(doc, body)
    version = build_prompt(body.task, text="", instructions=body.instructions or "x").version
    run = create_run(session, doc.id, body.task, version, body.instructions)
    return RunCreated(run_id=run.id)


def _sse(event: str, data: dict[str, Any]) -> ServerSentEvent:
    return ServerSentEvent(event=event, data=data)


def _replay(run: Run, rows: list[ModelResult]) -> list[ServerSentEvent]:
    events = [_sse("run.started", {"run_id": run.id, "task": run.task, "replayed": True})]
    for r in rows:
        if r.error_code:
            events.append(
                _sse(
                    "model.error",
                    {"model_key": r.model_key, "error_code": r.error_code, "message": r.error},
                )
            )
            continue
        output = json.loads(r.parsed_json) if r.parsed_json else r.raw_output
        events.append(
            _sse(
                "model.completed",
                {
                    "model_key": r.model_key,
                    "output": output,
                    "schema_valid": r.schema_valid,
                    "ttft_ms": r.ttft_ms,
                    "latency_ms": r.latency_ms,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": r.cost_usd,
                    "cold_start": r.cold_start,
                },
            )
        )
    events.append(_sse("run.completed", {"run_id": run.id}))
    return events


def _run_for_stream(
    run_id: str, engine: Annotated[Engine, Depends(get_engine)]
) -> tuple[Run, list[ModelResult]]:
    """Checks run before the stream starts, so errors are normal JSON responses, not SSE."""
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ApiError("run_not_found", "No run with that id.", 404)
        stored = list(session.exec(select(ModelResult).where(ModelResult.run_id == run_id)))
    if not stored and run_id in _active:
        raise ApiError("run_in_progress", "This run is already streaming.", 409)
    return run, stored


@router.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
async def stream_run(
    checked: Annotated[tuple[Run, list[ModelResult]], Depends(_run_for_stream)],
    engine: Annotated[Engine, Depends(get_engine)],
    factory: Annotated[ClientFactory, Depends(get_client_factory)],
) -> AsyncIterator[ServerSentEvent]:
    run, stored = checked
    run_id = run.id
    if stored:
        for ev in _replay(run, stored):
            yield ev
        return
    # Own session: the stream outlives the request's normal dependency lifetime.
    with Session(engine) as session:
        doc = session.get(Document, run.document_id)
        prompt = build_prompt(run.task, text=doc.text, instructions=run.instructions)
        models = load_models()
        specs = [models[k] for k in duel_keys()]

        _active.add(run_id)
        try:
            yield _sse(
                "run.started",
                {
                    "run_id": run_id,
                    "task": run.task,
                    "model_keys": [s.key for s in specs],
                    "placeholders": [s.key for s in specs if s.is_placeholder],
                    "prompt_version": prompt.version,
                },
            )
            queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

            async def emit(name: str, data: dict[str, Any]) -> None:
                await queue.put((name, data))

            task = asyncio.create_task(run_duel(specs, prompt, emit, factory))
            while not (task.done() and queue.empty()):
                try:
                    name, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                except TimeoutError:
                    continue
                yield _sse(name, data)
            save_outcomes(session, run_id, task.result())
            yield _sse("run.completed", {"run_id": run_id})
        finally:
            _active.discard(run_id)


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    run = session.get(Run, run_id)
    if run is None:
        raise ApiError("run_not_found", "No run with that id.", 404)
    rows = session.exec(select(ModelResult).where(ModelResult.run_id == run_id)).all()
    results = []
    for r in rows:
        item = r.model_dump(exclude={"parsed_json"})
        item["parsed"] = json.loads(r.parsed_json) if r.parsed_json else None
        results.append(item)
    return {"run": run.model_dump(), "results": results}
