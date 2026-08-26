from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path


def _load_backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "subscription-core" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_subscription_core_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subscription_image_candidates_keep_proxy_before_inner_url():
    backend = _load_backend()
    proxy = "http://noor.test/api/image?url=https%3A%2F%2Fcdn.test%2Fcover.jpg"

    assert backend._image_candidates({"cover_url": proxy}) == [proxy, "https://cdn.test/cover.jpg"]


def test_subscription_qb_completed_task_waits_for_library_import():
    backend = _load_backend()

    status = backend._download_stage("qbittorrent", {
        "name": "MIDA-727",
        "state": "stoppedUP",
        "progress": 1,
        "save_path": "/downloads/av",
    })

    assert status["stage"] == "completed"
    assert status["label"] == "下载完成 · 等待入库"
    assert status["tone"] == "success"
    assert status["progress"] == 1


def test_subscription_xunlei_error_task_is_exposed():
    backend = _load_backend()

    status = backend._download_stage("xunlei-remote", {
        "name": "TEST-001",
        "phase": "PHASE_TYPE_ERROR",
        "message": "磁盘空间不足",
    })

    assert status["stage"] == "error"
    assert status["label"] == "下载异常"
    assert status["message"] == "磁盘空间不足"


def test_subscription_does_not_consume_cracked_candidate_for_censored_media():
    backend = _load_backend()
    media = {
        "name": "MIDA-727",
        "path": "/media/MIDA-727/MIDA-727.mp4",
        "tags": {"is_cracked": False, "has_chinese": False},
        "subtitle_count": 1,
    }
    resource = {
        "title": "MIDA-727-U.无码破解.torrent",
        "features": {"is_cracked": True, "has_subtitle": False},
    }

    assert backend._media_matches_resource_profile(media, resource) is False


def test_subscription_upgrade_prioritizes_cracked_candidate_over_threshold():
    backend = _load_backend()
    subscription = {
        "type": "upgrade",
        "current_score": 30,
        "current_is_cracked": False,
        "current_has_subtitle": True,
    }
    resource = {
        "title": "MIDA-727-U.无码破解.torrent",
        "features": {"is_cracked": True, "has_subtitle": False},
    }

    ok, current, candidate, threshold, reason = backend._upgrade_improvement(
        subscription, resource, {"upgrade_score_threshold": 20},
    )

    assert ok is True
    assert (current, candidate, threshold) == (30, 40, 20)
    assert reason == "破解版本优先"


def test_subscription_refresh_cover_persists_candidates(monkeypatch, tmp_path):
    asyncio.run(_run_subscription_refresh_cover_persists_candidates(monkeypatch, tmp_path))


async def _run_subscription_refresh_cover_persists_candidates(monkeypatch, tmp_path):
    backend = _load_backend()
    data_file = tmp_path / "subscriptions.json"
    data_file.write_text(json.dumps({
        "version": 1,
        "subscriptions": [{"id": "sub-1", "code": "MIDA-669", "status": "active", "title": "测试"}],
        "events": [],
    }), encoding="utf-8")
    monkeypatch.setattr(backend, "_data_file", lambda: data_file)

    class FakeRuntime:
        def is_enabled(self, plugin_id):
            return plugin_id == "javdb"

        async def handle_action(self, plugin_id, action, payload):
            assert (plugin_id, action) == ("javdb", "video")
            assert payload == {"code": "MIDA-669", "refresh": True}
            return {"data": {
                "cover_url": "https://cdn.test/MIDA-669.jpg",
                "thumb_url": "https://cdn.test/MIDA-669-thumb.jpg",
                "preview_images": ["https://cdn.test/MIDA-669-preview.jpg"],
            }}

    import app.plugins.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "runtime", FakeRuntime())
    result = await backend.handle_action("refresh_cover", {"id": "sub-1"}, {})

    assert result["image_candidates"] == [
        "https://cdn.test/MIDA-669.jpg",
        "https://cdn.test/MIDA-669-thumb.jpg",
        "https://cdn.test/MIDA-669-preview.jpg",
    ]
    saved = json.loads(data_file.read_text(encoding="utf-8"))["subscriptions"][0]
    assert saved["title"] == "测试"
    assert saved["image_candidates"] == result["image_candidates"]
    assert saved["cover_refreshed_at"]
