from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_settings_index_enforces_readable_shared_typography() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "settings" / "SettingsIndex.vue").read_text(encoding="utf-8")

    assert ".settings-page__content :deep(.settings-card__title)" in source
    assert "font-size: 1rem" in source
    assert ".field-row__label-desc" in source
    assert ".field-row__hint" in source
    assert ".plugin-card__meta" in source
    assert "font-size: 0.75rem" in source


def test_hardlink_dense_metadata_has_twelve_pixel_floor() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "HardlinkView.vue").read_text(encoding="utf-8")

    for selector in (".hl-group__meta", ".hl-entry__count", ".row-action-btn", ".group-action-btn"):
        match = re.search(re.escape(selector) + r"[^\{]*\{([^}]*)\}", source)
        assert match is not None
        assert "font-size: 0.75rem" in match.group(1)


def test_global_typography_tokens_have_complete_readable_fallbacks() -> None:
    source = (ROOT / "frontend" / "src" / "style.css").read_text(encoding="utf-8")

    assert "--color-text-body:" in source
    assert "--color-text-tertiary:" in source
    assert "--color-surface-card:" in source
    assert re.search(r"html\s*\{[^}]*font-size:\s*16px", source, re.S)
    body = re.search(r"body\s*\{([^}]*)\}", source, re.S)
    assert body is not None
    assert "font-size: var(--font-size-base)" in body.group(1)
    assert "line-height: 1.5" in body.group(1)


def test_plugin_host_inherits_the_shared_typography_baseline() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "PluginHost.vue").read_text(encoding="utf-8")

    host = re.search(r"\.plugin-host-page\s*\{([^}]*)\}", source, re.S)
    assert host is not None
    assert "font-family: var(--font-body)" in host.group(1)
    assert "font-size: var(--font-size-sm)" in host.group(1)
    assert "line-height: 1.5" in host.group(1)
