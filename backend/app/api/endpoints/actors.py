"""Emby actor management endpoints recovered independently from media_library.

This module deliberately builds on the still-working media-library adapter
instead of replacing its recovered bytecode.  It is safe to evolve while the
rest of that adapter is reconstructed.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.endpoints import media_library as media
from app.api.system import SystemLogManager
from app.core.config import get_settings
from app.core.runtime_paths import data_path


router = APIRouter(prefix="/api/media-library", tags=["media-library-actors"])


class ActorMappingSourceRequest(BaseModel):
    mdc_ng_path: str


class ActorAvatarUrlRequest(BaseModel):
    url: str


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


class ActorTmdbApplyRequest(BaseModel):
    apply_name: bool = False
    apply_overview: bool = True
    apply_provider_ids: bool = True
    apply_avatar: bool = False


MDC_NG_ACTOR_MAPPING_RELATIVE_PATH = Path("data") / "data" / "mapping_actor.xml"
_mapping_records_cache: tuple[float, list[dict[str, Any]]] | None = None
_mapping_name_index_cache: tuple[int, dict[str, dict[str, Any]]] | None = None
_mapping_auto_update_task: asyncio.Task | None = None
_tmdb_backfill_progress: dict[str, dict[str, Any]] = {}
_name_sync_progress: dict[str, dict[str, Any]] = {}


def _mapping_settings_path() -> Path:
    path = data_path() / "actor_management_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _mapping_settings() -> dict[str, Any]:
    path = _mapping_settings_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_mapping_settings(value: dict[str, Any]) -> None:
    _mapping_settings_path().write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _require_config() -> dict[str, Any]:
    config = media._load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail="媒体库适配器尚未配置")
    return config


def _base_url(config: dict[str, Any]) -> str:
    return str(media._server_url(config)).rstrip("/")


def _headers(config: dict[str, Any]) -> dict[str, str]:
    return media._headers(str(config.get("api_key") or ""))


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[\s\u3000・·._\-]", "", str(value or "")).casefold()


def _lang_key(value: str | None) -> str:
    lowered = str(value or "zh-CN").lower()
    if lowered in {"zh-tw", "zh_tw", "tw"} or "hant" in lowered:
        return "zh_tw"
    if lowered.startswith("ja") or lowered in {"jp", "ja_jp"}:
        return "jp"
    return "zh_cn"


def _clean_text_lines(value: str | None) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(value or ""), flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip()


def _overview_external_urls(value: str | None) -> tuple[str, dict[str, str]]:
    text = _clean_text_lines(value)
    if not text:
        return "", {}
    urls: dict[str, str] = {}
    kept: list[str] = []
    label_map = {
        "twitter": "x", "x": "x", "instagram": "instagram", "ins": "instagram",
        "tiktok": "tiktok", "youtube": "youtube", "facebook": "facebook",
        "fanza": "fanza", "dmm": "fanza", "tmdb": "tmdb", "imdb": "imdb",
        "homepage": "homepage", "official": "homepage", "主页": "homepage", "官网": "homepage",
    }
    url_pattern = re.compile(r'https?://[^\s<>\"]+')
    for line in text.splitlines():
        lowered = line.lower()
        found = url_pattern.findall(line)
        is_link_line = bool(found) or "外部链接" in line or set(line) <= {"=", "-", " "}
        if found:
            label_text = lowered.split(found[0].lower(), 1)[0].strip(" :=：-[]()")
            key = next(
                (
                    mapped
                    for label, mapped in label_map.items()
                    if (label == "x" and label_text == "x") or (label != "x" and label in label_text)
                ),
                "",
            )
            for url in found:
                clean_url = url.rstrip("。.,，；;")
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


def _translation_name_map(person: dict[str, Any]) -> dict[str, str]:
    translations = ((person.get("translations") or {}).get("translations") or (person.get("translations") or {}).get("data") or [])
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
        if iso and country:
            names[f"{iso}-{country}"] = name
        if iso:
            names.setdefault(iso, name)
    return names


def _tmdb_identity_names(person: dict[str, Any]) -> dict[str, Any]:
    translated = _translation_name_map(person)
    jp = translated.get("ja-JP") or translated.get("ja") or ""
    zh_cn = translated.get("zh-CN") or translated.get("zh-HANS") or translated.get("zh-SG") or translated.get("zh") or ""
    zh_tw = translated.get("zh-TW") or translated.get("zh-HK") or translated.get("zh-HANT") or ""
    aliases: list[str] = []
    known_aliases = person.get("also_known_as") if isinstance(person.get("also_known_as"), list) else []
    for value in [person.get("name"), *known_aliases]:
        name = str(value or "").strip()
        if name and name not in {jp, zh_cn, zh_tw} and name not in aliases:
            aliases.append(name)
    return {"jp": jp, "zh_cn": zh_cn, "zh_tw": zh_tw, "aliases": aliases}


def _tmdb_external_urls(external_ids: dict[str, Any], tmdb_id: str | None = None) -> dict[str, str]:
    urls: dict[str, str] = {}
    if tmdb_id:
        urls["tmdb"] = f"https://www.themoviedb.org/person/{quote(str(tmdb_id))}"
    definitions = {
        "imdb_id": ("imdb", "https://www.imdb.com/name/{}/"),
        "twitter_id": ("x", "https://x.com/{}"),
        "instagram_id": ("instagram", "https://www.instagram.com/{}/"),
        "tiktok_id": ("tiktok", "https://www.tiktok.com/@{}"),
        "youtube_id": ("youtube", "https://www.youtube.com/{}"),
        "wikidata_id": ("wikidata", "https://www.wikidata.org/wiki/{}"),
        "facebook_id": ("facebook", "https://www.facebook.com/{}"),
    }
    for source_key, (target_key, template) in definitions.items():
        value = str(external_ids.get(source_key) or "").strip().lstrip("@")
        if value:
            urls[target_key] = template.format(quote(value))
    return urls


def _tmdb_gender_label(value: object) -> str:
    try:
        gender = int(value or 0)
    except (TypeError, ValueError):
        gender = 0
    return {1: "female", 2: "male", 3: "non-binary"}.get(gender, "")


def _is_actor_name(value: str | None) -> bool:
    name = str(value or "").strip()
    if not name or name.isdecimal() or re.fullmatch(r"[-_ .·・]+", name):
        return False
    return not bool(re.fullmatch(r"\[(?:red|deleted|unknown)\]", name, flags=re.IGNORECASE))


def _configured_mapping_root(config: dict[str, Any]) -> str:
    saved = _mapping_settings()
    return str(
        config.get("mdc_ng_actor_mapping_path")
        or config.get("mdc_ng_path")
        or saved.get("mdc_ng_actor_mapping_path")
        or saved.get("mdc_ng_path")
        or ""
    ).strip()


def _mapping_path(config: dict[str, Any]) -> Path | None:
    root = _configured_mapping_root(config)
    if not root:
        return None
    candidate = Path(root).expanduser()
    if candidate.is_file():
        return candidate
    return candidate / MDC_NG_ACTOR_MAPPING_RELATIVE_PATH


def _mapping_store_path() -> Path:
    path = data_path() / "media_actor_mappings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _mapping_sync_state_path() -> Path:
    path = data_path() / "media_actor_mapping_sync_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _actor_mapping_upload_dir() -> Path:
    path = data_path() / "media_actor_mapping_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_upload_filename(filename: str | None) -> str:
    raw = Path(filename or "actor_mapping").name.strip() or "actor_mapping"
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff\u3040-\u30ff\u3400-\u9fff]", "_", raw)[:120]


def _actor_mapping_upload_info(path: Path, size: int | None = None) -> dict[str, Any]:
    stat = path.stat()
    return {
        "filename": path.name,
        "size": size if size is not None else stat.st_size,
        "format": path.suffix.lower().lstrip(".") or "unknown",
        "saved_path": str(path),
        "uploaded_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _latest_actor_mapping_upload_path() -> Path | None:
    latest = _actor_mapping_upload_dir() / "latest"
    if not latest.is_file():
        return None
    path = Path(latest.read_text(encoding="utf-8").strip())
    return path if path.is_file() else None


def _profile_overrides_path() -> Path:
    path = data_path() / "actor_profile_overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _actor_merge_ignored_ghosts_path() -> Path:
    path = data_path() / "actor_merge_ignored_ghosts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _actor_merge_backup_dir() -> Path:
    path = data_path() / "actor_merge_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_actor_merge_ignored_ghosts() -> set[str]:
    payload = _load_json(_actor_merge_ignored_ghosts_path(), {})
    if isinstance(payload, list):
        return {str(item) for item in payload if str(item).strip()}
    if isinstance(payload, dict):
        return {str(item) for item in payload.get("actor_ids", []) if str(item).strip()}
    return set()


def _save_actor_merge_ignored_ghosts(actor_ids: set[str]) -> None:
    _save_json(
        _actor_merge_ignored_ghosts_path(),
        {
            "actor_ids": sorted(actor_ids),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _load_profile_overrides() -> dict[str, dict[str, Any]]:
    payload = _load_json(_profile_overrides_path(), {})
    return payload if isinstance(payload, dict) else {}


def _save_profile_overrides(payload: dict[str, dict[str, Any]]) -> None:
    _save_json(_profile_overrides_path(), payload)


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _element_values(element: ET.Element) -> dict[str, str]:
    values = {str(key).casefold(): str(value).strip() for key, value in element.attrib.items() if str(value).strip()}
    for child in element.iter():
        if child is element:
            continue
        key = child.tag.rsplit("}", 1)[-1].casefold()
        text = (child.text or "").strip()
        if text and key not in values:
            values[key] = text
    return values


def _first(values: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = values.get(key.casefold(), "").strip()
        if value:
            return value
    return ""


def _mapping_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    global _mapping_records_cache
    store = _mapping_store_path()
    if store.is_file():
        try:
            mtime = store.stat().st_mtime
            if _mapping_records_cache and _mapping_records_cache[0] == mtime:
                return _mapping_records_cache[1]
            payload = _load_json(store, {})
            records = [item for item in payload.get("records", []) if isinstance(item, dict)]
            _mapping_records_cache = (mtime, records)
            return records
        except OSError:
            pass
    path = _mapping_path(config)
    if not path or not path.is_file():
        return []
    records, _ = _parse_mapping_xml(path)
    return records


def _parse_mapping_xml(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    missing = {"keyword": 0, "tmdb_id": 0, "verified": 0}
    verified_count = 0
    for _event, element in ET.iterparse(path, events=("end",)):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag != "a":
            element.clear()
            continue
        values = _element_values(element)
        jp = _first(values, "jp", "name_jp", "japanese", "ja")
        zh_cn = _first(values, "zh_cn", "name_zh_cn", "simplified", "cn")
        zh_tw = _first(values, "zh_tw", "name_zh_tw", "traditional", "tw")
        aliases = _first(values, "keyword", "aliases", "alias", "other_name", "other_names")
        if not (jp or zh_cn or zh_tw):
            element.clear()
            continue
        names: list[str] = []
        for name in (jp, zh_cn, zh_tw):
            if name and name not in names:
                names.append(name)
        alias_values = [part.strip() for part in re.split(r"[,，、;；|/]+", aliases) if part.strip()]
        for name in alias_values:
            if name not in names:
                names.append(name)
        tmdb_id = _first(values, "tmdb_id", "tmdb")
        verified = _first(values, "verified").lower() in {"1", "true", "yes"}
        record = {
            "id": tmdb_id or _normalize_name(jp or zh_cn or zh_tw),
            "jp": jp,
            "zh_cn": zh_cn,
            "zh_tw": zh_tw,
            "aliases": alias_values,
            "names": names,
            "tmdb_id": tmdb_id,
            "verified": verified,
        }
        records.append(record)
        if not aliases:
            missing["keyword"] += 1
        if not tmdb_id:
            missing["tmdb_id"] += 1
        if not _first(values, "verified"):
            missing["verified"] += 1
        if verified:
            verified_count += 1
        element.clear()
    return records, {
        "total": len(records),
        "verified": verified_count,
        "with_tmdb": len(records) - missing["tmdb_id"],
        "missing": missing,
    }


def _save_mapping_records(records: list[dict[str, Any]], source: Path, stats: dict[str, Any]) -> dict[str, Any]:
    global _mapping_records_cache, _mapping_name_index_cache
    payload = {
        "version": 1,
        "source_path": str(source),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "records": records,
    }
    _save_json(_mapping_store_path(), payload)
    _mapping_records_cache = None
    _mapping_name_index_cache = None
    return {"path": str(_mapping_store_path()), "updated_at": payload["updated_at"], "stats": stats}


def _mapping_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    global _mapping_name_index_cache
    records = _mapping_records(config)
    if _mapping_name_index_cache and _mapping_name_index_cache[0] == id(records):
        return _mapping_name_index_cache[1]
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        for name in record["names"]:
            key = _normalize_name(name)
            if key:
                match = index.get(key)
                if match is None or (record.get("verified") and not match.get("verified")):
                    index[key] = record
    _mapping_name_index_cache = (id(records), index)
    return index


def _actor_from_emby(
    raw: dict[str, Any],
    config: dict[str, Any],
    mapping: dict[str, dict[str, Any]],
    *,
    lang: str = "zh_cn",
) -> dict[str, Any]:
    name = str(raw.get("Name") or "")
    sort_name = str(raw.get("SortName") or "")
    record = mapping.get(_normalize_name(name)) or mapping.get(_normalize_name(sort_name)) or {}
    actor_id = str(raw.get("Id") or "")
    tags = raw.get("ImageTags") or {}
    tag = tags.get("Primary")
    avatar_url = None
    if actor_id and tag:
        avatar_url = f"{_base_url(config)}/emby/Items/{quote(actor_id)}/Images/Primary?tag={quote(str(tag))}"
    server_id = str(raw.get("ServerId") or config.get("server_id") or "")
    emby_url = f"{_base_url(config)}/web/index.html#!/item?id={quote(actor_id)}"
    if server_id:
        emby_url += f"&serverId={quote(server_id)}"
    lang = _lang_key(lang)
    display_name = str(record.get(lang) or record.get("zh_cn") or record.get("jp") or name)
    provider_ids = raw.get("ProviderIds") or {}
    tmdb_id = str(provider_ids.get("Tmdb") or provider_ids.get("TMDB") or "")
    imdb_id = str(provider_ids.get("Imdb") or provider_ids.get("IMDB") or "")
    aliases = record.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [part.strip() for part in re.split(r"[,，、;；|/]+", aliases) if part.strip()]
    external_urls: dict[str, str] = {}
    if tmdb_id:
        external_urls["tmdb"] = f"https://www.themoviedb.org/person/{quote(tmdb_id)}"
    if imdb_id:
        external_urls["imdb"] = f"https://www.imdb.com/name/{quote(imdb_id)}/"
    return {
        "id": actor_id,
        "server_id": server_id,
        "name": name,
        "sort_name": sort_name,
        "display_name": display_name,
        "identity_names": {
            "selected_name": display_name,
            "selected_lang": lang,
            "emby_name": name,
            "emby_sort_name": sort_name,
            "jp": record.get("jp", ""),
            "zh_cn": record.get("zh_cn", ""),
            "zh_tw": record.get("zh_tw", ""),
            "aliases": aliases,
            "source": "mdc-ng" if record else "emby",
        },
        "overview": str(raw.get("Overview") or ""),
        "provider_ids": provider_ids,
        "avatar_url": avatar_url,
        "image_url": avatar_url,
        "emby_url": emby_url,
        "name_jp": record.get("jp", ""),
        "name_zh_cn": record.get("zh_cn", ""),
        "name_zh_tw": record.get("zh_tw", ""),
        "aliases": aliases,
        "mapping_id": record.get("id"),
        "mapping_tmdb_id": record.get("tmdb_id"),
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "external_urls": external_urls,
        "date_created": raw.get("DateCreated"),
    }


def _apply_profile_override(actor: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(override, dict):
        return actor
    result = dict(actor)
    for key in (
        "name", "sort_name", "overview", "birthday", "deathday", "place_of_birth",
        "gender", "known_for_department", "popularity", "homepage", "external_urls", "image_url",
    ):
        if key in override and override[key] is not None:
            result[key] = override[key]
    if isinstance(override.get("provider_ids"), dict):
        provider_ids = dict(result.get("provider_ids") or {})
        for key, value in override["provider_ids"].items():
            if str(value or "").strip():
                provider_ids[str(key)] = str(value).strip()
            else:
                for existing in list(provider_ids):
                    if existing.lower() == str(key).lower():
                        provider_ids.pop(existing, None)
        result["provider_ids"] = provider_ids
        result["tmdb_id"] = str(provider_ids.get("Tmdb") or provider_ids.get("TMDB") or "")
        result["imdb_id"] = str(provider_ids.get("Imdb") or provider_ids.get("IMDB") or "")
    identity = dict(result.get("identity_names") or {})
    if isinstance(override.get("identity_names"), dict):
        identity.update(override["identity_names"])
    result["identity_names"] = identity
    if result.get("image_url"):
        result["avatar_url"] = result["image_url"]
    return result


async def _raw_actor(config: dict[str, Any], actor_id: str) -> dict[str, Any]:
    user_id = str(config.get("user_id") or "").strip()
    paths = []
    if user_id:
        paths.append(f"/emby/Users/{quote(user_id)}/Items/{quote(actor_id)}")
    paths.append(f"/emby/Items/{quote(actor_id)}")
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        for path in paths:
            response = await client.get(
                f"{_base_url(config)}{path}",
                headers=_headers(config),
                params={"Fields": "Overview,ProviderIds,ImageTags,DateCreated,SortName,PremiereDate,EndDate,ProductionLocations,Gender,KnownForDepartment,Homepage,Popularity"},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return response.json()
    raise HTTPException(status_code=404, detail="未找到演员")


async def _actor_profile(config: dict[str, Any], actor_id: str, lang: str | None) -> dict[str, Any]:
    raw = await _raw_actor(config, actor_id)
    actor = _actor_from_emby(raw, config, _mapping_index(config), lang=_lang_key(lang))
    locations = raw.get("ProductionLocations") or []
    actor.update({
        "birthday": raw.get("PremiereDate") or "",
        "deathday": raw.get("EndDate") or "",
        "place_of_birth": locations[0] if locations else "",
        "gender": raw.get("Gender") or "",
        "known_for_department": raw.get("KnownForDepartment") or "",
        "popularity": raw.get("Popularity"),
        "homepage": raw.get("Homepage") or "",
    })
    return _apply_profile_override(actor, _load_profile_overrides().get(str(actor_id)))


def _actor_matches_query(actor: dict[str, Any], query: str | None) -> bool:
    needle = _normalize_name(query)
    if not needle:
        return True
    values = (
        actor.get("name"),
        actor.get("sort_name"),
        actor.get("display_name"),
        actor.get("name_jp"),
        actor.get("name_zh_cn"),
        actor.get("name_zh_tw"),
        actor.get("aliases"),
    )
    return any(needle in _normalize_name(str(value or "")) for value in values)


async def _list_actors(
    config: dict[str, Any],
    *,
    limit: int,
    offset: int,
    query: str | None,
    sort_by: str,
    sort_order: str,
    lang: str = "zh_cn",
) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {
        "IncludeItemTypes": "Person",
        "PersonTypes": "Actor",
        "Recursive": "true",
        "Fields": "Overview,ProviderIds,ImageTags,DateCreated,SortName",
        "SortBy": sort_by if sort_by in {"SortName", "DateCreated", "Name"} else "SortName",
        "SortOrder": sort_order if sort_order in {"Ascending", "Descending"} else "Ascending",
    }

    # Emby applies pagination before filtering PersonTypes consistently on all
    # deployments.  A library that starts with stale [RED] or numeric people
    # can therefore return a visibly empty first page.  Read the compact
    # person list in chunks, filter locally, then paginate the valid actors.
    raw_items: list[dict[str, Any]] = []
    raw_total = 0
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        start_index = 0
        while True:
            response = await client.get(
                f"{_base_url(config)}/emby/Persons",
                headers=_headers(config),
                params={**params, "StartIndex": start_index, "Limit": 500},
            )
            response.raise_for_status()
            payload = response.json()
            values = [item for item in payload.get("Items") or [] if isinstance(item, dict)]
            raw_items.extend(values)
            raw_total = int(payload.get("TotalRecordCount") or len(raw_items))
            start_index += len(values)
            if not values or start_index >= raw_total:
                break

    mapping = _mapping_index(config)
    actors = [
        _actor_from_emby(item, config, mapping, lang=lang)
        for item in raw_items
        if _is_actor_name(item.get("Name"))
    ]
    if query:
        actors = [actor for actor in actors if _actor_matches_query(actor, query)]
    valid_total = len(actors)
    return actors[max(0, offset) : max(0, offset) + limit], valid_total


@router.get("/actors")
async def get_actors(
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = None,
    sort_by: str = "SortName",
    sort_order: str = "Ascending",
    lang: str = "zh-CN",
):
    config = _require_config()
    try:
        actors, total = await _list_actors(config, limit=limit, offset=offset, query=q, sort_by=sort_by, sort_order=sort_order, lang=lang)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"获取 Emby 演员失败: {exc}") from exc
    return {"actors": actors, "total": total, "limit": limit, "offset": offset}


@router.get("/actors/mapping/status")
async def actor_mapping_status():
    _maybe_schedule_actor_mapping_auto_update()
    config = media._load_config()
    store = _mapping_store_path()
    payload = _load_json(store, {})
    source = _mapping_path(config)
    state = _load_json(_mapping_sync_state_path(), {})
    return {
        "ok": True,
        "imported": bool(store.is_file() and payload.get("records")),
        "path": str(store),
        "source_path": payload.get("source_path", ""),
        "updated_at": payload.get("updated_at", ""),
        "stats": payload.get("stats") or {"total": 0, "verified": 0, "with_tmdb": 0},
        "mdc_ng": {
            "enabled": bool(getattr(get_settings(), "actor_mapping_auto_update", True)),
            "configured_root": _configured_mapping_root(config),
            "relative_path": str(MDC_NG_ACTOR_MAPPING_RELATIVE_PATH),
            "configured_path": str(source) if source else "",
            **state,
        },
    }


@router.post("/actors/mapping/source")
async def set_actor_mapping_source(req: ActorMappingSourceRequest):
    root = req.mdc_ng_path.strip()
    if not root:
        raise HTTPException(status_code=400, detail="请填写 MDC-NG 路径")
    candidate = Path(root).expanduser()
    if not candidate.exists():
        raise HTTPException(status_code=400, detail="MDC-NG 路径不存在")
    config = media._load_config()
    config["mdc_ng_actor_mapping_path"] = root
    resolved = _mapping_path(config)
    if not resolved or not resolved.is_file():
        raise HTTPException(status_code=400, detail="在该路径下未找到 data/data/mapping_actor.xml")
    media._save_config(config)
    _save_mapping_settings({"mdc_ng_actor_mapping_path": root})
    return {
        "ok": True,
        "configured_path": str(resolved),
        "record_count": len(_mapping_records(config)),
    }


async def _sync_mapping_from_mdc_ng(*, force: bool = False) -> dict[str, Any]:
    config = media._load_config()
    source = _mapping_path(config)
    now = datetime.now(timezone.utc).isoformat()
    state = {**_load_json(_mapping_sync_state_path(), {}), "running": True, "last_attempt_at": now}
    _save_json(_mapping_sync_state_path(), state)
    try:
        if not source or not source.is_file():
            raise FileNotFoundError(f"MDC-NG 演员映射表不存在: {source or ''}")
        records, stats = _parse_mapping_xml(source)
        stat = source.stat()
        mapping = _save_mapping_records(records, source, {
            **stats,
            "mdc_ng": True,
            "source_path": str(source),
            "source_size": stat.st_size,
            "source_mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
        state = {
            "running": False,
            "last_attempt_at": now,
            "last_success_at": datetime.now(timezone.utc).isoformat(),
            "last_error": "",
            "source_path": str(source),
            "source_size": stat.st_size,
            "stats": stats,
        }
        _save_json(_mapping_sync_state_path(), state)
        return {"ok": True, "mapping": mapping, "mdc_ng": state}
    except Exception as exc:
        state.update({"running": False, "last_error": str(exc)})
        _save_json(_mapping_sync_state_path(), state)
        if force:
            raise
        return {"ok": False, "error": str(exc), "mdc_ng": state}


def _maybe_schedule_actor_mapping_auto_update() -> None:
    global _mapping_auto_update_task
    try:
        if not bool(getattr(get_settings(), "actor_mapping_auto_update", True)):
            return
        config = media._load_config()
        if not _configured_mapping_root(config):
            return
        state = _load_json(_mapping_sync_state_path(), {})
        if state.get("running"):
            return
        if _mapping_auto_update_task and not _mapping_auto_update_task.done():
            return
        last_success = str(state.get("last_success_at") or "")
        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last_dt).total_seconds() < 24 * 3600:
                    return
            except ValueError:
                pass
        _mapping_auto_update_task = asyncio.create_task(_sync_mapping_from_mdc_ng(force=False))
    except RuntimeError:
        return


@router.post("/actors/mapping/sync-mdc-ng")
async def sync_mdc_ng_actor_mapping():
    try:
        return await _sync_mapping_from_mdc_ng(force=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/actors/mapping/sync-online")
async def sync_online_actor_mapping():
    try:
        return await _sync_mapping_from_mdc_ng(force=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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


@router.post("/actors/mapping/import-latest")
async def import_latest_actor_mapping():
    path = _latest_actor_mapping_upload_path()
    if path is None:
        raise HTTPException(status_code=400, detail="还没有上传演员映射表")
    if path.suffix.lower() != ".xml":
        raise HTTPException(status_code=400, detail="当前仅支持导入 XML 演员映射表")
    try:
        records, stats = _parse_mapping_xml(path)
        result = _save_mapping_records(records, path, stats)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入演员映射表失败: {exc}") from exc
    SystemLogManager.get_instance().add_log(
        "info",
        f"[MediaLibrary] 已导入演员映射表: {stats.get('total', 0)} 条 · TMDB {stats.get('with_tmdb', 0)} 条",
        source="media_library.actors",
    )
    return {"ok": True, "mapping": result}


@router.delete("/actors/mapping")
async def clear_actor_mapping():
    global _mapping_records_cache, _mapping_name_index_cache
    removed: list[str] = []
    for path in (_mapping_store_path(), _mapping_sync_state_path()):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    _mapping_records_cache = None
    _mapping_name_index_cache = None
    return {"ok": True, "removed": removed}


@router.get("/actors/duplicates")
async def actor_duplicates(limit: int = Query(3000, ge=1, le=5000)):
    config = _require_config()
    actors, _ = await _list_actors(config, limit=limit, offset=0, query=None, sort_by="SortName", sort_order="Ascending")
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    mapping = _mapping_index(config)
    for actor in actors:
        record = mapping.get(_normalize_name(actor["name"]))
        if record:
            key = tuple(sorted(_normalize_name(name) for name in record["names"] if _normalize_name(name)))
        else:
            key = (_normalize_name(actor["name"]),)
        if key and key != (""):
            grouped.setdefault(key, []).append(actor)
    groups = []
    for members in grouped.values():
        if len(members) > 1:
            groups.append({"key": " / ".join(member["name"] for member in members), "actors": members})
    groups.sort(key=lambda group: (-len(group["actors"]), group["key"]))
    return {"groups": groups, "total": len(groups)}


def _mapping_display_name(record: dict[str, Any], lang: str | None) -> str:
    key = _lang_key(lang)
    return str(record.get(key) or record.get("zh_cn") or record.get("jp") or record.get("zh_tw") or "")


@router.get("/actors/mapping/matches")
async def actor_mapping_matches(
    limit: int = 5000,
    only_candidates: bool = True,
    lang: str = "zh-CN",
):
    config = _require_config()
    actors, total = await _list_actors(
        config, limit=min(limit, 5000), offset=0, query=None,
        sort_by="SortName", sort_order="Ascending", lang=lang,
    )
    records = _mapping_records(config)
    index = _mapping_index(config)
    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    active_actors = [
        actor for actor in actors
        if str(actor.get("id") or "").strip() not in ignored_ghost_ids
    ]
    grouped: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    rejected_matches: list[dict[str, Any]] = []
    for actor in actors:
        actor_id = str(actor.get("id") or "").strip()
        record = index.get(_normalize_name(actor.get("name"))) or index.get(_normalize_name(actor.get("sort_name")))
        if not record:
            unmatched.append(actor)
            continue
        if actor_id in ignored_ghost_ids:
            rejected = dict(actor)
            rejected.update({
                "rejected_reason": "ignored_person",
                "rejected_mapping_id": str(record.get("id") or ""),
                "rejected_mapping_name": _mapping_display_name(record, lang),
                "rejected_mapping_tmdb_id": str(record.get("tmdb_id") or ""),
            })
            rejected_matches.append(rejected)
            continue
        group = grouped.setdefault(str(record.get("id") or _normalize_name(_mapping_display_name(record, lang))), {
            "mapping_id": str(record.get("id") or ""),
            "canonical_name": _mapping_display_name(record, lang),
            "display_name": _mapping_display_name(record, lang),
            "jp": record.get("jp", ""),
            "zh_cn": record.get("zh_cn", ""),
            "zh_tw": record.get("zh_tw", ""),
            "tmdb_id": record.get("tmdb_id", ""),
            "actors": [],
        })
        group["actors"].append(actor)

    groups: list[dict[str, Any]] = []
    conflict_groups = 0
    for group in grouped.values():
        actor_tmdb_ids = {str(actor.get("tmdb_id") or "") for actor in group["actors"] if actor.get("tmdb_id")}
        expected_tmdb = str(group.get("tmdb_id") or "")
        has_conflict = bool(len(actor_tmdb_ids) > 1 or (expected_tmdb and any(value != expected_tmdb for value in actor_tmdb_ids)))
        if has_conflict:
            conflict_groups += 1
        group.update({
            "count": len(group["actors"]),
            "has_tmdb_conflict": has_conflict,
            "missing_tmdb_count": sum(1 for actor in group["actors"] if not actor.get("tmdb_id")),
            "missing_image_count": sum(1 for actor in group["actors"] if not actor.get("image_url")),
            "target_actor_id": next((actor["id"] for actor in group["actors"] if expected_tmdb and str(actor.get("tmdb_id") or "") == expected_tmdb), group["actors"][0]["id"]),
        })
        if not only_candidates or len(group["actors"]) > 1:
            groups.append(group)
        else:
            actor = dict(group["actors"][0])
            actor.update({
                "rejected_reason": "single_mapped_actor",
                "rejected_mapping_id": group.get("mapping_id") or "",
                "rejected_mapping_name": group.get("display_name") or "",
                "rejected_mapping_tmdb_id": group.get("tmdb_id") or "",
            })
            rejected_matches.append(actor)
    for actor in unmatched:
        if str(actor.get("id") or "").strip() in ignored_ghost_ids:
            rejected = dict(actor)
            rejected.update({
                "rejected_reason": "ignored_person",
                "rejected_mapping_id": "",
                "rejected_mapping_name": "",
                "rejected_mapping_tmdb_id": "",
            })
            rejected_matches.append(rejected)
            continue
        if actor.get("tmdb_id") or actor.get("image_url") or actor.get("sort_name"):
            rejected = dict(actor)
            rejected.update({
                "rejected_reason": "unmatched_emby_actor",
                "rejected_mapping_id": "",
                "rejected_mapping_name": "",
                "rejected_mapping_tmdb_id": "",
            })
            rejected_matches.append(rejected)
    groups.sort(key=lambda item: (-item["count"], item["display_name"]))
    return {
        "ok": True,
        "groups": groups,
        "candidate_groups": len(groups),
        "conflict_groups": conflict_groups,
        "matched_actors": sum(len(group["actors"]) for group in grouped.values()),
        "unmatched_actors": len(unmatched),
        "rejected_actors": len(rejected_matches),
        "rejected_matches": rejected_matches,
        "mapping_records": len(records),
        "total_actors": total,
        "active_actors": len(active_actors),
    }


async def _tmdb_backfill_candidates(config: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    actors, _ = await _list_actors(config, limit=5000, offset=0, query=None, sort_by="SortName", sort_order="Ascending", lang=lang)
    index = _mapping_index(config)
    tmdb_owners = {str(actor.get("tmdb_id")): actor for actor in actors if actor.get("tmdb_id")}
    candidates: list[dict[str, Any]] = []
    for actor in actors:
        if actor.get("tmdb_id"):
            continue
        record = index.get(_normalize_name(actor.get("name"))) or index.get(_normalize_name(actor.get("sort_name")))
        tmdb_id = str((record or {}).get("tmdb_id") or "")
        if not record or not tmdb_id:
            continue
        conflict = tmdb_owners.get(tmdb_id)
        candidates.append({
            "actor_id": actor["id"],
            "actor_name": actor.get("name"),
            "display_name": actor.get("display_name"),
            "actor": actor,
            "tmdb_id": tmdb_id,
            "mapping_name": _mapping_display_name(record, lang),
            "matched_name": actor.get("name"),
            "confidence": "high" if record.get("verified") and not conflict else "review",
            "conflict_actors": [conflict] if conflict else [],
        })
    return candidates


@router.get("/actors/tmdb-backfill/preview")
async def preview_actor_tmdb_backfill(lang: str = "zh-CN"):
    candidates = await _tmdb_backfill_candidates(_require_config(), lang)
    return {
        "ok": True,
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
            "high_confidence_count": sum(1 for item in candidates if item["confidence"] == "high"),
            "conflict_count": sum(1 for item in candidates if item["conflict_actors"]),
        },
    }


@router.post("/actors/tmdb-backfill/apply")
async def apply_actor_tmdb_backfill(req: ActorTmdbBackfillRequest, lang: str = "zh-CN"):
    config = _require_config()
    candidates = await _tmdb_backfill_candidates(config, lang)
    selected = set(req.actor_ids or [])
    if selected:
        candidates = [item for item in candidates if item["actor_id"] in selected]
    elif req.only_high_confidence:
        candidates = [item for item in candidates if item["confidence"] == "high"]
    key = str(req.progress_key or "").strip()
    progress = {"ok": True, "status": "running", "processed": 0, "total": len(candidates), "applied_count": 0, "skipped_count": 0, "current_actor": "", "failures": []}
    if key:
        _tmdb_backfill_progress[key] = progress
    for item in candidates:
        progress["current_actor"] = item["display_name"] or item["actor_name"]
        if req.dry_run or item["conflict_actors"]:
            progress["skipped_count"] += 1
        else:
            try:
                result = await update_actor(item["actor_id"], ActorProfileUpdateRequest(provider_ids={"Tmdb": item["tmdb_id"]}), lang)
            except Exception as exc:
                progress["failures"].append({"actor_id": item["actor_id"], "name": progress["current_actor"], "error": str(exc)})
                result = {}
            if result.get("synced"):
                progress["applied_count"] += 1
            else:
                progress["skipped_count"] += 1
        progress["processed"] += 1
    progress.update({"status": "completed", "current_actor": ""})
    return progress


@router.get("/actors/tmdb-backfill/progress/{progress_key}")
async def actor_tmdb_backfill_progress(progress_key: str):
    return _tmdb_backfill_progress.get(progress_key) or {"ok": True, "status": "idle", "processed": 0, "total": 0, "applied_count": 0, "skipped_count": 0}


async def _name_sync_candidates(config: dict[str, Any], lang: str) -> dict[str, Any]:
    actors, total = await _list_actors(config, limit=5000, offset=0, query=None, sort_by="SortName", sort_order="Ascending", lang=lang)
    index = _mapping_index(config)
    owners: dict[str, list[dict[str, Any]]] = {}
    for actor in actors:
        owners.setdefault(_normalize_name(actor.get("name")), []).append(actor)
    updates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for actor in actors:
        record = index.get(_normalize_name(actor.get("name"))) or index.get(_normalize_name(actor.get("sort_name")))
        target = _mapping_display_name(record, lang) if record else ""
        if not target or target == actor.get("name"):
            continue
        conflict_actors = [item for item in owners.get(_normalize_name(target), []) if item["id"] != actor["id"]]
        item = {"actor": actor, "actor_id": actor["id"], "current_name": actor.get("name"), "target_name": target, "target_source": _lang_key(lang), "conflict_actors": conflict_actors, "has_conflict": bool(conflict_actors)}
        (conflicts if conflict_actors else updates).append(item)
    return {"updates": updates, "conflicts": conflicts, "summary": {"actors_scanned": total, "update_count": len(updates) + len(conflicts), "safe_update_count": len(updates), "conflict_count": len(conflicts)}}


@router.get("/actors/name-sync/preview")
async def preview_actor_name_sync(lang: str = "zh-CN"):
    return {"ok": True, **await _name_sync_candidates(_require_config(), lang)}


@router.post("/actors/name-sync/apply")
async def apply_actor_name_sync(req: ActorNameSyncRequest, lang: str = "zh-CN"):
    preview = await _name_sync_candidates(_require_config(), lang)
    candidates = preview["updates"] + ([] if req.skip_conflicts else preview["conflicts"])
    selected = set(req.actor_ids or [])
    if selected:
        candidates = [item for item in candidates if item["actor_id"] in selected]
    key = str(req.progress_key or "").strip()
    progress = {"ok": True, "status": "running", "processed": 0, "total": len(candidates), "applied_count": 0, "skipped_count": 0, "current_actor": "", "current_target": "", "failures": []}
    if key:
        _name_sync_progress[key] = progress
    for item in candidates:
        progress.update({"current_actor": item["current_name"], "current_target": item["target_name"]})
        if req.dry_run:
            progress["skipped_count"] += 1
        else:
            try:
                result = await update_actor(item["actor_id"], ActorProfileUpdateRequest(name=item["target_name"]), lang)
            except Exception as exc:
                progress["failures"].append({"actor_id": item["actor_id"], "name": item["current_name"], "target": item["target_name"], "error": str(exc)})
                result = {}
            progress["applied_count" if result.get("synced") else "skipped_count"] += 1
        progress["processed"] += 1
    progress.update({"status": "completed", "current_actor": "", "current_target": ""})
    return progress


@router.get("/actors/name-sync/progress/{progress_key}")
async def actor_name_sync_progress(progress_key: str):
    return _name_sync_progress.get(progress_key) or {"ok": True, "status": "idle", "processed": 0, "total": 0, "applied_count": 0, "skipped_count": 0}


async def _mapping_group(config: dict[str, Any], mapping_id: str, lang: str, target_actor_id: str | None = None) -> dict[str, Any]:
    result = await actor_mapping_matches(limit=5000, only_candidates=False, lang=lang)
    group = next((item for item in result["groups"] if str(item.get("mapping_id")) == str(mapping_id)), None)
    if not group:
        raise HTTPException(status_code=404, detail="未找到演员映射组")
    if target_actor_id and not any(str(actor["id"]) == str(target_actor_id) for actor in group["actors"]):
        raise HTTPException(status_code=400, detail="目标演员不在当前映射组")
    return group


async def _related_movies(client: httpx.AsyncClient, config: dict[str, Any], actor_id: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"{_base_url(config)}/emby/Items",
        headers=_headers(config),
        params={"PersonIds": actor_id, "Recursive": "true", "IncludeItemTypes": "Movie", "Fields": "Path,ProviderIds,People,ImageTags", "Limit": 5000},
    )
    response.raise_for_status()
    return [item for item in response.json().get("Items") or [] if isinstance(item, dict)]


async def _emby_item_for_update(client: httpx.AsyncClient, config: dict[str, Any], item_id: str) -> dict[str, Any]:
    user_id = str(config.get("user_id") or "").strip()
    safe_item_id = quote(str(item_id), safe="")
    path = f"/emby/Users/{quote(user_id, safe='')}/Items/{safe_item_id}" if user_id else f"/emby/Items/{safe_item_id}"
    response = await client.get(
        f"{_base_url(config)}{path}",
        headers=_headers(config),
        params={
            "Fields": (
                "Path,People,ProviderIds,Genres,Studios,Tags,Overview,PremiereDate,SortName,"
                "DateCreated,ImageTags,LockedFields,OriginalTitle,ProductionYear,CommunityRating,"
                "CriticRating,OfficialRating,CustomRating,Taglines"
            )
        },
    )
    response.raise_for_status()
    return response.json()


def _actor_merge_apply_people(
    item: dict[str, Any],
    *,
    source_actor_ids: set[str],
    target_actor_id: str,
    target_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    people = item.get("People") if isinstance(item.get("People"), list) else []
    has_existing_target = any(
        isinstance(person, dict)
        and str(person.get("Type") or "") == "Actor"
        and (
            str(person.get("Id") or "") == target_actor_id
            or str(person.get("Name") or "") == target_name
        )
        and str(person.get("Id") or "") not in source_actor_ids
        for person in people
    )
    next_people: list[dict[str, Any]] = []
    changed_people: list[dict[str, Any]] = []
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
            next_person = {"Name": target_name, "Type": "Actor", "Id": target_actor_id}
            has_existing_target = True
        dedupe_key = (str(next_person.get("Type") or ""), str(next_person.get("Id") or next_person.get("Name") or ""))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        next_people.append(next_person)
    next_item = dict(item)
    next_item["People"] = next_people
    return next_item, changed_people


def _actor_merge_remove_source_people(
    item: dict[str, Any], *, source_actor_ids: set[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    people = item.get("People") if isinstance(item.get("People"), list) else []
    next_people: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
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
        if isinstance(person, dict):
            next_people.append(person)
    next_item = dict(item)
    next_item["People"] = next_people
    return next_item, removed


async def _emby_delete_item(client: httpx.AsyncClient, config: dict[str, Any], item_id: str) -> None:
    safe_id = quote(str(item_id), safe="")
    user_id = str(config.get("user_id") or "").strip()
    attempts: list[tuple[str, str, dict[str, str] | None]] = [
        ("DELETE", f"{_base_url(config)}/emby/Items/{safe_id}", None),
    ]
    if user_id:
        safe_user_id = quote(user_id, safe="")
        attempts.extend([
            ("DELETE", f"{_base_url(config)}/emby/Users/{safe_user_id}/Items/{safe_id}", None),
            ("POST", f"{_base_url(config)}/emby/Users/{safe_user_id}/Items/Delete", {"Ids": str(item_id)}),
        ])
    attempts.append(("POST", f"{_base_url(config)}/emby/Items/Delete", {"Ids": str(item_id)}))
    last_response: httpx.Response | None = None
    for method, url, params in attempts:
        if method == "DELETE":
            response = await client.delete(url, headers=_headers(config), params=params)
        else:
            response = await client.post(url, headers=_headers(config), params=params)
        last_response = response
        if response.status_code not in {404, 405}:
            break
    if last_response is None:
        raise RuntimeError("未执行 Emby 删除请求")
    last_response.raise_for_status()


async def _emby_item_exists(client: httpx.AsyncClient, config: dict[str, Any], item_id: str) -> bool:
    safe_id = quote(str(item_id), safe="")
    paths = [f"/emby/Items/{safe_id}"]
    user_id = str(config.get("user_id") or "").strip()
    if user_id:
        paths.append(f"/emby/Users/{quote(user_id, safe='')}/Items/{safe_id}")
    for path in paths:
        response = await client.get(f"{_base_url(config)}{path}", headers=_headers(config))
        if response.status_code == 404:
            continue
        response.raise_for_status()
        return True
    return False


async def _related_items_for_delete(client: httpx.AsyncClient, config: dict[str, Any], actor_id: str) -> tuple[int, list[dict[str, Any]]]:
    response = await client.get(
        f"{_base_url(config)}/emby/Items",
        headers=_headers(config),
        params={
            "PersonIds": actor_id,
            "Recursive": "true",
            "Fields": "Path,ProviderIds,People,ImageTags",
            "StartIndex": 0,
            "Limit": 25,
        },
    )
    response.raise_for_status()
    payload = response.json()
    items = [item for item in payload.get("Items") or [] if isinstance(item, dict)]
    return int(payload.get("TotalRecordCount") or len(items)), [
        {
            "id": str(item.get("Id") or ""),
            "name": str(item.get("Name") or ""),
            "type": str(item.get("Type") or item.get("MediaType") or ""),
            "path": str(item.get("Path") or ""),
            "provider_ids": item.get("ProviderIds") or {},
        }
        for item in items
    ]


async def _raw_actor_for_delete(client: httpx.AsyncClient, config: dict[str, Any], actor_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    user_id = str(config.get("user_id") or "").strip()
    paths = []
    if user_id:
        paths.append(f"/emby/Users/{quote(user_id)}/Items/{quote(actor_id)}")
    paths.append(f"/emby/Items/{quote(actor_id)}")
    last_error: dict[str, Any] | None = None
    for path in paths:
        response = await client.get(
            f"{_base_url(config)}{path}",
            headers=_headers(config),
            params={"Fields": "Overview,ProviderIds,ImageTags,DateCreated,SortName,CanDelete,Path"},
        )
        if response.status_code == 404:
            last_error = {"status_code": 404, "body": response.text[:1000], "path": path}
            continue
        if response.is_error:
            return None, {"status_code": response.status_code, "body": response.text[:1000], "path": path}
        return response.json(), None
    return None, last_error


async def _actor_delete_diagnostics(config: dict[str, Any], actor_id: str) -> dict[str, Any]:
    overrides = _load_profile_overrides()
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        raw, person_error = await _raw_actor_for_delete(client, config, actor_id)
        try:
            related_total, related_items = await _related_items_for_delete(client, config, actor_id)
            related_error = None
        except Exception as exc:
            related_total = 0
            related_items = []
            related_error = str(exc)

    provider_ids = raw.get("ProviderIds") if isinstance(raw, dict) else {}
    can_delete_flag = raw.get("CanDelete") if isinstance(raw, dict) else None
    blockers: list[str] = []
    if related_error:
        blockers.append("related_query_failed")
    if related_total > 0:
        blockers.append("related_items")
    if can_delete_flag is False:
        blockers.append("can_delete_false")
    person_exists = raw is not None
    return {
        "ok": True,
        "actor_id": actor_id,
        "person_exists": person_exists,
        "person_error": person_error,
        "name": str(raw.get("Name") or "") if isinstance(raw, dict) else "",
        "sort_name": str(raw.get("SortName") or "") if isinstance(raw, dict) else "",
        "can_delete_flag": can_delete_flag,
        "provider_ids": provider_ids or {},
        "related_total": related_total,
        "related_sample": related_items,
        "related_error": related_error,
        "noor_override_exists": str(actor_id) in overrides,
        "blockers": blockers,
        "can_clean_delete": person_exists and not blockers,
    }


async def _merge_plan(config: dict[str, Any], mapping_id: str, target_actor_id: str | None, target_name: str | None, lang: str) -> dict[str, Any]:
    group = await _mapping_group(config, mapping_id, lang, target_actor_id)
    target_id = str(target_actor_id or group.get("target_actor_id") or group["actors"][0]["id"])
    target_actor = next(actor for actor in group["actors"] if str(actor["id"]) == target_id)
    target = str(target_name or target_actor.get("name") or group.get("display_name") or "")
    source_ids = [str(actor["id"]) for actor in group["actors"] if str(actor["id"]) != target_id]
    movies_by_id: dict[str, dict[str, Any]] = {}
    source_counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        for actor_id in source_ids:
            related = await _related_movies(client, config, actor_id)
            source_counts[actor_id] = len(related)
            for movie in related:
                movies_by_id.setdefault(str(movie.get("Id") or ""), movie)
    movies: list[dict[str, Any]] = []
    for movie in movies_by_id.values():
        changed = [
            person
            for person in movie.get("People") or []
            if isinstance(person, dict)
            and str(person.get("Type") or "") == "Actor"
            and str(person.get("Id") or "") in source_ids
        ]
        if changed:
            movies.append({"id": movie.get("Id"), "name": movie.get("Name", ""), "path": movie.get("Path", ""), "changed_people": changed, "target_name": target})
    return {"mapping_id": mapping_id, "target_name": target, "target_actor_id": target_id, "group": group, "source_actor_ids": source_ids, "source_counts": source_counts, "empty_source_actor_ids": [actor_id for actor_id in source_ids if not source_counts.get(actor_id)], "movie_count": len(movies), "movies": movies}


@router.get("/actors/mapping/merge-plan")
async def actor_mapping_merge_plan(mapping_id: str, target_actor_id: str | None = None, target_name: str | None = None, lang: str = "zh-CN"):
    return {"ok": True, **await _merge_plan(_require_config(), mapping_id, target_actor_id, target_name, lang)}


async def _execute_merge(config: dict[str, Any], req: ActorMappingMergeRequest, lang: str) -> dict[str, Any]:
    plan = await _merge_plan(config, req.mapping_id, req.target_actor_id, req.target_name, lang)
    if req.dry_run:
        return {"ok": True, "dry_run": True, **plan}
    source_ids = set(plan["source_actor_ids"])
    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    backups: list[dict[str, Any]] = []
    deleted: list[str] = []
    delete_failed: list[dict[str, str]] = []
    remaining_source_counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        for movie in plan["movies"]:
            item_id = str(movie.get("id") or "")
            if not item_id:
                continue
            raw = await _emby_item_for_update(client, config, item_id)
            next_item, changed_people = _actor_merge_apply_people(
                raw,
                source_actor_ids=source_ids,
                target_actor_id=str(plan["target_actor_id"]),
                target_name=str(plan["target_name"]),
            )
            if not changed_people:
                skipped.append({"id": item_id, "name": raw.get("Name") or "", "reason": "no_matching_people"})
                continue
            backups.append({
                "id": item_id,
                "name": raw.get("Name") or "",
                "path": raw.get("Path") or "",
                "people": raw.get("People") or [],
            })
            response = await client.post(
                f"{_base_url(config)}/emby/Items/{quote(item_id, safe='')}",
                headers={**_headers(config), "Content-Type": "application/json"},
                json=next_item,
            )
            response.raise_for_status()
            verify_item = await _emby_item_for_update(client, config, item_id)
            cleanup_item, cleanup_people = _actor_merge_remove_source_people(verify_item, source_actor_ids=source_ids)
            if cleanup_people:
                cleanup_response = await client.post(
                    f"{_base_url(config)}/emby/Items/{quote(item_id, safe='')}",
                    headers={**_headers(config), "Content-Type": "application/json"},
                    json=cleanup_item,
                )
                cleanup_response.raise_for_status()
            updated.append({
                "id": item_id,
                "name": raw.get("Name") or movie.get("name") or "",
                "path": raw.get("Path") or movie.get("path") or "",
                "changed_people": changed_people,
                "cleanup_people": cleanup_people,
                "target_name": plan["target_name"],
            })
        for actor_id in source_ids:
            try:
                remaining = await _related_movies(client, config, actor_id)
                remaining_source_counts[actor_id] = len(remaining)
            except Exception as exc:
                delete_failed.append({"id": actor_id, "error": f"无法确认关联作品，跳过删除: {exc}"})
                continue
            if remaining_source_counts[actor_id] != 0:
                delete_failed.append({
                    "id": actor_id,
                    "error": f"仍关联 {remaining_source_counts[actor_id]} 部作品，跳过删除",
                })
                continue
            try:
                await _emby_delete_item(client, config, actor_id)
                if await _emby_item_exists(client, config, actor_id):
                    raise RuntimeError("Emby 删除接口返回成功，但该演员仍可通过 Items 查询到")
                deleted.append(actor_id)
            except Exception as exc:
                delete_failed.append({"id": actor_id, "error": str(exc)})
    backup_path = None
    if backups:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        safe_mapping_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(req.mapping_id)).strip("._") or "mapping"
        backup_file = _actor_merge_backup_dir() / f"{timestamp}_{safe_mapping_id}.json"
        _save_json(backup_file, {
            "mapping_id": req.mapping_id,
            "target_actor_id": plan["target_actor_id"],
            "target_name": plan["target_name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backups": backups,
        })
        backup_path = str(backup_file)
    if deleted:
        ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
        ignored_ghost_ids.update(str(actor_id) for actor_id in deleted)
        _save_actor_merge_ignored_ghosts(ignored_ghost_ids)
    return {
        "ok": True,
        "dry_run": False,
        "updated_count": len(updated),
        "updated": updated,
        "skipped": skipped,
        "backup_path": backup_path,
        "deleted_actor_count": len(deleted),
        "deleted_actor_ids": deleted,
        "delete_failed_actor_ids": delete_failed,
        "remaining_source_counts": remaining_source_counts,
        "plan": plan,
    }


@router.post("/actors/mapping/merge-execute")
async def execute_actor_mapping_merge(req: ActorMappingMergeRequest, lang: str = "zh-CN"):
    return await _execute_merge(_require_config(), req, lang)


@router.post("/actors/mapping/merge-batch")
async def execute_actor_mapping_batch(req: ActorMappingMergeBatchRequest, lang: str = "zh-CN"):
    config = _require_config()
    preview = await actor_mapping_matches(limit=5000, only_candidates=True, lang=lang)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for group in preview.get("groups") or []:
        mapping_id = str(group.get("mapping_id") or "").strip()
        if not mapping_id:
            continue
        if req.skip_conflicts and group.get("has_tmdb_conflict"):
            skipped.append({
                "mapping_id": mapping_id,
                "name": group.get("display_name") or group.get("canonical_name") or "",
                "reason": "tmdb_conflict",
            })
            continue
        target_actor_id = str(req.target_actor_ids.get(mapping_id) or group.get("target_actor_id") or "").strip()
        if not target_actor_id:
            skipped.append({
                "mapping_id": mapping_id,
                "name": group.get("display_name") or group.get("canonical_name") or "",
                "reason": "missing_target",
            })
            continue
        try:
            results.append(await _execute_merge(
                config,
                ActorMappingMergeRequest(mapping_id=mapping_id, target_actor_id=target_actor_id, dry_run=req.dry_run),
                lang,
            ))
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
        "candidate_count": len(preview.get("groups") or []),
        "executed_count": len(results),
        "updated_count": sum(item.get("updated_count", 0) for item in results),
        "deleted_actor_count": sum(item.get("deleted_actor_count", 0) for item in results),
        "delete_failed_actor_ids": [failure for item in results for failure in item.get("delete_failed_actor_ids", [])],
        "skipped_count": len(skipped),
        "failed_count": len(failures),
        "skipped": skipped,
        "failures": failures,
        "results": results,
    }


@router.get("/actor/{actor_id}/delete-diagnostics")
async def actor_delete_diagnostics(actor_id: str):
    return await _actor_delete_diagnostics(_require_config(), actor_id)


@router.get("/actor/{actor_id}")
async def get_actor(actor_id: str, lang: str = "zh-CN"):
    config = _require_config()
    return {"ok": True, "actor": await _actor_profile(config, actor_id, lang)}


@router.post("/actor/{actor_id}")
async def update_actor(actor_id: str, req: ActorProfileUpdateRequest, lang: str = "zh-CN"):
    config = _require_config()
    raw = await _raw_actor(config, actor_id)
    emby_update_fields = {
        "name": req.name,
        "sort_name": req.sort_name,
        "overview": req.overview,
        "provider_ids": req.provider_ids,
        "birthday": req.birthday,
        "deathday": req.deathday,
        "place_of_birth": req.place_of_birth,
        "gender": req.gender,
        "known_for_department": req.known_for_department,
        "homepage": req.homepage,
    }
    needs_emby_sync = any(value is not None for value in emby_update_fields.values())
    if req.name is not None:
        raw["Name"] = req.name
    if req.sort_name is not None:
        raw["SortName"] = req.sort_name
    if req.overview is not None:
        raw["Overview"] = req.overview
    if req.provider_ids is not None:
        provider_ids = dict(raw.get("ProviderIds") or {})
        for key, value in req.provider_ids.items():
            text = str(value or "").strip()
            if text:
                provider_ids[str(key)] = text
            else:
                for existing in list(provider_ids):
                    if existing.lower() == str(key).lower():
                        provider_ids.pop(existing, None)
        raw["ProviderIds"] = provider_ids
    if req.birthday is not None:
        raw["PremiereDate"] = req.birthday
    if req.deathday is not None:
        raw["EndDate"] = req.deathday
    if req.place_of_birth is not None:
        raw["ProductionLocations"] = [req.place_of_birth] if req.place_of_birth.strip() else []
    if req.gender is not None:
        raw["Gender"] = req.gender
    if req.known_for_department is not None:
        raw["KnownForDepartment"] = req.known_for_department
    if req.homepage is not None:
        raw["Homepage"] = req.homepage

    synced = False
    sync_error = None
    if needs_emby_sync:
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                response = await client.post(
                    f"{_base_url(config)}/emby/Items/{quote(actor_id)}",
                    headers={**_headers(config), "Content-Type": "application/json"},
                    json=raw,
                )
                response.raise_for_status()
                synced = True
        except Exception as exc:
            sync_error = str(exc)
            raise HTTPException(status_code=502, detail=f"同步 Emby 演员资料失败: {sync_error}") from exc

    overrides = _load_profile_overrides()
    override = dict(overrides.get(str(actor_id)) or {})
    for key, value in {"popularity": req.popularity, "external_urls": req.external_urls}.items():
        if value is not None:
            override[key] = value
    identity = dict(override.get("identity_names") or {})
    for key, value in {"jp": req.jp_name, "zh_cn": req.zh_cn_name, "zh_tw": req.zh_tw_name}.items():
        if value is not None:
            identity[key] = value.strip()
    if req.aliases is not None:
        identity["aliases"] = [value.strip() for value in req.aliases if value.strip()]
    if identity:
        override["identity_names"] = identity
    override["updated_at"] = datetime.now(timezone.utc).isoformat()
    overrides[str(actor_id)] = override
    _save_profile_overrides(overrides)
    return {"ok": True, "actor": await _actor_profile(config, actor_id, lang), "synced": synced, "sync_error": sync_error}


@router.post("/actor/{actor_id}/avatar")
async def upload_actor_avatar(actor_id: str, file: UploadFile = File(...), lang: str = "zh-CN"):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="头像文件为空")
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像图片超过 12 MB")
    config = _require_config()
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.post(
            f"{_base_url(config)}/emby/Items/{quote(actor_id)}/Images/Primary",
            headers={**_headers(config), "Content-Type": file.content_type or "image/jpeg"},
            content=content,
        )
        response.raise_for_status()
    return {"ok": True, "actor": await _actor_profile(config, actor_id, lang)}


@router.get("/actor/{actor_id}/movies")
async def get_actor_movies(actor_id: str, limit: int = Query(120, ge=1, le=500), offset: int = Query(0, ge=0)):
    config = _require_config()
    params = {
        "PersonIds": actor_id,
        "Recursive": "true",
        "IncludeItemTypes": "Movie",
        "Fields": "Path,ProviderIds,People,ImageTags,Overview,PremiereDate,DateCreated",
        "StartIndex": offset,
        "Limit": limit,
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
    }
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        response = await client.get(f"{_base_url(config)}/emby/Items", headers=_headers(config), params=params)
        response.raise_for_status()
    payload = response.json()
    items = [media._parse_item(item, config) for item in payload.get("Items") or []]
    return {"items": items, "total": int(payload.get("TotalRecordCount") or len(items)), "limit": limit, "offset": offset}


@router.post("/actor/{actor_id}/avatar-url")
async def set_actor_avatar_from_url(actor_id: str, req: ActorAvatarUrlRequest, lang: str = "zh-CN"):
    """Download an explicitly selected avatar and send it to Emby's person API."""
    config = _require_config()
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="头像地址必须是 HTTP(S) URL")
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, trust_env=False) as client:
            image = await client.get(url, headers={"Accept": "image/*,*/*;q=0.8", "User-Agent": "NOOR/1.0"})
            image.raise_for_status()
            content_type = str(image.headers.get("content-type") or "image/jpeg").split(";", 1)[0].strip()
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="远程地址未返回图片")
            if len(image.content) > 12 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="头像图片超过 12 MB")
            response = await client.post(
                f"{_base_url(config)}/emby/Items/{quote(actor_id)}/Images/Primary",
                headers={**_headers(config), "Content-Type": content_type},
                content=image.content,
            )
            response.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"写入 Emby 头像失败: {exc}") from exc
    return {"ok": True, "actor_id": actor_id, "actor": await _actor_profile(config, actor_id, lang)}


@router.delete("/actor/{actor_id}")
async def delete_actor(actor_id: str):
    config = _require_config()
    diagnostics_before = await _actor_delete_diagnostics(config, actor_id)
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.delete(f"{_base_url(config)}/emby/Items/{quote(actor_id)}", headers=_headers(config))
        if response.is_error:
            diagnostics_after = await _actor_delete_diagnostics(config, actor_id)
            raise HTTPException(
                status_code=502,
                detail={
                    "message": f"Emby 删除演员失败: HTTP {response.status_code}",
                    "status_code": response.status_code,
                    "body": response.text[:1000],
                    "diagnostics_before": diagnostics_before,
                    "diagnostics_after": diagnostics_after,
                },
            )
    overrides = _load_profile_overrides()
    overrides.pop(str(actor_id), None)
    _save_profile_overrides(overrides)
    ignored_ghost_ids = _load_actor_merge_ignored_ghosts()
    ignored_ghost_ids.add(str(actor_id))
    _save_actor_merge_ignored_ghosts(ignored_ghost_ids)
    return {"ok": True, "actor_id": actor_id, "diagnostics_before": diagnostics_before}


def _tmdb_preview_guard(config: dict[str, Any], actor: dict[str, Any]) -> tuple[bool, str]:
    api_key = str(config.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY") or "").strip()
    if not api_key:
        return False, "请先配置 TMDB API Key"
    tmdb_id = str(actor.get("tmdb_id") or actor.get("provider_ids", {}).get("Tmdb") or "").strip()
    if not tmdb_id:
        return False, "演员缺少 TMDB ID"
    return True, ""


async def _tmdb_person(config: dict[str, Any], actor: dict[str, Any], lang: str) -> dict[str, Any]:
    api_key = str(config.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="请先配置 TMDB API Key")
    tmdb_id = str(actor.get("tmdb_id") or actor.get("provider_ids", {}).get("Tmdb") or "").strip()
    if not tmdb_id:
        raise HTTPException(status_code=400, detail="演员缺少 TMDB ID")
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.get(
            f"https://api.themoviedb.org/3/person/{quote(tmdb_id)}",
            params={"api_key": api_key, "language": lang, "append_to_response": "external_ids,translations,images"},
        )
        response.raise_for_status()
        return response.json()


def _tmdb_proposal(person: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    external = person.get("external_ids") or {}
    provider_ids = dict(current.get("provider_ids") or {})
    provider_ids["Tmdb"] = str(person.get("id") or current.get("tmdb_id") or "")
    provider_keys = {
        "imdb_id": "Imdb", "twitter_id": "Twitter", "instagram_id": "Instagram",
        "tiktok_id": "TikTok", "youtube_id": "YouTube", "wikidata_id": "Wikidata",
        "facebook_id": "Facebook",
    }
    for source_key, provider_key in provider_keys.items():
        value = str(external.get(source_key) or "").strip().lstrip("@")
        if value:
            provider_ids[provider_key] = value
    external_urls = {**dict(current.get("external_urls") or {}), **_tmdb_external_urls(external, provider_ids["Tmdb"])}
    if person.get("homepage"):
        external_urls["homepage"] = person["homepage"]
    overview, overview_links = _overview_external_urls(person.get("biography"))
    external_urls = {**overview_links, **external_urls}
    identity_names = _tmdb_identity_names(person)
    profile = str(person.get("profile_path") or "")
    return {
        "name": person.get("name") or current.get("name"),
        "sort_name": person.get("name") or current.get("sort_name"),
        "overview": overview or current.get("overview") or "",
        "provider_ids": provider_ids,
        "tmdb_id": provider_ids.get("Tmdb", ""),
        "imdb_id": provider_ids.get("Imdb", ""),
        "jp_name": identity_names["jp"],
        "zh_cn_name": identity_names["zh_cn"],
        "zh_tw_name": identity_names["zh_tw"],
        "aliases": identity_names["aliases"],
        "birthday": person.get("birthday") or "",
        "deathday": person.get("deathday") or "",
        "place_of_birth": person.get("place_of_birth") or "",
        "gender": _tmdb_gender_label(person.get("gender")),
        "known_for_department": person.get("known_for_department") or "",
        "popularity": person.get("popularity"),
        "homepage": person.get("homepage") or "",
        "external_urls": external_urls,
        "image_url": f"https://image.tmdb.org/t/p/original{profile}" if profile else "",
    }


@router.post("/actor/{actor_id}/metadata/tmdb-preview")
async def preview_actor_tmdb_metadata(actor_id: str, lang: str = "zh-CN"):
    config = _require_config()
    current = await _actor_profile(config, actor_id, lang)
    ready, message = _tmdb_preview_guard(config, current)
    if not ready:
        return {"ok": False, "message": message, "current": current, "proposal": None, "diffs": []}
    proposal = _tmdb_proposal(await _tmdb_person(config, current, lang), current)
    labels = {"name": "名称", "overview": "简介", "tmdb_id": "TMDB", "imdb_id": "IMDb", "birthday": "出生日期", "place_of_birth": "出生地", "homepage": "主页", "image_url": "头像"}
    diffs = [{"field": key, "label": label, "current": current.get(key) or "", "proposed": proposal.get(key) or ""} for key, label in labels.items() if (current.get(key) or "") != (proposal.get(key) or "")]
    return {"ok": True, "current": current, "proposal": proposal, "diffs": diffs}


@router.post("/actor/{actor_id}/metadata/tmdb-apply")
async def apply_actor_tmdb_metadata(actor_id: str, req: ActorTmdbApplyRequest, lang: str = "zh-CN"):
    preview = await preview_actor_tmdb_metadata(actor_id, lang)
    if not preview.get("ok"):
        raise HTTPException(status_code=400, detail=preview.get("message", "TMDB 资料补全不可用"))
    current = preview["current"]
    proposal = preview["proposal"]
    current_overview, current_overview_links = _overview_external_urls(current.get("overview"))
    next_external_urls = {
        **dict(current.get("external_urls") or {}),
        **current_overview_links,
        **dict(proposal.get("external_urls") or {}),
    }
    update = ActorProfileUpdateRequest(
        name=proposal["name"] if req.apply_name else None,
        sort_name=proposal["sort_name"] if req.apply_name else None,
        jp_name=proposal.get("jp_name") or None,
        zh_cn_name=proposal.get("zh_cn_name") or None,
        zh_tw_name=proposal.get("zh_tw_name") or None,
        aliases=proposal.get("aliases") or None,
        overview=proposal["overview"] if req.apply_overview else current_overview,
        provider_ids=proposal["provider_ids"] if req.apply_provider_ids else None,
        birthday=proposal["birthday"], deathday=proposal["deathday"], place_of_birth=proposal["place_of_birth"],
        gender=proposal["gender"], known_for_department=proposal["known_for_department"], popularity=proposal["popularity"],
        homepage=proposal["homepage"], external_urls=next_external_urls,
    )
    result = await update_actor(actor_id, update, lang)
    avatar_synced = False
    avatar_sync_error = None
    if req.apply_avatar and proposal.get("image_url"):
        try:
            avatar_result = await set_actor_avatar_from_url(actor_id, ActorAvatarUrlRequest(url=proposal["image_url"]), lang)
            result["actor"] = avatar_result["actor"]
            avatar_synced = True
        except Exception as exc:
            avatar_sync_error = str(exc)
            overrides = _load_profile_overrides()
            override = dict(overrides.get(str(actor_id)) or {})
            override["image_url"] = proposal["image_url"]
            overrides[str(actor_id)] = override
            _save_profile_overrides(overrides)
            result["actor"] = await _actor_profile(_require_config(), actor_id, lang)
    return {"ok": True, **result, "preview": preview, "avatar_synced": avatar_synced, "avatar_sync_error": avatar_sync_error}
