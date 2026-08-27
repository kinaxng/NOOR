from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_plugin_manager_exposes_installed_market_and_repository_sections() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "PluginManager.vue").read_text(encoding="utf-8")

    assert "已安装" in source
    assert "插件商店" in source
    assert "仓库" in source
    assert "'/plugins/market/repos'" in source
    assert "'/plugins/market/items'" in source
    assert "'/plugins/market/install'" in source
    assert "'/plugins/reload'" in source
    assert "if (activeSection.value === 'market') return pluginCards.value" in source
    assert "plugin.installed ? '更新' : '安装'" in source
    assert 'v-if="!plugin.installed || plugin.updateAvailable"' in source
    assert 'plugin-card__installed-copy">已安装' in source


def test_removed_av_graph_is_not_bundled() -> None:
    assert not (ROOT / "plugins" / "av-graph").exists()
