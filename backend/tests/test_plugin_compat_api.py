from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import plugins


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(plugins.router)
    return app


def test_plugin_manager_returns_array(monkeypatch):
    async def fake_reload():
        return []

    monkeypatch.setattr(plugins.runtime, "_manifests", {})
    monkeypatch.setattr(plugins.runtime, "reload_plugins", fake_reload)
    response = TestClient(_app()).get("/api/plugins")
    assert response.status_code == 200
    assert response.json() == []


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


def test_market_items_route_forwards_to_runtime(monkeypatch):
    async def fake_items():
        return [{"id": "demo", "repo_url": "https://example.test/repo"}]

    monkeypatch.setattr(plugins.runtime, "list_market_items", fake_items)
    response = TestClient(_app()).get("/api/plugins/market/items")
    assert response.status_code == 200
    assert response.json() == [{"id": "demo", "repo_url": "https://example.test/repo"}]


def test_market_repo_routes_forward_to_runtime(monkeypatch):
    repos: list[dict[str, str]] = []

    monkeypatch.setattr(plugins.runtime, "list_market_repos", lambda: list(repos))

    def add(url: str):
        repos.append({"url": url})
        return list(repos)

    def remove(url: str):
        repos[:] = [item for item in repos if item["url"] != url]
        return list(repos)

    monkeypatch.setattr(plugins.runtime, "add_market_repo", add)
    monkeypatch.setattr(plugins.runtime, "remove_market_repo", remove)
    client = TestClient(_app())

    assert client.post("/api/plugins/market/repos", json={"url": "https://example.test/repo"}).json() == [
        {"url": "https://example.test/repo"}
    ]
    assert client.get("/api/plugins/market/repos").json() == [{"url": "https://example.test/repo"}]
    assert client.request(
        "DELETE",
        "/api/plugins/market/repos",
        json={"repo_url": "https://example.test/repo"},
    ).json() == []


def test_market_install_route_forwards_to_runtime(monkeypatch):
    async def fake_install(repo_url: str, plugin_id: str):
        return {"ok": True, "repo_url": repo_url, "plugin_id": plugin_id}

    monkeypatch.setattr(plugins.runtime, "install_market_plugin", fake_install)
    response = TestClient(_app()).post(
        "/api/plugins/market/install",
        json={"repo_url": "https://example.test/repo", "plugin_id": "demo"},
    )
    assert response.status_code == 200
    assert response.json()["plugin_id"] == "demo"


def test_resource_search_returns_groups_and_flat_items(monkeypatch):
    async def fake_search_resources(
        query: dict,
        *,
        provider_ids: list[str] | None = None,
        limit_per_plugin: int,
        requested_downloader_id: str = "",
    ):
        assert query == {"code": "AAA-001"}
        assert provider_ids == []
        assert requested_downloader_id == ""
        assert limit_per_plugin == 6
        return [
            {
                "provider": "javdb",
                "provider_name": "JavDB",
                "items": [{"id": "j1", "title": "JavDB resource"}],
            },
            {
                "provider": "mteam-plugin",
                "provider_name": "M-Team",
                "items": [{"id": "m1", "title": "M-Team resource", "provider": "mteam-plugin"}],
            },
        ]

    monkeypatch.setattr(plugins.runtime, "search_resources", fake_search_resources)

    response = TestClient(_app()).post(
        "/api/plugins/resources/search",
        json={"query": {"code": "AAA-001"}, "limit_per_plugin": 6},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["groups"]) == 2
    assert data["items"] == [
        {
            "id": "j1",
            "title": "JavDB resource",
            "provider": "javdb",
            "provider_label": "JavDB",
        },
        {
            "id": "m1",
            "title": "M-Team resource",
            "provider": "mteam-plugin",
            "provider_label": "M-Team",
        },
    ]


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
