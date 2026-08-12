from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import media_library_recovery


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(media_library_recovery.router)
    return app


def test_recovery_items_response_includes_pagination(monkeypatch):
    monkeypatch.setattr(media_library_recovery, "_config", lambda value=None: {"server_url": "http://emby", "api_key": "key", "user_id": "u"})

    async def fake_fetch_items(config, *, library_id, limit, offset):
        return ([{"id": "1", "name": "AAA-001", "tags": {}}], 12)

    monkeypatch.setattr(media_library_recovery, "_fetch_items", fake_fetch_items)

    response = TestClient(_app()).get("/api/media-library/items?limit=1&offset=3")

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": "1", "name": "AAA-001", "tags": {}}],
        "total": 12,
        "offset": 3,
        "limit": 1,
    }
