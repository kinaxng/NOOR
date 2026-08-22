"""Fallback Emby media adapter for servers where MediaFolders returns 502.

The recovered legacy adapter depends on ``/Library/MediaFolders``.  This is
not available on the configured Emby instance, while the authenticated user
item and view APIs work normally.  Keep the fallback narrow and register it
before the legacy router so hardlink and mutation endpoints remain untouched.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.endpoints import media_library as media
from app.api.endpoints.media_library_item_detail import build_stream_url_for_server_impl, get_main_nfo_impl, _sort_siblings


router = APIRouter(prefix="/api/media-library", tags=["media-library-recovery"])
DETAIL_FIELDS = "Path,ProviderIds,People,ImageTags,BackdropImageTags,Overview,OriginalTitle,PremiereDate,DateCreated,Genres,Studios,Tags,MediaSources,ParentId"


def _config(value: dict[str, Any] | None = None) -> dict[str, Any]:
    config = value if value is not None else media._load_config()
    if not config.get("server_url") or not config.get("api_key"):
        raise HTTPException(status_code=503, detail="媒体库适配器未配置，请在设置中配置 Emby / Jellyfin 服务器地址")
    return config


def _base(config: dict[str, Any]) -> str:
    return str(media._server_url(config)).rstrip("/")


def _headers(config: dict[str, Any]) -> dict[str, str]:
    return media._headers(str(config.get("api_key") or ""))


def _user_items_url(config: dict[str, Any]) -> str:
    user_id = str(config.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="媒体库未配置 Emby 用户 ID，无法使用恢复适配器")
    return f"{_base(config)}/emby/Users/{quote(user_id)}/Items"


def _matches_filter(item: dict[str, Any], filter_name: str | None) -> bool:
    if not filter_name:
        return True
    tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
    if filter_name == "cracked":
        return bool(tags.get("is_cracked"))
    if filter_name == "chinese":
        return bool(tags.get("has_chinese"))
    if filter_name == "leaked":
        return tags.get("release_type_key") == "leaked"
    if filter_name == "uncensored":
        return tags.get("release_type_key") == "uncensored"
    return True


def _matches_query(item: dict[str, Any], query: str | None) -> bool:
    needle = str(query or "").strip().casefold()
    if not needle:
        return True
    haystack = " ".join(
        str(item.get(key) or "") for key in ("name", "code", "original_title", "title")
    ).casefold()
    return needle in haystack


def _path_mappings() -> list[tuple[str, str]]:
    """Return container-to-host mappings without requiring Emby to know the host.

    A JSON object in ``NOOR_MEDIA_PATH_MAPPINGS`` takes precedence, for example
    ``{\"/data\": \"/mnt/media\"}``.  The recovery host has its NAS data mount at
    ``~/Videos``; use that conventional mapping only when the mount exists.
    """
    mappings: list[tuple[str, str]] = []
    raw = os.environ.get("NOOR_MEDIA_PATH_MAPPINGS", "").strip()
    if raw:
        try:
            configured = json.loads(raw)
            if isinstance(configured, dict):
                mappings.extend((str(source), str(target)) for source, target in configured.items())
        except json.JSONDecodeError:
            pass
    videos_root = Path.home() / "Videos"
    if videos_root.is_dir():
        mappings.append(("/data", str(videos_root)))
        mappings.append(("/volume1/data", str(videos_root)))
    return sorted(((source.rstrip("/"), target.rstrip("/")) for source, target in mappings if source and target), key=lambda item: len(item[0]), reverse=True)


def _host_path(path: Any) -> str:
    original = str(path or "").strip()
    if not original or Path(original).exists():
        return original
    for source, target in _path_mappings():
        if original == source or original.startswith(source + "/"):
            return target + original[len(source):]
    return original


def _map_host_path(server_path: str | None, config: dict[str, Any]) -> str | None:
    mapped = media._map_path(server_path, config)
    return _host_path(mapped) if mapped else mapped


def _parse_item(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    item = media._parse_item(raw, config)
    original_path = str(item.get("path") or "")
    translated_path = _host_path(original_path)
    if translated_path != original_path:
        item["emby_path"] = original_path
        item["path"] = translated_path
    people = raw.get("People") if isinstance(raw.get("People"), list) else []
    item.update({
        "file_path": item.get("path"),
        "original_title": raw.get("OriginalTitle"),
        "overview": raw.get("Overview"),
        "premiered": raw.get("PremiereDate"),
        "genres": raw.get("Genres") if isinstance(raw.get("Genres"), list) else [],
        "studios": [
            value.get("Name")
            for value in (raw.get("Studios") or [])
            if isinstance(value, dict) and value.get("Name")
        ],
        "actors": [
            {"name": value.get("Name"), "role": value.get("Role")}
            for value in people
            if isinstance(value, dict) and value.get("Name") and value.get("Type") == "Actor"
        ],
        "directors": [
            value.get("Name")
            for value in people
            if isinstance(value, dict) and value.get("Name") and value.get("Type") == "Director"
        ],
        "provider_ids": raw.get("ProviderIds") if isinstance(raw.get("ProviderIds"), dict) else {},
    })
    return item


def _media_source_path(raw: dict[str, Any], config: dict[str, Any]) -> str | None:
    media_sources = raw.get("MediaSources") if isinstance(raw.get("MediaSources"), list) else []
    file_path = None
    for source in media_sources:
        if isinstance(source, dict) and source.get("Type") == "Default":
            file_path = source.get("Path")
            break
    if not file_path and media_sources and isinstance(media_sources[0], dict):
        file_path = media_sources[0].get("Path")
    if not file_path:
        file_path = raw.get("Path")
    return _map_host_path(str(file_path), config) if file_path else None


def _text_of(root: ET.Element, *names: str) -> str:
    for name in names:
        node = root.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return ""


def _texts_of(root: ET.Element, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        for node in root.findall(name):
            if node.text and node.text.strip():
                values.append(node.text.strip())
    return values


def _parse_nfo(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    nfo_path = Path(path)
    if not nfo_path.is_file():
        return None
    try:
        root = ET.fromstring(nfo_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ET.ParseError):
        return {"path": str(nfo_path)}
    unique_genres = []
    for value in _texts_of(root, "genre", "tag"):
        if value not in unique_genres:
            unique_genres.append(value)
    return {
        "path": str(nfo_path),
        "title": _text_of(root, "title"),
        "originaltitle": _text_of(root, "originaltitle", "original_title"),
        "num": _text_of(root, "num", "id", "code"),
        "year": _text_of(root, "year"),
        "premiered": _text_of(root, "premiered", "releasedate", "release"),
        "rating": _text_of(root, "rating"),
        "votes": _text_of(root, "votes"),
        "director": _text_of(root, "director"),
        "set": _text_of(root, "set"),
        "outline": _text_of(root, "outline"),
        "plot": _text_of(root, "plot"),
        "maker": _text_of(root, "maker", "studio"),
        "label": _text_of(root, "label"),
        "publisher": _text_of(root, "publisher"),
        "genres": unique_genres,
    }


def _sibling_from_raw(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    file_path = _media_source_path(raw, config)
    media_sources = raw.get("MediaSources") if isinstance(raw.get("MediaSources"), list) else []
    selected_source = next((source for source in media_sources if source.get("Type") == "Default"), None)
    if selected_source is None and media_sources:
        selected_source = media_sources[0]
    container = str((selected_source or {}).get("Container") or Path(file_path or "").suffix.lstrip("."))
    item_id = str(raw.get("Id") or "")
    return {
        "id": item_id,
        "label": raw.get("Name") or (Path(file_path).name if file_path else ""),
        "file_path": file_path,
        "name": raw.get("Name") or (Path(file_path).name if file_path else ""),
        "media_source_id": (selected_source or {}).get("Id"),
        "container": container,
        "stream_url": build_stream_url_for_server_impl(
            _base(config), str(config.get("api_key") or ""), item_id,
            (selected_source or {}).get("Id"), container,
        ) if item_id else None,
    }


async def _fetch_item_raw(config: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.get(
            f"{_user_items_url(config)}/{quote(item_id)}",
            headers=_headers(config),
            params={"Fields": DETAIL_FIELDS},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def _fetch_sibling_raws(config: dict[str, Any], parent_id: str | None, current_id: str) -> list[dict[str, Any]]:
    if not parent_id:
        return []
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(
                _user_items_url(config),
                headers=_headers(config),
                params={
                    "ParentId": parent_id,
                    "Recursive": "false",
                    "Fields": "MediaSources,Path",
                    "Limit": 100,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return []
    return [
        item for item in response.json().get("Items") or []
        if isinstance(item, dict)
        and item.get("Id") != current_id
        and (item.get("Type") in ("Movie", "Video") or item.get("MediaType") == "Video")
    ]


async def _detail_from_raw(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    item_id = str(raw.get("Id") or "")
    file_path = _media_source_path(raw, config)
    media_sources = raw.get("MediaSources") if isinstance(raw.get("MediaSources"), list) else []
    selected_source = next((source for source in media_sources if source.get("Type") == "Default"), None)
    if selected_source is None and media_sources:
        selected_source = media_sources[0]
    media_source_id = (selected_source or {}).get("Id")
    media_container = str((selected_source or {}).get("Container") or Path(file_path or "").suffix.lstrip("."))
    sibling_raws = await _fetch_sibling_raws(config, str(raw.get("ParentId") or ""), item_id)
    siblings = _sort_siblings([_sibling_from_raw(item, config) for item in sibling_raws])
    studios = [s.get("Name") for s in raw.get("Studios", []) if isinstance(s, dict) and s.get("Name")]
    actors = [
        {"name": person.get("Name"), "role": person.get("Role")}
        for person in (raw.get("People") or [])
        if isinstance(person, dict) and person.get("Name") and person.get("Type") == "Actor"
    ]
    sibling_tags = []
    for sibling in siblings:
        sibling_tags.append(media._parse_tags(sibling.get("name") or sibling.get("label") or "", studios, sibling.get("file_path")))
        sibling["tags"] = sibling_tags[-1]

    image_tags = raw.get("ImageTags") if isinstance(raw.get("ImageTags"), dict) else {}
    backdrop_tags = raw.get("BackdropImageTags") if isinstance(raw.get("BackdropImageTags"), list) else []
    poster_url = f"{_base(config)}/emby/Items/{item_id}/Images/Primary?tag={image_tags['Primary']}" if image_tags.get("Primary") else None
    if not poster_url and image_tags.get("Thumb"):
        poster_url = f"{_base(config)}/emby/Items/{item_id}/Images/Thumb?tag={image_tags['Thumb']}"
    backdrop_url = None
    if backdrop_tags:
        backdrop_url = f"{_base(config)}/emby/Items/{item_id}/Images/Backdrop?tag={backdrop_tags[0]}"
    elif image_tags.get("Thumb"):
        backdrop_url = f"{_base(config)}/emby/Items/{item_id}/Images/Thumb?tag={image_tags['Thumb']}"

    tags = media._parse_tags(str(raw.get("Name") or ""), studios, file_path)
    if any(tag.get("has_chinese") for tag in sibling_tags):
        tags["has_chinese"] = True
    if any(tag.get("is_cracked") for tag in sibling_tags):
        tags["is_cracked"] = True
    if any(tag.get("is_leaked") for tag in sibling_tags):
        tags["is_leaked"] = True
    if any(tag.get("has_facefusion") for tag in sibling_tags):
        tags["has_facefusion"] = True

    main_nfo = get_main_nfo_impl(file_path) if file_path else None
    nfo = _parse_nfo(main_nfo)
    return {
        "id": item_id,
        "name": raw.get("Name", "Unknown"),
        "type": raw.get("Type", "Movie"),
        "media_type": raw.get("MediaType", "Video"),
        "file_path": file_path,
        "path": file_path,
        "emby_path": raw.get("Path"),
        "stream_url": build_stream_url_for_server_impl(
            _base(config), str(config.get("api_key") or ""), item_id, media_source_id, media_container,
        ),
        "date_created": raw.get("DateCreated"),
        "premiered": raw.get("PremiereDate"),
        "overview": raw.get("Overview"),
        "original_title": raw.get("OriginalTitle"),
        "studios": studios,
        "genres": raw.get("Genres", []) if isinstance(raw.get("Genres"), list) else [],
        "poster_path": poster_url,
        "backdrop_path": backdrop_url,
        "tags": tags,
        "actors": actors,
        "directors": [
            person.get("Name")
            for person in (raw.get("People") or [])
            if isinstance(person, dict) and person.get("Name") and person.get("Type") == "Director"
        ],
        "provider_ids": raw.get("ProviderIds") if isinstance(raw.get("ProviderIds"), dict) else {},
        "siblings": siblings,
        "variant_count": len(siblings) + (1 if file_path else 0),
        "main_nfo": main_nfo,
        "nfo": nfo,
    }


async def _fetch_items(config: dict[str, Any], *, library_id: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {
        "IncludeItemTypes": "Movie",
        "Recursive": "true",
        "Fields": "Path,ProviderIds,People,ImageTags,Overview,OriginalTitle,PremiereDate,DateCreated,Genres,Studios,Tags,MediaSources",
        "StartIndex": max(0, offset),
        "Limit": max(1, min(limit, 500)),
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
    }
    if library_id:
        params["ParentId"] = library_id
    async with httpx.AsyncClient(timeout=45, trust_env=False) as client:
        response = await client.get(_user_items_url(config), headers=_headers(config), params=params)
        response.raise_for_status()
    payload = response.json()
    raw_items = payload.get("Items") or []
    items = [_parse_item(raw, config) for raw in raw_items if isinstance(raw, dict)]
    return items, int(payload.get("TotalRecordCount") or len(items))


@router.post("/test")
async def test_connection(config: dict[str, Any] | None = None):
    cfg = _config(config)
    try:
        items, total = await _fetch_items(cfg, library_id=None, limit=1, offset=0)
        return {"ok": True, "message": f"已连接至 {cfg.get('server_url', 'Emby/Jellyfin')}", "libraries": [], "sample_count": len(items), "total": total}
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"连接失败: {exc}", "libraries": []}


@router.get("/libraries")
async def get_libraries():
    config = _config()
    user_id = str(config.get("user_id") or "").strip()
    if not user_id:
        return {"libraries": []}
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            response = await client.get(f"{_base(config)}/emby/Users/{quote(user_id)}/Views", headers=_headers(config))
            response.raise_for_status()
        views = response.json().get("Items") or []
        return {"libraries": [{"id": str(view.get("Id") or ""), "name": str(view.get("Name") or ""), "collection_type": str(view.get("CollectionType") or "")} for view in views if isinstance(view, dict)]}
    except httpx.HTTPError:
        return {"libraries": []}


@router.get("/items")
async def get_items(
    library_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    filter: str | None = None,
    q: str | None = None,
    force_refresh: bool = False,
):
    del force_refresh
    config = _config()
    try:
        items, total = await _fetch_items(config, library_id=library_id, limit=limit, offset=offset)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"获取媒体失败: {exc}") from exc
    # Emby performs pagination before these local derived-tag filters.  Return
    # its authoritative total when no local filtering is requested.
    filtered = [item for item in items if _matches_filter(item, filter) and _matches_query(item, q)]
    return {
        "items": filtered,
        "total": total if not (filter or q) else len(filtered),
        "offset": offset,
        "limit": limit,
    }


@router.get("/item/{item_id}")
async def get_item(item_id: str):
    config = _config()
    try:
        raw = await _fetch_item_raw(config, item_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"获取媒体项目失败: {exc}") from exc
    if raw is None:
        raise HTTPException(status_code=404, detail="未找到媒体项目")
    return await _detail_from_raw(raw, config)
