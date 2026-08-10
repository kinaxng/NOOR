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

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.endpoints import media_library as media


router = APIRouter(prefix="/api/media-library", tags=["media-library-recovery"])


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


def _parse_item(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    item = media._parse_item(raw, config)
    original_path = str(item.get("path") or "")
    translated_path = _host_path(original_path)
    if translated_path != original_path:
        item["emby_path"] = original_path
        item["path"] = translated_path
    return item


async def _fetch_items(config: dict[str, Any], *, library_id: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {
        "IncludeItemTypes": "Movie",
        "Recursive": "true",
        "Fields": "Path,ProviderIds,People,ImageTags,Overview,PremiereDate,DateCreated,Genres,Tags,MediaSources",
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
    return {"items": filtered, "total": total if not (filter or q) else len(filtered)}


@router.get("/item/{item_id}")
async def get_item(item_id: str):
    config = _config()
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.get(
            f"{_user_items_url(config)}/{quote(item_id)}",
            headers=_headers(config),
            params={"Fields": "Path,ProviderIds,People,ImageTags,Overview,PremiereDate,DateCreated,Genres,Tags,MediaSources"},
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="未找到媒体项目")
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"获取媒体项目失败: {exc}") from exc
    return _parse_item(response.json(), config)
