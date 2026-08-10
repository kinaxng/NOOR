"""Emby actor management endpoints recovered independently from media_library.

This module deliberately builds on the still-working media-library adapter
instead of replacing its recovered bytecode.  It is safe to evolve while the
rest of that adapter is reconstructed.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.endpoints import media_library as media
from app.core.runtime_paths import data_path


router = APIRouter(prefix="/api/media-library", tags=["media-library-actors"])


class ActorMappingSourceRequest(BaseModel):
    mdc_ng_path: str


class ActorAvatarUrlRequest(BaseModel):
    url: str


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


def _is_actor_name(value: str | None) -> bool:
    name = str(value or "").strip()
    if not name or name.isdecimal() or re.fullmatch(r"[-_ .·・]+", name):
        return False
    return not bool(re.fullmatch(r"\[(?:red|deleted|unknown)\]", name, flags=re.IGNORECASE))


def _mapping_path(config: dict[str, Any]) -> Path | None:
    explicit = str(config.get("mdc_ng_path") or _mapping_settings().get("mdc_ng_path") or "").strip()
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            # MDC-NG normally mounts its persistent directory at ``data``;
            # depending on whether the user points at the project root or the
            # mounted data directory, the mapping lives in one of these forms.
            for relative in ("data/data/mapping_actor.xml", "data/mapping_actor.xml", "mapping_actor.xml"):
                mapped = candidate / relative
                if mapped.is_file():
                    return mapped
            return candidate / "data/data/mapping_actor.xml"
        return candidate
    fallback = data_path() / "media_actor_mapping.xml"
    return fallback if fallback.is_file() else None


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
    path = _mapping_path(config)
    if not path or not path.is_file():
        return []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    records: list[dict[str, Any]] = []
    for element in root.iter():
        values = _element_values(element)
        jp = _first(values, "jp", "name_jp", "japanese", "ja")
        zh_cn = _first(values, "zh_cn", "name_zh_cn", "simplified", "cn")
        zh_tw = _first(values, "zh_tw", "name_zh_tw", "traditional", "tw")
        aliases = _first(values, "aliases", "alias", "other_name", "other_names", "keyword")
        if not (jp or zh_cn or zh_tw):
            continue
        names = [name for name in [jp, zh_cn, zh_tw] if name]
        names.extend(part.strip() for part in re.split(r"[|,;/]", aliases) if part.strip())
        key = tuple(sorted({_normalize_name(name) for name in names if _normalize_name(name)}))
        if not key:
            continue
        record = {"jp": jp, "zh_cn": zh_cn, "zh_tw": zh_tw, "aliases": aliases, "names": names}
        if not any(record["names"] == prior["names"] for prior in records):
            records.append(record)
    return records


def _mapping_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in _mapping_records(config):
        for name in record["names"]:
            key = _normalize_name(name)
            if key:
                index.setdefault(key, record)
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
    display_name = str(record.get(lang) or record.get("zh_cn") or record.get("jp") or name)
    return {
        "id": actor_id,
        "name": name,
        "sort_name": sort_name,
        "display_name": display_name,
        "overview": str(raw.get("Overview") or ""),
        "provider_ids": raw.get("ProviderIds") or {},
        "avatar_url": avatar_url,
        "emby_url": emby_url,
        "name_jp": record.get("jp", ""),
        "name_zh_cn": record.get("zh_cn", ""),
        "name_zh_tw": record.get("zh_tw", ""),
        "aliases": record.get("aliases", ""),
        "date_created": raw.get("DateCreated"),
    }


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
    lang: str = Query("zh_cn", pattern="^(zh_cn|zh_tw|jp)$"),
):
    config = _require_config()
    try:
        actors, total = await _list_actors(config, limit=limit, offset=offset, query=q, sort_by=sort_by, sort_order=sort_order, lang=lang)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"获取 Emby 演员失败: {exc}") from exc
    return {"actors": actors, "total": total, "limit": limit, "offset": offset}


@router.get("/actors/mapping/status")
async def actor_mapping_status():
    # Mapping setup is useful before Emby is configured, so do not require a
    # live media server for this status endpoint.
    config = media._load_config()
    path = _mapping_path(config)
    records = _mapping_records(config)
    return {
        "configured_path": str(path) if path else "",
        "configured_root": str(config.get("mdc_ng_path") or _mapping_settings().get("mdc_ng_path") or ""),
        "exists": bool(path and path.is_file()),
        "record_count": len(records),
        "source": "mdc-ng" if (config.get("mdc_ng_path") or _mapping_settings().get("mdc_ng_path")) else "noor-local",
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
    config["mdc_ng_path"] = root
    resolved = _mapping_path(config)
    if not resolved or not resolved.is_file():
        raise HTTPException(status_code=400, detail="在该路径下未找到 data/data/mapping_actor.xml")
    _save_mapping_settings({"mdc_ng_path": root})
    return {
        "ok": True,
        "configured_path": str(resolved),
        "record_count": len(_mapping_records(config)),
    }


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


@router.get("/actor/{actor_id}")
async def get_actor(actor_id: str, lang: str = Query("zh_cn", pattern="^(zh_cn|zh_tw|jp)$")):
    config = _require_config()
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        # Emby exposes person entities through a user's item view on a number
        # of deployments.  The bare /Items/{id} form can return 404 even
        # though the same person appears in /Persons and has related movies.
        item_prefix = f"/emby/Users/{quote(str(config.get('user_id') or ''))}/Items" if config.get("user_id") else "/emby/Items"
        response = await client.get(
            f"{_base_url(config)}{item_prefix}/{quote(actor_id)}",
            headers=_headers(config),
            params={"Fields": "Overview,ProviderIds,ImageTags,DateCreated,SortName"},
        )
        if response.status_code == 404 and config.get("user_id"):
            response = await client.get(
                f"{_base_url(config)}/emby/Items/{quote(actor_id)}",
                headers=_headers(config),
                params={"Fields": "Overview,ProviderIds,ImageTags,DateCreated,SortName"},
            )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="未找到演员")
        response.raise_for_status()
    return {"ok": True, "actor": _actor_from_emby(response.json(), config, _mapping_index(config), lang=lang)}


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
async def set_actor_avatar_from_url(actor_id: str, req: ActorAvatarUrlRequest):
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
    return {"ok": True, "actor_id": actor_id}
