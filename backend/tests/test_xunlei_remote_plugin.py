from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

spec = importlib.util.spec_from_file_location("xunlei_remote_backend", ROOT / "plugins/xunlei-remote/backend.py")
xunlei_backend = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(xunlei_backend)


class FakeResponse:
    def __init__(self, data=None, text: str = "", status_code: int = 200):
        self._data = data if data is not None else {}
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}: {self.text}")


class FakeClient:
    def __init__(self, paths=None):
        self.paths = paths or []
        self.gets: list[dict] = []
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers=None, params=None):
        self.gets.append({"url": url, "headers": headers or {}, "params": params or {}})
        if "user/me" in url:
            return FakeResponse({"sub": "user-1", "name": "测试用户"})
        if "download_paths" in url:
            return FakeResponse({"paths": self.paths})
        return FakeResponse({})

    async def post(self, url, headers=None, params=None, content=None):
        self.posts.append({"url": url, "headers": headers or {}, "params": params or {}, "content": content})
        return FakeResponse({})


def test_restore_candidates_scans_only_residual_files(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    residual = root / "ABCD-123.xtld"
    residual.write_text("partial", encoding="utf-8")
    (root / "movie.mp4").write_text("video", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    result = asyncio.run(xunlei_backend._restore_candidates(config, FakeClient(), "pan-auth", "device", limit=50))
    assert result["total"] == 1
    assert result["items"][0]["path"] == str(residual)


def test_delete_residual_deletes_only_allowed_files(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    residual = root / "ABCD-123.xltd"
    residual.write_text("partial", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    result = asyncio.run(xunlei_backend._delete_residual(config, str(residual)))
    assert result["ok"] is True
    assert not residual.exists()


def test_delete_residual_rejects_outside_root(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    outside = tmp_path / "outside.xltd"
    outside.write_text("partial", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    with pytest.raises(ValueError, match="不在允许扫描目录内"):
        asyncio.run(xunlei_backend._delete_residual(config, str(outside)))


def test_explicit_savepath_fails_closed_when_unknown():
    config = {"savepath": "/volume1/data/downloads/av/"}
    client = FakeClient(paths=[])
    with pytest.raises(ValueError, match="迅雷保存路径无法解析"):
        asyncio.run(xunlei_backend._require_parent_folder_id_for_explicit_savepath(config, client, "pan-auth", "/volume1/data/downloads/av/"))


def test_plugin_json_only_exposes_nas_and_auto_speed_schema():
    plugin = json.loads((ROOT / "plugins/xunlei-remote/plugin.json").read_text(encoding="utf-8"))
    defaults = plugin["default_config"]
    assert defaults["auto_try_speed"] is True
    assert defaults["auto_try_speed_interval"] == 15
    assert "auto_try_speed" in plugin["config_schema"]
    assert not any(key.startswith(("account_", "mobile_")) for key in defaults)
    assert not any(key.startswith(("account_", "mobile_")) for key in plugin["config_schema"])


def test_auto_try_speed_applies_only_when_active_task_exists(monkeypatch):
    async def client_factory(_config, timeout=15.0):
        return FakeClient()

    async def context(_config, _client):
        return "pan-auth", "device", {}

    async def tasks(_config, _client, _pan_auth, _device_id, **_kwargs):
        return {"tasks": [{"id": "active", "phase": "PHASE_TYPE_RUNNING"}]}

    async def apply(_config, _client, _pan_auth):
        return {"ok": True, "applied": True, "try_speed": {"usage_used": 1, "usage_total": 3}}

    monkeypatch.setattr(xunlei_backend, "_client", client_factory)
    monkeypatch.setattr(xunlei_backend, "_context", context)
    monkeypatch.setattr(xunlei_backend, "_tasks", tasks)
    monkeypatch.setattr(xunlei_backend, "_try_speed_apply", apply)

    result = asyncio.run(xunlei_backend._auto_try_speed_once({}))

    assert result["applied"] is True
    assert xunlei_backend._speed_scheduler_status["last_message"] == "已自动使用试用加速"


def test_removed_experimental_paths_are_absent_from_plugin_contract():
    backend = (ROOT / "plugins/xunlei-remote/backend.py").read_text(encoding="utf-8")
    frontend = (ROOT / "plugins/xunlei-remote/frontend/page.js").read_text(encoding="utf-8")

    for removed in ("account_static_info", "account_user_me", "account_clients", "mobile_submit", "mobile_status", "_mobile_submit_download"):
        assert removed not in backend
    assert "账号探针" not in frontend
    assert "移动端" not in frontend


def test_toolbar_uses_one_active_filter_and_embeds_search_in_stats():
    source = (ROOT / "plugins/xunlei-remote/frontend/page.js").read_text(encoding="utf-8")

    assert "{ key: 'active', label: '进行中' }" in source
    assert "{ key: 'running', label: '下载中' }" not in source
    assert "云盘用量" not in source
    assert "任务额度 ${limitText} · 加速 ${speedUsed}/${speedTotal || '—'}" in source
    assert "账号探针" not in source
    assert "移动端" not in source
    assert 'class="xunlei-remote-stat xunlei-remote-stat--search"' in source
    assert "['PHASE_TYPE_PENDING', 'PHASE_TYPE_RUNNING'].includes(t.phase)" in source
