from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import system


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(system.router)
    return app


def test_client_logs_are_recorded():
    client = TestClient(_app())
    response = client.post("/api/system/logs/client", json={
        "level": "warning",
        "message": "route restore check",
        "source": "frontend",
        "path": "/library",
    })
    assert response.status_code == 200
    assert response.json()["ok"] is True

    logs = client.get("/api/system/logs", params={"tail": 1}).json()["logs"]
    assert logs[-1]["level"] == "warning"
    assert logs[-1]["message"] == "route restore check"
    assert logs[-1]["line"] == "route restore check"
    assert logs[-1]["path"] == "/library"


def test_system_logs_accepts_legacy_since_cursor():
    client = TestClient(_app())
    first = client.post("/api/system/logs/client", json={"message": "first"}).json()["log"]["id"]
    client.post("/api/system/logs/client", json={"message": "second"})

    logs = client.get("/api/system/logs", params={"since": first}).json()
    assert logs["next_index"] >= first
    assert [item["line"] for item in logs["logs"]] == ["second"]
