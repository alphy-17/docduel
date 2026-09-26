"""Save runs and model results (Plan 9.7)."""

import json

from sqlmodel import Session

from docduel.db import ModelResult, Run
from docduel.runs.orchestrator import ModelOutcome


def create_run(
    session: Session, document_id: str, task: str, prompt_version: str, instructions: str | None
) -> Run:
    run = Run(
        document_id=document_id,
        task=task,
        instructions=instructions,
        prompt_version=prompt_version,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def save_outcomes(session: Session, run_id: str, outcomes: list[ModelOutcome]) -> None:
    for o in outcomes:
        session.add(
            ModelResult(
                run_id=run_id,
                model_key=o.model_key,
                model_id=o.model_id,
                raw_output=o.raw_output,
                parsed_json=json.dumps(o.parsed) if o.parsed is not None else None,
                schema_valid=o.schema_valid,
                ttft_ms=o.ttft_ms,
                latency_ms=o.latency_ms,
                input_tokens=o.input_tokens,
                cached_input_tokens=o.cached_input_tokens,
                output_tokens=o.output_tokens,
                reasoning_tokens=o.reasoning_tokens,
                cost_usd=o.cost_usd,
                cold_start=o.cold_start,
                error_code=o.error_code,
                error=o.error,
            )
        )
    session.commit()
