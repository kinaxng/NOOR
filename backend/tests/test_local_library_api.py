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

def test_local_library_result_uses_original_source_key(monkeypatch, tmp_path):
    lib_dir = tmp_path / "subtitles"
    lib_dir.mkdir()
    subtitle = lib_dir / "TEST-009.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    results = local_library.search_local_library_with_config(
        "TEST-009",
        {"library_paths": str(lib_dir), "index_enabled": False, "match_fuzzy": False},
    )

    assert results
    assert results[0]["source_key"] == "local-subtitle-library"
    assert results[0]["source_type"] == "local_library"
