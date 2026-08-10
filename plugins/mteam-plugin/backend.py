from __future__ import annotations

import re
from typing import Any

import httpx

from app.plugins.contracts import PluginTestResult


PLUGIN_ID = "mteam-plugin"
DEFAULT_API_BASE = "https://api.m-team.cc"


def _base(config: dict[str, Any]) -> str:
    return str(config.get("api_base") or DEFAULT_API_BASE).strip().rstrip("/")


def _key(config: dict[str, Any]) -> str:
    return str(config.get("api_key") or "").strip()


def _timeout(config: dict[str, Any]) -> float:
    try:
        return max(5.0, min(float(config.get("timeout") or 20), 120.0))
    except (TypeError, ValueError):
        return 20.0


def _page_size(config: dict[str, Any], value: Any = None) -> int:
    try:
        return max(5, min(int(value or config.get("page_size") or 30), 100))
    except (TypeError, ValueError):
        return 30


def _headers(config: dict[str, Any]) -> dict[str, str]:
    api_key = _key(config)
    if not api_key:
        raise ValueError("请先填写 M-Team API Key")
    return {"Accept": "application/json", "Content-Type": "application/json", "x-api-key": api_key, "User-Agent": "NOOR-MTeam-Plugin/0.1"}


def _code(value: Any) -> str:
    text = str(value or "").upper().replace("_", "-")
    match = re.search(r"\b([A-Z]{2,10})[- ]?(\d{2,8})\b", text)
    return f"{match.group(1)}-{match.group(2)}" if match else ""


def _number(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for path in (("data", "data"), ("data", "items"), ("data",), ("items",)):
        current: Any = payload
        for key in path:
            current = current.get(key) if isinstance(current, dict) else None
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
    return []


def _download_url(config: dict[str, Any], item: dict[str, Any]) -> str:
    for key in ("downloadUrl", "download_url", "url", "torrentUrl", "torrent_url"):
        value = str(item.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    torrent_id = str(item.get("id") or item.get("torrentId") or "").strip()
    passkey = str(config.get("passkey") or "").strip()
    if torrent_id and passkey:
        return f"https://kp.m-team.cc/download/{torrent_id}/{passkey}"
    return ""


def _normalize(config: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    title = str(item.get("name") or item.get("title") or "").strip()
    torrent_id = str(item.get("id") or item.get("torrentId") or "").strip()
    if not title or not torrent_id:
        return None
    url = _download_url(config, item)
    code = _code(item.get("smallDescr") or item.get("description") or title)
    size = _number(item.get("size") or item.get("sizeBytes") or item.get("fileSize"))
    discount = str(item.get("discount") or item.get("discountType") or "")
    tags = ["PT"]
    if discount:
        tags.append(discount)
    if bool(item.get("sticky")):
        tags.append("置顶")
    subtitle = " · ".join(part for part in (str(item.get("createdDate") or item.get("created_at") or ""), str(item.get("status") or "")) if part)
    return {
        "id": f"mteam:{torrent_id}",
        "kind": "torrent",
        "query_key": code or title,
        "title": title,
        "subtitle": subtitle,
        "url": url,
        "size_bytes": size,
        "file_count": _number(item.get("numFiles") or item.get("fileCount")),
        "tags": tags,
        "cover_url": str(item.get("poster") or item.get("image") or item.get("cover") or ""),
        "source_url": str(item.get("detailUrl") or item.get("detail_url") or ""),
        "features": {"has_subtitle": False, "is_cracked": False, "is_private_tracker": True},
        "requirements": {"accepts_private_torrent": True, "accepts_http_torrent": True},
        "compatible_downloaders": ["qbittorrent", "transmission"],
        "preferred_downloader": "qbittorrent",
        "metadata": {"source_plugin": PLUGIN_ID, "torrent_id": torrent_id, "video_code": code, "site": "M-Team", "raw": item},
    }


async def _request(config: dict[str, Any], endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_timeout(config), follow_redirects=True, trust_env=False) as client:
        response = await client.post(f"{_base(config)}{endpoint}", headers=_headers(config), json=body)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        detail = payload.get("message") if isinstance(payload, dict) else ""
        raise ValueError(f"M-Team API 请求失败 ({response.status_code})：{detail or response.text[:240]}")
    if not isinstance(payload, dict):
        raise ValueError("M-Team API 返回了无效响应")
    if payload.get("code") not in (None, 0, "0", 200):
        raise ValueError(str(payload.get("message") or payload.get("code")))
    return payload


async def search_resources(query: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    keyword = str(query.get("keyword") or query.get("q") or query.get("code") or query.get("number") or "").strip()
    if not keyword:
        return {"items": []}
    page = max(1, _number(query.get("page")) or 1)
    payload = await _request(config, "/api/torrent/search", {
        "mode": "normal", "categories": [], "visible": 1, "keyword": keyword,
        "pageNumber": page, "pageSize": _page_size(config, query.get("limit")),
    })
    resources = [_normalize(config, item) for item in _items(payload)]
    return {"items": [item for item in resources if item], "raw": payload}


async def resolve_resource_download(resource: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    url = str(resource.get("url") or "").strip()
    if not url:
        raise ValueError("M-Team 资源没有可用下载地址；请在插件配置中填写 Passkey 或确认 API Key 权限")
    return {"item": resource, "url": url}


async def test(config: dict[str, Any]) -> PluginTestResult:
    try:
        payload = await _request(config, "/api/torrent/search", {"mode": "normal", "categories": [], "visible": 1, "keyword": "", "pageNumber": 1, "pageSize": 1})
        return PluginTestResult(ok=True, message="mteam connected", details={"items": len(_items(payload))})
    except Exception as exc:
        return PluginTestResult(ok=False, message=f"mteam failed: {exc}")


async def handle_action(action: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if action in {"search", "resource_search"}:
        return await search_resources(payload, config)
    if action == "test":
        result = await test(config)
        return {"ok": result.ok, "message": result.message, "details": result.details or {}}
    raise ValueError(f"unsupported action: {action}")
