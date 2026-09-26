"""One model client for every model (Plan 3.3).

Uses the official `openai` SDK and the Chat Completions API, which both OpenAI and vLLM
speak. Only the base URL, key and model ID change between models, so the comparison is fair.
"""

import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import openai
from openai import AsyncOpenAI

from docduel.models.registry import ModelSpec


class ModelCallError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass
class Delta:
    text: str


@dataclass
class Finished:
    text: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int  # includes reasoning tokens (billed as output)
    reasoning_tokens: int
    ttft_ms: float | None  # time to first content token
    latency_ms: float


def _map_error(exc: Exception) -> ModelCallError:
    # Messages are generic on purpose: SDK errors can echo request details.
    if isinstance(exc, openai.AuthenticationError):
        return ModelCallError("auth_failed", "The model API rejected the API key.")
    if isinstance(exc, openai.APITimeoutError):
        return ModelCallError("timeout", "The model did not answer in time.")
    if isinstance(exc, openai.RateLimitError):
        return ModelCallError("rate_limited", "The model API is rate limiting or out of credit.")
    if isinstance(exc, openai.APIStatusError):
        return ModelCallError("api_error", f"The model API returned HTTP {exc.status_code}.")
    if isinstance(exc, openai.APIConnectionError):
        return ModelCallError("connection_error", "Could not reach the model API.")
    return ModelCallError("unknown_error", type(exc).__name__)


class ModelClient:
    def __init__(self, spec: ModelSpec, sdk: AsyncOpenAI) -> None:
        self.spec = spec
        self._sdk = sdk

    def _request_args(self, response_format: dict[str, Any] | None) -> dict[str, Any]:
        args: dict[str, Any] = {
            "model": self.spec.model_id,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if response_format is not None:
            args["response_format"] = response_format
        if self.spec.reasoning_effort is not None:
            args["reasoning_effort"] = self.spec.reasoning_effort
        if self.spec.extra_body:
            args["extra_body"] = self.spec.extra_body
        return args

    async def stream(
        self, messages: list[dict[str, Any]], response_format: dict[str, Any] | None = None
    ) -> AsyncIterator[Delta | Finished]:
        start = time.perf_counter()
        ttft_ms: float | None = None
        parts: list[str] = []
        usage = None
        try:
            stream = await self._sdk.chat.completions.create(
                messages=messages, **self._request_args(response_format)
            )
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = chunk.usage
                for choice in chunk.choices:
                    text = choice.delta.content if choice.delta else None
                    if text:
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - start) * 1000
                        parts.append(text)
                        yield Delta(text)
        except ModelCallError:
            raise
        except Exception as exc:  # noqa: BLE001 - every failure becomes a clean model.error
            raise _map_error(exc) from exc

        cached = reasoning = 0
        if usage is not None:
            if usage.prompt_tokens_details is not None:
                cached = usage.prompt_tokens_details.cached_tokens or 0
            if usage.completion_tokens_details is not None:
                reasoning = usage.completion_tokens_details.reasoning_tokens or 0
        yield Finished(
            text="".join(parts),
            input_tokens=usage.prompt_tokens if usage else 0,
            cached_input_tokens=cached,
            output_tokens=usage.completion_tokens if usage else 0,
            reasoning_tokens=reasoning,
            ttft_ms=ttft_ms,
            latency_ms=(time.perf_counter() - start) * 1000,
        )


def client_for(spec: ModelSpec, timeout_s: float = 60.0) -> ModelClient:
    """Build a client from env vars named in models.yaml. Never logs the key."""
    if spec.model_id is None or spec.status in {"not_deployed", "not_trained"}:
        raise ModelCallError("not_configured", f"Model '{spec.key}' is not available yet.")
    api_key = os.getenv(spec.api_key_env or "", "")
    if not api_key:
        raise ModelCallError("not_configured", f"No API key set for model '{spec.key}'.")
    base_url = os.getenv(spec.base_url_env) if spec.base_url_env else None
    sdk = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=0)
    return ModelClient(spec, sdk)
