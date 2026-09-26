"""Phase 3 acceptance: break ONLY the left model's key; the right model must still finish.

Runs one tiny summarise duel against the real OpenAI API. The left model gets a fake key
(OpenAI rejects it for free); the right model uses the real key (~US$0.0003).
Usage: uv run python scripts/check_broken_key.py
"""

import asyncio
import dataclasses
import os

from dotenv import load_dotenv

from docduel.models.registry import duel_keys, load_models
from docduel.runs.orchestrator import run_duel
from docduel.runs.prompting import build_prompt
from docduel.settings import BACKEND_DIR

load_dotenv(BACKEND_DIR / ".env")
os.environ["DOCDUEL_FAKE_KEY"] = "sk-this-key-is-deliberately-fake"


async def main() -> None:
    models = load_models()
    left_key, right_key = duel_keys()
    left = dataclasses.replace(models[left_key], api_key_env="DOCDUEL_FAKE_KEY")
    right = models[right_key]
    prompt = build_prompt("summarise", text="Invoice 42 from Acme Pty Ltd. Total AUD 110.00.")

    async def emit(name: str, data: dict) -> None:
        if name != "model.delta":
            print(
                name, {k: data[k] for k in ("model_key", "error_code", "schema_valid") if k in data}
            )

    outcomes = await run_duel([left, right], prompt, emit)
    by_key = {o.model_key: o for o in outcomes}
    ok = by_key[left_key].error_code == "auth_failed" and by_key[right_key].schema_valid is True
    print("PASS" if ok else "FAIL", f"right cost US${by_key[right_key].cost_usd}")


asyncio.run(main())
