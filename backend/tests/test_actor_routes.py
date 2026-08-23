from __future__ import annotations

import json
from pathlib import Path

from app.main import app


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


def test_media_library_route_parity_matches_original_index() -> None:
    index_path = Path(__file__).resolve().parents[2] / "forensics" / "original-symbol-index.json"
    original = json.loads(index_path.read_text(encoding="utf-8"))["targets"][
        "backend/app/api/endpoints/media_library.py"
    ]["routes"]
    original_routes = {
        (method.upper(), "/api/media-library" + path)
        for method, path in (item.split(" ", 1) for item in original)
    }

    # These routes were intentionally replaced by the later MDC-NG mapping workflow.
    intentionally_removed = {
        ("GET", "/api/media-library/actors/mapping/latest-upload"),
        ("POST", "/api/media-library/actors/mapping/import-latest"),
        ("POST", "/api/media-library/actors/mapping/sync-online"),
        ("POST", "/api/media-library/actors/mapping/upload"),
    }
    expected = original_routes - intentionally_removed
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
