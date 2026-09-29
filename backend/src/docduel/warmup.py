"""Wake the small model's GPU before a live run (Plan 9.3).

Azure Container Apps cuts any HTTP request after 240 s, but a cold Modal GPU takes about
5 minutes to start. So the site wakes the GPU first and only starts the run once it answers.
The site stops asking once the GPU is ready, so an open tab never keeps the GPU running.
"""

import asyncio
import os
import time

import httpx

from docduel.models.registry import duel_keys, load_models

READY_FOR_S = 180  # Modal keeps the container 5 min after the last request; stay well inside
MAX_WAIT_S = 480

_state: dict = {"task": None, "ready_at": -1e9}


def status() -> str:
    if time.monotonic() - _state["ready_at"] < READY_FOR_S:
        return "ready"
    task = _state["task"]
    return "waking" if task is not None and not task.done() else "cold"


async def _wake(base: str, token: str) -> None:
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=120) as c:
        while time.monotonic() - start < MAX_WAIT_S:
            try:
                r = await c.get(f"{base}/models", headers={"Authorization": f"Bearer {token}"})
                if r.status_code == 200:
                    _state["ready_at"] = time.monotonic()
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(10)


def ensure_awake() -> str:
    """Start waking the left Duel model if it runs on our GPU; return the current state."""
    state = status()
    if state != "cold":
        return state
    spec = load_models()[duel_keys()[0]]
    base = os.getenv(spec.base_url_env or "", "")
    token = os.getenv(spec.api_key_env or "", "")
    if spec.provider != "vllm" or not base or not token:
        return "ready"  # nothing to wake (an API model or not configured)
    _state["task"] = asyncio.create_task(_wake(base, token))
    return "waking"
