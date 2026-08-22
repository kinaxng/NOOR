from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.plugins.contracts import DashboardWidget, PluginManifest, PluginTestResult


def _text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return str(child.text or "").strip() if child is not None else ""


async def fetch_rss_items(
    manifest: PluginManifest,
    config: dict[str, Any],
    *,
    limit: int = 30,
    force_refresh: bool = False,
) -> dict[str, Any]:
    del force_refresh
    url = str(config.get("rss_url") or config.get("url") or "").strip()
    if not url:
        raise ValueError("rss_url is required")
    timeout = max(1.0, float(config.get("timeout") or 20))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False) as client:
        response = await client.get(url)
        response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise ValueError("invalid RSS response") from exc
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item")[: max(0, int(limit))]:
        enclosure = node.find("enclosure")
        download_url = enclosure.attrib.get("url", "").strip() if enclosure is not None else ""
        published = _text(node, "pubDate")
        try:
            published_at = parsedate_to_datetime(published).isoformat() if published else ""
        except (TypeError, ValueError, OverflowError):
            published_at = published
        link = _text(node, "link")
        items.append({
            "id": _text(node, "guid") or link or _text(node, "title"),
            "title": _text(node, "title"),
            "link": link,
            "url": link,
            "description": _text(node, "description"),
            "published_at": published_at,
            "download_url": download_url,
            "enclosure_url": download_url,
            "provider": manifest.id,
        })
    return {"items": items, "total": len(items), "source": manifest.id}


async def submit_download(manifest: PluginManifest, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("downloader plugin missing submit_download handler")


async def test_plugin(manifest: PluginManifest, config: dict[str, Any]) -> PluginTestResult:
    url = str(config.get("test_url") or config.get("base_url") or config.get("rss_url") or "").strip()
    if not url:
        return PluginTestResult(ok=True, message=f"{manifest.name or manifest.id} 配置可用")
    timeout = max(1.0, float(config.get("timeout") or 10))
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return PluginTestResult(ok=False, message=str(exc))
    return PluginTestResult(ok=True, message=f"HTTP {response.status_code}")


async def build_widget(manifest: PluginManifest, config: dict[str, Any]) -> DashboardWidget | None:
    del config
    widget = manifest.contributions.get("dashboard_widget") if isinstance(manifest.contributions, dict) else None
    if not isinstance(widget, dict):
        return None
    return DashboardWidget(
        plugin_id=manifest.id,
        key=str(widget.get("key") or manifest.id),
        title=str(widget.get("title") or widget.get("label") or manifest.name or manifest.id),
        badge=str(widget.get("badge") or ""),
        payload=dict(widget.get("payload") or {}),
    )


async def search_subtitles_for_plugin(
    manifest: PluginManifest,
    config: dict[str, Any],
    video_code: str,
) -> list[dict[str, Any]]:
    del manifest, config, video_code
    return []
