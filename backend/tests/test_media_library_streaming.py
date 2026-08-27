from __future__ import annotations

import asyncio

from app.api.endpoints import media_library
from app.api.endpoints.media_library_item_detail import (
    build_direct_stream_upstream_url_impl,
    build_stream_url_for_server_impl,
    resolve_playback_stream_url_impl,
)


def test_build_stream_url_preserves_source_and_safe_container():
    assert build_stream_url_for_server_impl(
        "http://emby", "secret", "123", "source-1", "MKV",
    ) == "/api/media-library/stream/123?media_source_id=source-1&container=mkv"
    assert build_stream_url_for_server_impl(
        "http://emby", "secret", "123", None, "mkv/unsafe",
    ) == "/api/media-library/stream/123"


def test_direct_stream_upstream_url_contains_emby_playback_parameters():
    url = build_direct_stream_upstream_url_impl(
        "http://emby", "secret", "123", "source-1", "mp4", "session-1",
    )

    assert url.startswith("http://emby/emby/Videos/123/stream.mp4?")
    assert "api_key=secret" in url
    assert "MediaSourceId=source-1" in url
    assert "PlaySessionId=session-1" in url


def test_resolve_playback_stream_prefers_emby_direct_stream():
    class Response:
        status_code = 200

        def json(self):
            return {
                "PlaySessionId": "session-1",
                "MediaSources": [{
                    "Id": "source-1",
                    "Container": "mkv",
                    "SupportsDirectPlay": True,
                    "DirectStreamUrl": "/emby/Videos/123/stream.mkv?static=true",
                }],
            }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    class Httpx:
        AsyncClient = Client

    result = asyncio.run(resolve_playback_stream_url_impl(
        {"server_url": "http://emby", "api_key": "secret", "user_id": "user-1"},
        "123",
        httpx_module=Httpx,
        server_url_fn=lambda config: config["server_url"],
        headers_fn=lambda api_key: {"X-Emby-Token": api_key},
    ))

    assert result["play_method"] == "direct_play"
    assert result["media_source_id"] == "source-1"
    assert result["play_session_id"] == "session-1"
    assert result["url"] == "http://emby/emby/Videos/123/stream.mkv?static=true&api_key=secret&PlaySessionId=session-1"


def test_media_library_router_restores_stream_endpoint():
    routes = {
        (method, route.path)
        for route in media_library.router.routes
        for method in (route.methods or set())
    }

    assert ("GET", "/api/media-library/stream/{item_id}") in routes
