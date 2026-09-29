"""Live-mode guard (Plan 9.3): env alias, access code on uploads, per-visitor rate limit."""

import pytest
from fastapi.testclient import TestClient

from docduel import guard
from docduel.errors import ApiError
from docduel.main import app
from docduel.settings import Settings, get_settings


def test_env_name_live_access_code_is_read(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_ACCESS_CODE", "from-env")
    assert Settings(_env_file=None).access_code.get_secret_value() == "from-env"


def test_rate_limit_counts_per_visitor_and_resets() -> None:
    guard._hits.clear()
    for _ in range(3):
        guard.check_rate("a", 3, now=0)
    with pytest.raises(ApiError) as err:
        guard.check_rate("a", 3, now=10)
    assert err.value.status == 429
    guard.check_rate("b", 3, now=10)  # another visitor is not affected
    guard.check_rate("a", 3, now=guard.WINDOW_S + 1)  # an hour later it works again


def test_upload_needs_code_in_live_mode() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        live_mode_enabled=True, access_code="letmein"
    )
    try:
        r = TestClient(app).post("/api/documents", files={"file": ("a.csv", b"x,y\n1,2\n")})
        assert r.status_code == 403 and r.json()["error_code"] == "access_denied"
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_access_check_endpoint() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        live_mode_enabled=True, access_code="letmein"
    )
    try:
        c = TestClient(app)
        assert c.post("/api/access").status_code == 403
        assert c.post("/api/access", headers={"X-Access-Code": "letmein"}).status_code == 204
    finally:
        app.dependency_overrides.pop(get_settings, None)
