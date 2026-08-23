from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_main_app_exposes_actor_api_routes() -> None:
    paths = app.openapi()["paths"]

    expected = {
        "/api/media-library/actors",
        "/api/media-library/actors/mapping/status",
        "/api/media-library/actors/mapping/sync-mdc-ng",
        "/api/media-library/actors/duplicates",
        "/api/media-library/actors/mapping/matches",
        "/api/media-library/actors/tmdb-backfill/preview",
        "/api/media-library/actors/name-sync/preview",
        "/api/media-library/actors/mapping/merge-plan",
        "/api/media-library/actor/{actor_id}",
        "/api/media-library/actor/{actor_id}/movies",
        "/api/media-library/actor/{actor_id}/delete-diagnostics",
        "/api/media-library/actor/{actor_id}/avatar",
        "/api/media-library/actor/{actor_id}/metadata/tmdb-preview",
        "/api/media-library/actor/{actor_id}/metadata/tmdb-apply",
    }

    assert expected <= set(paths)


def test_actor_router_keeps_media_library_prefix() -> None:
    from app.api.endpoints import actors

    route_paths = {route.path for route in actors.router.routes}
    assert all(path.startswith("/api/media-library") for path in route_paths)
    assert "/api/media-library/actor/{actor_id}" in route_paths


@pytest.mark.skipif(not (ROOT / "forensics").exists(), reason="recovery evidence is kept in noor-restored")
def test_media_library_route_parity_matches_original_index() -> None:
    index_path = ROOT / "forensics" / "original-symbol-index.json"
    original = json.loads(index_path.read_text(encoding="utf-8"))["targets"][
        "backend/app/api/endpoints/media_library.py"
    ]["routes"]
    original_routes = {
        (method.upper(), "/api/media-library" + path)
        for method, path in (item.split(" ", 1) for item in original)
    }

    expected = set(original_routes)
    expected |= {
        ("GET", "/api/media-library"),
        ("GET", "/api/media-library/actors/name-sync/progress/{progress_key}"),
        ("POST", "/api/media-library/actors/mapping/source"),
        ("POST", "/api/media-library/actors/mapping/sync-mdc-ng"),
    }

    actual = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", set()) or set())
        if route.path.startswith("/api/media-library")
    }
    assert actual == expected

def test_tmdb_preview_guard_requires_key_and_tmdb_id(monkeypatch):
    from app.api.endpoints import actors

    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    ready, message = actors._tmdb_preview_guard({"tmdb_api_key": ""}, {"tmdb_id": "123"})
    assert ready is False
    assert "API Key" in message

    ready, _ = actors._tmdb_preview_guard({"tmdb_api_key": "key"}, {"provider_ids": {"Tmdb": "123"}})
    assert ready is True

    ready, message = actors._tmdb_preview_guard({"tmdb_api_key": "key"}, {"imdb_id": "nm123"})
    assert ready is False
    assert "TMDB ID" in message


@pytest.mark.asyncio
async def test_tmdb_preview_returns_ok_false_without_key(monkeypatch):
    from app.api.endpoints import actors

    async def fake_profile(config, actor_id, lang):
        return {"name": "Test Actor", "imdb_id": "nm123"}

    monkeypatch.setattr(actors.media, "_load_config", lambda: {
        "server_url": "http://emby:8096",
        "api_key": "secret",
        "tmdb_api_key": "",
    })
    monkeypatch.setattr(actors, "_actor_profile", fake_profile)

    result = await actors.preview_actor_tmdb_metadata("1")

    assert result["ok"] is False
    assert result["proposal"] is None
    assert "API Key" in result["message"]
