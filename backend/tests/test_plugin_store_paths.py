from __future__ import annotations

from app.plugins import store


def test_plugin_store_uses_runtime_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    store.save_state({"enabled": {"gfriends": True}})
    store.save_config({"gfriends": {"enabled": True}})
    store.save_market_repos([{"url": "https://example.test/plugins.git"}])

    assert (tmp_path / "plugins_state.json").exists()
    assert (tmp_path / "plugins_config.json").exists()
    assert (tmp_path / "plugins_market_repos.json").exists()
    assert store.load_state()["enabled"]["gfriends"] is True
    assert store.load_config()["gfriends"]["enabled"] is True
    assert store.load_market_repos() == [{"url": "https://example.test/plugins.git"}]
