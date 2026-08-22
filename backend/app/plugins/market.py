from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.plugins.runtime_paths import PLUGINS_DIR


class MarketError(RuntimeError):
    pass


def _index_candidates(repo_url: str) -> list[str]:
    value = str(repo_url or "").strip().rstrip("/")
    if not value:
        return []
    parsed = urlparse(value)
    candidates = [value] if parsed.path.endswith(".json") else []
    if parsed.netloc == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            owner, repo = parts[:2]
            repo = repo.removesuffix(".git")
            candidates.extend([
                f"https://raw.githubusercontent.com/{owner}/{repo}/main/plugins.json",
                f"https://raw.githubusercontent.com/{owner}/{repo}/main/index.json",
                f"https://raw.githubusercontent.com/{owner}/{repo}/master/plugins.json",
                f"https://raw.githubusercontent.com/{owner}/{repo}/master/index.json",
            ])
    candidates.extend([f"{value}/plugins.json", f"{value}/index.json"])
    return list(dict.fromkeys(candidates))


def _market_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("plugins", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, dict)]
    return []


async def fetch_repo_index(repo_url: str) -> list[dict[str, Any]]:
    candidates = _index_candidates(repo_url)
    if not candidates:
        raise MarketError("plugin repository URL is required")
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for url in candidates:
            try:
                response = await client.get(url)
                response.raise_for_status()
                items = _market_items(response.json())
                if not items:
                    raise MarketError("plugin index contains no items")
                return items
            except (httpx.HTTPError, json.JSONDecodeError, ValueError, MarketError) as exc:
                errors.append(f"{url}: {exc}")
    raise MarketError("unable to load plugin repository index: " + "; ".join(errors))


def _archive_url(item: dict[str, Any]) -> str:
    for key in ("archive_url", "download_url", "zip_url", "url"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    source = str(item.get("repository") or item.get("repo_url") or "").strip().rstrip("/")
    ref = str(item.get("ref") or item.get("branch") or "main").strip()
    if source.startswith("https://github.com/"):
        return f"{source.removesuffix('.git')}/archive/refs/heads/{ref}.zip"
    return ""


def _safe_extract(zf: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in zf.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise MarketError("plugin archive contains an unsafe path") from exc
    zf.extractall(destination)


def _source_dir(root: Path, item: dict[str, Any]) -> Path:
    configured = str(item.get("source_dir") or "").strip().strip("/")
    if configured:
        matches = [path for path in root.rglob(configured) if path.is_dir()]
        if matches:
            return matches[0]
    manifests = sorted(root.rglob("plugin.json"))
    plugin_id = str(item.get("id") or "").strip()
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not plugin_id or str(manifest.get("id") or "") == plugin_id:
            return manifest_path.parent
    raise MarketError("plugin.json missing in source_dir")


async def install_from_market_item(item: dict[str, Any]) -> Path:
    plugin_id = str(item.get("id") or "").strip()
    if not plugin_id:
        raise MarketError("plugin id is required")
    archive_url = _archive_url(item)
    if not archive_url:
        raise MarketError("plugin archive URL is required")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(archive_url)
        response.raise_for_status()
        data = response.content
    with tempfile.TemporaryDirectory(prefix="noor-plugin-") as td:
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise MarketError("plugin archive is not a valid ZIP file") from exc
        root = Path(td)
        _safe_extract(zf, root)
        src = _source_dir(root, item)
        if not (src / "plugin.json").exists():
            raise MarketError("plugin.json missing in source_dir")
        target = PLUGINS_DIR / plugin_id
        staging = PLUGINS_DIR / f".{plugin_id}.installing"
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(src, staging)
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
    return target
