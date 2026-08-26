from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


def _load_backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "mteam-plugin" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_mteam_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resource_search_uses_adult_torrent_mode(monkeypatch):
    backend = _load_backend()
    captured = {}

    async def fake_post(config, path, *, params=None, json_body=None):
        captured.update({"config": config, "path": path, "params": params, "json_body": json_body})
        return {
            "data": [{"id": "123", "name": "SSIS-001 test", "createdDate": "2026-08-26"}],
            "total": "1",
        }

    monkeypatch.setattr(backend, "_mteam_post", fake_post)
    result = asyncio.run(backend.search_resources({"code": "SSIS-001", "limit": 6}, {"api_key": "secret"}))

    assert captured["path"] == "/api/torrent/search"
    assert captured["json_body"] == {
        "pageNumber": 1,
        "pageSize": 6,
        "keyword": "SSIS-001",
        "mode": "adult",
        "status": "NORMAL",
        "withCache": True,
    }
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "mteam:123"


def test_resource_search_falls_back_to_title_when_small_description_has_no_code():
    backend = _load_backend()

    item = backend._normalize_resource({}, {
        "id": "604631",
        "name": "MIDV-131 10年分の片思い 小野六花",
        "smallDescr": "4K",
        "dmmInfo": {"productNumber": "9midv131"},
        "size": "13549681013",
    })

    assert item is not None
    assert item["query_key"] == "MIDV-131"
    assert item["metadata"]["video_code"] == "MIDV-131"
