from __future__ import annotations

import asyncio

from app.plugins.runtime import PluginRuntime


class _Handler:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    async def search_resources(self, _config, _payload):
        return {"items": [{"id": self.provider, "title": self.provider, "url": "magnet:?xt=urn:btih:test"}]}


class _CoverHandler:
    async def handle_action(self, action, payload, _config):
        assert action == "video"
        return {"ok": True, "data": {"cover_url": f"https://covers.test/{payload['code']}.jpg"}}


def test_resource_search_prioritizes_avdb_then_mteam_then_javdb() -> None:
    runtime = PluginRuntime()
    runtime._manifests = {
        provider: {"id": provider, "name": provider, "capabilities": ["resource_search"]}
        for provider in ("javdb", "mteam-plugin", "avdb")
    }
    runtime._enabled = {provider: True for provider in runtime._manifests}
    runtime._handlers = {provider: _Handler(provider) for provider in runtime._manifests}
    runtime._configs = {provider: {} for provider in runtime._manifests}

    result = asyncio.run(runtime.search_resources("PRED-878"))

    assert [group["provider"] for group in result["groups"]] == ["avdb", "mteam-plugin", "javdb"]
    assert [item["provider"] for item in result["items"]] == ["avdb", "mteam-plugin", "javdb"]


def test_resource_search_enriches_missing_cover_from_javdb_detail() -> None:
    runtime = PluginRuntime()
    items = [{"provider": "avdb", "query_key": "SNIS-201", "title": "SNIS-201", "cover_url": "", "metadata": {}}]
    runtime._handlers["javdb"] = _CoverHandler()
    runtime._manifests["javdb"] = {"id": "javdb", "name": "JavDB", "capabilities": ["resource_search"]}

    asyncio.run(runtime._borrow_resource_covers_from_javdb(items, []))

    assert items[0]["cover_url"] == "https://covers.test/SNIS-201.jpg"
    assert items[0]["metadata"]["cover_borrowed_from"] == "javdb_detail"
