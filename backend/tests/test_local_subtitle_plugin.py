from __future__ import annotations

import asyncio
from pathlib import Path

from app.plugins.handlers import clear_handler_cache, get_plugin_handler


def _handler():
    clear_handler_cache()
    handler = get_plugin_handler("local-subtitle-library")
    assert handler is not None
    return handler


def test_local_subtitle_plugin_is_independent_from_legacy_api() -> None:
    source = Path(__file__).resolve().parents[2] / "plugins" / "local-subtitle-library" / "backend.py"
    text = source.read_text(encoding="utf-8")

    assert "from app.api import local_library" not in text
    assert "asyncio.to_thread(_search" in text
    assert "asyncio.to_thread(_build_index" in text
    assert 'plugin_data_path(PLUGIN_ID, "subtitle_index.db")' in text


def test_local_subtitle_plugin_owns_index_search_and_status(tmp_path: Path, monkeypatch) -> None:
    handler = _handler()
    library = tmp_path / "library"
    library.mkdir()
    (library / "PRED-878.zh.srt").write_text("subtitle", encoding="utf-8")
    plugin_data = tmp_path / "plugin-data"
    legacy_data = tmp_path / "legacy-data"
    monkeypatch.setattr(handler, "plugin_data_path", lambda _plugin_id, *parts: plugin_data.joinpath(*parts))
    monkeypatch.setattr(handler, "data_path", lambda *parts: legacy_data.joinpath(*parts))
    config = {"library_paths": str(library), "index_enabled": True, "match_fuzzy": True}

    rebuilt = asyncio.run(handler.handle_action("rebuild_index", config, {}))
    status = asyncio.run(handler.handle_action("index_status", config, {}))
    results = asyncio.run(handler.search_subtitles(config, "PRED-878"))

    assert rebuilt["indexed_files"] == 1
    assert status["index_exists"] is True
    assert status["indexed_count"] == 1
    assert status["configured_paths"] == [str(library)]
    assert len(results) == 1
    assert results[0]["source_key"] == "local-subtitle-library"
    assert (plugin_data / "subtitle_index.db").is_file()

