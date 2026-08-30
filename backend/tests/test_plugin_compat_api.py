from __future__ import annotations

from fastapi import FastAPI
import pytest
from fastapi.testclient import TestClient

from app.api import plugins
from app.knowledge import intelligence


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


def test_legacy_test_route_forwards_to_runtime_test(monkeypatch):
    async def fake_test(plugin_id: str):
        return {"ok": True, "plugin_id": plugin_id}

    monkeypatch.setattr(plugins.runtime, "test", fake_test)
    response = TestClient(_app()).post("/api/plugins/qbittorrent/test")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "plugin_id": "qbittorrent"}


def test_plugin_websocket_overview_forwards_to_runtime(monkeypatch):
    async def fake_handle_action(plugin_id: str, action: str, payload: dict | None = None):
        return {"ok": True, "plugin_id": plugin_id, "action": action, "payload": payload}

    monkeypatch.setattr(plugins.runtime, "handle_action", fake_handle_action)
    client = TestClient(_app())

    with client.websocket_connect("/api/plugins/qbittorrent/ws/overview?interval=2") as websocket:
        data = websocket.receive_json()

    assert data == {"ok": True, "plugin_id": "qbittorrent", "action": "overview", "payload": {}}


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


def test_resource_search_records_only_first_page_user_intent(monkeypatch):
    recorded: list[str] = []

    async def fake_search_resources(query, **_kwargs):
        return {"groups": [{"provider": "avdb", "items": [{"id": "one", "title": "result"}]}], "downloaders": []}

    async def fake_record(query, **_kwargs):
        recorded.append(str(query))
        return {"recorded": True}

    monkeypatch.setattr(plugins.runtime, "search_resources", fake_search_resources)
    monkeypatch.setattr(intelligence, "record_search_intent", fake_record)
    client = TestClient(_app())

    assert client.post("/api/plugins/resources/search", json={"query": {"keyword": "吉泽明步 破解", "page": 1}}).status_code == 200
    assert client.post("/api/plugins/resources/search", json={"query": {"keyword": "吉泽明步 破解", "page": 2}}).status_code == 200
    assert client.post("/api/plugins/resources/search", json={"query": {"keyword": "吉泽明步 破解"}, "track_intent": False}).status_code == 200
    assert recorded == ["吉泽明步 破解"]


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


def test_successful_downloader_submission_records_core_outcome(monkeypatch):
    recorded: list[tuple[str, str, str, dict]] = []

    async def fake_submit(plugin_id: str, payload: dict):
        return {"ok": True, "task_id": "task-1"}

    async def fake_record(code: str, event_type: str, *, source: str, data: dict, **_kwargs):
        recorded.append((code, event_type, source, data))
        return True

    monkeypatch.setattr(plugins.runtime, "submit_download", fake_submit)
    monkeypatch.setattr(intelligence, "record_preference_event", fake_record)
    response = TestClient(_app()).post(
        "/api/plugins/qbittorrent/downloads",
        json={"payload": {"rename": "PRED-878-破解", "source_plugin": "javdb", "url": "magnet:?xt=urn:btih:test"}},
    )

    assert response.status_code == 200
    assert recorded == [("PRED-878", "download_submitted", "downloader:qbittorrent", {
        "evidence_id": "qbittorrent:task-1", "downloader_id": "qbittorrent", "source_plugin": "javdb",
    })]


def test_failed_downloader_submission_does_not_record_core_outcome(monkeypatch):
    async def fake_submit(_plugin_id: str, _payload: dict):
        return {"ok": False, "failure_count": 1}

    async def fail_if_recorded(*_args, **_kwargs):
        raise AssertionError("failed download must not become preference evidence")

    monkeypatch.setattr(plugins.runtime, "submit_download", fake_submit)
    monkeypatch.setattr(intelligence, "record_preference_event", fail_if_recorded)
    response = TestClient(_app()).post(
        "/api/plugins/qbittorrent/downloads",
        json={"payload": {"title": "PRED-878", "url": "magnet:?xt=urn:btih:test"}},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_resource_resolve_download_backfills_compatible_downloaders(monkeypatch):
    from types import SimpleNamespace

    from app.plugins.runtime import runtime

    class FakeHandler:
        async def resolve_resource_download(self, resource, config):
            return {
                "item": {"url": "magnet:?xt=urn:btih:abc"},
                "url": "magnet:?xt=urn:btih:abc",
            }

    monkeypatch.setattr(runtime, "_handlers", {"javdb": FakeHandler()})
    monkeypatch.setattr(
        runtime,
        "get_manifest",
        lambda plugin_id: SimpleNamespace(name="JavDB", type="resource_search"),
    )
    monkeypatch.setattr(runtime, "is_enabled", lambda plugin_id: plugin_id == "qbittorrent")
    monkeypatch.setattr(
        runtime,
        "list_enabled_downloaders",
        lambda: [{
            "id": "qbittorrent",
            "name": "qBittorrent",
            "capabilities": {"accepts_public_magnet": True},
        }],
    )
    monkeypatch.setattr(runtime, "_normalize_plugin_downloader_preferences", lambda plugin_id: ["qbittorrent"])

    result = await runtime.resolve_resource_download("javdb", {
        "url": "magnet:?xt=urn:btih:abc",
    })

    assert result["url"] == "magnet:?xt=urn:btih:abc"
    assert result["item"]["requirements"] == {"accepts_public_magnet": True}
    assert result["item"]["compatible_downloaders"] == ["qbittorrent"]
    assert result["item"]["preferred_downloader"] == "qbittorrent"


@pytest.mark.asyncio
async def test_resource_resolve_does_not_offer_unbound_downloaders(monkeypatch):
    from types import SimpleNamespace

    from app.plugins.runtime import runtime

    class FakeHandler:
        async def resolve_resource_download(self, resource, config):
            return {"item": resource, "url": resource["url"]}

    monkeypatch.setattr(runtime, "_handlers", {"avdb": FakeHandler()})
    monkeypatch.setattr(runtime, "get_manifest", lambda plugin_id: SimpleNamespace(name="AVDB", type="source"))
    monkeypatch.setattr(runtime, "list_enabled_downloaders", lambda: [{
        "id": "xunlei-remote", "name": "迅雷远程",
        "capabilities": {"accepts_public_magnet": True},
    }])
    monkeypatch.setattr(runtime, "_normalize_plugin_downloader_preferences", lambda plugin_id: [])

    result = await runtime.resolve_resource_download("avdb", {"url": "magnet:?xt=urn:btih:abc"})

    assert result["item"]["compatible_downloaders"] == []
    assert result["item"]["source_bound_downloaders"] == []
    assert result["item"]["preferred_downloader"] is None


def test_pt_resource_only_keeps_bound_active_pt_downloaders(monkeypatch):
    from types import SimpleNamespace

    from app.plugins.runtime import runtime

    monkeypatch.setattr(runtime, "get_manifest", lambda plugin_id: SimpleNamespace(name="M-Team", type="rss_source"))
    monkeypatch.setattr(runtime, "_normalize_plugin_downloader_preferences", lambda plugin_id: ["xunlei-remote", "qbittorrent", "transmission"])
    monkeypatch.setattr(runtime, "list_enabled_downloaders", lambda: [
        {"id": "xunlei-remote", "capabilities": {"accepts_private_tracker": False, "accepts_http_torrent": True}},
        {"id": "qbittorrent", "capabilities": {"accepts_private_tracker": True, "accepts_http_torrent": True}},
    ])

    result = runtime.resolve_downloaders_for_resource("mteam-plugin", {
        "url": "https://m-team.test/torrent/1",
        "requirements": {"accepts_private_tracker": True, "accepts_http_torrent": True},
    })

    assert result["source_bound_downloaders"] == ["xunlei-remote", "qbittorrent", "transmission"]
    assert result["compatible_downloaders"] == ["qbittorrent"]
    assert result["preferred_downloader"] == "qbittorrent"


@pytest.mark.asyncio
async def test_disabled_read_action_returns_empty_state(monkeypatch):
    from app.plugins.runtime import runtime

    monkeypatch.setattr(runtime, "_manifests", {"qbittorrent": {}})
    monkeypatch.setattr(runtime, "is_enabled", lambda plugin_id: False)

    body = plugins.PluginActionPayload()
    result = await plugins._handle_plugin_action("qbittorrent", "overview", body, None)

    assert result["ok"] is False
    assert result["disabled"] is True
    assert result["jobs"] == []
    assert result["stats"] == {"total": 0, "running": 0, "finished": 0, "failed": 0}
