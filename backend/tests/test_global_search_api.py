from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import search


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(search.router)
    return app


def test_global_search_get_returns_frontend_scopes(monkeypatch):
    async def fake_search_resources(query: dict, *, limit_per_plugin: int):
        assert query["keyword"] == "TEST-001"
        assert limit_per_plugin == 5
        return [{
            "provider": "javdb",
            "provider_name": "JavDB",
            "items": [{
                "id": "javdb:TEST-001:0",
                "title": "TEST-001 sample",
                "query_key": "TEST-001",
                "subtitle": "1.2 GB · JavDB",
                "cover_url": "https://example.test/cover.jpg",
                "tags": ["中文字幕"],
                "preferred_downloader": "xunlei-remote",
                "metadata": {"video_code": "TEST-001"},
            }],
        }]

    monkeypatch.setattr(search.runtime, "search_resources", fake_search_resources)
    response = TestClient(_app()).get("/api/search", params={"q": "TEST-001", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "TEST-001"
    scope = payload["scopes"][0]
    assert scope["key"] == "catalog"
    assert scope["count"] == 1
    item = scope["items"][0]
    assert item["title"] == "TEST-001 sample"
    assert item["image"] == "https://example.test/cover.jpg"
    assert item["action"]["route"] == "/search/resources?q=TEST-001"


def test_global_search_post_preserves_resource_contract(monkeypatch):
    async def fake_search_resources(query: dict, *, limit_per_plugin: int):
        return [{"provider": "x", "provider_name": "X", "items": [{"id": "1"}]}]

    monkeypatch.setattr(search.runtime, "search_resources", fake_search_resources)
    response = TestClient(_app()).post("/api/search", json={"query": "abc", "limit": 7})

    assert response.status_code == 200
    assert response.json()["groups"][0]["provider"] == "x"
    assert "scopes" not in response.json()
