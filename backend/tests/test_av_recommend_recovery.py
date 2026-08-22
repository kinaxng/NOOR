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


def test_candidate_pool_scan_uses_candidate_code(monkeypatch, tmp_path):
    asyncio.run(_run_candidate_pool_scan_uses_candidate_code(monkeypatch, tmp_path))


def test_image_candidates_keep_proxy_before_inner_url():
    backend = _load_backend()

    proxy = "http://noor.test/api/image?url=https%3A%2F%2Fcdn.test%2Fcover.jpg"
    assert backend._image_candidates({"cover_url": proxy}, {"thumb_url": "https://cdn.test/thumb.jpg"}) == [
        proxy,
        "https://cdn.test/cover.jpg",
        "https://cdn.test/thumb.jpg",
    ]


def test_refresh_candidate_cover_persists_candidates(monkeypatch, tmp_path):
    asyncio.run(_run_refresh_candidate_cover_persists_candidates(monkeypatch, tmp_path))


def test_media_library_item_codes_include_provider_and_nfo_values():
    backend = _load_backend()

    codes = backend._media_library_item_codes({
        "name": "无码破解标题不应作为唯一依据",
        "provider_ids": {"Javdb": "DLDSS-498"},
        "nfo": {"num": "mida669"},
        "siblings": [{"label": "ABCD-123-facefusion.mp4"}],
    })

    assert "DLDSS-498" in codes
    assert "MIDA-669" in codes
    assert "ABCD-123" in codes


def test_recommend_crack_signal_ignores_title_only_keywords():
    backend = _load_backend()

    assert backend._detail_has_cracked_signal({"title": "MIDA-669 無碼破解"}) is False
    assert backend._detail_has_cracked_signal({"magnets": [{"name": "MIDA-669 破解版"}]}) is True
    assert backend._detail_has_cracked_signal({"is_cracked": True, "title": "MIDA-669"}) is True


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


async def _run_candidate_pool_scan_uses_candidate_code(monkeypatch, tmp_path):
    backend = _load_backend()

    monkeypatch.setattr(backend, "_pool_path", lambda: tmp_path / "candidate_pool.json")

    class FakeRuntime:
        def is_enabled(self, plugin_id):
            return plugin_id == "javdb"

        async def handle_action(self, plugin_id, action, payload):
            assert plugin_id == "javdb"
            return {
                "items": [
                    {"code": "ABCD-123", "title": "测试标题"},
                    {"number": "MIDA669", "display_title": "MIDA-669 测试标题"},
                ]
            }

    import app.plugins.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "runtime", FakeRuntime())

    result = await backend._scan_candidate_pool({"full_scan_pages": 1}, force=True)

    assert result["ok"] is True
    pool = backend._pool()
    assert set(pool["items"]) == {"ABCD-123", "MIDA-669"}


async def _run_refresh_candidate_cover_persists_candidates(monkeypatch, tmp_path):
    backend = _load_backend()
    pool_path = tmp_path / "candidate_pool.json"
    pool_path.write_text('{"items":{"MIDA-669":{"code":"MIDA-669","title":"测试"}}}', encoding="utf-8")
    monkeypatch.setattr(backend, "_pool_path", lambda: pool_path)

    class FakeRuntime:
        def is_enabled(self, plugin_id):
            return plugin_id == "javdb"

        async def handle_action(self, plugin_id, action, payload):
            assert (plugin_id, action) == ("javdb", "video")
            assert payload == {"code": "MIDA-669", "refresh": True}
            return {
                "data": {
                    "cover_url": "https://cdn.test/MIDA-669.jpg",
                    "thumb_url": "https://cdn.test/MIDA-669-thumb.jpg",
                    "preview_images": ["https://cdn.test/MIDA-669-preview.jpg"],
                }
            }

    import app.plugins.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "runtime", FakeRuntime())
    result = await backend._refresh_candidate_cover("mida669")

    assert result["image_candidates"] == [
        "https://cdn.test/MIDA-669.jpg",
        "https://cdn.test/MIDA-669-thumb.jpg",
        "https://cdn.test/MIDA-669-preview.jpg",
    ]
    saved = backend._pool()["items"]["MIDA-669"]
    assert saved["image_candidates"] == result["image_candidates"]
    assert saved["title"] == "测试"
    assert saved["cover_refreshed_at"]
