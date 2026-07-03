"""API smoke tests using FastAPI's TestClient (no LLM required)."""
from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_settings():
    with TestClient(app) as client:
        r = client.get("/api/settings")
        assert r.status_code == 200
        body = r.json()
        assert body["active_model"]
        assert "pdf" in body["supported_types"]


def test_history_empty_ok():
    with TestClient(app) as client:
        r = client.get("/api/history?limit=5")
        assert r.status_code == 200
        assert "conversations" in r.json()


def test_upload_rejects_bad_type():
    with TestClient(app) as client:
        r = client.post(
            "/api/upload",
            files={"file": ("evil.exe", b"data", "application/octet-stream")},
        )
        assert r.status_code == 400
