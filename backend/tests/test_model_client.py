"""Model client, strict schemas and cost maths. No real API calls: HTTP is faked."""

import asyncio
import json
from decimal import Decimal

import httpx
import pytest
from openai import AsyncOpenAI

from docduel.models.client import Delta, Finished, ModelCallError, ModelClient, client_for
from docduel.models.registry import ModelSpec, duel_keys, load_models
from docduel.runs.costing import gpu_cost, load_pricing, openai_cost, per_1000_docs
from docduel.schemas.extraction import ReceiptExtraction, SummaryOutput, TransactionCategories
from docduel.schemas.strict import response_format, strict_schema

SPEC = ModelSpec("openai", "openai", "gpt-test", None, "OPENAI_API_KEY", reasoning_effort="low")


def _sse(chunks: list[dict]) -> bytes:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return body.encode()


def _chunk(content: str | None = None, usage: dict | None = None) -> dict:
    choices = [] if content is None else [{"index": 0, "delta": {"content": content}}]
    return {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "gpt-test",
        "choices": choices,
        "usage": usage,
    }


def _client(handler) -> ModelClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="sk-fake", base_url="http://fake/v1", http_client=http, max_retries=0)
    return ModelClient(SPEC, sdk)


def _collect(client: ModelClient, **kw) -> list:
    async def run() -> list:
        return [e async for e in client.stream([{"role": "user", "content": "hi"}], **kw)]

    return asyncio.run(run())


def test_stream_success_collects_text_usage_and_request_args() -> None:
    seen: dict = {}
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 30,
        "total_tokens": 130,
        "prompt_tokens_details": {"cached_tokens": 40},
        "completion_tokens_details": {"reasoning_tokens": 12},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        body = _sse([_chunk('{"bullets": '), _chunk('["a","b","c"]}'), _chunk(usage=usage)])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    events = _collect(_client(handler), response_format=response_format(SummaryOutput))
    assert [e.text for e in events if isinstance(e, Delta)] == ['{"bullets": ', '["a","b","c"]}']
    done = events[-1]
    assert isinstance(done, Finished)
    assert json.loads(done.text) == {"bullets": ["a", "b", "c"]}
    assert (done.input_tokens, done.cached_input_tokens) == (100, 40)
    assert (done.output_tokens, done.reasoning_tokens) == (30, 12)
    assert done.ttft_ms is not None and done.latency_ms >= done.ttft_ms
    assert seen["reasoning_effort"] == "low"
    assert seen["stream_options"] == {"include_usage": True}
    assert seen["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize(
    ("status", "code"), [(401, "auth_failed"), (429, "rate_limited"), (500, "api_error")]
)
def test_http_errors_become_clean_codes(status: int, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "secret detail sk-abc"}})

    with pytest.raises(ModelCallError) as err:
        _collect(_client(handler))
    assert err.value.error_code == code
    assert "sk-abc" not in err.value.message


def test_timeout_becomes_timeout_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ModelCallError) as err:
        _collect(_client(handler))
    assert err.value.error_code == "timeout"


def test_client_for_refuses_missing_key_and_undeployed(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ModelCallError, match="No API key"):
        client_for(SPEC)
    models = load_models()
    with pytest.raises(ModelCallError) as err:
        client_for(models["small-ft-r1"])
    assert err.value.error_code == "not_configured"


def test_config_has_small_model_left_and_openai_right() -> None:
    """Phase 6: the real small model replaces the placeholder in the left panel."""
    models = load_models()
    left, right = duel_keys()
    assert (left, right) == ("small-base", "openai")
    assert models[left].provider == "vllm" and not models[left].is_placeholder
    assert models[left].gpu == "L4" and models[right].reasoning_effort == "medium"


@pytest.mark.parametrize("model", [ReceiptExtraction, TransactionCategories, SummaryOutput])
def test_schemas_meet_strict_mode_rules(model) -> None:
    schema = strict_schema(model)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_strict_check_rejects_optional_field() -> None:
    from pydantic import BaseModel

    class Bad(BaseModel):
        a: str | None = None

    with pytest.raises(ValueError):
        strict_schema(Bad)


# Hand-worked cost examples (Plan 3 acceptance: costs match hand maths).
def test_openai_cost_hand_worked() -> None:
    prices = {"input_per_1m": 0.10, "cached_input_per_1m": 0.01, "output_per_1m": 0.50}
    # 1,000 input (400 cached) + 200 output:
    # 600 x 0.10/1M = 0.00006; 400 x 0.01/1M = 0.000004; 200 x 0.50/1M = 0.0001
    assert openai_cost(prices, 1000, 400, 200) == Decimal("0.000164")
    assert per_1000_docs(Decimal("0.000164")) == Decimal("0.164")


def test_gpu_cost_hand_worked() -> None:
    # L4 at $0.80/hour busy for 4.5 s: 0.80 / 3600 x 4.5 = $0.001
    assert gpu_cost(0.80, 4.5) == Decimal("0.001")


def test_pricing_file_has_luna() -> None:
    assert load_pricing()["openai"]["gpt-6-luna"]["output_per_1m"] == 0.50


def test_vllm_waits_through_503_while_gpu_boots(monkeypatch) -> None:
    """Modal returns 503 at once while a sleeping container boots; we retry, not fail."""
    from docduel.models import client as client_mod

    monkeypatch.setattr(client_mod, "WAKE_RETRY_S", 0.0)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="booting")
        body = _sse([_chunk('{"bullets": ["a","b","c"]}'), _chunk(usage=None)])
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="k", base_url="http://fake/v1", http_client=http, max_retries=0)
    vllm = ModelSpec("small-base", "vllm", "small-base", None, "K", gpu="L4")
    events = _collect(ModelClient(vllm, sdk))
    assert calls["n"] == 3 and isinstance(events[-1], Finished)


def test_openai_503_is_not_retried() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with pytest.raises(ModelCallError) as err:
        _collect(_client(handler))
    assert err.value.error_code == "api_error"


def test_vllm_gives_up_after_wake_limit(monkeypatch) -> None:
    from docduel.models import client as client_mod

    monkeypatch.setattr(client_mod, "WAKE_RETRY_S", 0.0)
    monkeypatch.setattr(client_mod, "WAKE_LIMIT_S", -1.0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="booting")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sdk = AsyncOpenAI(api_key="k", base_url="http://fake/v1", http_client=http, max_retries=0)
    vllm = ModelSpec("small-base", "vllm", "small-base", None, "K", gpu="L4")
    with pytest.raises(ModelCallError) as err:
        _collect(ModelClient(vllm, sdk))
    assert err.value.error_code == "timeout"
