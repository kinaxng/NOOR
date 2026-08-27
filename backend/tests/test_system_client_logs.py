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


def test_legacy_emby_webhook_invalidates_media_library_cache():
    from app.api.endpoints import media_library

    client = TestClient(_app())
    before = media_library._sync_state_payload()["version"]

    response = client.post(
        "/api/webhooks/emby",
        json={"Event": "Library.New", "Item": {"Name": "Webhook Test"}},
        headers={"X-Forwarded-For": "192.0.2.10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["source"] == "192.0.2.10"
    assert payload["summary"] == "Library.New: Webhook Test"
    assert payload["sync_state"]["version"] == before + 1
    assert payload["sync_state"]["last_webhook_at"]

    logs = client.get("/api/system/logs", params={"tail": 1}).json()["logs"]
    assert logs[-1]["source"] == "Emby · 192.0.2.10"
    assert "Webhook Test" in logs[-1]["message"]
