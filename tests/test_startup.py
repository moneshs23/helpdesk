from fastapi.testclient import TestClient

from backend.main import app


def test_app_starts_without_blocking_warmup(monkeypatch):
    async def fake_warmup():
        return None

    monkeypatch.setattr("backend.main._warmup", fake_warmup)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
