from __future__ import annotations

from typing import Any

from app.api import local_library
from app.plugins.contracts import PluginTestResult

PLUGIN_ID = "local-subtitle-library"


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    legacy = local_library._load_config()
    if not any(key in config for key in ("library_paths", "index_enabled", "match_fuzzy")):
        return legacy
    return {**legacy, **config}


async def on_config_updated(config: dict[str, Any]) -> None:
    local_library._save_config(resolve_config(config))


async def test(config: dict[str, Any]) -> PluginTestResult:
    paths = local_library._get_library_paths(resolve_config(config))
    return PluginTestResult(ok=True, message=f"local subtitle library ready: {len(paths)} configured path(s)")


async def search_subtitles(config: dict[str, Any], video_code: str) -> list[dict[str, Any]]:
    results = local_library.search_local_library_with_config(video_code, resolve_config(config))
    for item in results:
        item.update(source="本地字幕库", source_key=PLUGIN_ID, source_type="local_library")
    return results


async def handle_action(action: str, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    cfg = resolve_config(config)
    if action == "index_status":
        stats = local_library._index_stats(cfg)
        return {**stats, "configured_paths": local_library._get_library_paths(cfg), "index_enabled": cfg.get("index_enabled", False)}
    if action == "rebuild_index":
        count, elapsed = local_library._build_index(cfg, force=True)
        return {"indexed_files": count, "elapsed_seconds": round(elapsed, 2)}
    raise ValueError(f"unsupported action: {action}")
