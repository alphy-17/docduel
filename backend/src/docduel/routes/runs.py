"""Duel endpoints (Plan 3.5 / 9.5): start a run, stream it live (SSE), fetch it later.

Flow: POST /api/runs creates the run -> the browser opens GET /api/runs/{id}/stream ->
both models run in parallel and every chunk is pushed to the browser as it arrives.
Opening the stream again after it finished replays the stored results (no new model calls).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session, select

from docduel import warmup
from docduel.db import Document, ModelResult, Run, get_engine, get_session
from docduel.errors import ApiError
from docduel.guard import code_only, live_guard
from docduel.ingest.csv import is_transactions_text
from docduel.ingest.vision import DESCRIBE_KINDS
from docduel.models.client import client_for
from docduel.models.registry import duel_keys, load_models
from docduel.runs import image_store
from docduel.runs.orchestrator import ClientFactory, run_duel
from docduel.runs.prompting import VERSION as PROMPT_VERSION
from docduel.runs.prompting import build_prompt
from docduel.runs.store import create_run, save_outcomes
from docduel.scoring.live import ground_truth_event
from docduel.testset import frozen_entry

router = APIRouter(prefix="/api")

Task = Literal["extract", "categorise", "summarise", "custom", "describe"]
_active: set[str] = set()  # runs currently streaming (stops double model calls)


class RunIn(BaseModel):
    document_id: str
    task: Task
    instructions: str | None = Field(default=None, max_length=2000)


class RunCreated(BaseModel):
    run_id: str


IMAGE_GONE = "image_expired"


def get_client_factory() -> ClientFactory:
    return client_for


def _check_task(doc: Document, body: RunIn) -> None:
    if body.task == "describe":
        if doc.kind not in DESCRIBE_KINDS:
            raise ApiError("wrong_task", "Describe needs a photo, image or scanned PDF.", 422)
        if image_store.get(doc.id) is None:
            raise ApiError(IMAGE_GONE, "The image is no longer in memory; upload it again.", 410)
    if body.task == "categorise" and not (doc.kind == "csv" and is_transactions_text(doc.text)):
        raise ApiError(
            "wrong_task",
            "Categorise needs a CSV with date, description and amount columns.",
            422,
        )
    if body.task == "extract" and doc.kind == "csv":
        raise ApiError("wrong_task", "Extract needs a receipt or invoice, not a CSV.", 422)
    if body.task == "custom" and not (body.instructions or "").strip():
        raise ApiError("instructions_required", "The custom task needs instructions.", 422)


@router.post("/access", status_code=204)
def check_access(_: Annotated[None, Depends(live_guard)]) -> None:
    """Lets the site check a live-mode access code before the visitor uploads anything."""


@router.get("/gpu")
async def gpu_status(_: Annotated[None, Depends(code_only)]) -> dict[str, str]:
    """Wakes the small model's GPU if it is asleep. States: cold, waking, ready."""
    return {"state": warmup.ensure_awake()}


@router.post("/runs", response_model=RunCreated)
def start_run(
    body: RunIn,
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[None, Depends(live_guard)],
) -> RunCreated:
    doc = session.get(Document, body.document_id)
    if doc is None:
        raise ApiError("document_not_found", "No document with that id.", 404)
    _check_task(doc, body)
    version = f"{body.task}_{PROMPT_VERSION}"
    run = create_run(session, doc.id, body.task, version, body.instructions)
    return RunCreated(run_id=run.id)


def _sse(event: str, data: dict[str, Any]) -> ServerSentEvent:
    return ServerSentEvent(event=event, data=data)


def _score_event(run: Run, entry: dict | None, answers: dict) -> list[ServerSentEvent]:
    """score.completed for a frozen test document; nothing for other documents."""
    if entry is None:
        return []
    payload = ground_truth_event(run.task, entry, answers)
    return [_sse("score.completed", payload)] if payload else []


def _replay(run: Run, rows: list[ModelResult], entry: dict | None) -> list[ServerSentEvent]:
    events = [_sse("run.started", {"run_id": run.id, "task": run.task, "replayed": True})]
    answers = {
        r.model_key: (r.schema_valid, json.loads(r.parsed_json) if r.parsed_json else None)
        for r in rows
        if not r.error_code
    }
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
    events += _score_event(run, entry, answers)
    events.append(_sse("run.completed", {"run_id": run.id}))
    return events


def _run_for_stream(
    run_id: str, engine: Annotated[Engine, Depends(get_engine)]
) -> tuple[Run, list[ModelResult], dict | None]:
    """Checks run before the stream starts, so errors are normal JSON responses, not SSE."""
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ApiError("run_not_found", "No run with that id.", 404)
        stored = list(session.exec(select(ModelResult).where(ModelResult.run_id == run_id)))
        doc = session.get(Document, run.document_id)
        entry = frozen_entry(doc.sha256) if doc else None
    if not stored and run_id in _active:
        raise ApiError("run_in_progress", "This run is already streaming.", 409)
    if not stored and run.task == "describe" and image_store.get(run.document_id) is None:
        raise ApiError(IMAGE_GONE, "The image is no longer in memory; upload it again.", 410)
    return run, stored, entry


@router.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
async def stream_run(
    checked: Annotated[tuple[Run, list[ModelResult], dict | None], Depends(_run_for_stream)],
    engine: Annotated[Engine, Depends(get_engine)],
    factory: Annotated[ClientFactory, Depends(get_client_factory)],
) -> AsyncIterator[ServerSentEvent]:
    run, stored, entry = checked
    run_id = run.id
    if stored:
        for ev in _replay(run, stored, entry):
            yield ev
        return
    # Own session: the stream outlives the request's normal dependency lifetime.
    with Session(engine) as session:
        doc = session.get(Document, run.document_id)
        image = image_store.get(run.document_id)
        prompt = build_prompt(
            run.task,
            text=doc.text,
            instructions=run.instructions,
            image=(image, "image/jpeg") if run.task == "describe" and image else None,
        )
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
            outcomes = task.result()
            save_outcomes(session, run_id, outcomes)
            answers = {
                o.model_key: (o.schema_valid, o.parsed) for o in outcomes if not o.error_code
            }
            for ev in _score_event(run, entry, answers):
                yield ev
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
