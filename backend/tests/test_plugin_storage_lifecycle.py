from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import plugins as plugins_api
from app.core.runtime_paths import plugin_cache_path, plugin_data_path, plugin_storage_path, purge_plugin_storage
from app.plugins.runtime import PluginRuntime


def _settings(tmp_path):
    return SimpleNamespace(noor_data_dir=str(tmp_path))


def test_plugin_paths_are_isolated_and_legacy_cache_is_copied(tmp_path) -> None:
    settings = _settings(tmp_path)
    legacy = tmp_path / "plugin_cache" / "gfriends"
    legacy.mkdir(parents=True)
    (legacy / "index.json").write_text("{}", encoding="utf-8")

    cache = plugin_cache_path("gfriends", settings=settings)

    assert cache == tmp_path / "plugins" / "gfriends" / "cache"
    assert (cache / "index.json").read_text(encoding="utf-8") == "{}"
    assert plugin_data_path("gfriends", settings=settings) == tmp_path / "plugins" / "gfriends" / "data"


def test_purge_plugin_storage_only_removes_exact_plugin_root(tmp_path) -> None:
    settings = _settings(tmp_path)
    target = plugin_storage_path("demo", settings=settings)
    sibling = plugin_storage_path("demo-two", settings=settings)
    (target / "data").mkdir(parents=True)
    (target / "data" / "state.json").write_text("{}", encoding="utf-8")
    sibling.mkdir(parents=True)

    assert purge_plugin_storage("demo", settings=settings) is True
    assert not target.exists()
    assert sibling.exists()


def test_runtime_uninstall_runs_hook_and_honors_purge_flag(tmp_path, monkeypatch) -> None:
    runtime = PluginRuntime.__new__(PluginRuntime)
    runtime._lock = asyncio.Lock()
    runtime.plugin_root = tmp_path / "code"
    target = runtime.plugin_root / "demo"
    target.mkdir(parents=True)
    events = []

    class Handler:
        async def on_uninstall(self, config, *, purge_data):
            events.append((config, purge_data))

    async def stop(_plugin_id):
        return None

    runtime._stop_plugin_background = stop
    runtime._handler = lambda _plugin_id: Handler()
    runtime.get_config = lambda _plugin_id: {"key": "value"}
    runtime.reload = lambda: None
    monkeypatch.setattr("app.plugins.runtime.purge_plugin_storage", lambda plugin_id: events.append((plugin_id, "purged")) or True)

    result = asyncio.run(runtime.uninstall_plugin("demo", purge_data=True))

    assert not target.exists()
    assert events == [({"key": "value"}, True), ("demo", "purged")]
    assert result["data_removed"] is True


def test_uninstall_api_forwards_preserve_choice(monkeypatch) -> None:
    calls = []

    async def uninstall(plugin_id: str, *, purge_data: bool = True):
        calls.append((plugin_id, purge_data))
        return {"ok": True, "plugin_id": plugin_id, "purge_data": purge_data}

    monkeypatch.setattr(plugins_api.runtime, "uninstall_plugin", uninstall)
    app = FastAPI()
    app.include_router(plugins_api.router)
    client = TestClient(app)

    assert client.delete("/api/plugins/demo").json()["purge_data"] is True
    assert client.delete("/api/plugins/demo?purge_data=false").json()["purge_data"] is False
    assert calls == [("demo", True), ("demo", False)]


def test_plugin_manager_exposes_purge_or_preserve_uninstall_choice() -> None:
    source = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "PluginManager.vue"
    text = source.read_text(encoding="utf-8")

    assert "preserveUninstallData" in text
    assert "params: { purge_data: !preserveUninstallData.value }" in text
    assert "保留插件数据，便于以后重新安装恢复" in text
    assert "删除数据并卸载" in text


def test_official_plugins_use_explicit_private_storage_ids() -> None:
    root = Path(__file__).resolve().parents[2] / "plugins"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*/backend.py"))

    assert "plugin_cache_path()" not in sources
    assert 'plugin_data_path("av_recommend"' not in sources
    assert 'plugin_data_path("subscription_core"' not in sources
