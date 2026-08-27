from __future__ import annotations

from app.plugins import store


def test_plugin_store_seeds_official_market_for_new_install(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    assert store.load_market_repos() == [{"url": "https://github.com/kinaxng/NOOR-Plugins"}]


def test_plugin_store_respects_explicitly_empty_market_list(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    store.save_market_repos([])

    assert store.load_market_repos() == []


def test_plugin_store_uses_runtime_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    store.save_state({"enabled": {"gfriends": True}})
    store.save_config({"gfriends": {"enabled": True}})
    store.save_market_repos([{"url": "https://example.test/plugins.git"}])

    assert (tmp_path / "plugins_state.json").exists()
    assert (tmp_path / "plugins" / "gfriends" / "config.json").exists()
    assert (tmp_path / "plugins" / ".config_migrated").exists()
    assert (tmp_path / "plugins_market_repos.json").exists()
    assert store.load_state()["enabled"]["gfriends"] is True
    assert store.load_config()["gfriends"]["enabled"] is True
    assert store.load_market_repos() == [{"url": "https://example.test/plugins.git"}]


def test_plugin_store_migrates_legacy_config_to_private_files(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    store._write_json(tmp_path / "plugins_config.json", {"javdb": {"base_url": "legacy"}})

    loaded = store.load_config()
    store.save_config(loaded)

    assert loaded == {"javdb": {"base_url": "legacy"}}
    assert (tmp_path / "plugins" / "javdb" / "config.json").read_text(encoding="utf-8")
    assert store.load_config() == {"javdb": {"base_url": "legacy"}}


def test_migrated_legacy_config_does_not_resurrect_after_private_config_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    store._write_json(tmp_path / "plugins_config.json", {"javdb": {"base_url": "legacy"}})

    store.save_config(store.load_config())
    (tmp_path / "plugins" / "javdb" / "config.json").unlink()

    assert store.load_config() == {}
