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
    monkeypatch.setattr(backend, "DATA_FILE", data_file)

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
