from __future__ import annotations

import importlib.util
import asyncio
import inspect
import json
from pathlib import Path


def _load_backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "av-recommend" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_av_recommend_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommendations_exclude_library_and_subscription_codes(monkeypatch, tmp_path):
    asyncio.run(_run_recommendations_exclude_library_and_subscription_codes(monkeypatch, tmp_path))


def test_recommendation_cache_key_includes_requested_limit(monkeypatch):
    asyncio.run(_run_recommendation_cache_key_includes_requested_limit(monkeypatch))


def test_candidate_pool_scan_uses_candidate_code(monkeypatch, tmp_path):
    asyncio.run(_run_candidate_pool_scan_uses_candidate_code(monkeypatch, tmp_path))


def test_candidate_pool_scan_enriches_detail_metadata(monkeypatch, tmp_path):
    asyncio.run(_run_candidate_pool_scan_enriches_detail_metadata(monkeypatch, tmp_path))


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


def test_live_library_codes_prefers_original_media_library_adapter(monkeypatch):
    asyncio.run(_run_live_library_codes_prefers_original_media_library_adapter(monkeypatch))


def test_live_library_codes_warns_without_recovery_fallback(monkeypatch):
    asyncio.run(_run_live_library_codes_warns_without_recovery_fallback(monkeypatch))


def test_recommend_crack_signal_ignores_title_only_keywords():
    backend = _load_backend()

    assert backend._detail_has_cracked_signal({"title": "MIDA-669 無碼破解"}) is False
    assert backend._detail_has_cracked_signal({"magnets": [{"name": "MIDA-669 破解版"}]}) is True
    assert backend._detail_has_cracked_signal({"is_cracked": True, "title": "MIDA-669"}) is True


def test_recommendation_controls_filter_confidence_and_explore():
    backend = _load_backend()

    items = [
        {"code": f"AB-{index:03d}", "title": f"AB-{index:03d}", "confidence": index * 10, "score": 100 - index}
        for index in range(1, 11)
    ]

    selected = backend._apply_recommendation_controls(
        items,
        {"minimum_confidence_threshold": 30, "exploration_ratio": 0.2},
        5,
    )

    assert len(selected) == 5
    assert all(float(item["confidence"] or 0) >= 30 for item in selected)
    assert selected[0]["code"] == "AB-003"
    assert any(item["code"] in {"AB-008", "AB-009", "AB-010"} for item in selected)


def test_candidate_score_sanitizes_dict_string_relations_and_uses_recommendation_type():
    backend = _load_backend()

    item = {
        "code": "DVAJ-752",
        "title": "DVAJ-752",
        "maker": "{'external_id': 'J2x', 'name': 'アリスJAPAN'}",
        "series": "[{'external_id': 'S1', 'name': 'アリス'}]",
        "director": "{'name': '矢澤レシーブ'}",
        "magnets_count": 1,
        "release_date": "2026-08-12",
    }
    rec = backend._candidate_score(item, {"media_count": 1}, {}, {})

    assert rec is not None
    assert rec["maker"] == "アリスJAPAN"
    assert rec["series"] == "アリス"
    assert rec["director"] == "矢澤レシーブ"
    assert rec["type"] == "recommendation"


def test_preference_strength_preserves_legacy_behavior():
    backend = _load_backend()

    assert backend._preference_strength({}, "strength", "legacy") == 100
    assert backend._preference_strength({"legacy": False}, "strength", "legacy") == -1
    assert backend._preference_strength({"strength": 40}, "strength", "legacy") == 40
    assert backend._preference_strength({"strength": 999}, "strength", "legacy") == 100


def test_candidate_pool_background_stale_state(monkeypatch, tmp_path):
    backend = _load_backend()
    monkeypatch.setattr(backend, "_pool_path", lambda: tmp_path / "candidate_pool.json")

    now = backend.dt.datetime.now(backend.dt.timezone.utc).isoformat()
    old = "2026-08-01T00:00:00+00:00"
    older_finish = "2026-08-02T00:00:00+00:00"

    assert backend._candidate_pool_background_stale(
        {"last_full_scan": {"at": now}},
        {"running": True, "started_at": old, "finished_at": older_finish},
    ) is True
    assert backend._candidate_pool_background_stale(
        {"last_full_scan": {"at": now}},
        {"running": True, "started_at": old},
    ) is True
    assert backend._candidate_pool_background_stale(
        {"last_full_scan": {"at": old}},
        {"running": True, "started_at": now},
    ) is False


def test_candidate_pool_background_tasks_hide_stale_running(monkeypatch, tmp_path):
    backend = _load_backend()
    pool_path = tmp_path / "candidate_pool.json"
    monkeypatch.setattr(backend, "_pool_path", lambda: pool_path)
    pool_path.write_text(backend.json.dumps({
        "items": {},
        "background": {
            "running": True,
            "started_at": "2026-08-01T00:00:00+00:00",
            "finished_at": "2026-08-02T00:00:00+00:00",
        },
        "last_full_scan": {"at": "2026-08-03T00:00:00+00:00", "scanned": 596},
    }), encoding="utf-8")

    tasks = backend.background_tasks({})

    assert tasks[0]["status"] == "idle"
    assert tasks[0]["id"] == "av-recommend.candidate-pool"


def test_candidate_pool_requests_respects_source_toggles():
    backend = _load_backend()

    default = backend._candidate_pool_requests({"full_scan_pages": 2})
    assert [item[0] for item in default] == ["latest", "rankings", "rankings", "rankings", "recommend", "videos", "videos"]

    disabled = backend._candidate_pool_requests({
        "full_scan_pages": 2,
        "candidate_latest_enabled": False,
        "candidate_rankings_enabled": False,
        "candidate_recommend_enabled": False,
        "candidate_videos_enabled": False,
    })
    assert disabled == []

    only_videos = backend._candidate_pool_requests({
        "full_scan_pages": 2,
        "candidate_latest_enabled": False,
        "candidate_rankings_enabled": False,
        "candidate_recommend_enabled": False,
    })
    assert [item[0] for item in only_videos] == ["videos", "videos"]


def test_resource_features_separate_uncensored_from_cracked():
    backend = _load_backend()

    uncensored = backend._resource_features({"title": "MIDA-669 無碼"})
    assert uncensored["is_uncensored"] is True
    assert uncensored["is_cracked"] is False

    cracked = backend._resource_features({"title": "MIDA-669 無碼破解"})
    assert cracked["is_cracked"] is True

    leaked = backend._resource_features({"title": "MIDA-669 uncensored leak"})
    assert leaked["is_cracked"] is True


async def _run_recommendations_exclude_library_and_subscription_codes(monkeypatch, tmp_path):
    backend = _load_backend()

    monkeypatch.setattr(backend, "_data_file", lambda: tmp_path / "feedback.json")
    monkeypatch.setattr(backend, "_title_profile_file", lambda: tmp_path / "title_profile.json")
    monkeypatch.setattr(backend, "_pool_path", lambda: tmp_path / "candidate_pool.json")
    subscription_file = tmp_path / "subscriptions.json"
    subscription_file.write_text(json.dumps({
        "subscriptions": [
            {"code": "EFGH-456"},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(backend, "_subscription_path", lambda: subscription_file)
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
            {"code": "EFGH-456", "title": "EFGH-456 邻居", "actors": ["测试演员"], "categories": ["邻居"], "magnets_count": 3},
        ], []

    async def fake_enrich_resources(config, items):
        return []

    monkeypatch.setattr(backend, "_library_profile", fake_library_profile)
    monkeypatch.setattr(backend, "_live_library_codes", fake_live_library_codes)
    monkeypatch.setattr(backend, "_javdb_candidates", fake_javdb_candidates)
    monkeypatch.setattr(backend, "_enrich_recommendation_resources", fake_enrich_resources)

    result = await backend._recommendations({}, {"source_mode": "latest", "refresh": True})

    assert [item["code"] for item in result["items"]] == ["ABCD-123"]


async def _run_live_library_codes_prefers_original_media_library_adapter(monkeypatch):
    backend = _load_backend()
    backend._LIVE_LIBRARY_CODES_CACHE.update({"ts": 0, "key": "", "codes": set(), "warning": ""})

    import app.api.endpoints.media_library as media_library
    import app.api.endpoints.media_library_helpers as media_library_helpers

    media_config = {
        "server_url": "http://emby",
        "api_key": "key",
        "user_id": "u",
        "enabled_library_ids": "3",
    }
    monkeypatch.setattr(media_library_helpers, "load_config", lambda: media_config)

    async def fake_list_libraries(config):
        return [{"id": "3", "name": "Movies"}]

    async def fake_list_items(config, library_id, limit=50, offset=0, filter=None, q=None, force_refresh=False):
        assert library_id == "3"
        assert force_refresh is True
        return [{"provider_ids": {"Javdb": "MIDA-669"}}], 1

    monkeypatch.setattr(media_library, "_list_libraries", fake_list_libraries)
    monkeypatch.setattr(media_library, "_list_items", fake_list_items)
    source = inspect.getsource(backend._live_library_codes)
    assert "media_library_recovery" not in source
    assert "media_library._list_libraries" in source
    assert "media_library._list_items" in source

    codes, warning = await backend._live_library_codes({"library_exclusion_scan_limit": 100}, force=True)

    assert codes == {"MIDA-669"}
    assert warning == ""


async def _run_live_library_codes_warns_without_recovery_fallback(monkeypatch):
    backend = _load_backend()
    backend._LIVE_LIBRARY_CODES_CACHE.update({"ts": 0, "key": "", "codes": set(), "warning": ""})

    import app.api.endpoints.media_library as media_library
    import app.api.endpoints.media_library_helpers as media_library_helpers

    media_config = {
        "server_url": "http://emby",
        "api_key": "key",
        "user_id": "u",
        "enabled_library_ids": "3",
    }
    monkeypatch.setattr(media_library_helpers, "load_config", lambda: media_config)
    monkeypatch.setattr(media_library, "_list_libraries", async_fake_list_libraries)

    async def fail_list_items(*args, **kwargs):
        raise RuntimeError("emby unavailable")

    monkeypatch.setattr(media_library, "_list_items", fail_list_items)

    codes, warning = await backend._live_library_codes({"library_exclusion_scan_limit": 100}, force=True)

    assert codes == set()
    assert "实时媒体库排除失败" in warning


async def async_fake_list_libraries(config):
    return [{"id": "3", "name": "Movies"}]


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


async def _run_recommendation_cache_key_includes_requested_limit(monkeypatch):
    backend = _load_backend()
    backend._CACHE.update({"ts": 0, "key": "", "value": None})
    applied_limits: list[int] = []
    monkeypatch.setattr(backend, "_subscription_codes", lambda: set())
    monkeypatch.setattr(backend, "_pool", lambda: {"items": {}})

    async def fake_library_profile():
        return {
            "media_count": 1,
            "codes": set(),
            "media_by_code": {},
            "actors": backend.Counter(),
            "genres": backend.Counter(),
            "tags": backend.Counter(),
            "studios": backend.Counter(),
            "series": backend.Counter(),
            "directors": backend.Counter(),
            "title_traits": backend.Counter(),
            "title_terms": backend.Counter(),
            "actor_category": backend.Counter(),
            "local_features": {},
            "top_media": [],
        }

    async def fake_live_library_codes(config, *, force=False):
        return set(), ""

    async def fake_javdb_candidates(config):
        return [
            {"code": f"AB-{index:03d}", "title": f"AB-{index:03d}", "actors": [], "categories": []}
            for index in range(30)
        ], []

    async def fake_enrich_resources(config, items):
        return []

    def fake_candidate_score(item, profile, config, feedback, diagnostics=None):
        return {
            "code": item["code"],
            "title": item["code"],
            "display_title": item["code"],
            "cover_url": "",
            "fanart_url": "",
            "image_candidates": [],
            "release_date": "",
            "actors": [],
            "categories": [],
            "title_traits": [],
            "title_profile": {},
            "maker": "",
            "series": "",
            "director": "",
            "score": 50,
            "personalized_score": 0,
            "actionability_score": 0,
            "quality_score": 0,
            "penalty_score": 0,
            "match_level": "none",
            "confidence": 50,
            "score_breakdown": {},
            "type": "recommendation",
            "in_library": False,
            "magnets_count": 0,
            "has_cnsub": False,
            "is_cracked": False,
            "is_uncensored": False,
            "best_resource_size_mb": 0,
            "reasons": [],
            "source_tags": [],
            "is_today_increment": False,
            "source": "javdb",
            "source_label": "JavDB",
            "route": "",
            "raw": {},
        }

    def fake_apply_controls(items, config, limit):
        applied_limits.append(int(limit))
        return items[:limit]

    monkeypatch.setattr(backend, "_library_profile", fake_library_profile)
    monkeypatch.setattr(backend, "_live_library_codes", fake_live_library_codes)
    monkeypatch.setattr(backend, "_javdb_candidates", fake_javdb_candidates)
    monkeypatch.setattr(backend, "_enrich_recommendation_resources", fake_enrich_resources)
    monkeypatch.setattr(backend, "_candidate_score", fake_candidate_score)
    monkeypatch.setattr(backend, "_apply_recommendation_controls", fake_apply_controls)

    first = await backend._recommendations({}, {"source_mode": "latest", "limit": 20, "refresh": False})
    second = await backend._recommendations({}, {"source_mode": "latest", "limit": 60, "refresh": False})

    assert applied_limits == [20, 60]
    assert len(first["items"]) == 20
    assert len(second["items"]) == 30


async def _run_candidate_pool_scan_enriches_detail_metadata(monkeypatch, tmp_path):
    backend = _load_backend()

    monkeypatch.setattr(backend, "_pool_path", lambda: tmp_path / "candidate_pool.json")

    class FakeRuntime:
        def is_enabled(self, plugin_id):
            return plugin_id == "javdb"

        async def handle_action(self, plugin_id, action, payload):
            assert plugin_id == "javdb"
            if action == "video":
                return {
                    "data": {
                        "actors": [{"name": "测试演员"}],
                        "categories": [{"name": "邻居"}],
                        "maker": {"name": "S1 NO.1 STYLE"},
                        "series": [{"name": "测试系列"}],
                        "director": {"name": "测试导演"},
                        "magnets": [{"name": "ABCD-123", "size_mb": 2048}],
                    }
                }
            return {"items": [{"code": "ABCD-123", "title": "测试标题"}]}

    import app.plugins.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "runtime", FakeRuntime())
    result = await backend._scan_candidate_pool({
        "full_scan_pages": 1,
        "candidate_latest_enabled": False,
        "candidate_rankings_enabled": False,
        "candidate_recommend_enabled": False,
    }, force=True)

    assert result["ok"] is True
    item = backend._pool()["items"]["ABCD-123"]
    assert item["actors"] == ["测试演员"]
    assert item["categories"] == ["邻居"]
    assert item["maker"] == "S1 NO.1 STYLE"
    assert item["series"] == "测试系列"
    assert item["director"] == "测试导演"
    assert item["best_resource_size_mb"] == 2048


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


def test_dedupe_recommendations_drops_same_normalized_code() -> None:
    backend = _load_backend()

    items = [
        {"code": "MIDA-727", "title": "MIDA-727", "score": 98},
        {"code": "MIDA-727", "id": "DRX262", "title": "MIDA-727", "score": 91},
        {"code": "MIDA-728", "title": "MIDA-728", "score": 81},
        {"code": "FC2-PPV-1844862", "title": "FC2", "score": 80},
        {"code": "FC2-1844862", "title": "FC2", "score": 79},
    ]

    deduped = backend._dedupe_recommendations(items)

    assert [item["code"] for item in deduped] == ["MIDA-727", "MIDA-728", "FC2-PPV-1844862"]


def test_media_item_codes_extract_emby_cache_codes() -> None:
    backend = _load_backend()

    codes = backend._media_item_codes({
        "name": "DVAJ-727-C.mp4",
        "path": "/media/DVAJ-727/DVAJ-727-C.mp4",
        "nfo": {"num": "mida669", "originaltitle": "MIDA-669"},
    })

    assert codes == {"DVAJ-727", "MIDA-669"}


def test_filtered_summary_groups_reasons_and_examples() -> None:
    backend = _load_backend()

    diagnostics: list[dict[str, str]] = []
    backend._record_filter(diagnostics, {"code": "MIDA-669", "title": "MIDA-669"}, "MIDA-669", "missing_code", "候选缺少可识别番号")
    backend._record_filter(diagnostics, {"code": "MIDA-669", "title": "MIDA-669"}, "MIDA-669", "ignored", "用户已忽略")
    backend._record_filter(diagnostics, {"code": "MIDA-669", "title": "MIDA-669"}, "MIDA-669", "ignored", "用户已忽略")

    summary = backend._filtered_summary(diagnostics)

    assert summary["total"] == 3
    assert summary["reasons"] == [
        {"reason": "ignored", "label": "已忽略", "count": 2},
        {"reason": "missing_code", "label": "缺少番号", "count": 1},
    ]
    assert len(summary["examples"]) == 3


def test_candidate_score_records_filter_diagnostics() -> None:
    backend = _load_backend()

    diagnostics: list[dict[str, str]] = []
    result = backend._candidate_score(
        {"title": "没有番号标题"},
        {"media_count": 1},
        {},
        {},
        diagnostics,
    )

    assert result is None
    assert diagnostics == [{
        "code": "",
        "title": "没有番号标题",
        "reason": "missing_code",
        "detail": "候选缺少可识别番号",
    }]
