from fastapi.testclient import TestClient

from docduel.main import app

client = TestClient(app)


def test_health_ok() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["models"]) == {
        "openai",
        "placeholder",
        "small-base",
        "small-ft-r1",
        "small-ft-r2",
    }


def test_health_never_leaks_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-should-not-appear")
    r = client.get("/api/health")
    assert "sk-test-should-not-appear" not in r.text
    assert r.json()["models"]["openai"]["key_present"] is True
