from __future__ import annotations

import importlib.util
import asyncio
from pathlib import Path


def _load_backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "av-recommend" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_av_recommend_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommendations_exclude_live_emby_codes(monkeypatch, tmp_path):
    asyncio.run(_run_recommendations_exclude_live_emby_codes(monkeypatch, tmp_path))


async def _run_recommendations_exclude_live_emby_codes(monkeypatch, tmp_path):
    backend = _load_backend()

    monkeypatch.setattr(backend, "DATA_FILE", tmp_path / "feedback.json")
    monkeypatch.setattr(backend, "TITLE_PROFILE_FILE", tmp_path / "title_profile.json")
    monkeypatch.setattr(backend, "_pool_path", lambda: tmp_path / "candidate_pool.json")
    backend._CACHE.update({"ts": 0, "key": "", "value": None})
    backend._LIVE_LIBRARY_CODES_CACHE.update({"ts": 0, "key": "", "codes": set(), "warning": ""})

    async def fake_library_profile():
        return {
            "media_count": 20,
            "codes": set(),
            "media_by_code": {},
            "actors": backend.Counter({"测试演员": 4}),
            "genres": backend.Counter(),
            "tags": backend.Counter({"邻居": 4}),
            "studios": backend.Counter(),
            "series": backend.Counter(),
            "directors": backend.Counter(),
            "title_traits": backend.Counter({"邻居": 4}),
            "title_terms": backend.Counter(),
            "actor_category": backend.Counter(),
            "local_features": {},
            "top_media": [],
        }

    async def fake_live_library_codes(config, *, force=False):
        assert force is True
        return {"MIDA-669"}, ""

    async def fake_javdb_candidates(config):
        return [
            {"code": "MIDA-669", "title": "MIDA-669 邻居", "actors": ["测试演员"], "categories": ["邻居"], "magnets_count": 3},
            {"code": "ABCD-123", "title": "ABCD-123 邻居", "actors": ["测试演员"], "categories": ["邻居"], "magnets_count": 3},
        ], []

    async def fake_enrich_resources(config, items):
        return []

    monkeypatch.setattr(backend, "_library_profile", fake_library_profile)
    monkeypatch.setattr(backend, "_live_library_codes", fake_live_library_codes)
    monkeypatch.setattr(backend, "_javdb_candidates", fake_javdb_candidates)
    monkeypatch.setattr(backend, "_enrich_recommendation_resources", fake_enrich_resources)

    result = await backend._recommendations({}, {"source_mode": "latest", "refresh": True})

    assert [item["code"] for item in result["items"]] == ["ABCD-123"]
