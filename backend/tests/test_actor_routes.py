from __future__ import annotations

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
