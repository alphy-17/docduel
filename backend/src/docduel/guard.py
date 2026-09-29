"""Live-mode guard (Plan 9.3): access code + a small per-visitor rate limit.

Only active when LIVE_MODE_ENABLED=true (the public deployment). Local dev is unaffected.
The limit is in memory: fine for our single replica, reset whenever it restarts.
"""

import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, Header, Request

from docduel.errors import ApiError
from docduel.settings import Settings, get_settings

WINDOW_S = 3600
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # The host's proxy puts the visitor's address first in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def check_rate(key: str, limit: int, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    hits = _hits[key]
    while hits and now - hits[0] > WINDOW_S:
        hits.popleft()
    if len(hits) >= limit:
        raise ApiError("rate_limited", "Too many requests; try again in an hour.", 429)
    hits.append(now)


def live_guard(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_access_code: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.live_mode_enabled:
        return
    check_code(settings, x_access_code)
    check_rate(_client_ip(request), settings.rate_limit_per_hour)


def check_code(settings: Settings, code: str | None) -> None:
    expected = settings.access_code.get_secret_value()
    if not expected or code != expected:
        raise ApiError("access_denied", "A valid access code is needed.", 403)


def code_only(
    settings: Annotated[Settings, Depends(get_settings)],
    x_access_code: Annotated[str | None, Header()] = None,
) -> None:
    """Access code without counting towards the rate limit (for cheap status checks)."""
    if settings.live_mode_enabled:
        check_code(settings, x_access_code)
