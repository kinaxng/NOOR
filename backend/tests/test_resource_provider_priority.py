from __future__ import annotations

import asyncio

from app.plugins.runtime import PluginRuntime


class _Handler:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    async def search_resources(self, _config, _payload):
        return {"items": [{"id": self.provider, "title": self.provider, "url": "magnet:?xt=urn:btih:test"}]}


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
