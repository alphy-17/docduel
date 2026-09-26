"""Run both models on the same prompt at the same time (Plan 3.4).

Each model has its own timeout and its own error handling, so one slow or broken model
never stops the other. Progress is reported through an `emit(event, data)` callback,
which the SSE endpoint (3.5) turns into browser events (Plan 9.6).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from docduel.models.client import Delta, Finished, ModelCallError, ModelClient, client_for
from docduel.models.registry import ModelSpec
from docduel.runs.costing import gpu_cost, load_pricing, openai_cost
from docduel.runs.prompting import SCHEMAS, Prompt

Emit = Callable[[str, dict[str, Any]], Awaitable[None]]
ClientFactory = Callable[[ModelSpec], ModelClient]

TIMEOUT_S = 60.0
COLD_START_TTFT_MS = 10_000  # Plan 11: our model's TTFT above 10 s = cold start


@dataclass
class ModelOutcome:
    model_key: str
    model_id: str | None
    raw_output: str = ""
    parsed: Any = None  # dict when schema-valid
    schema_valid: bool | None = None  # None: task has no schema
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

    def completed_event(self) -> dict[str, Any]:
        return {
            "model_key": self.model_key,
            "output": self.parsed if self.schema_valid else self.raw_output,
            "schema_valid": self.schema_valid,
            "ttft_ms": self.ttft_ms,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "cold_start": self.cold_start,
        }

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate(task: str, text: str) -> tuple[bool | None, Any]:
    """(schema_valid, parsed). Invalid output keeps parsed=None (scores zero, Plan 10.1)."""
    model: type[BaseModel] | None = SCHEMAS[task]
    if model is None:
        return None, None
    try:
        return True, model.model_validate(json.loads(text)).model_dump()
    except (json.JSONDecodeError, ValidationError):
        return False, None


def cost_for(spec: ModelSpec, done: Finished, pricing: dict[str, Any]) -> float | None:
    if spec.provider == "openai":
        prices = pricing.get("openai", {}).get(spec.model_id or "")
        if prices is None:
            return None
        return float(
            openai_cost(prices, done.input_tokens, done.cached_input_tokens, done.output_tokens)
        )
    gpu_prices = pricing.get("modal", {}).get("gpu_per_hour", {})
    if spec.gpu is None or spec.gpu not in gpu_prices:
        return None  # GPU chosen in Phase 6
    return float(gpu_cost(gpu_prices[spec.gpu], done.latency_ms / 1000))


async def run_model(
    spec: ModelSpec,
    prompt: Prompt,
    emit: Emit,
    client_factory: ClientFactory = client_for,
    pricing: dict[str, Any] | None = None,
    timeout_s: float = TIMEOUT_S,
) -> ModelOutcome:
    out = ModelOutcome(model_key=spec.key, model_id=spec.model_id)
    pricing = pricing if pricing is not None else load_pricing()
    done: Finished | None = None
    try:
        client = client_factory(spec)
        async with asyncio.timeout(timeout_s):
            async for event in client.stream(prompt.messages, prompt.response_format):
                if isinstance(event, Delta):
                    out.raw_output += event.text
                    await emit("model.delta", {"model_key": spec.key, "text": event.text})
                else:
                    done = event
    except TimeoutError:
        out.error_code, out.error = "timeout", f"No complete answer within {timeout_s:.0f} s."
    except ModelCallError as exc:
        out.error_code, out.error = exc.error_code, exc.message
    if done is None and out.error_code is None:
        out.error_code, out.error = "no_answer", "The model stream ended without an answer."
    if out.error_code or done is None:
        await emit("model.error", {"model_key": spec.key, **_err(out)})
        return out

    out.raw_output = done.text
    out.ttft_ms, out.latency_ms = done.ttft_ms, done.latency_ms
    out.input_tokens, out.cached_input_tokens = done.input_tokens, done.cached_input_tokens
    out.output_tokens, out.reasoning_tokens = done.output_tokens, done.reasoning_tokens
    out.cost_usd = cost_for(spec, done, pricing)
    out.cold_start = (
        spec.provider == "vllm" and done.ttft_ms is not None and done.ttft_ms > COLD_START_TTFT_MS
    )
    out.schema_valid, out.parsed = validate(prompt.task, done.text)
    await emit("model.completed", out.completed_event())
    return out


def _err(out: ModelOutcome) -> dict[str, str | None]:
    return {"error_code": out.error_code, "message": out.error}


async def run_duel(
    specs: list[ModelSpec],
    prompt: Prompt,
    emit: Emit,
    client_factory: ClientFactory = client_for,
    timeout_s: float = TIMEOUT_S,
) -> list[ModelOutcome]:
    """Run every model in `specs` in parallel. Never raises for a single model's failure."""
    pricing = load_pricing()
    return list(
        await asyncio.gather(
            *(run_model(s, prompt, emit, client_factory, pricing, timeout_s) for s in specs)
        )
    )
