"""Shared helpers for the Emby media-library adapter.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from app.api.settings_helpers import read_env_file, set_env_values
from app.core.runtime_paths import data_path


SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".sbv", ".sup"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".mpeg", ".mpg", ".webm"}
UNCENSORED_STUDIOS = {
    "tokyo-hot", "一本画", "d3s", "empire", "tokyohot", "ArFORD", "kbn", "ipponga", "パコパコ団", "fc2", "光date", "mow-av", "无码", "hikari", "black", "supercard", "honmono", "uncensored", "caribbeancom", "tokyohotn", "n1", "30多岁", "大臣", "热狼", "daijin", "hot", "geino", "freak", "rocket-ch", "kaater", "天然素材", "东京热", "加勒比", "n0598", "d伞 Studios", "一本道", "caribbean", "heck", "无忌", "carib", "n0599", "ステージ2メディア", "自然资源", "10musume", "arford", "fc2ppv", "ichi", "bangbrokers", "s2media", "fc2-ppv", "heyzo", "エンパイア", "HEYZO", "shame", "geinou", "empiremedia", "SUPERSTUDIO", "untouched", "|-|鹰", "mow", "番号商店", "ippondo", "ebony", "無碼", "pacopaco", "IP", "d伞", "10mu", "s2-media", "一本", "カリビアン", "30s", "rocket", "nozoki", "unedited", "無修正", "shameless",
}
UNCENSORED_PATH_KEYWORDS = {
    "tokyo-hot", "無碼", "saika-", "流出", "n0842", "n0843", "heyzo", "fc2", "10mu", "10musume", "カリビアン", "toph", "無修正", "unco", "无码", "saika", "blacked", "n0598", "n1pon", "uncensored", "carib", "n0599", "n1",
}
ADAPTER_NOT_ACTIVATED = "媒体库适配器未配置，请在设置中配置 Emby / Jellyfin 服务器地址"
MEDIA_LIBRARY_SCAN_GROUPS_ENV = "MEDIA_LIBRARY_SCAN_GROUPS"
MEDIA_LIBRARY_PATH_PREFIX_ENV = "MEDIA_LIBRARY_PATH_PREFIX"
MEDIA_LIBRARY_LOCAL_PATH_PREFIX_ENV = "MEDIA_LIBRARY_LOCAL_PATH_PREFIX"


def config_path() -> Path:
    path = data_path("media_library_config.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _parse_scan_groups(raw_value: str) -> list[dict[str, str]]:
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    groups = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        groups.append({
            "name": str(item.get("name", "") or ""),
            "source_dir": str(item.get("source_dir", "") or ""),
            "hardlink_dir": str(item.get("hardlink_dir", "") or ""),
        })
    return groups


def _scan_groups_to_env(groups: list[dict[str, Any]] | None) -> str:
    normalized = []
    for item in groups or []:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "name": str(item.get("name", "") or ""),
            "source_dir": str(item.get("source_dir", "") or ""),
            "hardlink_dir": str(item.get("hardlink_dir", "") or ""),
        })
    return json.dumps(normalized, ensure_ascii=False)


def _env_backed_config(env_data: dict[str, str]) -> dict[str, Any]:
    return {
        "server_url": env_data.get("EMBY_SERVER", ""),
        "api_key": env_data.get("EMBY_API_KEY", ""),
        "user_id": env_data.get("EMBY_USER_ID", ""),
        "enabled_library_ids": env_data.get("EMBY_ENABLED_LIBRARY_IDS", ""),
        "path_prefix": env_data.get(MEDIA_LIBRARY_PATH_PREFIX_ENV, "/data/media"),
        "local_path_prefix": env_data.get(MEDIA_LIBRARY_LOCAL_PATH_PREFIX_ENV, env_data.get("SOURCE_DIR", "")),
        "scan_groups": _parse_scan_groups(env_data.get(MEDIA_LIBRARY_SCAN_GROUPS_ENV, "")),
        "webhook_token": env_data.get("MEDIA_LIBRARY_WEBHOOK_TOKEN", ""),
        "tmdb_api_key": env_data.get("TMDB_API_KEY", ""),
        "tmdb_api_token": env_data.get("TMDB_API_TOKEN", ""),
        "mdc_ng_actor_mapping_path": env_data.get("MDC_NG_ACTOR_MAPPING_PATH", ""),
    }


def _build_env_updates_from_config(config: dict[str, Any]) -> dict[str, str]:
    return {
        "EMBY_SERVER": str(config.get("server_url", "") or ""),
        "EMBY_API_KEY": str(config.get("api_key", "") or ""),
        "EMBY_USER_ID": str(config.get("user_id", "") or ""),
        "EMBY_ENABLED_LIBRARY_IDS": str(config.get("enabled_library_ids", "") or ""),
        MEDIA_LIBRARY_PATH_PREFIX_ENV: str(config.get("path_prefix", "/data/media") or "/data/media"),
        MEDIA_LIBRARY_LOCAL_PATH_PREFIX_ENV: str(config.get("local_path_prefix", "") or ""),
        MEDIA_LIBRARY_SCAN_GROUPS_ENV: _scan_groups_to_env(config.get("scan_groups", []) or []),
        "MEDIA_LIBRARY_WEBHOOK_TOKEN": str(config.get("webhook_token", "") or ""),
        "TMDB_API_KEY": str(config.get("tmdb_api_key", "") or ""),
        "TMDB_API_TOKEN": str(config.get("tmdb_api_token", "") or ""),
        "MDC_NG_ACTOR_MAPPING_PATH": str(config.get("mdc_ng_actor_mapping_path", "") or ""),
    }


def load_config() -> dict[str, Any]:
    return _env_backed_config(read_env_file())


def save_config(config: dict[str, Any]) -> None:
    current = load_config()
    current.update(config)
    if "local_path_prefix" not in current or not str(current.get("local_path_prefix", "")).strip():
        current["local_path_prefix"] = str(current.get("local_path_prefix") or current.get("source_dir") or "")
    set_env_values(_build_env_updates_from_config(current))


def get_config() -> dict[str, Any]:
    return load_config()


def headers(api_key: str) -> dict[str, str]:
    return {"X-Emby-Token": api_key}


def server_url(config: dict[str, Any]) -> str:
    return config.get("server_url", "http://localhost:8096").rstrip("/")


def env_source_dir() -> str:
    return read_env_file().get("SOURCE_DIR", "")


def local_media_root(config: dict[str, Any]) -> str:
    scan_groups = config.get("scan_groups", []) or []
    hardlink_parents = []
    for group in scan_groups:
        hardlink_dir = group.get("hardlink_dir")
        if hardlink_dir:
            hardlink_parents.append(str(Path(hardlink_dir).resolve().parent))
    if hardlink_parents:
        try:
            return os.path.commonpath(hardlink_parents)
        except Exception:
            return hardlink_parents[0]
    source_dir = env_source_dir()
    if source_dir:
        return source_dir
    return ""


def map_path(server_path: str | None, config: dict[str, Any]) -> str | None:
    if not server_path:
        return server_path
    prefix = config.get("path_prefix", "/data/media")
    local_root = (config.get("local_path_prefix") or "").strip() or local_media_root(config)
    if local_root and server_path.startswith(prefix):
        return server_path.replace(prefix, local_root, 1)
    return server_path


def parse_tags(name: str, studios: list[str], file_path: str | None) -> dict[str, Any]:
    base = name.rsplit(".", 1)[0] if "." in name else name
    lower = base.lower()
    fp_lower = (file_path or "").lower()
    fp_dir_lower = ""
    fp_base = ""
    fp_name = ""
    if file_path:
        fp_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        fp_dir = os.path.basename(os.path.dirname(file_path)).lower()
        fp_dir_lower = os.path.dirname(file_path).lower()
        fp_base = fp_name + " " + fp_dir

    has_chinese = bool(
        re.search(r"[-_]c(\d*)[-_\.]", lower)
        or "中文字幕" in base
        or "chinese" in lower
        or "中文字幕" in fp_lower
        or (file_path and (fp_name.endswith("-c") or fp_name.endswith("-c1") or fp_name.endswith("-c2")))
    )
    is_cracked = bool(
        re.search(r"[-_]u\d*[-_\.]", lower)
        or "破解" in base
        or "uncensored" in lower
        or "破解" in fp_lower
        or "破解" in fp_base
        or (file_path and (fp_name.endswith("-u") or fp_name.endswith("-u1")))
    )
    is_leaked = bool("流出" in base or "leaked" in lower or "流出" in fp_lower)
    has_facefusion = bool(
        re.search(r"(^|[^a-z0-9])(facefusion|ff)(?=[^a-z0-9]|$)", lower)
        or re.search(r"(^|[^a-z0-9])(facefusion|ff)(?=[^a-z0-9]|$)", fp_lower)
    )
    has_uncensored_studio = any(s.lower() in UNCENSORED_STUDIOS or any(k in s.lower() for k in UNCENSORED_STUDIOS) for s in studios)
    # Do not infer real uncensored works from the Emby title or filename. Phrases
    # like "無碼破解" are common marketing/variant labels for cracked mosaics.
    has_uncensored_path = any(k in fp_dir_lower for k in UNCENSORED_PATH_KEYWORDS)
    is_uncensored = bool(has_uncensored_studio or has_uncensored_path)
    if is_uncensored and not is_leaked and not is_cracked:
        release_type = "无码"
        release_type_key = "uncensored"
    elif is_leaked:
        release_type = "流出"
        release_type_key = "leaked"
    else:
        release_type = None
        release_type_key = None
    return {
        "is_uncensored": is_uncensored,
        "is_cracked": is_cracked,
        "has_chinese": has_chinese,
        "is_leaked": is_leaked,
        "has_facefusion": has_facefusion,
        "release_type": release_type,
        "release_type_key": release_type_key,
    }


def parse_item(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    poster_url = None
    for img_type in ("Primary", "Thumb", "Backdrop"):
        tag = item.get("ImageTags", {}).get(img_type)
        if tag:
            poster_url = f"{server_url(config)}/emby/Items/{item['Id']}/Images/{img_type}?tag={tag}"
            break

    file_path = None
    media_sources = item.get("MediaSources", [])
    for source in media_sources:
        if source.get("Type") == "Default":
            file_path = source.get("Path")
            break
    if not file_path and media_sources:
        file_path = media_sources[0].get("Path")
    if file_path:
        file_path = map_path(file_path, config)

    subtitle_count = 0
    if file_path and os.path.isdir(os.path.dirname(file_path)):
        video_name = os.path.splitext(os.path.basename(file_path))[0].lower()
        video_dir = os.path.dirname(file_path)
        try:
            for fn in os.listdir(video_dir):
                filepath = os.path.join(video_dir, fn)
                if not os.path.isfile(filepath):
                    continue
                base, ext = os.path.splitext(fn)
                base = base.lower()
                ext = ext.lower()
                if ext not in SUBTITLE_EXTS:
                    continue
                if base in video_name or video_name.startswith(base) or (len(base) >= 8 and video_name.startswith(base[:8])):
                    subtitle_count += 1
        except PermissionError:
            pass

    studios = [s.get("Name") for s in item.get("Studios", []) if s.get("Name")]
    return {
        "id": item["Id"],
        "name": item.get("Name", "Unknown"),
        "type": item.get("Type", "unknown"),
        "media_type": item.get("MediaType"),
        "poster_path": poster_url,
        "date_created": item.get("DateCreated"),
        "path": file_path,
        "tags": parse_tags(item.get("Name", ""), studios, file_path),
        "subtitle_count": subtitle_count,
    }
