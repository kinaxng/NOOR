from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import plugins


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(plugins.router)
    return app


def test_plugin_manager_reads_items_payload(monkeypatch):
    async def fake_reload():
        return []

    monkeypatch.setattr(plugins.runtime, "_manifests", {})
    monkeypatch.setattr(plugins.runtime, "reload_plugins", fake_reload)
    response = TestClient(_app()).get("/api/plugins")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_legacy_enable_disable_routes_forward_to_runtime(monkeypatch):
    calls: list[tuple[str, bool]] = []

    async def fake_set_enabled(plugin_id: str, enabled: bool):
        calls.append((plugin_id, enabled))
        return enabled

    monkeypatch.setattr(plugins.runtime, "set_enabled", fake_set_enabled)
    client = TestClient(_app())

    assert client.post("/api/plugins/javdb/enable").json() == {"enabled": True}
    assert client.post("/api/plugins/javdb/disable").json() == {"enabled": False}
    assert calls == [("javdb", True), ("javdb", False)]


def test_legacy_test_route_forwards_to_plugin_action(monkeypatch):
    async def fake_handle_action(plugin_id: str, action: str, payload: dict | None = None):
        return {"ok": True, "plugin_id": plugin_id, "action": action, "payload": payload}

    monkeypatch.setattr(plugins.runtime, "handle_action", fake_handle_action)
    response = TestClient(_app()).post("/api/plugins/qbittorrent/test")
    assert response.status_code == 200
    assert response.json()["action"] == "test"


def test_market_items_compat_returns_empty_list():
    response = TestClient(_app()).get("/api/plugins/market/items")
    assert response.status_code == 200
    assert response.json() == []


def test_resource_resolve_download_route_forwards_to_runtime(monkeypatch):
    async def fake_resolve(plugin_id: str, item: dict):
        return {"item": item, "url": item["url"], "plugin_id": plugin_id}

    monkeypatch.setattr(plugins.runtime, "resolve_resource_download", fake_resolve)

    response = TestClient(_app()).post(
        "/api/plugins/resources/resolve-download",
        json={"provider_id": "avdb", "item": {"url": "magnet:?xt=urn:btih:test"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "item": {"url": "magnet:?xt=urn:btih:test"},
        "url": "magnet:?xt=urn:btih:test",
        "plugin_id": "avdb",
    }


def test_resource_resolve_download_route_requires_provider():
    response = TestClient(_app()).post(
        "/api/plugins/resources/resolve-download",
        json={"item": {"url": "magnet:?xt=urn:btih:test"}},
    )

    assert response.status_code == 400
