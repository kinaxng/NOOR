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
        expected = "0.8125rem" if selector in (".hl-group__meta", ".hl-entry__count") else "0.75rem"
        assert f"font-size: {expected}" in match.group(1)


def test_files_page_uses_the_shared_noor_tabs() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "FilesView.vue").read_text(encoding="utf-8")

    assert "import VisionTabs" in source
    assert "<VisionTabs" in source
    assert 'class="files-tab"' not in source


def test_emby_webhook_uses_readable_explicit_typography() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "settings" / "SystemSettings.vue").read_text(encoding="utf-8")

    webhook_url = re.search(r"\.webhook-url-row code\s*\{([^}]*)\}", source, re.S)
    guide = re.search(r"\.webhook-guide\s*\{([^}]*)\}", source, re.S)
    assert webhook_url is not None and "font-size: var(--font-size-sm)" in webhook_url.group(1)
    assert "font-family: var(--font-display)" in webhook_url.group(1)
    assert guide is not None and "font-size: var(--font-size-xs)" in guide.group(1)


def test_file_tabs_do_not_repeat_the_topbar_title_and_child_titles_match() -> None:
    files = (ROOT / "frontend" / "src" / "views" / "FilesView.vue").read_text(encoding="utf-8")
    hardlinks = (ROOT / "frontend" / "src" / "views" / "HardlinkView.vue").read_text(encoding="utf-8")
    actors = (ROOT / "frontend" / "src" / "views" / "ActorManagementView.vue").read_text(encoding="utf-8")

    assert '<h1 class="files-title">' not in files
    assert '<h1 class="page-title">' in hardlinks
    assert '<h1 class="page-title">' in actors
    for source in (hardlinks, actors):
        title = re.search(r"\.page-title\s*\{([^}]*)\}", source, re.S)
        assert title is not None
        assert "font-family: var(--font-display)" in title.group(1)
        assert "font-size: 1.25rem" in title.group(1)


def test_hardlink_work_code_uses_noor_display_typography() -> None:
    source = (ROOT / "frontend" / "src" / "views" / "HardlinkView.vue").read_text(encoding="utf-8")
    code = re.search(r"\.hl-group__code\s*\{([^}]*)\}", source, re.S)

    assert 'class="hl-group__code"' in source
    assert code is not None and "font-family: var(--font-display)" in code.group(1)


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
