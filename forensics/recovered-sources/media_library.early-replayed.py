"""
Media Library API — direct Emby/Jellyfin adapter.
"""
import os
import re
import secrets
import shutil
import time
import json
import asyncio
import base64
import mimetypes
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.api.system import SystemLogManager
from app.core.config import get_settings
from app.core.runtime_paths import data_path

from app.api.endpoints.media_library_helpers import (
    ADAPTER_NOT_ACTIVATED as _ADAPTER_NOT_ACTIVATED,
    VIDEO_EXTS,
    env_source_dir as _env_source_dir,
    config_path as _config_path,
    get_config as _get_config,
    headers as _headers,
    load_config as _load_config,
    map_path as _map_path,
    parse_item as _parse_item,
    parse_tags as _parse_tags,
    save_config as _save_config,
    server_url as _server_url,
)

from app.api.endpoints.media_library_item_detail import (
    get_item_impl,
    get_main_nfo_impl,
    get_siblings_impl,
)

from app.api.endpoints.media_library_hardlinks import (
    build_hardlink_groups_impl,
    enrich_hardlink_groups_impl,
    extract_code_from_path_impl,
    fetch_emby_item_info_impl,
    hardlink_groups_path_impl,
    load_hardlink_groups_impl,
    save_hardlink_groups_impl,
    scan_inodes_impl,
    scan_single_group_impl,
)

_ACTOR_TMDB_BACKFILL_PROGRESS: dict[str, dict[str, Any]] = {}
_ACTOR_NAME_SYNC_PROGRESS: dict[str, dict[str, Any]] = {}

router = APIRouter(prefix="/api/media-library", tags=["media-library"])

_items_cache: dict[str, tuple[list[dict], float]] = {}
_CACHE_TTL = 86400  # 24h
_sync_version = 0
_last_invalidated_at: float | None = None
_last_webhook_at: float | None = None
_actor_mapping_records_cache: tuple[float, list[dict]] | None = None
_actor_mapping_name_index_cache: tuple[int, dict[str, dict]] | None = None
_actor_mapping_tmdb_index_cache: tuple[int, dict[str, dict]] | None = None
_actor_mapping_auto_update_task: asyncio.Task | None = None

MDC_NG_ACTOR_MAPPING_RELATIVE_PATH = Path("data") / "data" / "mapping_actor.xml"


class HardlinkDeleteRequest(BaseModel):
    file_path: str
    remove_nfo: bool = True
    dry_run: bool = False


class SourceChainDeleteRequest(BaseModel):
    source_path: str
    hardlink_paths: list[str] = []
    code: str | None = None
    dry_run: bool = False


class HardlinkEntryDeletePayload(BaseModel):
    source_path: str | None = None
    hardlink_paths: list[str] = []


class GroupDeleteRequest(BaseModel):
    code: str
    entries: list[HardlinkEntryDeletePayload]
    dry_run: bool = False


class MediaItemDeleteRequest(BaseModel):
    item_id: str
    dry_run: bool = False


class ActorMappingMergeRequest(BaseModel):
    mapping_id: str
    target_name: str | None = None
    target_actor_id: str | None = None
    dry_run: bool = False


class ActorMappingMergeBatchRequest(BaseModel):
    target_actor_ids: dict[str, str] = {}
    skip_conflicts: bool = True
    dry_run: bool = False


class ActorTmdbBackfillRequest(BaseModel):
    actor_ids: list[str] | None = None
    only_high_confidence: bool = True
    dry_run: bool = False
    progress_key: str | None = None


class ActorNameSyncRequest(BaseModel):
    actor_ids: list[str] | None = None
    skip_conflicts: bool = True
    dry_run: bool = False
    progress_key: str | None = None


class ActorProfileUpdateRequest(BaseModel):
    name: str | None = None
    sort_name: str | None = None
    jp_name: str | None = None
    zh_cn_name: str | None = None
    zh_tw_name: str | None = None
    aliases: list[str] | None = None
    overview: str | None = None
    provider_ids: dict[str, str] | None = None
    birthday: str | None = None
    deathday: str | None = None
    place_of_birth: str | None = None
    gender: str | None = None
    known_for_department: str | None = None
    popularity: float | None = None
    homepage: str | None = None
    external_urls: dict[str, str] | None = None


class ActorAvatarUrlRequest(BaseModel):
    url: str


class ActorTmdbApplyRequest(BaseModel):
    apply_name: bool = False
    apply_overview: bool = True
    apply_provider_ids: bool = True
    apply_avatar: bool = False


def _actor_mapping_upload_dir() -> Path:
    path = data_path() / "media_actor_mapping_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_filename(filename: str | None) -> str:
    raw = Path(filename or "actor_mapping").name.strip() or "actor_mapping"
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fffぁ-んァ-ン一-龯]", "_", raw)[:120]


def _actor_mapping_upload_info(path: Path, size: int | None = None) -> dict:
    stat = path.stat()
    return {
        "filename": path.name,
        "size": size if size is not None else stat.st_size,
        "format": path.suffix.lower().lstrip(".") or "unknown",
        "saved_path": str(path),
        "uploaded_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _actor_mapping_store_path() -> Path:
    path = data_path() / "media_actor_mappings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _actor_mapping_sync_state_path() -> Path:
    path = data_path() / "media_actor_mapping_sync_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_actor_mapping_online_state_path() -> Path:
    return data_path() / "media_actor_mapping_online_state.json"


def _load_actor_mapping_sync_state() -> dict:
    path = _actor_mapping_sync_state_path()
    if not path.is_file() and _legacy_actor_mapping_online_state_path().is_file():
        path = _legacy_actor_mapping_online_state_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_actor_mapping_sync_state(payload: dict) -> None:
    path = _actor_mapping_sync_state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _actor_merge_backup_dir() -> Path:
    path = data_path() / "actor_merge_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _actor_merge_ignored_ghosts_path() -> Path:
    path = data_path() / "actor_merge_ignored_ghosts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_actor_merge_ignored_ghosts() -> set[str]:
    path = _actor_merge_ignored_ghosts_path()
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(payload, list):
        return {str(item) for item in payload if str(item).strip()}
    if isinstance(payload, dict):
        return {str(item) for item in payload.get("actor_ids", []) if str(item).strip()}
    return set()


def _save_actor_merge_ignored_ghosts(actor_ids: set[str]) -> None:
    _actor_merge_ignored_ghosts_path().write_text(
        json.dumps(
            {"actor_ids": sorted(actor_ids), "updated_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _actor_profile_overrides_path() -> Path:
    path = data_path() / "actor_profile_overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_actor_profile_overrides() -> dict[str, dict]:
    path = _actor_profile_overrides_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_actor_profile_overrides(overrides: dict[str, dict]) -> None:
    _actor_profile_overrides_path().write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_actor_mapping_upload_path() -> Path | None:
    latest = _actor_mapping_upload_dir() / "latest"
    if not latest.is_file():
        return None
    path = Path(latest.read_text(encoding="utf-8").strip())
    return path if path.is_file() else None


def _split_mapping_keywords(value: str | None) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    # Spaces are part of many English names, so only explicit list separators split aliases.
    parts = re.split(r"[,，、;；|/]+", raw)
    out: list[str] = []
    for part in parts:
        name = part.strip()
        if name and name not in out:
            out.append(name)
    return out


def _normalize_mapping_record(attrs: dict[str, str]) -> dict:
    zh_cn = str(attrs.get("zh_cn") or "").strip()
    zh_tw = str(attrs.get("zh_tw") or "").strip()
    jp = str(attrs.get("jp") or "").strip()
    keyword_names = _split_mapping_keywords(attrs.get("keyword"))
    names: list[str] = []
    for name in [jp, zh_cn, zh_tw, *keyword_names]:
        if name and name not in names:
            names.append(name)
    tmdb_id = str(attrs.get("tmdb_id") or "").strip()
    key_source = tmdb_id or jp or zh_cn or zh_tw or (names[0] if names else "")
    return {
        "id": tmdb_id or _normalize_actor_key(key_source),
        "jp": jp,
        "zh_cn": zh_cn,
        "zh_tw": zh_tw,
        "aliases": [name for name in names if name not in {jp, zh_cn, zh_tw}],
        "names": names,
        "tmdb_id": tmdb_id,
        "verified": str(attrs.get("verified") or "").strip() in {"1", "true", "True", "yes"},
    }


def _parse_actor_mapping_xml(path: Path) -> tuple[list[dict], dict]:
    records: list[dict] = []
    missing: dict[str, int] = {"keyword": 0, "tmdb_id": 0, "verified": 0}
    verified_count = 0
    for _event, elem in ET.iterparse(path, events=("end",)):
        tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
        if tag != "a":
            elem.clear()
            continue
        attrs = {key: value for key, value in elem.attrib.items()}
        record = _normalize_mapping_record(attrs)
        records.append(record)
        if not attrs.get("keyword"):
            missing["keyword"] += 1
        if not attrs.get("tmdb_id"):
            missing["tmdb_id"] += 1
        if not attrs.get("verified"):
            missing["verified"] += 1
        if record["verified"]:
            verified_count += 1
        elem.clear()
    stats = {
        "total": len(records),
        "verified": verified_count,
        "missing": missing,
        "with_tmdb": len(records) - missing["tmdb_id"],
    }
    return records, stats


def _save_actor_mapping_records(records: list[dict], source_path: Path, stats: dict) -> dict:
    global _actor_mapping_records_cache, _actor_mapping_name_index_cache, _actor_mapping_tmdb_index_cache
    payload = {
        "version": 1,
        "source_path": str(source_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "records": records,
    }
    path = _actor_mapping_store_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    try:
        mtime = path.stat().st_mtime
        _actor_mapping_records_cache = (mtime, records)
    except OSError:
        _actor_mapping_records_cache = None
    _actor_mapping_name_index_cache = None
    _actor_mapping_tmdb_index_cache = None
    return {
        "path": str(path),
        "updated_at": payload["updated_at"],
        "stats": stats,
    }


def _clear_actor_mapping_records() -> dict:
    global _actor_mapping_records_cache, _actor_mapping_name_index_cache, _actor_mapping_tmdb_index_cache
    removed: list[str] = []
    for path in (_actor_mapping_store_path(), _actor_mapping_sync_state_path(), _legacy_actor_mapping_online_state_path()):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    _actor_mapping_records_cache = None
    _actor_mapping_name_index_cache = None
    _actor_mapping_tmdb_index_cache = None
    return {"ok": True, "removed": removed}


def _configured_mdc_ng_root_path(config: dict | None = None) -> Path | None:
    cfg = config if config is not None else _load_config()
    raw = str(cfg.get("mdc_ng_actor_mapping_path") or "").strip()
    return Path(raw) if raw else None


def _configured_mdc_ng_actor_mapping_path(config: dict | None = None) -> Path:
    root = _configured_mdc_ng_root_path(config)
    if root is None:
        raise ValueError("请先在设置-EMBY 中填写 MDC-NG 路径")
    return root / MDC_NG_ACTOR_MAPPING_RELATIVE_PATH


def _validate_actor_mapping_xml_path(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"MDC-NG 演员映射表不存在: {path}")
    if path.suffix.lower() != ".xml":
        raise ValueError("MDC-NG 演员映射表必须是 XML 文件")
    if path.stat().st_size <= 0:
        raise ValueError("MDC-NG 演员映射表为空")


async def _sync_actor_mapping_from_mdc_ng(*, force: bool = False) -> dict:
    state = _load_actor_mapping_sync_state()
    now = datetime.now(timezone.utc)
    state.update({"last_attempt_at": now.isoformat(), "running": True})
    _save_actor_mapping_sync_state(state)
    try:
        source = _configured_mdc_ng_actor_mapping_path()
        _validate_actor_mapping_xml_path(source)
        records, stats = _parse_actor_mapping_xml(source)
        source_stat = source.stat()
        meta = {
            "source_path": str(source),
            "source_label": "mdc-ng",
            "source_mtime": datetime.fromtimestamp(source_stat.st_mtime, timezone.utc).isoformat(),
            "source_size": source_stat.st_size,
        }
        result = _save_actor_mapping_records(records, source, {**stats, "mdc_ng": True, **meta})
        state = {
            "enabled": bool(getattr(get_settings(), "actor_mapping_auto_update", False)),
            "running": False,
            "last_attempt_at": now.isoformat(),
            "last_success_at": datetime.now(timezone.utc).isoformat(),
            "last_error": "",
            "source_path": str(source),
            "source_label": meta.get("source_label"),
            "source_mtime": meta.get("source_mtime"),
            "source_size": meta.get("source_size"),
            "stats": stats,
        }
        _save_actor_mapping_sync_state(state)
        SystemLogManager.get_instance().add_log(
            "info",
            f"[MediaLibrary] MDC-NG 演员映射表已同步: {stats.get('total', 0)} 条 · {source}",
            source="media_library.actors",
        )
        return {"ok": True, "mapping": result, "mdc_ng": state, "online": state}
    except Exception as exc:
        state.update({"running": False, "last_error": str(exc)})
        _save_actor_mapping_sync_state(state)
        SystemLogManager.get_instance().add_log("error", f"[MediaLibrary] MDC-NG 演员映射表同步失败: {exc}", source="media_library.actors")
        if force:
            raise
        return {"ok": False, "error": str(exc), "mdc_ng": state, "online": state}


def _maybe_schedule_actor_mapping_auto_update() -> None:
    global _actor_mapping_auto_update_task
    try:
        settings = get_settings()
        if not bool(getattr(settings, "actor_mapping_auto_update", False)):
            return
        config = _load_config()
        if _configured_mdc_ng_root_path(config) is None:
            return
        state = _load_actor_mapping_sync_state()
        if state.get("running"):
            return
        if _actor_mapping_auto_update_task and not _actor_mapping_auto_update_task.done():
            return
        last_success = str(state.get("last_success_at") or "")
        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last_dt).total_seconds() < 24 * 3600:
                    return
            except Exception:
                pass
        _actor_mapping_auto_update_task = asyncio.create_task(_sync_actor_mapping_from_mdc_ng(force=False))
    except RuntimeError:
        return


def _load_actor_mapping_status() -> dict:
    path = _actor_mapping_store_path()
    if not path.is_file():
        return {"imported": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"imported": False, "error": "映射表文件无法读取"}
    records = payload.get("records") if isinstance(payload, dict) else []
    return {
        "imported": True,
        "path": str(path),
        "source_path": payload.get("source_path"),
        "updated_at": payload.get("updated_at"),
        "stats": payload.get("stats") or {"total": len(records or [])},
    }


def _load_actor_mapping_records() -> list[dict]:
    global _actor_mapping_records_cache, _actor_mapping_name_index_cache, _actor_mapping_tmdb_index_cache
    path = _actor_mapping_store_path()
    if not path.is_file():
        _actor_mapping_records_cache = None
        _actor_mapping_name_index_cache = None
        _actor_mapping_tmdb_index_cache = None
        return []
    try:
        mtime = path.stat().st_mtime
    except OSError:
        _actor_mapping_records_cache = None
        _actor_mapping_name_index_cache = None
        _actor_mapping_tmdb_index_cache = None
        return []
    if _actor_mapping_records_cache and _actor_mapping_records_cache[0] == mtime:
        return _actor_mapping_records_cache[1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _actor_mapping_records_cache = None
        _actor_mapping_name_index_cache = None
        _actor_mapping_tmdb_index_cache = None
        return []
    records = payload.get("records") if isinstance(payload, dict) else []
    parsed = [item for item in (records or []) if isinstance(item, dict)]
    _actor_mapping_records_cache = (mtime, parsed)
    _actor_mapping_name_index_cache = None
    _actor_mapping_tmdb_index_cache = None
    return parsed


def _actor_mapping_primary_names(record: dict) -> set[str]:
    return {
        str(name or "")
        for name in (record.get("jp"), record.get("zh_cn"), record.get("zh_tw"))
        if str(name or "").strip()
    }


def _actor_mapping_name_index(records: list[dict]) -> dict[str, dict]:
    global _actor_mapping_name_index_cache
    cache_key = id(records)
    if _actor_mapping_name_index_cache and _actor_mapping_name_index_cache[0] == cache_key:
        return _actor_mapping_name_index_cache[1]
    index: dict[str, dict] = {}
    primary_keys: set[str] = set()
    for record in records:
        primary_names = _actor_mapping_primary_names(record)
        for name in primary_names:
            key = _normalize_actor_key(str(name or ""))
            if key and key not in index:
                index[key] = {
                    "record": record,
                    "name": str(name or ""),
                    "source": "primary",
                }
            if key:
                primary_keys.add(key)
    for record in records:
        primary_names = _actor_mapping_primary_names(record)
        for name in record.get("names") or []:
            key = _normalize_actor_key(str(name or ""))
            if (
                key
                and key not in index
                and key not in primary_keys
                and str(name or "") not in primary_names
            ):
                index[key] = {
                    "record": record,
                    "name": str(name or ""),
                    "source": "alias",
                }
    _actor_mapping_name_index_cache = (cache_key, index)
    return index


def _actor_mapping_tmdb_index(records: list[dict]) -> dict[str, dict]:
    global _actor_mapping_tmdb_index_cache
    cache_key = id(records)
    if _actor_mapping_tmdb_index_cache and _actor_mapping_tmdb_index_cache[0] == cache_key:
        return _actor_mapping_tmdb_index_cache[1]
    index: dict[str, dict] = {}
    for record in records:
        tmdb_id = str(record.get("tmdb_id") or "").strip()
        if tmdb_id and tmdb_id not in index:
            index[tmdb_id] = record
    _actor_mapping_tmdb_index_cache = (cache_key, index)
    return index


def _mapping_match_record(match: dict | None) -> dict | None:
    if not match:
        return None
    return match.get("record") if isinstance(match.get("record"), dict) else match


def _should_reject_actor_mapping_match(actor: dict, record: dict, match: dict | None) -> bool:
    if not match or match.get("source") != "alias":
        return False
    if record.get("verified"):
        return False
    actor_tmdb = str(actor.get("tmdb_id") or "").strip()
    mapping_tmdb = str(record.get("tmdb_id") or "").strip()
    return not (actor_tmdb and mapping_tmdb and actor_tmdb == mapping_tmdb)


def _actor_mapping_warning_reason(actor: dict, record: dict, match: dict | None, ignored_ghost_ids: set[str]) -> str | None:
    actor_id = str(actor.get("id") or "").strip()
    if actor_id in ignored_ghost_ids:
        return "ignored_person"
    if _should_reject_actor_mapping_match(actor, record, match):
        return "tmdb_conflict_alias"
    return None


def _provider_id(provider_ids: dict, *keys: str) -> str | None:
    if not isinstance(provider_ids, dict):
        return None
    wanted = {key.lower() for key in keys}
    for key, value in provider_ids.items():
        if str(key).lower() in wanted and str(value or "").strip():
            return str(value).strip()
    return None


def _tmdb_credentials(config: dict) -> tuple[str, str]:
    api_key = str(config.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY") or "").strip()
    api_token = str(config.get("tmdb_api_token") or os.environ.get("TMDB_API_TOKEN") or "").strip()
    return api_key, api_token


def _tmdb_request_params(config: dict, params: dict | None = None) -> dict:
    api_key, api_token = _tmdb_credentials(config)
    if not api_key and not api_token:
        raise HTTPException(status_code=400, detail="TMDB API Key 未配置，请在系统设置中填写 TMDB API Key")
    next_params = dict(params or {})
    if api_key and not api_token:
        next_params["api_key"] = api_key
    return next_params


def _tmdb_headers(config: dict) -> dict:
    _api_key, api_token = _tmdb_credentials(config)
    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    return headers


def _tmdb_lang_candidates(lang: str | None) -> list[str]:
    normalized = str(lang or "").replace("_", "-")
    out: list[str] = []
    if normalized:
        out.append(normalized)
    if normalized.lower().startswith("zh"):
        out.extend(["zh-CN", "zh-TW", "ja-JP", "en-US"])
    elif normalized.lower().startswith("ja"):
        out.extend(["ja-JP", "zh-CN", "en-US"])
    else:
        out.extend(["en-US", "ja-JP", "zh-CN"])
    seen: set[str] = set()
    return [item for item in out if item and not (item in seen or seen.add(item))]


async def _tmdb_get_json(client: httpx.AsyncClient, config: dict, path: str, *, params: dict | None = None) -> dict:
    resp = await client.get(
        f"https://api.themoviedb.org/3{path}",
        headers=_tmdb_headers(config),
        params=_tmdb_request_params(config, params),
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}


def _tmdb_profile_url(profile_path: str | None) -> str:
    path = str(profile_path or "").strip()
    if not path:
        return ""
    return f"https://image.tmdb.org/t/p/original{path if path.startswith('/') else '/' + path}"


def _tmdb_external_urls(external_ids: dict, tmdb_id: str | None = None) -> dict[str, str]:
    urls: dict[str, str] = {}
    if tmdb_id:
        urls["tmdb"] = f"https://www.themoviedb.org/person/{quote(str(tmdb_id), safe='')}"
    imdb_id = str(external_ids.get("imdb_id") or "").strip()
    if imdb_id:
        urls["imdb"] = f"https://www.imdb.com/name/{quote(imdb_id, safe='')}/"
    twitter_id = str(external_ids.get("twitter_id") or "").strip().lstrip("@")
    if twitter_id:
        urls["x"] = f"https://x.com/{quote(twitter_id, safe='')}"
    instagram_id = str(external_ids.get("instagram_id") or "").strip().lstrip("@")
    if instagram_id:
        urls["instagram"] = f"https://www.instagram.com/{quote(instagram_id, safe='')}/"
    tiktok_id = str(external_ids.get("tiktok_id") or "").strip().lstrip("@")
    if tiktok_id:
        urls["tiktok"] = f"https://www.tiktok.com/@{quote(tiktok_id, safe='')}"
    youtube_id = str(external_ids.get("youtube_id") or "").strip()
    if youtube_id:
        urls["youtube"] = f"https://www.youtube.com/{quote(youtube_id, safe='')}"
    wikidata_id = str(external_ids.get("wikidata_id") or "").strip()
    if wikidata_id:
        urls["wikidata"] = f"https://www.wikidata.org/wiki/{quote(wikidata_id, safe='')}"
    facebook_id = str(external_ids.get("facebook_id") or "").strip()
    if facebook_id:
        urls["facebook"] = f"https://www.facebook.com/{quote(facebook_id, safe='')}"
    return urls


def _clean_text_lines(value: str | None) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    lines = []
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines).strip()


def _overview_external_urls(value: str | None) -> tuple[str, dict[str, str]]:
    text = _clean_text_lines(value)
    if not text:
        return "", {}
    urls: dict[str, str] = {}
    kept: list[str] = []
    label_map = {
        "twitter": "x",
        "x": "x",
        "instagram": "instagram",
        "ins": "instagram",
        "tiktok": "tiktok",
        "youtube": "youtube",
        "facebook": "facebook",
        "fanza": "fanza",
        "dmm": "fanza",
        "tmdb": "tmdb",
        "imdb": "imdb",
        "homepage": "homepage",
        "official": "homepage",
        "主页": "homepage",
        "官网": "homepage",
    }
    url_pattern = re.compile(r"https?://[^\s<>\"]+")
    for line in text.splitlines():
        lowered = line.lower()
        found = url_pattern.findall(line)
        is_link_line = bool(found) or "外部链接" in line or set(line) <= {"=", "-", " "}
        if found:
            key = ""
            for label, mapped in label_map.items():
                if label in lowered:
                    key = mapped
                    break
            for idx, url in enumerate(found):
                clean_url = url.rstrip("。.,，；;)")
                next_key = key or "homepage"
                if next_key in urls and urls[next_key] != clean_url:
                    suffix = 2
                    while f"{next_key}_{suffix}" in urls:
                        suffix += 1
                    next_key = f"{next_key}_{suffix}"
                urls[next_key] = clean_url
        if not is_link_line:
            kept.append(line)
    return "\n".join(kept).strip(), urls


def _merge_external_urls(*items: dict | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip()
            if not clean_key or not clean_value:
                continue
            if clean_key not in merged:
                merged[clean_key] = clean_value
                continue
            if merged[clean_key] == clean_value:
                continue
            suffix = 2
            while f"{clean_key}_{suffix}" in merged:
                suffix += 1
            merged[f"{clean_key}_{suffix}"] = clean_value
    return merged


def _translation_name_map(person: dict) -> dict[str, str]:
    translations = ((person.get("translations") or {}).get("translations") or person.get("translations", {}).get("data") or [])
    if not isinstance(translations, list):
        return {}
    names: dict[str, str] = {}
    for item in translations:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        name = str(data.get("name") or "").strip()
        if not name:
            continue
        iso = str(item.get("iso_639_1") or "").lower()
        country = str(item.get("iso_3166_1") or "").upper()
        key = f"{iso}-{country}" if country else iso
        if key:
            names[key] = name
        if iso:
            names.setdefault(iso, name)
    return names


def _tmdb_identity_names(person: dict) -> dict:
    translated = _translation_name_map(person)
    jp = translated.get("ja-JP") or translated.get("ja") or ""
    zh_cn = (
        translated.get("zh-CN")
        or translated.get("zh-HANS")
        or translated.get("zh-SG")
        or translated.get("zh")
        or ""
    )
    zh_tw = (
        translated.get("zh-TW")
        or translated.get("zh-HK")
        or translated.get("zh-HANT")
        or ""
    )
    aliases: list[str] = []
    raw_aliases = person.get("also_known_as") if isinstance(person.get("also_known_as"), list) else []
    for name in [person.get("name"), *raw_aliases]:
        text = str(name or "").strip()
        if text and text not in {jp, zh_cn, zh_tw} and text not in aliases:
            aliases.append(text)
    return {"jp": jp, "zh_cn": zh_cn, "zh_tw": zh_tw, "aliases": aliases}


def _tmdb_gender_label(value: object) -> str:
    try:
        gender = int(value or 0)
    except Exception:
        gender = 0
    return {1: "female", 2: "male", 3: "non-binary"}.get(gender, "")


def _tmdb_pick_biography(person: dict, lang: str | None = None) -> str:
    biography = str(person.get("biography") or "").strip()
    if biography:
        return biography
    translations = ((person.get("translations") or {}).get("translations") or person.get("translations", {}).get("data") or [])
    if not isinstance(translations, list):
        return ""
    by_lang: dict[str, str] = {}
    for item in translations:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        bio = str(data.get("biography") or "").strip()
        if not bio:
            continue
        iso = str(item.get("iso_639_1") or "").lower()
        country = str(item.get("iso_3166_1") or "").upper()
        by_lang[f"{iso}-{country}"] = bio
        by_lang.setdefault(iso, bio)
    for candidate in _tmdb_lang_candidates(lang):
        key = candidate.lower()
        if key in by_lang:
            return by_lang[key]
        short = key.split("-", 1)[0]
        if short in by_lang:
            return by_lang[short]
    return next(iter(by_lang.values()), "")


async def _tmdb_person_payload(config: dict, actor: dict, *, lang: str | None = None) -> dict:
    tmdb_id = str(actor.get("tmdb_id") or "").strip()
    imdb_id = str(actor.get("imdb_id") or "").strip()
    async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
        if not tmdb_id and imdb_id:
            found = await _tmdb_get_json(
                client,
                config,
                f"/find/{quote(imdb_id, safe='')}",
                params={"external_source": "imdb_id", "language": _tmdb_lang_candidates(lang)[0]},
            )
            people = found.get("person_results") if isinstance(found.get("person_results"), list) else []
            if people:
                tmdb_id = str(people[0].get("id") or "").strip()
        if not tmdb_id:
            raise HTTPException(status_code=400, detail="该演员没有 TMDB ID，且无法通过 IMDB ID 反查")
        person = await _tmdb_get_json(
            client,
            config,
            f"/person/{quote(tmdb_id, safe='')}",
            params={"language": _tmdb_lang_candidates(lang)[0], "append_to_response": "external_ids,translations,images"},
        )
    external_ids = person.get("external_ids") if isinstance(person.get("external_ids"), dict) else {}
    profile_url = _tmdb_profile_url(person.get("profile_path"))
    proposal_provider_ids = dict(actor.get("provider_ids") or {})
    proposal_provider_ids["Tmdb"] = str(person.get("id") or tmdb_id)
    if external_ids.get("imdb_id"):
        proposal_provider_ids["Imdb"] = str(external_ids.get("imdb_id"))
    if external_ids.get("twitter_id"):
        proposal_provider_ids["Twitter"] = str(external_ids.get("twitter_id")).lstrip("@")
    if external_ids.get("instagram_id"):
        proposal_provider_ids["Instagram"] = str(external_ids.get("instagram_id")).lstrip("@")
    if external_ids.get("tiktok_id"):
        proposal_provider_ids["TikTok"] = str(external_ids.get("tiktok_id")).lstrip("@")
    if external_ids.get("youtube_id"):
        proposal_provider_ids["YouTube"] = str(external_ids.get("youtube_id"))
    if external_ids.get("wikidata_id"):
        proposal_provider_ids["Wikidata"] = str(external_ids.get("wikidata_id"))
    if external_ids.get("facebook_id"):
        proposal_provider_ids["Facebook"] = str(external_ids.get("facebook_id"))
    tmdb_id_final = str(person.get("id") or tmdb_id)
    external_urls = _tmdb_external_urls(external_ids, tmdb_id_final)
    homepage = str(person.get("homepage") or "").strip()
    if homepage:
        external_urls["homepage"] = homepage
    biography, biography_links = _overview_external_urls(_tmdb_pick_biography(person, lang=lang))
    external_urls = _merge_external_urls(external_urls, biography_links)
    identity_names = _tmdb_identity_names(person)
    return {
        "name": str(person.get("name") or "").strip(),
        "sort_name": str(person.get("name") or "").strip(),
        "overview": biography,
        "provider_ids": proposal_provider_ids,
        "tmdb_id": tmdb_id_final,
        "imdb_id": str(external_ids.get("imdb_id") or actor.get("imdb_id") or ""),
        "jp_name": identity_names.get("jp") or "",
        "zh_cn_name": identity_names.get("zh_cn") or "",
        "zh_tw_name": identity_names.get("zh_tw") or "",
        "aliases": identity_names.get("aliases") or [],
        "image_url": profile_url,
        "birthday": person.get("birthday") or "",
        "deathday": person.get("deathday") or "",
        "place_of_birth": person.get("place_of_birth") or "",
        "known_for_department": person.get("known_for_department") or "",
        "gender": _tmdb_gender_label(person.get("gender")),
        "popularity": person.get("popularity"),
        "adult": bool(person.get("adult")),
        "homepage": homepage,
        "also_known_as": person.get("also_known_as") if isinstance(person.get("also_known_as"), list) else [],
        "external_urls": external_urls,
        "source": "tmdb",
    }


def _actor_metadata_diff(current: dict, proposal: dict) -> list[dict]:
    fields = [
        ("name", "名称"),
        ("sort_name", "排序名"),
        ("overview", "简介"),
        ("birthday", "出生日期"),
        ("deathday", "去世日期"),
        ("place_of_birth", "出生地"),
        ("gender", "性别"),
        ("known_for_department", "领域"),
        ("homepage", "主页"),
        ("tmdb_id", "TMDB"),
        ("imdb_id", "IMDB"),
        ("image_url", "头像"),
    ]
    diffs = []
    for key, label in fields:
        old = str(current.get(key) or "").strip()
        new = str(proposal.get(key) or "").strip()
        if old != new and new:
            diffs.append({"field": key, "label": label, "current": old, "proposed": new})
    return diffs


async def _preview_actor_tmdb_metadata(config: dict, actor_id: str, *, lang: str | None = None) -> dict:
    actor = await _get_actor_profile(config, actor_id, lang=lang)
    proposal = await _tmdb_person_payload(config, actor, lang=lang)
    return {"ok": True, "current": actor, "proposal": proposal, "diffs": _actor_metadata_diff(actor, proposal)}


async def _apply_actor_tmdb_metadata(config: dict, actor_id: str, req: ActorTmdbApplyRequest, *, lang: str | None = None) -> dict:
    preview = await _preview_actor_tmdb_metadata(config, actor_id, lang=lang)
    current = preview["current"]
    proposal = preview["proposal"]
    current_overview, current_overview_links = _overview_external_urls(current.get("overview"))
    next_external_urls = _merge_external_urls(current.get("external_urls") or {}, current_overview_links, proposal.get("external_urls") or {})
    update_req = ActorProfileUpdateRequest(
        name=proposal.get("name") if req.apply_name else current.get("name"),
        sort_name=proposal.get("sort_name") if req.apply_name else current.get("sort_name"),
        jp_name=proposal.get("jp_name") or None,
        zh_cn_name=proposal.get("zh_cn_name") or None,
        zh_tw_name=proposal.get("zh_tw_name") or None,
        aliases=proposal.get("aliases") or None,
        overview=proposal.get("overview") if req.apply_overview else current_overview,
        provider_ids=proposal.get("provider_ids") if req.apply_provider_ids else current.get("provider_ids"),
        birthday=proposal.get("birthday"),
        deathday=proposal.get("deathday"),
        place_of_birth=proposal.get("place_of_birth"),
        gender=proposal.get("gender"),
        known_for_department=proposal.get("known_for_department"),
        popularity=proposal.get("popularity"),
        homepage=proposal.get("homepage"),
        external_urls=next_external_urls,
    )
    result = await _update_actor_profile(config, actor_id, update_req, lang=lang)
    avatar_result = None
    avatar_sync_error = None
    if req.apply_avatar and proposal.get("image_url"):
        try:
            avatar_result = await _set_actor_avatar_from_url(config, actor_id, proposal["image_url"], lang=lang)
            result["actor"] = avatar_result.get("actor") or result.get("actor")
        except Exception as exc:
            avatar_sync_error = str(exc)
            _save_actor_avatar_override_url(actor_id, proposal["image_url"])
            result["actor"] = await _get_actor_profile(config, actor_id, lang=lang)
    return {
        "ok": True,
        **result,
        "preview": preview,
        "avatar_synced": bool(avatar_result),
        "avatar_sync_error": avatar_sync_error,
    }


def _localized_mapping_name(record: dict | None, fallback: str, lang: str | None = None) -> str:
    if not record:
        return fallback
    normalized_lang = str(lang or "").lower()
    if normalized_lang in {"zh-tw", "zh_hant", "zht", "tw"}:
        return str(record.get("zh_tw") or record.get("zh_cn") or record.get("jp") or fallback)
    if normalized_lang.startswith("zh") or normalized_lang in {"cn", "zh-cn"}:
        return str(record.get("zh_cn") or record.get("zh_tw") or record.get("jp") or fallback)
    return str(record.get("jp") or record.get("zh_cn") or record.get("zh_tw") or fallback)


def _actor_identity_names(actor: dict, record: dict | None, *, lang: str | None = None) -> dict:
    override = actor.get("identity_names") if isinstance(actor.get("identity_names"), dict) else {}
    aliases = override.get("aliases") if isinstance(override.get("aliases"), list) else None
    names = {
        "emby_name": actor.get("name") or "",
        "emby_sort_name": actor.get("sort_name") or actor.get("name") or "",
        "jp": override.get("jp") or (record.get("jp") if record else "") or "",
        "zh_cn": override.get("zh_cn") or (record.get("zh_cn") if record else "") or "",
        "zh_tw": override.get("zh_tw") or (record.get("zh_tw") if record else "") or "",
        "aliases": aliases if aliases is not None else ((record.get("aliases") or []) if record else []),
        "source": "noor" if override else ("mapping" if record else "emby"),
    }
    fallback = str(actor.get("display_name") or actor.get("name") or "")
    names["selected_lang"] = lang or ""
    names["selected_name"] = _localized_mapping_name(
        {"jp": names["jp"], "zh_cn": names["zh_cn"], "zh_tw": names["zh_tw"]},
        fallback,
        lang,
    )
    return names


def _enrich_actor_display_names(actors: list[dict], *, lang: str | None = None) -> list[dict]:
    records = _load_actor_mapping_records()
    if not records:
        return [{**actor, "display_name": actor.get("name") or ""} for actor in actors]
    name_index = _actor_mapping_name_index(records)
    out: list[dict] = []
    for actor in actors:
        name = str(actor.get("name") or "")
        match = name_index.get(_normalize_actor_key(name))
        record = _mapping_match_record(match)
        if record and _should_reject_actor_mapping_match(actor, record, match):
            record = None
        identity_names = _actor_identity_names(actor, record, lang=lang)
        out.append({
            **actor,
            "display_name": identity_names.get("selected_name") or _localized_mapping_name(record, name, lang),
            "mapping_id": record.get("id") if record else None,
            "mapping_tmdb_id": record.get("tmdb_id") if record else None,
            "identity_names": identity_names,
        })
    return out


def _actor_merge_score(actor: dict, mapping_tmdb_id: str) -> tuple[int, int, int, int, str]:
    tmdb_id = str(actor.get("tmdb_id") or "")
    return (
        int(actor.get("related_movie_count") or 0),
        1 if mapping_tmdb_id and tmdb_id == mapping_tmdb_id else 0,
        1 if actor.get("image_url") else 0,
        1 if actor.get("overview") else 0,
        str(actor.get("name") or ""),
    )


def _normalize_actor_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).translate(str.maketrans({
        "菫": "堇",
    }))
    return re.sub(r"[\s\u3000・·._\-]+", "", normalized).lower()


def _actor_emby_aliases(actor: dict) -> set[str]:
    aliases: set[str] = set()
    provider_ids = actor.get("provider_ids") if isinstance(actor.get("provider_ids"), dict) else {}
    for value in provider_ids.values():
        text = str(value or "").strip()
        if not text:
            continue
        if "?" in text:
            alias = text.rsplit("?", 1)[-1].strip()
            if alias:
                aliases.add(alias)
    overview = str(actor.get("overview") or "")
    for alias in re.findall(r"[（(]([^()（）]{2,40})[）)]", overview):
        alias = alias.strip()
        if alias:
            aliases.add(alias)
    aliases.discard(str(actor.get("name") or "").strip())
    return aliases


def _person_image_url(config: dict, person: dict) -> str | None:
    person_id = person.get("Id")
    if not person_id:
        return None
    tag = person.get("PrimaryImageTag") or (person.get("ImageTags") or {}).get("Primary")
    if not tag:
        return None
    return f"{_server_url(config)}/emby/Items/{person_id}/Images/Primary?tag={tag}"


def _external_urls_from_provider_ids(provider_ids: dict) -> dict[str, str]:
    urls: dict[str, str] = {}
    tmdb_id = _provider_id(provider_ids, "Tmdb", "TMDB", "tmdb")
    imdb_id = _provider_id(provider_ids, "Imdb", "IMDB", "imdb")
    twitter_id = _provider_id(provider_ids, "Twitter", "twitter", "X", "x")
    instagram_id = _provider_id(provider_ids, "Instagram", "instagram")
    tiktok_id = _provider_id(provider_ids, "TikTok", "Tiktok", "tiktok")
    youtube_id = _provider_id(provider_ids, "YouTube", "Youtube", "youtube")
    wikidata_id = _provider_id(provider_ids, "Wikidata", "wikidata")
    facebook_id = _provider_id(provider_ids, "Facebook", "facebook")
    homepage = _provider_id(provider_ids, "Homepage", "homepage", "OfficialSite", "Official Website")
    if tmdb_id:
        urls["tmdb"] = f"https://www.themoviedb.org/person/{quote(tmdb_id, safe='')}"
    if imdb_id:
        urls["imdb"] = f"https://www.imdb.com/name/{quote(imdb_id, safe='')}/"
    if twitter_id:
        urls["x"] = f"https://x.com/{quote(str(twitter_id).lstrip('@'), safe='')}"
    if instagram_id:
        urls["instagram"] = f"https://www.instagram.com/{quote(str(instagram_id).lstrip('@'), safe='')}/"
    if tiktok_id:
        urls["tiktok"] = f"https://www.tiktok.com/@{quote(str(tiktok_id).lstrip('@'), safe='')}"
    if youtube_id:
        urls["youtube"] = f"https://www.youtube.com/{quote(youtube_id, safe='')}"
    if wikidata_id:
        urls["wikidata"] = f"https://www.wikidata.org/wiki/{quote(wikidata_id, safe='')}"
    if facebook_id:
        urls["facebook"] = f"https://www.facebook.com/{quote(facebook_id, safe='')}"
    if homepage:
        urls["homepage"] = homepage if str(homepage).startswith(("http://", "https://")) else f"https://{homepage}"
    return urls


def _parse_person(config: dict, person: dict) -> dict:
    provider_ids = person.get("ProviderIds") if isinstance(person.get("ProviderIds"), dict) else {}
    item_counts = person.get("ItemCounts") if isinstance(person.get("ItemCounts"), dict) else {}
    movie_count = person.get("MovieCount") or item_counts.get("Movie") or item_counts.get("Movies")
    production_locations = person.get("ProductionLocations")
    return {
        "id": person.get("Id"),
        "server_id": person.get("ServerId") or "",
        "name": person.get("Name") or "Unknown",
        "sort_name": person.get("SortName") or person.get("Name") or "",
        "overview": person.get("Overview") or "",
        "image_url": _person_image_url(config, person),
        "provider_ids": provider_ids,
        "tmdb_id": _provider_id(provider_ids, "Tmdb", "TMDB", "tmdb"),
        "imdb_id": _provider_id(provider_ids, "Imdb", "IMDB", "imdb"),
        "movie_count": movie_count,
        "premiere_date": person.get("PremiereDate"),
        "birthday": person.get("PremiereDate"),
        "deathday": person.get("EndDate"),
        "place_of_birth": (
            ", ".join(str(item) for item in production_locations if str(item).strip())
            if isinstance(production_locations, list)
            else person.get("PlaceOfBirth") or person.get("BirthPlace") or ""
        ),
        "gender": person.get("Gender") or "",
        "known_for_department": person.get("KnownForDepartment") or "",
        "popularity": person.get("Popularity"),
        "homepage": person.get("Homepage") or "",
        "external_urls": _external_urls_from_provider_ids(provider_ids),
        "date_created": person.get("DateCreated"),
    }


def _apply_actor_profile_override(actor: dict, override: dict | None) -> dict:
    if not isinstance(override, dict):
        return actor
    next_actor = dict(actor)
    for key, actor_key in (
        ("name", "name"),
        ("sort_name", "sort_name"),
        ("overview", "overview"),
        ("birthday", "birthday"),
        ("deathday", "deathday"),
        ("place_of_birth", "place_of_birth"),
        ("gender", "gender"),
        ("known_for_department", "known_for_department"),
        ("popularity", "popularity"),
        ("homepage", "homepage"),
    ):
        if key in override and override.get(key) is not None:
            next_actor[actor_key] = override.get(key)
    if override.get("image_url"):
        next_actor["image_url"] = override.get("image_url")
    if isinstance(override.get("external_urls"), dict):
        external_urls = dict(next_actor.get("external_urls") or {})
        external_urls.update({str(k): str(v) for k, v in override["external_urls"].items() if str(v).strip()})
        next_actor["external_urls"] = external_urls
    if isinstance(override.get("provider_ids"), dict):
        provider_ids = dict(next_actor.get("provider_ids") or {})
        for key, value in override["provider_ids"].items():
            key = str(key)
            text = str(value or "").strip()
            if text:
                provider_ids[key] = text
                continue
            for existing_key in list(provider_ids.keys()):
                if existing_key.lower() == key.lower():
                    provider_ids.pop(existing_key, None)
        next_actor["provider_ids"] = provider_ids
        next_actor["tmdb_id"] = _provider_id(provider_ids, "Tmdb", "TMDB", "tmdb")
        next_actor["imdb_id"] = _provider_id(provider_ids, "Imdb", "IMDB", "imdb")
        next_actor["external_urls"] = {**_external_urls_from_provider_ids(provider_ids), **(next_actor.get("external_urls") or {})}
    if isinstance(override.get("identity_names"), dict):
        next_actor["identity_names"] = dict(override.get("identity_names") or {})
    return next_actor


async def _media_server_info(config: dict, client: httpx.AsyncClient | None = None) -> dict:
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0, trust_env=False)
        close_client = True
    try:
        data = await _emby_get_json(client, config, "/System/Info")
        product = str(data.get("ProductName") or data.get("ServerName") or "Emby / Jellyfin")
        lowered = product.lower()
        kind = "jellyfin" if "jellyfin" in lowered else "emby"
        return {
            "kind": kind,
            "name": "Jellyfin" if kind == "jellyfin" else "Emby",
            "server_name": data.get("ServerName") or "",
            "version": data.get("Version") or "",
        }
    except Exception:
        return {"kind": "emby", "name": "Emby / Jellyfin", "server_name": "", "version": ""}
    finally:
        if close_client:
            await client.aclose()


async def _get_actor_profile(config: dict, actor_id: str, *, lang: str | None = None) -> dict:
    user_id = str(config.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Emby 未配置用户 ID，无法读取演员详情")
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        data = await _emby_get_json(
            client,
            config,
            f"/Users/{quote(user_id, safe='')}/Items/{quote(str(actor_id), safe='')}",
            params={"Fields": "ProviderIds,Overview,PrimaryImageAspectRatio,ImageTags,DateCreated,SortName,PremiereDate,EndDate,ProductionLocations,Gender,KnownForDepartment,Homepage,Popularity"},
        )
        media_server = await _media_server_info(config, client)
    actor = _parse_person(config, data)
    actor["emby_url"] = _actor_web_url(config, actor.get("id"), actor.get("server_id"))
    actor["media_server"] = media_server
    actor = _apply_actor_profile_override(actor, _load_actor_profile_overrides().get(str(actor_id)))
    return _enrich_actor_display_names([actor], lang=lang)[0]


async def _update_actor_profile(config: dict, actor_id: str, req: ActorProfileUpdateRequest, *, lang: str | None = None) -> dict:
    user_id = str(config.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Emby 未配置用户 ID，无法保存演员详情")
    actor_id = str(actor_id)
    overrides = _load_actor_profile_overrides()
    current_override = dict(overrides.get(actor_id) or {})
    for key, value in {
        "name": req.name,
        "sort_name": req.sort_name,
        "overview": req.overview,
        "provider_ids": req.provider_ids,
        "birthday": req.birthday,
        "deathday": req.deathday,
        "place_of_birth": req.place_of_birth,
        "gender": req.gender,
        "known_for_department": req.known_for_department,
        "popularity": req.popularity,
        "homepage": req.homepage,
        "external_urls": req.external_urls,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }.items():
        if value is not None:
            current_override[key] = value
    identity_names = dict(current_override.get("identity_names") or {})
    for key, value in {
        "jp": req.jp_name,
        "zh_cn": req.zh_cn_name,
        "zh_tw": req.zh_tw_name,
    }.items():
        if value is not None:
            identity_names[key] = str(value or "").strip()
    if req.aliases is not None:
        identity_names["aliases"] = [str(alias).strip() for alias in req.aliases if str(alias).strip()]
    if identity_names:
        current_override["identity_names"] = identity_names
    overrides[actor_id] = current_override
    _save_actor_profile_overrides(overrides)

    synced = False
    sync_error = None
    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            item = await _emby_get_json(
                client,
                config,
                f"/Users/{quote(user_id, safe='')}/Items/{quote(actor_id, safe='')}",
                params={"Fields": "ProviderIds,Overview,ImageTags,SortName,DateCreated,PremiereDate,EndDate,ProductionLocations,Gender,KnownForDepartment,Homepage,Popularity"},
            )
            if req.name is not None:
                item["Name"] = req.name
            if req.sort_name is not None:
                item["SortName"] = req.sort_name
            if req.overview is not None:
                item["Overview"] = req.overview
            if req.birthday is not None:
                item["PremiereDate"] = req.birthday
            if req.deathday is not None:
                item["EndDate"] = req.deathday
            if req.place_of_birth is not None:
                item["ProductionLocations"] = [req.place_of_birth] if str(req.place_of_birth).strip() else []
            if req.gender is not None:
                item["Gender"] = req.gender
            if req.known_for_department is not None:
                item["KnownForDepartment"] = req.known_for_department
            if req.homepage is not None:
                item["Homepage"] = req.homepage
            if req.provider_ids is not None:
                provider_ids = dict(item.get("ProviderIds") or {})
                for key, value in req.provider_ids.items():
                    key = str(key)
                    text = str(value or "").strip()
                    if text:
                        provider_ids[key] = text
                        continue
                    for existing_key in list(provider_ids.keys()):
                        if existing_key.lower() == key.lower():
                            provider_ids.pop(existing_key, None)
                item["ProviderIds"] = provider_ids
            resp = await client.post(
                f"{_server_url(config)}/emby/Items/{quote(actor_id, safe='')}",
                headers={**_headers(config.get("api_key", "")), "Content-Type": "application/json"},
                json=item,
            )
            resp.raise_for_status()
            synced = True
    except Exception as exc:
        sync_error = str(exc)
    actor = await _get_actor_profile(config, actor_id, lang=lang)
    return {"ok": True, "actor": actor, "synced": synced, "sync_error": sync_error}


async def _set_actor_avatar_bytes(
    config: dict,
    actor_id: str,
    content: bytes,
    *,
    content_type: str = "image/jpeg",
    lang: str | None = None,
) -> dict:
    if not content:
        raise HTTPException(status_code=400, detail="头像文件为空")
    safe_id = quote(str(actor_id), safe="")
    body = base64.b64encode(content)
    async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
        headers = {**_headers(config.get("api_key", "")), "Content-Type": content_type or "image/jpeg"}
        resp = await client.post(f"{_server_url(config)}/emby/Items/{safe_id}/Images/Primary", headers=headers, content=body)
        if resp.status_code in {404, 405}:
            resp = await client.put(f"{_server_url(config)}/emby/Items/{safe_id}/Images/Primary", headers=headers, content=body)
        resp.raise_for_status()
    overrides = _load_actor_profile_overrides()
    current_override = dict(overrides.get(str(actor_id)) or {})
    current_override["image_url"] = f"{_server_url(config)}/emby/Items/{safe_id}/Images/Primary?ts={int(time.time())}"
    current_override["updated_at"] = datetime.now(timezone.utc).isoformat()
    overrides[str(actor_id)] = current_override
    _save_actor_profile_overrides(overrides)
    actor = await _get_actor_profile(config, actor_id, lang=lang)
    return {"ok": True, "actor": actor}


def _save_actor_avatar_override_url(actor_id: str, image_url: str) -> None:
    image_url = str(image_url or "").strip()
    if not image_url:
        return
    overrides = _load_actor_profile_overrides()
    current_override = dict(overrides.get(str(actor_id)) or {})
    current_override["image_url"] = image_url
    current_override["updated_at"] = datetime.now(timezone.utc).isoformat()
    overrides[str(actor_id)] = current_override
    _save_actor_profile_overrides(overrides)


async def _set_actor_avatar_from_url(config: dict, actor_id: str, url: str, *, lang: str | None = None) -> dict:
    source_url = str(url or "").strip()
    if not source_url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="头像 URL 必须是 http 或 https 地址")
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, trust_env=False) as client:
        resp = await client.get(source_url, headers={"Accept": "image/*,*/*;q=0.8", "User-Agent": "NOOR/actor-avatar"})
        resp.raise_for_status()
        content_type = str(resp.headers.get("content-type") or "image/jpeg").split(";", 1)[0].strip()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="URL 返回的不是图片")
        content = resp.content
    return await _set_actor_avatar_bytes(config, actor_id, content, content_type=content_type, lang=lang)


async def _delete_actor_profile(config: dict, actor_id: str) -> dict:
    actor_id = str(actor_id)
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        related = await _emby_related_movies_for_actor(client, config, actor_id, limit=1)
        await _emby_delete_item(client, config, actor_id)
        if await _emby_item_exists(client, config, actor_id):
            raise RuntimeError("Emby 删除接口返回成功，但该演员仍可通过用户 Items 查询到")
    ignored = _load_actor_merge_ignored_ghosts()
    ignored.add(actor_id)
    _save_actor_merge_ignored_ghosts(ignored)
    overrides = _load_actor_profile_overrides()
    overrides.pop(actor_id, None)
    _save_actor_profile_overrides(overrides)
    return {"ok": True, "actor_id": actor_id, "had_related_movies": bool(related)}


def _actor_web_url(config: dict, actor_id: str | None, server_id: str | None = None) -> str | None:
    if not actor_id:
        return None
    url = f"{_server_url(config)}/web/index.html#!/item?id={quote(str(actor_id), safe='')}"
    if server_id:
        url += f"&serverId={quote(str(server_id), safe='')}"
    return url


def _bump_sync_state(*, webhook: bool = False) -> dict:
    global _sync_version, _last_invalidated_at, _last_webhook_at
    _items_cache.clear()
    now = time.time()
    _sync_version += 1
    _last_invalidated_at = now
    if webhook:
        _last_webhook_at = now
    return _sync_state_payload()


def _iso_from_ts(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _sync_state_payload() -> dict:
    return {
        "version": _sync_version,
        "last_invalidated_at": _iso_from_ts(_last_invalidated_at),
        "last_webhook_at": _iso_from_ts(_last_webhook_at),
        "cache_keys": sorted(_items_cache.keys()),
    }


def _ensure_webhook_token(config: dict) -> dict:
    token = str(config.get("webhook_token") or "").strip()
    if token:
        return config
    next_config = dict(config)
    next_config["webhook_token"] = secrets.token_urlsafe(24)
    _save_config(next_config)
    return _load_config()


def _request_source_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _allowed_scan_roots(config: dict) -> tuple[list[Path], list[Path]]:
    source_roots: list[Path] = []
    hardlink_roots: list[Path] = []
    for group in config.get("scan_groups", []) or []:
        source_dir = group.get("source_dir")
        hardlink_dir = group.get("hardlink_dir")
        if source_dir:
            source_roots.append(Path(source_dir).resolve())
        if hardlink_dir:
            hardlink_roots.append(Path(hardlink_dir).resolve())
    return source_roots, hardlink_roots


def _is_under_roots(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        if path == root or root in path.parents:
            return True
    return False


def _assert_safe_path(path: Path, roots: list[Path], *, label: str) -> None:
    if not roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")
    if not _is_under_roots(path, roots):
        raise HTTPException(status_code=400, detail=f"{label} 不在允许的扫描路径内: {path}")


def _remove_file_and_sibling_nfo(path: Path, *, remove_nfo: bool) -> list[str]:
    deleted: list[str] = []
    if path.is_file():
        path.unlink()
        deleted.append(str(path))
    if remove_nfo:
        sibling_nfo = path.with_suffix(".nfo")
        if sibling_nfo.is_file():
            sibling_nfo.unlink()
            deleted.append(str(sibling_nfo))
    return deleted


def _normalize_code_token(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())




def _directory_matches_target_videos(dir_path: Path, target_files: set[Path]) -> bool:
    if not dir_path.is_dir() or not target_files:
        return False

    target_in_dir = {path.resolve() for path in target_files if path.parent == dir_path}
    if not target_in_dir:
        return False

    try:
        video_files: set[Path] = set()
        for child in dir_path.rglob("*"):
            if not child.is_file() or child.suffix.lower() not in VIDEO_EXTS:
                continue
            video_files.add(child.resolve())
    except OSError:
        return False

    return bool(video_files) and video_files == target_in_dir

def _parent_is_code_bucket(file_path: Path, code: str | None) -> bool:
    if not code:
        return False
    code_token = _normalize_code_token(code)
    if not code_token:
        return False
    parent_token = _normalize_code_token(file_path.parent.name)
    return bool(parent_token) and code_token in parent_token


def _collect_chain_delete_targets(
    source_path: Path | None,
    hardlink_paths: list[Path],
    *,
    code: str | None,
    source_roots: list[Path],
    hardlink_roots: list[Path],
) -> tuple[set[Path], set[Path]]:
    delete_dirs: set[Path] = set()
    delete_files: set[Path] = set()
    protected_roots = set(source_roots + hardlink_roots)

    if source_path:
        if _parent_is_code_bucket(source_path, code) and _directory_matches_target_videos(source_path.parent, {source_path}):
            if source_path.parent in protected_roots:
                raise HTTPException(status_code=400, detail=f"禁止删除扫描根目录: {source_path.parent}")
            delete_dirs.add(source_path.parent)
        else:
            delete_files.add(source_path)

    hardlink_targets = set(hardlink_paths)
    for hardlink_path in hardlink_paths:
        if _parent_is_code_bucket(hardlink_path, code) and _directory_matches_target_videos(hardlink_path.parent, hardlink_targets):
            if hardlink_path.parent in protected_roots:
                raise HTTPException(status_code=400, detail=f"禁止删除扫描根目录: {hardlink_path.parent}")
            delete_dirs.add(hardlink_path.parent)
        else:
            delete_files.add(hardlink_path)

    for d in list(delete_dirs):
        delete_files = {f for f in delete_files if d not in f.parents}

    return delete_dirs, delete_files


def _execute_delete_targets(
    delete_dirs: set[Path],
    delete_files: set[Path],
) -> dict:
    deleted_dirs: list[str] = []
    missing_dirs: list[str] = []
    deleted_files: list[str] = []
    missing_files: list[str] = []
    errors: list[str] = []

    for target_dir in sorted(delete_dirs, key=lambda p: len(p.parts), reverse=True):
        if not target_dir.exists():
            missing_dirs.append(str(target_dir))
            continue
        try:
            shutil.rmtree(target_dir)
            deleted_dirs.append(str(target_dir))
        except Exception as e:
            errors.append(f"{target_dir}: {e}")

    for target_file in sorted(delete_files):
        if not target_file.exists():
            missing_files.append(str(target_file))
            continue
        try:
            deleted_files.extend(_remove_file_and_sibling_nfo(target_file, remove_nfo=True))
        except Exception as e:
            errors.append(f"{target_file}: {e}")

    if errors:
        raise HTTPException(status_code=500, detail=f"部分删除失败: {'; '.join(errors)}")

    if not deleted_dirs and not deleted_files and (missing_dirs or missing_files):
        raise HTTPException(status_code=404, detail="目标不存在")

    return {
        "deleted_dirs": deleted_dirs,
        "missing_dirs": missing_dirs,
        "deleted_files": deleted_files,
        "missing_files": missing_files,
    }


def _preview_delete_targets(
    delete_dirs: set[Path],
    delete_files: set[Path],
) -> dict:
    planned_dirs = sorted(str(p) for p in delete_dirs)
    planned_files: list[str] = []
    for file_path in sorted(delete_files):
        planned_files.append(str(file_path))
        nfo_path = file_path.with_suffix(".nfo")
        if nfo_path.exists():
            planned_files.append(str(nfo_path))
    return {
        "planned_dirs": planned_dirs,
        "planned_files": planned_files,
    }


def _path_matches_hardlink_entry(target: Path, entry: dict) -> bool:
    try:
        resolved = target.resolve()
    except Exception:
        resolved = target
    source_path = entry.get("source_path")
    if source_path:
        try:
            if Path(source_path).resolve() == resolved:
                return True
        except Exception:
            pass
    for hardlink_path in entry.get("hardlink_paths") or []:
        try:
            if Path(hardlink_path).resolve() == resolved:
                return True
        except Exception:
            continue
    return False


def _delete_plan_from_hardlink_entry(
    entry: dict,
    *,
    code: str | None,
    source_roots: list[Path],
    hardlink_roots: list[Path],
) -> tuple[set[Path], set[Path]]:
    source_path = Path(entry["source_path"]).resolve() if entry.get("source_path") else None
    if source_path:
        _assert_safe_path(source_path, source_roots + hardlink_roots, label="主文件路径")

    hardlink_paths: list[Path] = []
    for hardlink_path in entry.get("hardlink_paths") or []:
        p = Path(hardlink_path).resolve()
        _assert_safe_path(p, source_roots + hardlink_roots, label="硬链接路径")
        hardlink_paths.append(p)

    return _collect_chain_delete_targets(
        source_path,
        hardlink_paths,
        code=code,
        source_roots=source_roots,
        hardlink_roots=hardlink_roots,
    )


def _find_inode_chain_for_path(target: Path, roots: list[Path]) -> list[Path]:
    try:
        target_stat = target.stat()
    except OSError:
        return []
    inode_key = (target_stat.st_ino, target_stat.st_dev)
    matches: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            walker = os.walk(root)
            for dirpath, _dirnames, filenames in walker:
                for filename in filenames:
                    if Path(filename).suffix.lower() not in VIDEO_EXTS:
                        continue
                    path = Path(dirpath) / filename
                    try:
                        st = path.stat()
                    except (OSError, PermissionError):
                        continue
                    if (st.st_ino, st.st_dev) != inode_key:
                        continue
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        matches.append(resolved)
        except (OSError, PermissionError):
            continue
    return matches


def _delete_plan_from_inode_chain(
    target: Path,
    *,
    code: str | None,
    source_roots: list[Path],
    hardlink_roots: list[Path],
) -> tuple[set[Path], set[Path]]:
    roots = source_roots + hardlink_roots
    matches = _find_inode_chain_for_path(target, roots)
    if not matches:
        return set(), {target}

    source_path = next((path for path in matches if _is_under_roots(path, source_roots)), None)
    if source_path is None and _is_under_roots(target, source_roots):
        source_path = target
    hardlink_paths = [path for path in matches if path != source_path]

    return _collect_chain_delete_targets(
        source_path,
        hardlink_paths,
        code=code,
        source_roots=source_roots,
        hardlink_roots=hardlink_roots,
    )


async def _media_item_delete_plan(item_id: str, config: dict) -> tuple[str, set[Path], set[Path]]:
    try:
        raw = await _get_item(config, item_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取媒体项目失败: {exc}") from exc
    if not raw:
        raise HTTPException(status_code=404, detail=f"未找到媒体项目: {item_id}")

    file_path = str(raw.get("file_path") or "").strip()
    if not file_path:
        raise HTTPException(status_code=400, detail="媒体项目没有可删除的文件路径")

    source_roots, hardlink_roots = _allowed_scan_roots(config)
    if not source_roots and not hardlink_roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")

    target = Path(file_path).resolve()
    _assert_safe_path(target, source_roots + hardlink_roots, label="媒体文件路径")

    groups = _enrich_hardlink_groups(_load_hardlink_groups()).get("groups") or []
    for group in groups:
        for entry in group.get("entries") or []:
            if not _path_matches_hardlink_entry(target, entry):
                continue
            delete_dirs, delete_files = _delete_plan_from_hardlink_entry(
                entry,
                code=group.get("code") or _extract_code_from_path(str(target)),
                source_roots=source_roots,
                hardlink_roots=hardlink_roots,
            )
            return str(group.get("code") or raw.get("name") or target.name), delete_dirs, delete_files

    # Fallback for files not present in the hardlink index: delete only the
    # indexed entry by scanning same-inode files under configured roots. The
    # collect step still decides whether parent directories are safe to remove.
    delete_dirs, delete_files = _delete_plan_from_inode_chain(
        target,
        code=_extract_code_from_path(str(target)),
        source_roots=source_roots,
        hardlink_roots=hardlink_roots,
    )
    return str(raw.get("name") or target.name), delete_dirs, delete_files



# ─── Emby connection test ──────────────────────────────────────────────────────

async def _test_connection(config: dict) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_server_url(config)}/emby/System/Info",
                headers=_headers(config.get("api_key", "")),
            )
            if resp.status_code == 401:
                return False, "API Key 无效或已过期"
            resp.raise_for_status()
            data = resp.json()
            return True, f"已连接至 {data.get('ServerName', 'Emby/Jellyfin')}"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return False, "API Key 无效或已过期"
        return False, f"连接失败: HTTP {e.response.status_code}"
    except Exception as e:
        return False, f"连接失败: {e}"


# ─── Libraries ─────────────────────────────────────────────────────────────────

async def _list_libraries(config: dict) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_server_url(config)}/emby/Library/MediaFolders",
            headers=_headers(config.get("api_key", "")),
        )
        resp.raise_for_status()
        data = resp.json()
    libraries = []
    for item in data.get("Items", []):
        item_type = item.get("Type")
        collection_type = item.get("CollectionType")
        if item_type in ("movies", "tvshows") or collection_type in ("movies", "tvshows"):
            poster_url = None
            if item.get("ImageTags"):
                tag = item["ImageTags"].get("Primary")
                if tag:
                    poster_url = f"{_server_url(config)}/emby/Items/{item['Id']}/Images/Primary?tag={tag}"
            libraries.append({
                "id": item["Id"],
                "name": item["Name"],
                "type": collection_type or item_type or "unknown",
                "poster_url": poster_url,
            })
    return libraries


_VARIANT_MARKER_RE = re.compile(r'(^|[-_.\s])(restored-u|u\d*|c\d*|chs|cht|cn|tw|zh|字幕|中文|破解|流出|uncensored|leaked)(?=$|[-_.\s])', re.IGNORECASE)


def _item_variant_penalty(item: dict) -> int:
    path = (item.get("path") or "").lower()
    name = (item.get("name") or "").lower()
    tags = item.get("tags", {}) or {}
    penalty = 0

    basename = os.path.splitext(os.path.basename(path))[0] if path else name
    if _VARIANT_MARKER_RE.search(basename):
        penalty += 60
    if '.restored-u' in path:
        penalty += 120
    if tags.get('is_cracked'):
        penalty += 40
    if tags.get('is_leaked'):
        penalty += 20
    if tags.get('has_chinese'):
        penalty += 5
    return penalty


def _merge_group_metadata(representative: dict, group: list[dict]) -> dict:
    merged = dict(representative)
    merged_tags = dict((representative.get('tags') or {}))

    if any((item.get('tags') or {}).get('is_cracked') for item in group):
        merged_tags['is_cracked'] = True
    if any((item.get('tags') or {}).get('is_uncensored') for item in group):
        merged_tags['is_uncensored'] = True
    if any((item.get('tags') or {}).get('has_chinese') for item in group):
        merged_tags['has_chinese'] = True
    if any((item.get('tags') or {}).get('has_facefusion') for item in group):
        merged_tags['has_facefusion'] = True
    if any((item.get('tags') or {}).get('is_leaked') for item in group):
        merged_tags['is_leaked'] = True

    release_type_key = None
    if any((item.get('tags') or {}).get('release_type_key') == 'leaked' for item in group):
        release_type_key = 'leaked'
    elif any((item.get('tags') or {}).get('release_type_key') == 'uncensored' for item in group):
        release_type_key = 'uncensored'

    if release_type_key == 'leaked':
        merged_tags['release_type_key'] = 'leaked'
        merged_tags['release_type'] = '流出'
    elif release_type_key == 'uncensored':
        merged_tags['release_type_key'] = 'uncensored'
        merged_tags['release_type'] = '无码'

    merged['tags'] = merged_tags
    merged['subtitle_count'] = max((item.get('subtitle_count') or 0) for item in group)
    merged['variant_count'] = len(group)
    return merged


def _pick_group_representative(group: list[dict]) -> dict:
    def sort_key(item: dict) -> tuple:
        path = item.get('path') or ''
        name = item.get('name') or ''
        return (
            bool(path),
            -_item_variant_penalty(item),
            bool(item.get('poster_path')),
            -(len(os.path.basename(path)) if path else len(name)),
            name,
        )

    representative = dict(max(group, key=sort_key))
    if not representative.get('poster_path'):
        fallback = next((item.get('poster_path') for item in group if item.get('poster_path')), None)
        if fallback:
            representative['poster_path'] = fallback
    return _merge_group_metadata(representative, group)


def _deduplicate_items(items: list[dict]) -> list[dict]:
    """Merge items in the same folder (e.g. MIDA-368.mp4 and MIDA-368.restored-u.mp4).
    Groups by parent folder and keeps the main version (most complete metadata) for list display.
    All versions are still available as siblings in the detail endpoint.
    """
    groups: dict[str, list[dict]] = {}
    result: list[dict] = []

    for item in items:
        path = item.get("path", "")
        if not path:
            result.append(item)
            continue
        folder = os.path.dirname(path)
        if folder not in groups:
            groups[folder] = []
        groups[folder].append(item)

    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            result.append(_pick_group_representative(group))
    return result


async def _list_items(
    config: dict,
    library_id: str,
    limit: int = 50,
    offset: int = 0,
    filter: str | None = None,
    q: str | None = None,
    force_refresh: bool = False,
) -> tuple[list[dict], int]:
    now = time.time()
    cache_key = library_id

    if not force_refresh and cache_key in _items_cache:
        cached_items, cached_at = _items_cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            return _apply_filter_and_paginate(cached_items, filter, q, offset, limit)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{_server_url(config)}/emby/Items",
            headers=_headers(config.get("api_key", "")),
            params={
                "ParentId": library_id,
                "Fields": "PrimaryImageAspectRatio,MediaSources,DateCreated,Path,Studios",
                "Limit": 2000,
                "StartIndex": 0,
                "Recursive": "true",
                "SortBy": "DateCreated",
                "SortOrder": "Descending",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    all_items = []
    for item in data.get("Items", []):
        if item.get("Type") != "Movie" and item.get("MediaType") != "Video":
            continue
        all_items.append(_parse_item(item, config))

    all_items = _deduplicate_items(all_items)

    _items_cache[cache_key] = (all_items, now)
    return _apply_filter_and_paginate(all_items, filter, q, offset, limit)




async def _list_actors(
    config: dict,
    *,
    limit: int = 60,
    offset: int = 0,
    q: str | None = None,
    sort_by: str = "SortName",
    sort_order: str = "Ascending",
    lang: str | None = None,
    include_ignored: bool = False,
) -> tuple[list[dict], int]:
    params = {
        "Limit": max(1, min(limit, 5000)),
        "StartIndex": max(0, offset),
        "SortBy": sort_by if sort_by in {"SortName", "Name", "DateCreated"} else "SortName",
        "SortOrder": sort_order if sort_order in {"Ascending", "Descending"} else "Ascending",
        "Fields": "ProviderIds,Overview,PrimaryImageAspectRatio,ImageTags,DateCreated,SortName",
    }
    if q and q.strip():
        params["SearchTerm"] = q.strip()

    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        resp = await client.get(
            f"{_server_url(config)}/emby/Persons",
            headers=_headers(config.get("api_key", "")),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    overrides = _load_actor_profile_overrides()
    actors = [
        _apply_actor_profile_override(_parse_person(config, item), overrides.get(str(item.get("Id") or "")))
        for item in data.get("Items", [])
        if include_ignored or str(item.get("Id") or "") not in ignored_ghost_ids
    ]
    for actor in actors:
        actor["emby_url"] = _actor_web_url(config, actor.get("id"), actor.get("server_id"))
    actors = _enrich_actor_display_names(actors, lang=lang)
    raw_total = int(data.get("TotalRecordCount") or len(actors))
    removed_count = 0 if include_ignored else len(data.get("Items", [])) - len(actors)
    return actors, max(0, raw_total - removed_count)


async def _detect_duplicate_actors(config: dict, *, limit: int = 2000) -> list[dict]:
    actors, _total = await _list_actors(
        config,
        limit=max(1, min(limit, 5000)),
        offset=0,
        sort_by="SortName",
        sort_order="Ascending",
    )
    groups: dict[str, list[dict]] = {}
    for actor in actors:
        key = _normalize_actor_key(actor.get("name"))
        if not key:
            continue
        groups.setdefault(key, []).append(actor)

    duplicate_groups = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        duplicate_groups.append({
            "key": key,
            "name": members[0].get("name") or key,
            "count": len(members),
            "actors": members,
            "tmdb_ids": sorted({str(actor.get("tmdb_id")) for actor in members if actor.get("tmdb_id")}),
        })

    duplicate_groups.sort(key=lambda item: (-item["count"], item["name"]))
    return duplicate_groups


async def _preview_actor_mapping_matches(
    config: dict,
    *,
    limit: int = 5000,
    only_candidates: bool = False,
    lang: str | None = None,
) -> dict:
    mapping_records = _load_actor_mapping_records()
    if not mapping_records:
        return {
            "groups": [],
            "total_groups": 0,
            "candidate_groups": 0,
            "matched_actors": 0,
            "unmatched_actors": 0,
            "rejected_actors": 0,
            "rejected_matches": [],
            "mapping_records": 0,
        }

    name_index = _actor_mapping_name_index(mapping_records)
    tmdb_index = _actor_mapping_tmdb_index(mapping_records)
    actors, total = await _list_actors(
        config,
        limit=max(1, min(limit, 5000)),
        offset=0,
        sort_by="SortName",
        sort_order="Ascending",
        lang=lang,
        include_ignored=True,
    )
    groups_by_mapping: dict[str, dict] = {}
    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    active_actors = [actor for actor in actors if str(actor.get("id") or "").strip() not in ignored_ghost_ids]
    unmatched = []
    rejected = []
    actors_by_key = {
        _normalize_actor_key(str(actor.get("name") or "")): actor
        for actor in active_actors
        if _normalize_actor_key(str(actor.get("name") or ""))
    }
    for actor in actors:
        actor_id = str(actor.get("id") or "")
        actor_name = str(actor.get("name") or "").strip()
        key = _normalize_actor_key(actor_name)
        match = name_index.get(key)
        record = _mapping_match_record(match)
        if not record:
            actor_tmdb = str(actor.get("tmdb_id") or "").strip()
            record = tmdb_index.get(actor_tmdb)
            if record:
                match = {"record": record, "name": actor_tmdb, "source": "tmdb"}
        if not record:
            unmatched.append(actor)
            continue
        if actor_id in ignored_ghost_ids:
            rejected.append({
                "actor": actor,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "record": record,
                "mapping_id": record.get("id") or key,
                "mapping_name": _localized_mapping_name(record, actor_name, lang),
                "reason": "ignored_person",
            })
            continue
        record_id = str(record.get("id") or key)
        group = groups_by_mapping.get(record_id)
        if not group:
            group = {
                "mapping_id": record_id,
                "canonical_name": record.get("jp") or record.get("zh_cn") or record.get("zh_tw") or actor_name,
                "display_name": _localized_mapping_name(record, actor_name, lang),
                "jp": record.get("jp") or "",
                "zh_cn": record.get("zh_cn") or "",
                "zh_tw": record.get("zh_tw") or "",
                "tmdb_id": record.get("tmdb_id") or "",
                "verified": bool(record.get("verified")),
                "names": record.get("names") or [],
                "actors": [],
            }
            groups_by_mapping[record_id] = group
        next_actor = dict(actor)
        next_actor["matched_name"] = actor_name
        warning_reason = _actor_mapping_warning_reason(actor, record, match, ignored_ghost_ids)
        if warning_reason:
            next_actor["mapping_warning_reason"] = warning_reason
        group["actors"].append(next_actor)

    matched_actor_ids = {str(actor.get("id") or "") for group in groups_by_mapping.values() for actor in group.get("actors") or []}
    supplemental_groups: dict[str, dict] = {}
    for actor in active_actors:
        actor_id = str(actor.get("id") or "")
        if actor_id in matched_actor_ids:
            continue
        actor_name = str(actor.get("name") or "").strip()
        members = [actor]
        member_ids = {actor_id}
        matched_aliases = []
        for alias in _actor_emby_aliases(actor):
            alias_key = _normalize_actor_key(alias)
            other = actors_by_key.get(alias_key)
            other_id = str(other.get("id") or "") if other else ""
            if other and other_id and other_id != actor_id and other_id not in member_ids:
                members.append(other)
                member_ids.add(other_id)
                matched_aliases.append(alias)
        if len(members) < 2:
            continue
        group_key = "|".join(sorted(member_ids))
        if group_key in supplemental_groups:
            continue
        display_name = actor.get("display_name") or actor_name
        supplemental_groups[group_key] = {
            "mapping_id": f"emby-alias:{_normalize_actor_key(actor_name) or actor_id}",
            "canonical_name": actor_name,
            "display_name": display_name,
            "jp": actor_name,
            "zh_cn": display_name,
            "zh_tw": display_name,
            "tmdb_id": actor.get("tmdb_id") or "",
            "verified": False,
            "names": [actor_name, *matched_aliases],
            "actors": [{**member, "matched_name": member.get("name") or ""} for member in members],
            "match_source": "emby_alias",
        }
    groups_by_mapping.update({group["mapping_id"]: group for group in supplemental_groups.values()})

    groups = list(groups_by_mapping.values())
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        for group in groups:
            actors_in_group = group.get("actors") or []
            ignored_actor_ids = {
                str(actor.get("id") or "").strip()
                for actor in actors_in_group
                if str(actor.get("id") or "").strip() in ignored_ghost_ids
            }
            if len(actors_in_group) < 2 and not ignored_actor_ids:
                continue
            mapping_tmdb_id = str(group.get("tmdb_id") or "")
            for actor in actors_in_group:
                actor_id = str(actor.get("id") or "").strip()
                related_count = 0
                if actor_id and (len(actors_in_group) > 1 or actor_id in ignored_actor_ids):
                    related_limit = 5000 if len(actors_in_group) > 1 else 1
                    related_count = len(await _emby_related_movies_for_actor(client, config, actor_id, limit=related_limit))
                actor["related_movie_count"] = related_count
            for actor in actors_in_group:
                actor_id = str(actor.get("id") or "").strip()
                related_count = int(actor.get("related_movie_count") or 0)
                if actor_id in ignored_ghost_ids:
                    actor["mapping_warning_reason"] = (
                        "ignored_empty_non_target_person"
                        if related_count == 0
                        else "ignored_person"
                    )
    for group in groups:
        group["count"] = len(group["actors"])
        group["needs_merge"] = len(group["actors"]) > 1
        mapping_tmdb_id = str(group.get("tmdb_id") or "")
        target_actor = None
        if group["actors"]:
            target_actor = max(group["actors"], key=lambda actor: _actor_merge_score(actor, mapping_tmdb_id))
        tmdb_conflicts = [
            actor for actor in group["actors"]
            if actor.get("tmdb_id") and mapping_tmdb_id and str(actor.get("tmdb_id")) != mapping_tmdb_id
        ]
        group["target_actor_id"] = target_actor.get("id") if target_actor else None
        group["target_actor_name"] = target_actor.get("name") if target_actor else ""
        group["target_actor_display_name"] = target_actor.get("display_name") if target_actor else ""
        group["tmdb_conflicts"] = tmdb_conflicts
        group["has_tmdb_conflict"] = bool(tmdb_conflicts)
        group["missing_tmdb_count"] = sum(1 for actor in group["actors"] if not actor.get("tmdb_id"))
        group["missing_image_count"] = sum(1 for actor in group["actors"] if not actor.get("image_url"))
    if only_candidates:
        groups = [group for group in groups if group["needs_merge"]]
    groups.sort(key=lambda item: (
        -int(item.get("has_tmdb_conflict") or 0),
        -int(item.get("needs_merge") or 0),
        -int(item.get("count") or 0),
        str(item.get("canonical_name") or ""),
    ))
    return {
        "groups": groups,
        "total_groups": len(groups_by_mapping),
        "candidate_groups": sum(1 for group in groups_by_mapping.values() if len(group["actors"]) > 1),
        "conflict_groups": sum(1 for group in groups_by_mapping.values() if group.get("has_tmdb_conflict")),
        "matched_actors": sum(len(group["actors"]) for group in groups_by_mapping.values()),
        "unmatched_actors": len(unmatched),
        "rejected_actors": len(rejected),
        "rejected_matches": rejected,
        "emby_total": total,
        "emby_scanned": len(actors),
        "mapping_records": len(mapping_records),
    }


async def _preview_actor_tmdb_backfill(
    config: dict,
    *,
    limit: int = 5000,
    lang: str | None = None,
) -> dict:
    mapping_records = _load_actor_mapping_records()
    if not mapping_records:
        return {"candidates": [], "summary": {"scanned": 0, "candidate_count": 0, "high_confidence_count": 0, "conflict_count": 0, "mapping_records": 0}}

    name_index = _actor_mapping_name_index(mapping_records)
    actors, _total = await _list_actors(
        config,
        limit=max(1, min(limit, 5000)),
        offset=0,
        sort_by="SortName",
        sort_order="Ascending",
        lang=lang,
        include_ignored=True,
    )
    active_tmdb_owners: dict[str, list[dict]] = {}
    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    for actor in actors:
        tmdb_id = str(actor.get("tmdb_id") or "").strip()
        actor_id = str(actor.get("id") or "").strip()
        if tmdb_id and actor_id not in ignored_ghost_ids:
            active_tmdb_owners.setdefault(tmdb_id, []).append(actor)

    candidates: list[dict] = []
    for actor in actors:
        actor_id = str(actor.get("id") or "").strip()
        if actor.get("tmdb_id"):
            continue
        names = [
            actor.get("name"),
            actor.get("sort_name"),
            (actor.get("identity_names") or {}).get("jp") if isinstance(actor.get("identity_names"), dict) else None,
            (actor.get("identity_names") or {}).get("zh_cn") if isinstance(actor.get("identity_names"), dict) else None,
            (actor.get("identity_names") or {}).get("zh_tw") if isinstance(actor.get("identity_names"), dict) else None,
        ]
        if isinstance((actor.get("identity_names") or {}).get("aliases") if isinstance(actor.get("identity_names"), dict) else None, list):
            names.extend(actor["identity_names"]["aliases"])
        names.extend(_actor_emby_aliases(actor))

        match = None
        matched_name = ""
        for name in names:
            key = _normalize_actor_key(str(name or ""))
            if key and key in name_index:
                match = name_index[key]
                matched_name = str(name or "")
                break
        record = _mapping_match_record(match)
        mapping_tmdb_id = str(record.get("tmdb_id") or "").strip() if record else ""
        if not record or not mapping_tmdb_id:
            continue
        owners = [owner for owner in active_tmdb_owners.get(mapping_tmdb_id, []) if str(owner.get("id") or "") != actor_id]
        confidence = "high" if record.get("verified") and not owners else "review"
        reason = "verified_mapping" if confidence == "high" else ("tmdb_owned_by_other_actor" if owners else "unverified_mapping")
        candidates.append({
            "actor": actor,
            "actor_id": actor_id,
            "actor_name": actor.get("name") or "",
            "display_name": actor.get("display_name") or actor.get("name") or "",
            "matched_name": matched_name,
            "mapping_id": record.get("id"),
            "mapping_name": _localized_mapping_name(record, str(actor.get("name") or ""), lang),
            "tmdb_id": mapping_tmdb_id,
            "verified": bool(record.get("verified")),
            "confidence": confidence,
            "reason": reason,
            "conflict_actors": [{"id": owner.get("id"), "name": owner.get("name"), "display_name": owner.get("display_name")} for owner in owners],
        })

    candidates.sort(key=lambda item: (
        0 if item.get("confidence") == "high" else 1,
        str(item.get("display_name") or item.get("actor_name") or ""),
    ))
    return {
        "candidates": candidates,
        "summary": {
            "scanned": len(actors),
            "candidate_count": len(candidates),
            "high_confidence_count": sum(1 for item in candidates if item.get("confidence") == "high"),
            "conflict_count": sum(1 for item in candidates if item.get("conflict_actors")),
            "mapping_records": len(mapping_records),
        },
    }


async def _apply_actor_tmdb_backfill(
    config: dict,
    req: ActorTmdbBackfillRequest,
    *,
    lang: str | None = None,
) -> dict:
    preview = await _preview_actor_tmdb_backfill(config, lang=lang)
    allowed_ids = {str(actor_id) for actor_id in (req.actor_ids or []) if str(actor_id).strip()}
    applied = []
    skipped = []
    candidates = []
    for item in preview.get("candidates") or []:
        actor_id = str(item.get("actor_id") or "")
        if allowed_ids and actor_id not in allowed_ids:
            continue
        candidates.append(item)
    progress_key = str(req.progress_key or "").strip()
    if progress_key:
        _ACTOR_TMDB_BACKFILL_PROGRESS[progress_key] = {
            "ok": True,
            "status": "running",
            "processed": 0,
            "total": len(candidates),
            "applied_count": 0,
            "skipped_count": 0,
            "current_actor": "",
            "started_at": time.time(),
            "updated_at": time.time(),
        }
    for item in candidates:
        actor_id = str(item.get("actor_id") or "")
        if progress_key:
            _ACTOR_TMDB_BACKFILL_PROGRESS[progress_key].update({
                "current_actor": item.get("display_name") or item.get("actor_name") or actor_id,
                "updated_at": time.time(),
            })
        if req.only_high_confidence and item.get("confidence") != "high":
            skipped.append({**item, "skip_reason": "not_high_confidence"})
        elif item.get("conflict_actors"):
            skipped.append({**item, "skip_reason": "conflict"})
        else:
            if not req.dry_run:
                provider_ids = dict((item.get("actor") or {}).get("provider_ids") or {})
                provider_ids["Tmdb"] = str(item.get("tmdb_id") or "")
                await _update_actor_profile(
                    config,
                    actor_id,
                    ActorProfileUpdateRequest(provider_ids=provider_ids),
                    lang=lang,
                )
            applied.append(item)
        if progress_key:
            _ACTOR_TMDB_BACKFILL_PROGRESS[progress_key].update({
                "processed": len(applied) + len(skipped),
                "applied_count": len(applied),
                "skipped_count": len(skipped),
                "updated_at": time.time(),
            })
    if progress_key:
        _ACTOR_TMDB_BACKFILL_PROGRESS[progress_key].update({
            "status": "completed",
            "current_actor": "",
            "processed": len(applied) + len(skipped),
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "updated_at": time.time(),
        })
    return {
        "ok": True,
        "dry_run": req.dry_run,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
        "summary": preview.get("summary") or {},
    }


def _actor_mapping_record_for_name_sync(actor: dict, records: list[dict], name_index: dict[str, dict]) -> tuple[dict | None, dict | None]:
    names = actor.get("identity_names") if isinstance(actor.get("identity_names"), dict) else {}
    candidates = [
        actor.get("name"),
        actor.get("sort_name"),
        names.get("emby_name") if isinstance(names, dict) else None,
        names.get("emby_sort_name") if isinstance(names, dict) else None,
        *_actor_emby_aliases(actor),
    ]
    seen: set[str] = set()
    for value in candidates:
        key = _normalize_actor_key(str(value or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        match = name_index.get(key)
        record = _mapping_match_record(match)
        if record and not _should_reject_actor_mapping_match(actor, record, match):
            return record, match
    return None, None


def _actor_target_name_for_lang(record: dict | None, lang: str | None) -> tuple[str, str]:
    if not record:
        return "", "missing_mapping"
    lowered = str(lang or "").lower()
    if lowered == "zh-tw" or "hant" in lowered or lowered == "tw":
        candidates = [
            ("zh_tw", str(record.get("zh_tw") or "")),
        ]
    elif lowered.startswith("zh") or lowered == "cn":
        candidates = [
            ("zh_cn", str(record.get("zh_cn") or "")),
        ]
    else:
        candidates = [
            ("jp", str(record.get("jp") or "")),
        ]
    for source, value in candidates:
        text = value.strip()
        if text:
            return text, source
    return "", "missing_mapping_name"


async def _preview_actor_name_sync(config: dict, *, lang: str | None = None, limit: int = 5000) -> dict:
    actors, total = await _list_actors(
        config,
        limit=max(1, min(limit, 5000)),
        offset=0,
        sort_by="SortName",
        sort_order="Ascending",
        lang=lang,
        include_ignored=False,
    )
    raw_name_owner: dict[str, list[dict]] = {}
    candidates: list[dict] = []
    mapping_records = _load_actor_mapping_records()
    mapping_name_index = _actor_mapping_name_index(mapping_records) if mapping_records else {}
    for actor in actors:
        actor_id = str(actor.get("id") or "")
        current_name = str(actor.get("name") or "").strip()
        if current_name:
            raw_name_owner.setdefault(_normalize_actor_key(current_name), []).append(actor)
        mapping_record, mapping_match = _actor_mapping_record_for_name_sync(actor, mapping_records, mapping_name_index)
        target_name, target_source = _actor_target_name_for_lang(mapping_record, lang)
        candidates.append({
            "actor": actor,
            "actor_id": actor_id,
            "current_name": current_name,
            "target_name": target_name,
            "target_source": target_source,
            "mapping_id": mapping_record.get("id") if mapping_record else None,
            "mapping_match_name": mapping_match.get("name") if mapping_match else "",
            "mapping_match_source": mapping_match.get("source") if mapping_match else "",
            "needs_update": bool(target_name and target_name != current_name),
            "conflict_actors": [],
            "has_conflict": False,
        })

    by_target: dict[str, list[dict]] = {}
    for item in candidates:
        key = _normalize_actor_key(item.get("target_name"))
        if key:
            by_target.setdefault(key, []).append(item)

    for item in candidates:
        key = _normalize_actor_key(item.get("target_name"))
        if not key:
            continue
        conflicts: list[dict] = []
        for other in by_target.get(key, []):
            if str(other.get("actor_id") or "") != str(item.get("actor_id") or ""):
                conflicts.append(other.get("actor") or {})
        for owner in raw_name_owner.get(key, []):
            owner_id = str(owner.get("id") or "")
            if owner_id != str(item.get("actor_id") or "") and all(str(conflict.get("id") or "") != owner_id for conflict in conflicts):
                conflicts.append(owner)
        item["conflict_actors"] = [
            {
                "id": actor.get("id"),
                "name": actor.get("name"),
                "display_name": actor.get("display_name"),
                "image_url": actor.get("image_url"),
            }
            for actor in conflicts
        ]
        item["has_conflict"] = bool(conflicts)

    updates = [item for item in candidates if item.get("needs_update")]
    safe_updates = [item for item in updates if not item.get("has_conflict")]
    conflicts = [item for item in updates if item.get("has_conflict")]
    missing = [item for item in candidates if not item.get("target_name")]
    updates.sort(key=lambda item: (
        1 if item.get("has_conflict") else 0,
        str(item.get("target_name") or ""),
        str(item.get("current_name") or ""),
    ))
    return {
        "lang": lang or "",
        "actors_scanned": len(actors),
        "total": total,
        "updates": updates,
        "safe_updates": safe_updates,
        "conflicts": conflicts,
        "missing": missing,
        "summary": {
            "actors_scanned": len(actors),
            "update_count": len(updates),
            "safe_update_count": len(safe_updates),
            "conflict_count": len(conflicts),
            "missing_count": len(missing),
        },
    }


async def _apply_actor_name_sync(
    config: dict,
    req: ActorNameSyncRequest,
    *,
    lang: str | None = None,
) -> dict:
    preview = await _preview_actor_name_sync(config, lang=lang)
    allowed_ids = {str(actor_id) for actor_id in (req.actor_ids or []) if str(actor_id).strip()}
    applied: list[dict] = []
    skipped: list[dict] = []
    candidates = []
    for item in preview.get("updates") or []:
        actor_id = str(item.get("actor_id") or "")
        if allowed_ids and actor_id not in allowed_ids:
            continue
        candidates.append(item)
    progress_key = str(req.progress_key or "").strip()
    if progress_key:
        _ACTOR_NAME_SYNC_PROGRESS[progress_key] = {
            "ok": True,
            "status": "running",
            "processed": 0,
            "total": len(candidates),
            "applied_count": 0,
            "skipped_count": 0,
            "current_actor": "",
            "started_at": time.time(),
            "updated_at": time.time(),
        }
    for item in candidates:
        actor_id = str(item.get("actor_id") or "")
        if progress_key:
            _ACTOR_NAME_SYNC_PROGRESS[progress_key].update({
                "current_actor": item.get("current_name") or actor_id,
                "current_target": item.get("target_name") or "",
                "updated_at": time.time(),
            })
        if item.get("has_conflict") and req.skip_conflicts:
            skipped.append({**item, "skip_reason": "conflict"})
        elif not item.get("target_name"):
            skipped.append({**item, "skip_reason": "missing_target_name"})
        else:
            if not req.dry_run:
                await _update_actor_profile(
                    config,
                    actor_id,
                    ActorProfileUpdateRequest(name=str(item.get("target_name") or "")),
                    lang=lang,
                )
            applied.append(item)
        if progress_key:
            _ACTOR_NAME_SYNC_PROGRESS[progress_key].update({
                "processed": len(applied) + len(skipped),
                "applied_count": len(applied),
                "skipped_count": len(skipped),
                "updated_at": time.time(),
            })
    if progress_key:
        _ACTOR_NAME_SYNC_PROGRESS[progress_key].update({
            "status": "completed",
            "current_actor": "",
            "current_target": "",
            "processed": len(applied) + len(skipped),
            "applied_count": len(applied),
            "skipped_count": len(skipped),
            "updated_at": time.time(),
        })
    return {
        "ok": True,
        "dry_run": req.dry_run,
        "lang": lang or "",
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
        "summary": preview.get("summary") or {},
    }


def _actor_group_target_name(
    group: dict,
    target_name: str | None = None,
    *,
    lang: str | None = None,
    target_actor_id: str | None = None,
) -> str:
    selected_id = str(target_actor_id or "").strip()
    if selected_id:
        for actor in group.get("actors") or []:
            if str(actor.get("id") or "").strip() == selected_id:
                selected_name = str(actor.get("name") or actor.get("display_name") or "").strip()
                if selected_name:
                    return selected_name
    explicit = str(target_name or "").strip()
    if explicit:
        return explicit
    fallback = str(group.get("display_name") or group.get("canonical_name") or group.get("jp") or group.get("zh_cn") or "").strip()
    return _localized_mapping_name(group, fallback, lang).strip()


def _actor_group_source_ids(group: dict, *, target_actor_id: str | None = None) -> list[str]:
    selected_id = str(target_actor_id or "").strip()
    out: list[str] = []
    for actor in group.get("actors") or []:
        actor_id = str(actor.get("id") or "").strip()
        if selected_id and actor_id == selected_id:
            continue
        if actor_id and actor_id not in out:
            out.append(actor_id)
    return out


async def _find_actor_mapping_group(config: dict, mapping_id: str, *, lang: str | None = None) -> dict:
    result = await _preview_actor_mapping_matches(config, limit=5000, only_candidates=False, lang=lang)
    for group in result.get("groups") or []:
        if str(group.get("mapping_id") or "") == str(mapping_id):
            return group
    raise HTTPException(status_code=404, detail=f"未找到映射组: {mapping_id}")


async def _emby_get_json(client: httpx.AsyncClient, config: dict, path: str, *, params: dict | None = None) -> dict:
    resp = await client.get(
        f"{_server_url(config)}/emby{path}",
        headers=_headers(config.get("api_key", "")),
        params=params or {},
    )
    resp.raise_for_status()
    return resp.json()


async def _emby_related_movies_for_actor(client: httpx.AsyncClient, config: dict, actor_id: str, *, limit: int = 5000) -> list[dict]:
    user_id = str(config.get("user_id") or "").strip()
    path = f"/Users/{quote(user_id, safe='')}/Items" if user_id else "/Items"
    data = await _emby_get_json(
        client,
        config,
        path,
        params={
            "PersonIds": actor_id,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
            "Limit": max(1, min(limit, 5000)),
            "Fields": "Path,People,ProviderIds,ImageTags,DateCreated",
        },
    )
    return [item for item in data.get("Items", []) if isinstance(item, dict)]


async def _emby_item_for_update(client: httpx.AsyncClient, config: dict, item_id: str) -> dict:
    user_id = str(config.get("user_id") or "").strip()
    path = f"/Users/{quote(user_id, safe='')}/Items/{quote(str(item_id), safe='')}" if user_id else f"/Items/{quote(str(item_id), safe='')}"
    return await _emby_get_json(
        client,
        config,
        path,
        params={
            "Fields": (
                "Path,People,ProviderIds,Genres,Studios,Tags,Overview,PremiereDate,SortName,"
                "DateCreated,ImageTags,LockedFields,OriginalTitle,ProductionYear,CommunityRating,"
                "CriticRating,OfficialRating,CustomRating,Taglines"
            )
        },
    )


async def _emby_delete_item(client: httpx.AsyncClient, config: dict, item_id: str) -> None:
    safe_id = quote(str(item_id), safe="")
    user_id = str(config.get("user_id") or "").strip()
    headers = _headers(config.get("api_key", ""))
    attempts = [
        ("DELETE", f"{_server_url(config)}/emby/Items/{safe_id}", None),
    ]
    if user_id:
        attempts.append(("DELETE", f"{_server_url(config)}/emby/Users/{quote(user_id, safe='')}/Items/{safe_id}", None))
        attempts.append(("POST", f"{_server_url(config)}/emby/Users/{quote(user_id, safe='')}/Items/Delete", {"Ids": str(item_id)}))
    attempts.append(("POST", f"{_server_url(config)}/emby/Items/Delete", {"Ids": str(item_id)}))

    last_resp: httpx.Response | None = None
    for method, url, params in attempts:
        if method == "DELETE":
            resp = await client.delete(url, headers=headers, params=params)
        else:
            resp = await client.post(url, headers=headers, params=params)
        last_resp = resp
        if resp.status_code not in {404, 405}:
            break
    resp = last_resp
    if resp is None:
        raise RuntimeError("未执行 Emby 删除请求")
    resp.raise_for_status()


async def _emby_item_exists(client: httpx.AsyncClient, config: dict, item_id: str) -> bool:
    safe_id = quote(str(item_id), safe="")
    paths = [f"/Items/{safe_id}"]
    user_id = str(config.get("user_id") or "").strip()
    if user_id:
        paths.append(f"/Users/{quote(user_id, safe='')}/Items/{safe_id}")
    for path in paths:
        resp = await client.get(
            f"{_server_url(config)}/emby{path}",
            headers=_headers(config.get("api_key", "")),
        )
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return True
    return False


async def _emby_optional_item(client: httpx.AsyncClient, config: dict, item_id: str) -> dict | None:
    safe_id = quote(str(item_id), safe="")
    paths = [f"/Items/{safe_id}"]
    user_id = str(config.get("user_id") or "").strip()
    if user_id:
        paths.append(f"/Users/{quote(user_id, safe='')}/Items/{safe_id}")
    for path in paths:
        resp = await client.get(
            f"{_server_url(config)}/emby{path}",
            headers=_headers(config.get("api_key", "")),
            params={"Fields": "Path,ProviderIds,CanDelete,DateCreated,SortName,Overview,People"},
        )
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        return resp.json()
    return None


def _emby_item_diagnostic_brief(item: dict) -> dict:
    provider_ids = item.get("ProviderIds") if isinstance(item.get("ProviderIds"), dict) else {}
    people = item.get("People") if isinstance(item.get("People"), list) else []
    return {
        "id": item.get("Id") or "",
        "name": item.get("Name") or "",
        "type": item.get("Type") or "",
        "path": item.get("Path") or "",
        "can_delete": item.get("CanDelete"),
        "sort_name": item.get("SortName") or "",
        "date_created": item.get("DateCreated") or "",
        "provider_ids": provider_ids,
        "people_count": len(people),
    }


async def _emby_items_for_person(
    client: httpx.AsyncClient,
    config: dict,
    actor_id: str,
    *,
    item_type: str | None = None,
    limit: int = 20,
) -> dict:
    user_id = str(config.get("user_id") or "").strip()
    path = f"/Users/{quote(user_id, safe='')}/Items" if user_id else "/Items"
    params = {
        "PersonIds": actor_id,
        "Recursive": "true",
        "Limit": max(1, min(limit, 100)),
        "Fields": "Path,People,ProviderIds,ImageTags,DateCreated,SortName",
    }
    if item_type:
        params["IncludeItemTypes"] = item_type
    data = await _emby_get_json(client, config, path, params=params)
    items = [item for item in data.get("Items", []) if isinstance(item, dict)]
    return {
        "total": int(data.get("TotalRecordCount") or len(items) or 0),
        "items": [_emby_item_diagnostic_brief(item) for item in items],
    }


async def _diagnose_actor_delete(config: dict, actor_id: str) -> dict:
    actor_id = str(actor_id).strip()
    if not actor_id:
        raise HTTPException(status_code=400, detail="演员 ID 不能为空")
    item_types = [
        "Movie",
        "Series",
        "Episode",
        "MusicVideo",
        "Video",
        "Trailer",
        "BoxSet",
        "Playlist",
    ]
    async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
        person = await _emby_optional_item(client, config, actor_id)
        all_related = await _emby_items_for_person(client, config, actor_id, item_type=None, limit=30)
        by_type: dict[str, dict] = {}
        for item_type in item_types:
            by_type[item_type] = await _emby_items_for_person(client, config, actor_id, item_type=item_type, limit=30)
    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    related_total = int(all_related.get("total") or 0)
    delete_blockers: list[str] = []
    if person and person.get("CanDelete") is False:
        delete_blockers.append("person_can_delete_false")
    if related_total > 0:
        delete_blockers.append("person_still_has_related_items")
    return {
        "ok": True,
        "actor_id": actor_id,
        "person_exists": person is not None,
        "person": _emby_item_diagnostic_brief(person) if person else None,
        "is_ignored_by_noor": actor_id in ignored_ghost_ids,
        "related_total": related_total,
        "all_related": all_related,
        "by_type": by_type,
        "delete_blockers": delete_blockers,
        "can_delete_cleanly": person is None or (person.get("CanDelete") is not False and related_total == 0),
    }


def _actor_merge_apply_people(item: dict, *, source_actor_ids: set[str], target_name: str) -> tuple[dict, list[dict]]:
    people = item.get("People") if isinstance(item.get("People"), list) else []
    has_existing_target = any(
        isinstance(person, dict)
        and str(person.get("Type") or "") == "Actor"
        and str(person.get("Name") or "") == target_name
        and str(person.get("Id") or "") not in source_actor_ids
        for person in people
    )
    next_people: list[dict] = []
    changed_people: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for person in people:
        if not isinstance(person, dict):
            continue
        next_person = dict(person)
        person_type = str(next_person.get("Type") or "")
        person_id = str(next_person.get("Id") or "")
        if person_type == "Actor" and person_id in source_actor_ids:
            changed_people.append({
                "id": person_id,
                "name": next_person.get("Name") or "",
                "type": person_type,
                "primary_image_tag": next_person.get("PrimaryImageTag"),
            })
            if has_existing_target:
                continue
            next_person["Name"] = target_name
            next_person["Type"] = "Actor"
            next_person.pop("Id", None)
            next_person.pop("PrimaryImageTag", None)
        dedupe_key = (str(next_person.get("Type") or ""), str(next_person.get("Name") or ""))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        next_people.append(next_person)
    next_item = dict(item)
    next_item["People"] = next_people
    return next_item, changed_people


def _actor_merge_remove_source_people(item: dict, *, source_actor_ids: set[str]) -> tuple[dict, list[dict]]:
    people = item.get("People") if isinstance(item.get("People"), list) else []
    next_people: list[dict] = []
    removed: list[dict] = []
    for person in people:
        if (
            isinstance(person, dict)
            and str(person.get("Type") or "") == "Actor"
            and str(person.get("Id") or "") in source_actor_ids
        ):
            removed.append({
                "id": person.get("Id"),
                "name": person.get("Name") or "",
                "type": person.get("Type") or "",
                "primary_image_tag": person.get("PrimaryImageTag"),
            })
            continue
        next_people.append(person)
    next_item = dict(item)
    next_item["People"] = next_people
    return next_item, removed


async def _build_actor_mapping_merge_plan(
    config: dict,
    mapping_id: str,
    *,
    target_name: str | None = None,
    target_actor_id: str | None = None,
    lang: str | None = None,
) -> dict:
    group = await _find_actor_mapping_group(config, mapping_id, lang=lang)
    target = _actor_group_target_name(group, target_name, lang=lang, target_actor_id=target_actor_id)
    if not target:
        raise HTTPException(status_code=400, detail="无法确定目标演员名")
    source_ids = _actor_group_source_ids(group, target_actor_id=target_actor_id)
    if target_actor_id:
        if len(source_ids) < 1:
            raise HTTPException(status_code=400, detail="当前映射组没有需要合并到目标的演员")
    elif len(source_ids) < 2:
        raise HTTPException(status_code=400, detail="当前映射组不足两位演员，无需合并")

    movies_by_id: dict[str, dict] = {}
    source_counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
        for actor_id in source_ids:
            related = await _emby_related_movies_for_actor(client, config, actor_id)
            source_counts[actor_id] = len(related)
            for item in related:
                item_id = str(item.get("Id") or "")
                if item_id and item_id not in movies_by_id:
                    movies_by_id[item_id] = item

    source_id_set = set(source_ids)
    movies: list[dict] = []
    for item in movies_by_id.values():
        changed_people = []
        for person in item.get("People") or []:
            if isinstance(person, dict) and str(person.get("Type") or "") == "Actor" and str(person.get("Id") or "") in source_id_set:
                changed_people.append({
                    "id": person.get("Id"),
                    "name": person.get("Name") or "",
                    "type": person.get("Type") or "",
                    "primary_image_tag": person.get("PrimaryImageTag"),
                })
        if changed_people:
            movies.append({
                "id": item.get("Id"),
                "name": item.get("Name") or "",
                "path": item.get("Path") or "",
                "changed_people": changed_people,
                "target_name": target,
            })
    movies.sort(key=lambda item: str(item.get("name") or ""))
    return {
        "mapping_id": mapping_id,
        "target_name": target,
        "target_actor_id": str(target_actor_id or "").strip() or None,
        "group": group,
        "source_actor_ids": source_ids,
        "source_counts": source_counts,
        "empty_source_actor_ids": [actor_id for actor_id in source_ids if source_counts.get(actor_id, 0) == 0],
        "movie_count": len(movies),
        "movies": movies,
    }


async def _execute_actor_mapping_merge(
    config: dict,
    req: ActorMappingMergeRequest,
    *,
    lang: str | None = None,
) -> dict:
    plan = await _build_actor_mapping_merge_plan(
        config,
        req.mapping_id,
        target_name=req.target_name,
        target_actor_id=req.target_actor_id,
        lang=lang,
    )
    source_ids = set(plan["source_actor_ids"])
    target_name = str(plan["target_name"])
    updated: list[dict] = []
    skipped: list[dict] = []
    backups: list[dict] = []
    deleted_actor_ids: list[str] = []
    delete_failed_actor_ids: list[dict] = []

    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        for movie in plan["movies"]:
            item_id = str(movie.get("id") or "")
            if not item_id:
                continue
            item = await _emby_item_for_update(client, config, item_id)
            next_item, changed_people = _actor_merge_apply_people(item, source_actor_ids=source_ids, target_name=target_name)
            if not changed_people:
                skipped.append({"id": item_id, "name": item.get("Name") or "", "reason": "no_matching_people"})
                continue
            backups.append({
                "id": item_id,
                "name": item.get("Name") or "",
                "path": item.get("Path") or "",
                "people": item.get("People") or [],
            })
            if not req.dry_run:
                resp = await client.post(
                    f"{_server_url(config)}/emby/Items/{quote(item_id, safe='')}",
                    headers={**_headers(config.get("api_key", "")), "Content-Type": "application/json"},
                    json=next_item,
                )
                resp.raise_for_status()
                verify_item = await _emby_item_for_update(client, config, item_id)
                cleanup_item, cleanup_people = _actor_merge_remove_source_people(verify_item, source_actor_ids=source_ids)
                if cleanup_people:
                    cleanup_resp = await client.post(
                        f"{_server_url(config)}/emby/Items/{quote(item_id, safe='')}",
                        headers={**_headers(config.get("api_key", "")), "Content-Type": "application/json"},
                        json=cleanup_item,
                    )
                    cleanup_resp.raise_for_status()
                else:
                    cleanup_people = []
            else:
                cleanup_people = []
            updated.append({
                "id": item_id,
                "name": item.get("Name") or "",
                "path": item.get("Path") or "",
                "changed_people": changed_people,
                "cleanup_people": cleanup_people,
                "target_name": target_name,
            })

        before_counts = dict(plan.get("source_counts") or {})
        after_counts = {}
        if not req.dry_run:
            for actor_id in plan["source_actor_ids"]:
                related = await _emby_related_movies_for_actor(client, config, actor_id, limit=5000)
                after_counts[actor_id] = len(related)
                if related:
                    continue
                try:
                    await _emby_delete_item(client, config, actor_id)
                    if await _emby_item_exists(client, config, actor_id):
                        raise RuntimeError("Emby 删除接口返回成功，但该演员仍可通过用户 Items 查询到")
                    deleted_actor_ids.append(actor_id)
                except Exception as exc:
                    delete_failed_actor_ids.append({"id": actor_id, "error": str(exc)})

    if deleted_actor_ids and not req.dry_run:
        ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
        ignored_ghost_ids.update(str(actor_id) for actor_id in deleted_actor_ids)
        _save_actor_merge_ignored_ghosts(ignored_ghost_ids)

    backup_path = None
    if backups and not req.dry_run:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path_obj = _actor_merge_backup_dir() / f"{timestamp}_{_safe_upload_filename(req.mapping_id)}.json"
        backup_path_obj.write_text(
            json.dumps({
                "mapping_id": req.mapping_id,
                "target_name": target_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "backups": backups,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        backup_path = str(backup_path_obj)

    return {
        "ok": True,
        "dry_run": req.dry_run,
        "plan": plan,
        "updated_count": len(updated),
        "updated": updated,
        "skipped": skipped,
        "backup_path": backup_path,
        "after_counts": after_counts,
        "before_counts": before_counts,
        "deleted_actor_ids": deleted_actor_ids,
        "delete_failed_actor_ids": delete_failed_actor_ids,
    }


async def _execute_actor_mapping_merge_batch(
    config: dict,
    req: ActorMappingMergeBatchRequest,
    *,
    lang: str | None = None,
) -> dict:
    preview = await _preview_actor_mapping_matches(config, limit=5000, only_candidates=True, lang=lang)
    groups = preview.get("groups") or []
    results: list[dict] = []
    failures: list[dict] = []
    skipped: list[dict] = []
    updated_count = 0
    deleted_actor_count = 0
    delete_failed_actor_ids: list[dict] = []

    for group in groups:
        mapping_id = str(group.get("mapping_id") or "").strip()
        if not mapping_id:
            continue
        if req.skip_conflicts and group.get("has_tmdb_conflict"):
            skipped.append({"mapping_id": mapping_id, "name": group.get("display_name") or group.get("canonical_name") or "", "reason": "tmdb_conflict"})
            continue
        target_actor_id = str(req.target_actor_ids.get(mapping_id) or group.get("target_actor_id") or "").strip()
        if not target_actor_id:
            skipped.append({"mapping_id": mapping_id, "name": group.get("display_name") or group.get("canonical_name") or "", "reason": "missing_target"})
            continue
        try:
            result = await _execute_actor_mapping_merge(
                config,
                ActorMappingMergeRequest(
                    mapping_id=mapping_id,
                    target_actor_id=target_actor_id,
                    dry_run=req.dry_run,
                ),
                lang=lang,
            )
            results.append(result)
            updated_count += int(result.get("updated_count") or 0)
            deleted_actor_count += len(result.get("deleted_actor_ids") or [])
            delete_failed_actor_ids.extend(result.get("delete_failed_actor_ids") or [])
        except HTTPException as exc:
            failures.append({
                "mapping_id": mapping_id,
                "name": group.get("display_name") or group.get("canonical_name") or "",
                "status_code": exc.status_code,
                "error": exc.detail,
            })
        except Exception as exc:
            failures.append({
                "mapping_id": mapping_id,
                "name": group.get("display_name") or group.get("canonical_name") or "",
                "error": str(exc),
            })

    return {
        "ok": not failures,
        "dry_run": req.dry_run,
        "candidate_count": len(groups),
        "executed_count": len(results),
        "updated_count": updated_count,
        "deleted_actor_count": deleted_actor_count,
        "delete_failed_actor_count": len(delete_failed_actor_ids),
        "delete_failed_actor_ids": delete_failed_actor_ids,
        "skipped_count": len(skipped),
        "failed_count": len(failures),
        "results": results,
        "skipped": skipped,
        "failures": failures,
    }


def _item_matches_query(item: dict, query: str | None) -> bool:
    if not query:
        return True
    q = query.strip().lower()
    if not q:
        return True
    fields = [
        item.get('name'),
        item.get('path'),
        (item.get('nfo') or {}).get('title') if isinstance(item.get('nfo'), dict) else None,
        (item.get('nfo') or {}).get('originaltitle') if isinstance(item.get('nfo'), dict) else None,
        (item.get('nfo') or {}).get('num') if isinstance(item.get('nfo'), dict) else None,
    ]
    haystack = '\n'.join(str(field) for field in fields if field).lower()
    return q in haystack

def _apply_filter_and_paginate(items: list[dict], filter: str | None, q: str | None, offset: int, limit: int) -> tuple[list[dict], int]:
    filtered = []
    for item in items:
        tags = item.get("tags", {})
        matches_filter = not filter
        if filter:
            if not tags:
                matches_filter = False
            elif filter == "cracked":
                matches_filter = bool(tags.get("is_cracked"))
            elif filter == "chinese":
                matches_filter = bool(tags.get("has_chinese"))
            elif filter == "leaked":
                matches_filter = tags.get("release_type_key") == "leaked"
            elif filter == "uncensored":
                matches_filter = tags.get("release_type_key") == "uncensored"
        if matches_filter and _item_matches_query(item, q):
            filtered.append(item)
    return filtered[offset:offset + limit], len(filtered)



async def _get_siblings(config: dict, parent_id: str, current_id: str) -> list[dict]:
    return await get_siblings_impl(
        config,
        parent_id,
        current_id,
        httpx_module=httpx,
        server_url_fn=_server_url,
        headers_fn=_headers,
        map_path_fn=_map_path,
    )


def _get_main_nfo(file_path: str | None) -> str | None:
    return get_main_nfo_impl(file_path)


async def _get_item(config: dict, item_id: str) -> dict | None:
    return await get_item_impl(
        config,
        item_id,
        httpx_module=httpx,
        server_url_fn=_server_url,
        headers_fn=_headers,
        map_path_fn=_map_path,
        parse_tags_fn=_parse_tags,
        get_siblings_fn=_get_siblings,
        get_main_nfo_fn=_get_main_nfo,
    )


# ─── Hardlink group management ─────────────────────────────────────────────────

def _hardlink_groups_path() -> Path:
    return hardlink_groups_path_impl(_config_path)


def _hardlink_groups_last_scanned_at() -> str | None:
    path = _hardlink_groups_path()
    if not path.is_file():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def _scan_inodes(dir_path: str) -> dict[tuple[int, int], str]:
    return scan_inodes_impl(dir_path)


def _scan_single_group(source_dir: str, hardlink_dir: str) -> list[dict]:
    return scan_single_group_impl(source_dir, hardlink_dir, scan_inodes_fn=_scan_inodes)


def _fetch_emby_item_info(config: dict, emby_id: str | None) -> tuple[str | None, str | None]:
    return fetch_emby_item_info_impl(
        config,
        emby_id,
        httpx_module=httpx,
        server_url_fn=_server_url,
        headers_fn=_headers,
    )


def _extract_code_from_path(file_path: str) -> str:
    return extract_code_from_path_impl(file_path)


async def _build_hardlink_groups() -> list[dict]:
    return await build_hardlink_groups_impl(
        _load_config(),
        scan_single_group_fn=_scan_single_group,
        extract_code_from_path_fn=_extract_code_from_path,
    )


def _save_hardlink_groups(groups: list[dict]) -> None:
    save_hardlink_groups_impl(groups, hardlink_groups_path_fn=_hardlink_groups_path)


def _load_hardlink_groups() -> list[dict]:
    return load_hardlink_groups_impl(hardlink_groups_path_fn=_hardlink_groups_path)


def _enrich_hardlink_groups(groups: list[dict]) -> dict:
    return enrich_hardlink_groups_impl(groups)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class MediaAdapterMeta(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str


class MediaLibraryStatus(BaseModel):
    available: bool
    current: MediaAdapterMeta | None
    message: str | None


# ─── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=MediaLibraryStatus)
async def get_status():
    """Get media library adapter status."""
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        return MediaLibraryStatus(
            available=False,
            current=None,
            message=_ADAPTER_NOT_ACTIVATED,
        )
    return MediaLibraryStatus(
        available=True,
        current=MediaAdapterMeta(
            id="emby",
            name="Emby / Jellyfin",
            version="1.0.0",
            description="连接 Emby 或 Jellyfin 媒体服务器",
            author="NOOR",
        ),
        message=None,
    )


@router.get("/config")
async def get_config():
    """Get saved media library configuration."""
    return {"config": _ensure_webhook_token(_load_config())}


@router.post("/config")
async def save_config(config: dict):
    """Partially update media library configuration.
    Only updates the fields provided; all other fields are preserved.
    """
    existing = _load_config()
    existing.update(config)
    _save_config(existing)
    if "mdc_ng_actor_mapping_path" in config:
        try:
            await _sync_actor_mapping_from_mdc_ng(force=False)
        except Exception:
            pass
    state = _bump_sync_state()
    return {"ok": True, "sync_state": state}


@router.get("/sync-state")
async def get_sync_state():
    """Return the media library cache sync state for lightweight polling."""
    return _sync_state_payload()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """Clear NOOR's media library cache without touching Emby."""
    state = _bump_sync_state()
    SystemLogManager.get_instance().add_log(
        "info",
        "[MediaLibrary] 媒体库缓存已手动刷新",
        source="media_library",
    )
    return {"ok": True, "sync_state": state}


@router.post("/webhook/emby")
async def emby_webhook(request: Request, token: str | None = None):
    """Receive Emby webhook notifications and invalidate NOOR media cache."""
    config = _ensure_webhook_token(_load_config())
    expected = str(config.get("webhook_token") or "").strip()
    provided = (token or request.headers.get("X-NOOR-Webhook-Token") or "").strip()
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    event_name = ""
    item_name = ""
    notification_type = ""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip() or "unknown"
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            event_name = str(payload.get("Event") or payload.get("event") or payload.get("NotificationType") or "")
            notification_type = str(payload.get("NotificationType") or payload.get("Type") or payload.get("type") or "")
            item = payload.get("Item") if isinstance(payload.get("Item"), dict) else {}
            item_name = str(item.get("Name") or payload.get("Name") or payload.get("Title") or "")
    except Exception:
        payload = None

    state = _bump_sync_state(webhook=True)
    is_test = any("test" in value.lower() or "测试" in value for value in [event_name, notification_type, item_name])
    source_ip = _request_source_ip(request)
    hint_parts = []
    if is_test:
        hint_parts.append("测试通知")
    if event_name:
        hint_parts.append(f"事件={event_name}")
    if notification_type and notification_type != event_name:
        hint_parts.append(f"类型={notification_type}")
    if item_name:
        hint_parts.append(f"条目={item_name}")
    hint_parts.append(f"内容类型={content_type}")
    hint_parts.append(f"来源={source_ip}")
    hint = " · ".join(hint_parts)
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 收到 Emby Webhook，已刷新媒体库缓存 · {hint}",
        source="media_library.webhook",
    )
    return {"ok": True, "sync_state": state}


@router.post("/test")
async def test_connection(config: dict | None = None):
    """Test connection with provided config. Returns available libraries on success."""
    cfg = config if config is not None else _load_config()
    if not cfg:
        return {"ok": False, "message": _ADAPTER_NOT_ACTIVATED, "libraries": []}
    # Test connection by fetching items (works reliably; MediaFolders may return 502)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_server_url(cfg)}/emby/Items",
                headers=_headers(cfg.get("api_key", "")),
                params={"limit": 1, "Fields": "BasicSyncInfo"},
            )
            resp.raise_for_status()
        # Also try to get libraries
        try:
            libraries = await _list_libraries(cfg)
        except Exception:
            libraries = []
        return {"ok": True, "message": f"已连接至 {cfg.get('server_url', 'Emby/Jellyfin')}", "libraries": libraries}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return {"ok": False, "message": "API Key 无效或已过期", "libraries": []}
        return {"ok": False, "message": f"连接失败: HTTP {e.response.status_code}", "libraries": []}
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {e}", "libraries": []}


@router.get("/libraries")
async def get_libraries():
    """Get list of media libraries."""
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)

    try:
        libraries = await _list_libraries(config)
    except Exception:
        return {"libraries": []}

    return {"libraries": libraries}


@router.get("/items")
async def get_items(
    library_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    filter: str | None = None,
    q: str | None = None,
    force_refresh: bool = Query(False, description="强制刷新缓存"),
):
    """Get items from the media library."""
    import time

    force_refresh = force_refresh if isinstance(force_refresh, bool) else False

    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)

    now = time.time()

    if not library_id:
        raw = config.get("enabled_library_ids", "") if isinstance(config, dict) else ""
        enabled_ids = [lid.strip() for lid in raw.split(",") if lid.strip()] if raw else []

        try:
            all_libraries = await _list_libraries(config)
            target_ids = enabled_ids if enabled_ids else [lib["id"] for lib in all_libraries]

            all_items: list[dict] = []
            for lid in target_ids:
                cache_key = f"all_{lid}"
                if not force_refresh and cache_key in _items_cache:
                    cached, cached_at = _items_cache[cache_key]
                    if now - cached_at < _CACHE_TTL:
                        all_items.extend(cached)
                        continue
                items, _ = await _list_items(config, lid, limit=2000, offset=0, force_refresh=force_refresh)
                _items_cache[cache_key] = (items, now)
                all_items.extend(items)

            all_items.sort(key=lambda x: x.get("date_created") or "", reverse=True)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"获取媒体失败: {e}")

        all_items = [i for i in all_items if _item_matches_filter(i, filter)] if filter else all_items
        all_items = [i for i in all_items if _item_matches_query(i, q)] if q else all_items

        total = len(all_items)
        return {"items": all_items[offset:offset + limit], "total": total}

    cache_key = library_id
    if not force_refresh and cache_key in _items_cache:
        cached_items, cached_at = _items_cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            return _paginate_filter(cached_items, filter, q, offset, limit)

    try:
        all_items, _ = await _list_items(config, library_id, limit=2000, offset=0, force_refresh=force_refresh)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取媒体失败: {e}")

    _items_cache[cache_key] = (all_items, now)
    return _paginate_filter(all_items, filter, q, offset, limit)


def _item_matches_filter(item: dict, filter_str: str) -> bool:
    tags = item.get("tags", {})
    if not tags:
        return False
    if filter_str == "cracked" and tags.get("is_cracked"):
        return True
    if filter_str == "chinese" and tags.get("has_chinese"):
        return True
    if filter_str == "leaked" and tags.get("release_type_key") == "leaked":
        return True
    if filter_str == "uncensored" and tags.get("release_type_key") == "uncensored":
        return True
    return False


def _paginate_filter(all_items: list, filter_str: str | None, q: str | None, offset: int, limit: int):
    filtered = [i for i in all_items if _item_matches_filter(i, filter_str)] if filter_str else list(all_items)
    filtered = [i for i in filtered if _item_matches_query(i, q)] if q else filtered
    total = len(filtered)
    return {"items": filtered[offset:offset + limit], "total": total}


@router.get("/actors")
async def get_actors(
    limit: int = 60,
    offset: int = 0,
    q: str | None = None,
    sort_by: str = "SortName",
    sort_order: str = "Ascending",
    lang: str | None = None,
):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)

    try:
        actors, total = await _list_actors(
            config,
            limit=limit,
            offset=offset,
            q=q,
            sort_by=sort_by,
            sort_order=sort_order,
            lang=lang,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取演员失败: {e}")

    return {"actors": actors, "total": total, "limit": limit, "offset": offset}


@router.get("/actors/duplicates")
async def get_duplicate_actors(limit: int = 2000):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)

    try:
        groups = await _detect_duplicate_actors(config, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"检测重名演员失败: {e}")

    return {"groups": groups, "total": len(groups)}


@router.get("/actor/{actor_id}/movies")
async def get_actor_movies(actor_id: str, limit: int = 120, offset: int = 0):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
            movies = await _emby_related_movies_for_actor(client, config, actor_id, limit=5000)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取演员作品失败: {exc}")
    items = [_parse_item(item, config) for item in movies]
    items = _deduplicate_items(items)
    total = len(items)
    return {"items": items[offset:offset + max(1, min(limit, 500))], "total": total, "limit": limit, "offset": offset}


@router.get("/actor/{actor_id}")
async def get_actor_profile(actor_id: str, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        return {"ok": True, "actor": await _get_actor_profile(config, actor_id, lang=lang)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取演员详情失败: {exc}")


@router.post("/actor/{actor_id}")
async def update_actor_profile(actor_id: str, req: ActorProfileUpdateRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _update_actor_profile(config, actor_id, req, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"保存演员详情失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 演员资料已保存: {actor_id} · Emby 同步 {'成功' if result.get('synced') else '失败'}",
        source="media_library.actors",
    )
    return result


@router.post("/actor/{actor_id}/avatar")
async def upload_actor_avatar(actor_id: str, file: UploadFile = File(...), lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/jpeg"
    if not str(content_type).startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    content = await file.read()
    try:
        result = await _set_actor_avatar_bytes(config, actor_id, content, content_type=content_type, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上传演员头像失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 演员头像已上传: {actor_id}",
        source="media_library.actors",
    )
    _bump_sync_state()
    return result


@router.post("/actor/{actor_id}/avatar-url")
async def set_actor_avatar_from_url(actor_id: str, req: ActorAvatarUrlRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _set_actor_avatar_from_url(config, actor_id, req.url, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"设置演员头像失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 演员头像已从 URL 设置: {actor_id}",
        source="media_library.actors",
    )
    _bump_sync_state()
    return result


@router.post("/actor/{actor_id}/metadata/tmdb-preview")
async def preview_actor_tmdb_metadata(actor_id: str, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        return await _preview_actor_tmdb_metadata(config, actor_id, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"读取 TMDB 演员资料失败: {exc}")


@router.post("/actor/{actor_id}/metadata/tmdb-apply")
async def apply_actor_tmdb_metadata(actor_id: str, req: ActorTmdbApplyRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _apply_actor_tmdb_metadata(config, actor_id, req, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"应用 TMDB 演员资料失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 演员 TMDB 资料已应用: {actor_id}",
        source="media_library.actors",
    )
    _bump_sync_state()
    return result


@router.get("/actor/{actor_id}/delete-diagnostics")
async def diagnose_actor_delete(actor_id: str):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        return await _diagnose_actor_delete(config, actor_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"诊断演员删除失败: {exc}")


@router.delete("/actor/{actor_id}")
async def delete_actor_profile(actor_id: str):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _delete_actor_profile(config, actor_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"删除演员失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "warning",
        f"[MediaLibrary] 演员已删除: {actor_id}",
        source="media_library.actors",
    )
    _bump_sync_state()
    return result


@router.post("/actors/mapping/upload")
async def upload_actor_mapping(file: UploadFile = File(...)):
    filename = _safe_upload_filename(file.filename)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="上传文件超过 30MB")

    upload_dir = _actor_mapping_upload_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = upload_dir / f"{timestamp}_{filename}"
    target.write_bytes(content)
    latest = upload_dir / "latest"
    latest.write_text(str(target), encoding="utf-8")

    file_info = _actor_mapping_upload_info(target, len(content))
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 已上传演员映射表: {filename} · {len(content)} bytes",
        source="media_library.actors",
    )
    return {"ok": True, "file": file_info}


@router.get("/actors/mapping/latest-upload")
async def get_latest_actor_mapping_upload():
    path = _latest_actor_mapping_upload_path()
    if path is None:
        return {"ok": True, "uploaded": False}
    return {"ok": True, "uploaded": True, "file": _actor_mapping_upload_info(path)}


@router.get("/actors/mapping/status")
async def get_actor_mapping_status():
    _maybe_schedule_actor_mapping_auto_update()
    settings = get_settings()
    sync_state = _load_actor_mapping_sync_state()
    return {
        "ok": True,
        **_load_actor_mapping_status(),
        "mdc_ng": {
            "enabled": bool(getattr(settings, "actor_mapping_auto_update", False)),
            "configured_root": str(_configured_mdc_ng_root_path() or ""),
            "relative_path": str(MDC_NG_ACTOR_MAPPING_RELATIVE_PATH),
            "configured_path": str(_configured_mdc_ng_actor_mapping_path()) if _configured_mdc_ng_root_path() is not None else "",
            **sync_state,
        },
        "online": sync_state,
    }


@router.post("/actors/mapping/sync-online")
async def sync_online_actor_mapping():
    try:
        return await _sync_actor_mapping_from_mdc_ng(force=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/actors/mapping/sync-mdc-ng")
async def sync_mdc_ng_actor_mapping():
    try:
        return await _sync_actor_mapping_from_mdc_ng(force=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/actors/mapping")
async def clear_actor_mapping():
    result = _clear_actor_mapping_records()
    SystemLogManager.get_instance().add_log(
        "warning",
        "[MediaLibrary] 演员映射表已清除",
        source="media_library.actors",
    )
    return result


@router.post("/actors/mapping/import-latest")
async def import_latest_actor_mapping():
    path = _latest_actor_mapping_upload_path()
    if path is None:
        raise HTTPException(status_code=400, detail="还没有上传演员映射表")
    if path.suffix.lower() != ".xml":
        raise HTTPException(status_code=400, detail="当前仅支持导入 XML 演员映射表")
    try:
        records, stats = _parse_actor_mapping_xml(path)
        result = _save_actor_mapping_records(records, path, stats)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入演员映射表失败: {exc}")
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 已导入演员映射表: {stats.get('total', 0)} 条 · TMDB {stats.get('with_tmdb', 0)} 条",
        source="media_library.actors",
    )
    return {"ok": True, "mapping": result}


@router.get("/actors/mapping/matches")
async def get_actor_mapping_matches(
    limit: int = 5000,
    only_candidates: bool = Query(False, description="只返回需要合并确认的候选组"),
    lang: str | None = None,
):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _preview_actor_mapping_matches(config, limit=limit, only_candidates=only_candidates, lang=lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"匹配演员映射表失败: {exc}")
    return {"ok": True, **result}


@router.get("/actors/tmdb-backfill/preview")
async def preview_actor_tmdb_backfill(limit: int = 5000, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _preview_actor_tmdb_backfill(config, limit=limit, lang=lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"预览演员 TMDB ID 补全失败: {exc}")
    return {"ok": True, **result}


@router.post("/actors/tmdb-backfill/apply")
async def apply_actor_tmdb_backfill(req: ActorTmdbBackfillRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _apply_actor_tmdb_backfill(config, req, lang=lang)
    except Exception as exc:
        progress_key = str(req.progress_key or "").strip()
        if progress_key:
            _ACTOR_TMDB_BACKFILL_PROGRESS[progress_key] = {
                **_ACTOR_TMDB_BACKFILL_PROGRESS.get(progress_key, {}),
                "ok": False,
                "status": "failed",
                "error": str(exc),
                "updated_at": time.time(),
            }
        raise HTTPException(status_code=502, detail=f"应用演员 TMDB ID 补全失败: {exc}")
    if not req.dry_run:
        _bump_sync_state()
        SystemLogManager.get_instance().add_log(
            "info",
            f"[MediaLibrary] 演员 TMDB ID 补全完成: {result.get('applied_count', 0)} 位",
            source="media_library.actors",
        )
    return result


@router.get("/actors/tmdb-backfill/progress/{progress_key}")
async def get_actor_tmdb_backfill_progress(progress_key: str):
    key = str(progress_key or "").strip()
    progress = _ACTOR_TMDB_BACKFILL_PROGRESS.get(key)
    if not progress:
        return {"ok": True, "status": "idle", "processed": 0, "total": 0, "applied_count": 0, "skipped_count": 0}
    return progress


@router.get("/actors/name-sync/preview")
async def preview_actor_name_sync(lang: str | None = None, limit: int = 5000):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _preview_actor_name_sync(config, lang=lang, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"预览演员名称同步失败: {exc}")
    return {"ok": True, **result}


@router.post("/actors/name-sync/apply")
async def apply_actor_name_sync(req: ActorNameSyncRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _apply_actor_name_sync(config, req, lang=lang)
    except Exception as exc:
        progress_key = str(req.progress_key or "").strip()
        if progress_key:
            _ACTOR_NAME_SYNC_PROGRESS[progress_key] = {
                **_ACTOR_NAME_SYNC_PROGRESS.get(progress_key, {}),
                "ok": False,
                "status": "failed",
                "error": str(exc),
                "updated_at": time.time(),
            }
        raise HTTPException(status_code=502, detail=f"应用演员名称同步失败: {exc}")
    if not req.dry_run:
        _bump_sync_state()
        SystemLogManager.get_instance().add_log(
            "info",
            f"[MediaLibrary] 演员名称同步完成: {result.get('applied_count', 0)} 位 · 跳过 {result.get('skipped_count', 0)} 位",
            source="media_library.actors",
        )
    return result


@router.get("/actors/name-sync/progress/{progress_key}")
async def get_actor_name_sync_progress(progress_key: str):
    key = str(progress_key or "").strip()
    progress = _ACTOR_NAME_SYNC_PROGRESS.get(key)
    if not progress:
        return {"ok": True, "status": "idle", "processed": 0, "total": 0, "applied_count": 0, "skipped_count": 0}
    return progress


@router.get("/actors/mapping/merge-plan")
async def get_actor_mapping_merge_plan(
    mapping_id: str,
    target_name: str | None = None,
    target_actor_id: str | None = None,
    lang: str | None = None,
):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        return {
            "ok": True,
            **await _build_actor_mapping_merge_plan(
                config,
                mapping_id,
                target_name=target_name,
                target_actor_id=target_actor_id,
                lang=lang,
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"生成演员合并计划失败: {exc}")


@router.post("/actors/mapping/merge-execute")
async def execute_actor_mapping_merge(req: ActorMappingMergeRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _execute_actor_mapping_merge(config, req, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"执行演员合并失败: {exc}")
    if not req.dry_run:
        _bump_sync_state()
        SystemLogManager.get_instance().add_log(
            "info",
            (
                f"[MediaLibrary] 演员合并完成: {req.mapping_id} -> {result.get('plan', {}).get('target_name')}"
                f" · {result.get('updated_count', 0)} 部作品"
                f" · 删除空演员 {len(result.get('deleted_actor_ids') or [])} 个"
            ),
            source="media_library.actors",
        )
    return result


@router.post("/actors/mapping/merge-batch")
async def execute_actor_mapping_merge_batch(req: ActorMappingMergeBatchRequest, lang: str | None = None):
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)
    try:
        result = await _execute_actor_mapping_merge_batch(config, req, lang=lang)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"批量执行演员合并失败: {exc}")
    if not req.dry_run:
        _bump_sync_state()
        SystemLogManager.get_instance().add_log(
            "info",
            (
                f"[MediaLibrary] 批量演员合并完成: {result.get('executed_count', 0)} 组"
                f" · {result.get('updated_count', 0)} 部作品"
                f" · 删除空演员 {result.get('deleted_actor_count', 0)} 个"
                f" · 失败 {result.get('failed_count', 0)} 组"
            ),
            source="media_library.actors",
        )
    return result


@router.get("/item/{item_id}")
async def get_item(item_id: str):
    """Get item details."""
    config = _load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail=_ADAPTER_NOT_ACTIVATED)

    try:
        raw = await _get_item(config, item_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取详情失败: {e}")

    if not raw:
        raise HTTPException(status_code=404, detail=f"未找到媒体项目: {item_id}")

    return raw


@router.post("/items/delete-chain")
async def delete_media_item_chain(req: MediaItemDeleteRequest):
    config = _load_config()
    code, delete_dirs, delete_files = await _media_item_delete_plan(req.item_id, config)

    if req.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "code": code,
            **_preview_delete_targets(delete_dirs, delete_files),
        }

    result = _execute_delete_targets(delete_dirs, delete_files)
    state = _bump_sync_state()
    return {
        "ok": True,
        "code": code,
        "sync_state": state,
        **result,
    }


# ─── Hardlink group endpoints ──────────────────────────────────────────────────

@router.get("/hardlinks/groups")
async def get_hardlink_groups():
    """Return current hardlink groups from the stored file.
    Does NOT scan the filesystem — use POST /hardlinks/scan to refresh.
    """
    payload = _enrich_hardlink_groups(_load_hardlink_groups())
    return {
        "groups": payload["groups"],
        "summary": payload["summary"],
        "count": payload["summary"]["total_groups"],
        "last_scanned_at": _hardlink_groups_last_scanned_at(),
    }


def _parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None
    match = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
    if not match:
        raise HTTPException(status_code=416, detail="无效的 Range 请求")

    start_raw, end_raw = match.groups()
    if not start_raw and not end_raw:
        raise HTTPException(status_code=416, detail="无效的 Range 请求")

    if start_raw:
        start = int(start_raw)
        end = int(end_raw) if end_raw else file_size - 1
    else:
        suffix_length = int(end_raw)
        if suffix_length <= 0:
            raise HTTPException(status_code=416, detail="无效的 Range 请求")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Range 超出文件范围")

    end = min(end, file_size - 1)
    return start, end


def _iter_file_range(target: Path, start: int, end: int, *, chunk_size: int = 1024 * 1024):
    with target.open("rb") as fh:
        fh.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = fh.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/hardlinks/preview-file")
async def preview_hardlink_file(request: Request, path: str = Query(..., min_length=1)):
    config = _load_config()
    source_roots, hardlink_roots = _allowed_scan_roots(config)
    target = Path(_map_path(path, config)).resolve()
    _assert_safe_path(target, source_roots + hardlink_roots, label="预览文件")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {target}")

    if target.suffix.lower() not in VIDEO_EXTS:
        raise HTTPException(status_code=400, detail="仅支持视频文件预览")

    file_size = target.stat().st_size
    media_type, _ = mimetypes.guess_type(str(target))
    media_type = media_type or "application/octet-stream"
    byte_range = _parse_range_header(request.headers.get("range"), file_size)

    headers = {
        "accept-ranges": "bytes",
        "content-type": media_type,
    }

    if byte_range is None:
        headers["content-length"] = str(file_size)
        return StreamingResponse(_iter_file_range(target, 0, file_size - 1), headers=headers, media_type=media_type)

    start, end = byte_range
    headers["content-length"] = str(end - start + 1)
    headers["content-range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(
        _iter_file_range(target, start, end),
        status_code=206,
        headers=headers,
        media_type=media_type,
    )


@router.post("/hardlinks/scan")
async def scan_hardlinks():
    """Scan all configured scan_groups for hardlinks and rebuild hardlink_groups.txt.
    Returns the rebuilt groups.
    """
    config = _load_config()
    scan_groups: list[dict] = config.get("scan_groups", [])
    if not scan_groups:
        raise HTTPException(status_code=400, detail="未配置任何扫描组，请在存储设置中添加扫描组")

    # Validate directories
    for group in scan_groups:
        for key in ("source_dir", "hardlink_dir"):
            path = group.get(key, "")
            if path:
                try:
                    os.stat(path)
                except OSError as e:
                    raise HTTPException(status_code=400, detail=f"{group.get('name', '未命名')} / {key} 不可访问: {e}")

    groups = await _build_hardlink_groups()
    _save_hardlink_groups(groups)
    payload = _enrich_hardlink_groups(groups)

    return {
        "ok": True,
        "scan_groups": scan_groups,
        "total_count": payload["summary"]["total_groups"],
        "total_entries": payload["summary"]["total_entries"],
        "groups": payload["groups"],
        "summary": payload["summary"],
        "last_scanned_at": _hardlink_groups_last_scanned_at(),
    }


@router.post("/hardlinks/delete-hardlink")
async def delete_hardlink_file(req: HardlinkDeleteRequest):
    config = _load_config()
    source_roots, hardlink_roots = _allowed_scan_roots(config)
    allowed_roots = source_roots + hardlink_roots

    target = Path(req.file_path).resolve()
    _assert_safe_path(target, allowed_roots, label="硬链接文件")

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {target}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"不是文件: {target}")

    if req.dry_run:
        planned_files = [str(target)]
        sibling_nfo = target.with_suffix(".nfo")
        if req.remove_nfo and sibling_nfo.is_file():
            planned_files.append(str(sibling_nfo))
        return {
            "ok": True,
            "dry_run": True,
            "planned_files": planned_files,
        }

    deleted = _remove_file_and_sibling_nfo(target, remove_nfo=req.remove_nfo)
    if not deleted:
        raise HTTPException(status_code=400, detail=f"未删除任何文件: {target}")

    return {
        "ok": True,
        "deleted_paths": deleted,
    }


@router.post("/hardlinks/delete-source-chain")
async def delete_source_chain(req: SourceChainDeleteRequest):
    config = _load_config()
    source_roots, hardlink_roots = _allowed_scan_roots(config)
    if not source_roots and not hardlink_roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")

    source_path = Path(req.source_path).resolve()
    _assert_safe_path(source_path, source_roots + hardlink_roots, label="主文件路径")
    hardlink_paths: list[Path] = []
    for hardlink_path in req.hardlink_paths:
        p = Path(hardlink_path).resolve()
        _assert_safe_path(p, source_roots + hardlink_roots, label="硬链接路径")
        hardlink_paths.append(p)

    delete_dirs, delete_files = _collect_chain_delete_targets(
        source_path,
        hardlink_paths,
        code=req.code,
        source_roots=source_roots,
        hardlink_roots=hardlink_roots,
    )
    if req.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            **_preview_delete_targets(delete_dirs, delete_files),
        }

    result = _execute_delete_targets(delete_dirs, delete_files)

    return {
        "ok": True,
        **result,
    }


@router.post("/hardlinks/delete-group")
async def delete_hardlink_group(req: GroupDeleteRequest):
    config = _load_config()
    source_roots, hardlink_roots = _allowed_scan_roots(config)
    if not source_roots and not hardlink_roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")

    delete_dirs: set[Path] = set()
    delete_files: set[Path] = set()

    for entry in req.entries:
        source_path = Path(entry.source_path).resolve() if entry.source_path else None
        if source_path:
            _assert_safe_path(source_path, source_roots + hardlink_roots, label="主文件路径")

        hardlink_paths: list[Path] = []
        for hardlink_path in entry.hardlink_paths:
            p = Path(hardlink_path).resolve()
            _assert_safe_path(p, source_roots + hardlink_roots, label="硬链接路径")
            hardlink_paths.append(p)

        e_dirs, e_files = _collect_chain_delete_targets(
            source_path,
            hardlink_paths,
            code=req.code,
            source_roots=source_roots,
            hardlink_roots=hardlink_roots,
        )
        delete_dirs.update(e_dirs)
        delete_files.update(e_files)

    if req.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            **_preview_delete_targets(delete_dirs, delete_files),
        }

    result = _execute_delete_targets(delete_dirs, delete_files)
    return {
        "ok": True,
        **result,
    }
