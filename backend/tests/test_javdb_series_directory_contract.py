from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_backend():
    path = ROOT / "plugins" / "javdb" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_javdb_series_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_series_entries_normalizes_single_and_list_entries() -> None:
    backend = _load_backend()

    assert backend._series_entries({"external_id": "S1", "name": "系列一"}) == [
        {"id": "S1", "name": "系列一"},
    ]
    assert backend._series_entries([
        {"external_id": "S2", "name": "系列二"},
        {"id": "S3", "label": "系列三"},
        "系列四",
    ]) == [
        {"id": "S2", "name": "系列二"},
        {"id": "S3", "name": "系列三"},
        {"id": "系列四", "name": "系列四"},
    ]
    assert backend._series_entries([None, {}, ""]) == []


def test_series_options_builds_bounded_directory_from_recent_details(monkeypatch) -> None:
    backend = _load_backend()
    backend.SERIES_OPTIONS_CACHE.clear()

    async def fake_latest_page_items(config, latest_type, sort_by, page, *, scan_limit=80, filter_by="all"):
        return [
            {"code": "A-001", "release_date": "2026-08-20", "cover_url": "/cover-a.jpg"},
            {"code": "A-002", "release_date": "2026-08-21", "cover_url": "/cover-b.jpg"},
            {"code": "B-001", "release_date": "2026-08-22", "cover_url": "/cover-c.jpg"},
        ]

    async def fake_video(config, code):
        if code == "A-001":
            return {"series": [{"external_id": "S1", "name": "系列一"}]}
        if code == "A-002":
            return {"series": [{"external_id": "S1", "name": "系列一"}]}
        return {"series": [{"external_id": "S2", "name": "系列二"}]}

    monkeypatch.setattr(backend, "_latest_page_items", fake_latest_page_items)
    monkeypatch.setattr(backend, "_video", fake_video)

    result = asyncio.run(backend._series_options({}))

    assert result["sample_size"] == 3
    assert result["total"] == 2
    assert result["items"][0] == {
        "id": "S2",
        "name": "系列二",
        "recent_work_count": 1,
        "latest_release_date": "2026-08-22",
        "cover_url": "/cover-c.jpg",
    }
    assert result["items"][1]["recent_work_count"] == 2
    assert result["items"][1]["latest_release_date"] == "2026-08-21"
    assert result["items"][1]["cover_url"] == "/cover-b.jpg"


def test_javdb_series_directory_frontend_contract() -> None:
    page = (ROOT / "plugins" / "javdb" / "frontend" / "page.js").read_text(encoding="utf-8")

    assert "{ value: 'series', label: '系列', path: 'series' }" in page
    assert "function isSeriesDirectoryFrame()" in page
    assert "state.tab === 'series' && !state.relation" in page
    assert "state.seriesSearch" in page
    assert "series_options" in page
    assert "setRelation('series'" in page
    assert "javdb-series-card" in page
    assert "javdb-grid--series" in page


def test_javdb_series_directory_backend_contract() -> None:
    source = (ROOT / "plugins" / "javdb" / "backend.py").read_text(encoding="utf-8")

    assert "SERIES_OPTIONS_CACHE_TTL = 900" in source
    assert "def _series_entries" in source
    assert "async def _series_options" in source
    assert '"/series/{id}/movies"' in source
    assert 'if action == "series_options":' in source
