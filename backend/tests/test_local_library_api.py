from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import local_library


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(local_library.router)
    return app


def test_local_library_routes_are_mounted():
    paths = _app().openapi()["paths"]

    assert "/api/local-library/config" in paths
    assert "/api/local-library/index/status" in paths
    assert "/api/local-library/index/rebuild" in paths


def test_local_library_config_round_trip(monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(
        local_library,
        "_load_config",
        lambda: {"library_paths": "/srv/subtitles", "index_enabled": True, "match_fuzzy": False},
    )
    monkeypatch.setattr(local_library, "_save_config", lambda config: saved.append(config))
    client = TestClient(_app())

    response = client.get("/api/local-library/config")
    assert response.status_code == 200
    assert response.json()["config"]["library_paths"] == "/srv/subtitles"

    payload = {"library_paths": "/mnt/subtitles", "index_enabled": False, "match_fuzzy": True}
    response = client.post("/api/local-library/config", json={"config": payload})
    assert response.status_code == 200
    assert saved == [payload]
