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


class _FilteredHandler:
    def __init__(self) -> None:
        self.query = ""

    async def search_resources(self, config, payload):
        self.query = payload["keyword"]
        return {"items": [
            {"id": "plain", "query_key": "TEST-010", "title": "TEST-010", "features": {"is_cracked": False}},
            {"id": "cracked", "query_key": "TEST-011", "title": "TEST-011 破解", "features": {"is_cracked": True}},
        ]}


def test_resource_search_prioritizes_avdb_then_mteam_then_javdb() -> None:
    runtime = PluginRuntime()
    runtime._manifests = {
        provider: {"id": provider, "name": provider, "capabilities": ["resource_search"]}
        for provider in ("javdb", "mteam-plugin", "avdb")
    }
    runtime._enabled = {provider: True for provider in runtime._manifests}
    runtime._handlers = {provider: _Handler(provider) for provider in runtime._manifests}
    runtime._configs = {provider: {} for provider in runtime._manifests}

    result = asyncio.run(runtime.search_resources("TEST-004"))

    assert [group["provider"] for group in result["groups"]] == ["avdb", "mteam-plugin", "javdb"]
    assert [item["provider"] for item in result["items"]] == ["avdb", "mteam-plugin", "javdb"]


def test_resource_search_enriches_missing_cover_from_javdb_detail() -> None:
    runtime = PluginRuntime()
    items = [{"provider": "avdb", "query_key": "TEST-012", "title": "TEST-012", "cover_url": "", "metadata": {}}]
    runtime._handlers["javdb"] = _CoverHandler()
    runtime._manifests["javdb"] = {"id": "javdb", "name": "JavDB", "capabilities": ["resource_search"]}

    asyncio.run(runtime._borrow_resource_covers_from_javdb(items, []))

    assert items[0]["cover_url"] == "https://covers.test/TEST-012.jpg"
    assert items[0]["metadata"]["cover_borrowed_from"] == "javdb_detail"


def test_single_code_cover_borrow_does_not_call_detail_enrichment() -> None:
    runtime = PluginRuntime()
    items = [{"provider": "avdb", "query_key": "TEST-012", "title": "TEST-012", "cover_url": "", "metadata": {}}]
    runtime._handlers["javdb"] = _CoverHandler()
    runtime._manifests["javdb"] = {"id": "javdb", "name": "JavDB", "capabilities": ["resource_search"]}

    asyncio.run(runtime._borrow_resource_covers_from_javdb(items, [], enrich_missing_details=False))

    assert items[0]["cover_url"] == ""


def test_resource_search_parses_feature_keyword_as_and_filter() -> None:
    runtime = PluginRuntime()
    handler = _FilteredHandler()
    runtime._manifests = {"avdb": {"id": "avdb", "name": "AVDB", "capabilities": ["resource_search"]}}
    runtime._handlers = {"avdb": handler}

    result = asyncio.run(runtime.search_resources("吉泽明步 破解"))

    assert handler.query == "吉泽明步"
    assert [item["id"] for item in result["items"]] == ["cracked"]


def test_resource_search_supports_negative_and_source_filters() -> None:
    payload, filters, sources, title_terms = PluginRuntime._parse_resource_query_filters({"keyword": "吉泽明步 -中文 来源:AVDB"})

    assert payload["keyword"] == "吉泽明步"
    assert filters == {"chinese": False}
    assert sources == {"avdb"}
    assert title_terms == []


def test_resource_search_treats_following_plain_words_as_title_and_filters() -> None:
    payload, filters, sources, title_terms = PluginRuntime._parse_resource_query_filters({"keyword": "吉泽明步 教师 诱惑 -合集 破解"})

    assert payload["keyword"] == "吉泽明步"
    assert filters == {"cracked": True}
    assert sources == set()
    assert title_terms == [("教师", True), ("诱惑", True), ("合集", False)]
    assert PluginRuntime._resource_matches_query_filters(
        {"title": "被诱惑的美女教师", "features": {"is_cracked": True}}, filters, title_terms,
    ) is True
    assert PluginRuntime._resource_matches_query_filters(
        {"title": "美女教师合集", "features": {"is_cracked": True}}, filters, title_terms,
    ) is False


def test_resource_search_keeps_quoted_phrase_as_one_title_term() -> None:
    payload, _filters, _sources, title_terms = PluginRuntime._parse_resource_query_filters({"keyword": '吉泽明步 "家庭 教师"'})

    assert payload["keyword"] == "吉泽明步"
    assert title_terms == [("家庭 教师", True)]
