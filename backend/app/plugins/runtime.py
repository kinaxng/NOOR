from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.plugins.adapters import build_widget, fetch_rss_items, search_subtitles_for_plugin, submit_download, test_plugin
from app.plugins.contracts import PluginManifest
from app.plugins.handlers import clear_handler_cache, get_plugin_handler
from app.plugins.market import MarketError, fetch_repo_index, install_from_market_item
from app.plugins.runtime_paths import PLUGINS_DIR
from app.plugins.store import load_config, load_market_repos, load_state, save_config, save_market_repos, save_state

LEGACY_DOWNLOADER_CAPABILITIES: dict[str, dict[str, Any]] = {
    "qbittorrent": {
        "accepts_public_magnet": True,
        "accepts_private_tracker": True,
        "accepts_http_torrent": True,
        "accepts_http_url": True,
    },
    "transmission": {
        "accepts_public_magnet": True,
        "accepts_private_tracker": True,
        "accepts_http_torrent": True,
        "accepts_http_url": True,
    },
    "xunlei-remote": {
        "accepts_public_magnet": True,
        "accepts_private_tracker": False,
        "accepts_http_torrent": True,
        "accepts_http_url": True,
    },
}


class PluginRuntime:
    def __init__(self) -> None:
        self.plugin_root = PLUGINS_DIR
        self._lock = asyncio.Lock()
        self._manifests: dict[str, dict[str, Any]] = {}
        self._state: dict[str, dict[str, Any]] = {}
        self._config: dict[str, dict[str, Any]] = {}
        self._market_repos: list[dict[str, str]] = []
        self._handlers: dict[str, Any] = {}
        self._background_started: set[str] = set()
        self.reload()

    def _manifest_model(self, plugin_id: str) -> PluginManifest:
        raw = self._manifests.get(plugin_id) or {}
        fields = PluginManifest.__dataclass_fields__
        return PluginManifest(**{key: value for key, value in raw.items() if key in fields})

    def _handler(self, plugin_id: str) -> Any | None:
        if plugin_id in self._handlers:
            return self._handlers[plugin_id]
        handler = get_plugin_handler(plugin_id)
        if handler is not None:
            self._handlers[plugin_id] = handler
        return handler

    def get_handler(self, plugin_id: str) -> Any | None:
        return self._handler(plugin_id)

    def reload(self) -> None:
        clear_handler_cache()
        self._handlers.clear()
        self._background_started.clear()
        manifests: dict[str, dict[str, Any]] = {}
        if self.plugin_root.is_dir():
            for manifest_path in sorted(self.plugin_root.glob("*/plugin.json")):
                try:
                    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
                    plugin_id = str(raw.get("id") or manifest_path.parent.name)
                except (OSError, json.JSONDecodeError):
                    continue
                raw["id"] = plugin_id
                manifests[plugin_id] = raw
        self._manifests = manifests
        self._market_repos = load_market_repos()

        raw_state = load_state()
        raw_cfg = load_config()
        self._state = {}
        self._config = {}
        for plugin_id, manifest in manifests.items():
            default = bool(manifest.get("enabled_by_default", True))
            saved_state = raw_state.get(plugin_id)
            self._state[plugin_id] = dict(saved_state) if isinstance(saved_state, dict) else {"enabled": default}
            defaults = manifest.get("default_config") if isinstance(manifest.get("default_config"), dict) else {}
            saved_cfg = raw_cfg.get(plugin_id)
            self._config[plugin_id] = {**dict(defaults), **(saved_cfg if isinstance(saved_cfg, dict) else {})}
        self._persist()

    def _persist(self) -> None:
        save_state({key: dict(value) for key, value in self._state.items()})
        save_config({key: dict(value) for key, value in self._config.items()})
        save_market_repos(list(self._market_repos))

    def _is_enabled(self, plugin_id: str) -> bool:
        manifest = self._manifests.get(plugin_id)
        if manifest is None:
            return False
        default = bool(manifest.get("enabled_by_default", True))
        state = self._state.get(plugin_id, {})
        return bool(state.get("enabled", default)) if isinstance(state, dict) else default

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._manifests and self._is_enabled(plugin_id)

    def get_manifest(self, plugin_id: str) -> PluginManifest:
        if plugin_id not in self._manifests:
            raise KeyError("plugin not found")
        return self._manifest_model(plugin_id)

    async def reload_plugins(self) -> list[dict[str, Any]]:
        async with self._lock:
            await self.stop_background_tasks()
            self.reload()
            await self.start_background_tasks()
        return self.list_plugins()

    def list_plugins(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for plugin_id, manifest in self._manifests.items():
            item = dict(manifest)
            item["id"] = plugin_id
            item["enabled"] = self.is_enabled(plugin_id)
            item["loaded"] = plugin_id in self._handlers
            item["config"] = dict(self._config.get(plugin_id, {}))
            items.append(item)
        return items

    def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list_plugins() if item["id"] == plugin_id), None)

    def get_config(self, plugin_id: str) -> dict[str, Any]:
        self.get_manifest(plugin_id)
        cfg = dict(self._config.get(plugin_id, {}))
        handler = self._handler(plugin_id)
        resolver = getattr(handler, "resolve_config", None)
        if callable(resolver):
            resolved = resolver(cfg)
            if isinstance(resolved, dict):
                return resolved
        return cfg

    async def update_config(self, plugin_id: str, config: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            manifest = self.get_manifest(plugin_id)
            merged = {**manifest.default_config, **config}
            handler = self._handler(plugin_id)
            persist = getattr(handler, "persist_config", None)
            if callable(persist):
                persisted = persist(merged)
                if isinstance(persisted, dict):
                    merged = {**manifest.default_config, **persisted}
            self._config[plugin_id] = merged
            self._persist()
            callback = getattr(handler, "on_config_updated", None)
            if callable(callback):
                result = callback(merged)
                if asyncio.iscoroutine(result):
                    await result
            return merged.copy()

    async def set_config(self, plugin_id: str, config: dict[str, Any]) -> dict[str, Any]:
        return await self.update_config(plugin_id, config)

    async def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        async with self._lock:
            self.get_manifest(plugin_id)
            current = self._state.get(plugin_id, {})
            self._state[plugin_id] = {**current, "enabled": enabled}
            self._persist()
        if enabled:
            await self._start_plugin_background(plugin_id)
        else:
            await self._stop_plugin_background(plugin_id)
        return enabled

    async def _call(self, handler: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        callback = getattr(handler, name, None)
        if not callable(callback):
            raise AttributeError(name)
        result = callback(*args, **kwargs)
        return await result if asyncio.iscoroutine(result) else result

    async def handle_action(self, plugin_id: str, action: str, payload: dict[str, Any] | None = None) -> Any:
        handler = self._handler(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        if not self.is_enabled(plugin_id):
            raise ValueError("plugin disabled")
        config = self.get_config(plugin_id)
        payload = payload or {}
        callback = getattr(handler, "handle_action", None)
        if callable(callback):
            parameters = list(inspect.signature(callback).parameters)
            args = (action, config, payload) if len(parameters) >= 2 and parameters[1] == "config" else (action, payload, config)
            result = callback(*args)
            return await result if asyncio.iscoroutine(result) else result
        for name, args in (
            (action, (payload, config)),
            (action, (payload,)),
        ):
            try:
                return await self._call(handler, name, *args)
            except AttributeError:
                continue
            except TypeError:
                continue
        raise LookupError(f"Plugin action not found: {plugin_id}/{action}")

    async def get_rss_items(self, plugin_id: str, *, limit: int = 30, force_refresh: bool = False, include_images: bool = False) -> Any:
        manifest = self.get_manifest(plugin_id)
        if manifest.type != "rss_source" and "rss_source" not in (manifest.capabilities or []):
            raise ValueError("not rss_source plugin")
        if not self.is_enabled(plugin_id):
            raise ValueError("plugin disabled")
        cfg = {**self.get_config(plugin_id), "include_images": include_images}
        handler = self._handler(plugin_id)
        callback = getattr(handler, "fetch_rss_items", None)
        if callable(callback):
            result = callback(manifest, cfg, limit=limit, force_refresh=force_refresh)
        else:
            result = fetch_rss_items(manifest, cfg, limit=limit, force_refresh=force_refresh)
        return await result if asyncio.iscoroutine(result) else result

    async def push_rss_download(self, plugin_id: str, item: dict[str, Any]) -> dict[str, Any]:
        manifest = self.get_manifest(plugin_id)
        if manifest.type != "rss_source" and "rss_source" not in (manifest.capabilities or []):
            raise ValueError("not rss_source plugin")
        if not self.is_enabled(plugin_id):
            raise ValueError("plugin disabled")
        cfg = self.get_config(plugin_id)
        downloader_id = str(cfg.get("downloader_binding") or "none").strip()
        if not downloader_id or downloader_id == "none":
            raise ValueError("未绑定下载器")
        downloader_manifest = self.get_manifest(downloader_id)
        if downloader_manifest.type != "downloader":
            raise ValueError("绑定目标不是下载器")
        if not self.is_enabled(downloader_id):
            raise ValueError("下载器插件未启用")
        url = str(item.get("download_url") or item.get("enclosure_url") or item.get("url") or "").strip()
        if not url:
            raise ValueError("缺少种子地址")
        title = str(item.get("title") or item.get("name") or "").strip()
        return await self.submit_download(downloader_id, {"url": url, "urls": url, "name": title, "title": title})

    async def _call_resource_search(self, handler: Any, config: dict[str, Any], payload: dict[str, Any]) -> Any:
        callback = getattr(handler, "search_resources", None)
        if not callable(callback):
            return None
        parameters = list(inspect.signature(callback).parameters)
        if parameters and parameters[0] in {"config", "cfg", "plugin_config", "settings"}:
            result = callback(config, payload)
        else:
            result = callback(payload, config)
        return await result if asyncio.iscoroutine(result) else result

    def _normalize_plugin_downloader_preferences(self, plugin_id: str) -> list[str]:
        cfg = self.get_config(plugin_id)
        bindings_raw = cfg.get("downloader_binding")
        default_downloader = str(cfg.get("default_downloader") or "").strip()
        bindings: list[str] = []
        if isinstance(bindings_raw, list):
            for item in bindings_raw:
                value = str(item or "").strip()
                if value and value != "none" and value not in bindings:
                    bindings.append(value)
        elif isinstance(bindings_raw, str):
            value = bindings_raw.strip()
            if value and value != "none":
                bindings.append(value)
        if default_downloader and default_downloader != "none":
            bindings = [default_downloader] + [item for item in bindings if item != default_downloader]
        return [item for item in bindings if item in self._manifests and self._manifests[item].get("type") == "downloader"]

    def get_downloader_capabilities(self, plugin_id: str) -> dict[str, Any]:
        manifest = self.get_manifest(plugin_id)
        if manifest.type != "downloader":
            return {}
        declared = manifest.contributions.get("downloader_capabilities") if isinstance(manifest.contributions, dict) else {}
        caps = dict(LEGACY_DOWNLOADER_CAPABILITIES.get(plugin_id, {}))
        if isinstance(declared, dict):
            caps.update(declared)
        return caps

    def list_enabled_downloaders(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for pid, manifest in self._manifests.items():
            if manifest.get("type") != "downloader" or not self.is_enabled(pid):
                continue
            out.append({
                "id": pid,
                "name": manifest.get("name") or pid,
                "capabilities": self.get_downloader_capabilities(pid),
            })
        return sorted(out, key=lambda item: str(item.get("id") or ""))

    @staticmethod
    def _normalize_resource_item(provider_id: str, provider_label: str, item: dict[str, Any]) -> dict[str, Any]:
        features = item.get("features") if isinstance(item.get("features"), dict) else {}
        requirements = item.get("requirements") if isinstance(item.get("requirements"), dict) else {}
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        resolver = item.get("resolver") if isinstance(item.get("resolver"), dict) else None
        tags_raw = item.get("tags") if isinstance(item.get("tags"), list) else []
        preferences_raw = item.get("download_preference")
        download_preference: list[str] = []
        if isinstance(preferences_raw, list):
            for entry in preferences_raw:
                value = str(entry or "").strip()
                if value and value not in download_preference:
                    download_preference.append(value)
        elif isinstance(preferences_raw, str):
            value = preferences_raw.strip()
            if value:
                download_preference.append(value)
        return {
            "provider": str(item.get("provider") or provider_id),
            "provider_label": str(item.get("provider_label") or provider_label or provider_id),
            "kind": str(item.get("kind") or "torrent"),
            "id": str(item.get("id") or item.get("guid") or item.get("url") or item.get("title") or ""),
            "query_key": str(item.get("query_key") or item.get("code") or item.get("number") or ""),
            "title": str(item.get("title") or item.get("name") or item.get("display_title") or ""),
            "subtitle": str(item.get("subtitle") or ""),
            "url": str(item.get("url") or item.get("download_url") or item.get("magnet") or ""),
            "cover_url": str(item.get("fanart_url") or item.get("backdrop_url") or item.get("cover_url") or item.get("image_url") or ""),
            "fanart_url": str(item.get("fanart_url") or item.get("backdrop_url") or item.get("cover_url") or item.get("image_url") or ""),
            "source_url": str(item.get("source_url") or item.get("link") or ""),
            "size_bytes": int(item.get("size_bytes") or 0),
            "file_count": int(item.get("file_count") or item.get("numfiles") or 0),
            "tags": [str(tag) for tag in tags_raw if str(tag or "").strip()],
            "features": features,
            "requirements": requirements,
            "download_preference": download_preference,
            "resolver": resolver,
            "metadata": metadata,
        }

    @staticmethod
    def _downloader_matches_requirements(capabilities: dict[str, Any], requirements: dict[str, Any]) -> bool:
        if not requirements:
            return True
        for key, expected in requirements.items():
            if expected in (None, "", False):
                continue
            actual = capabilities.get(key)
            if isinstance(expected, bool):
                if expected and not bool(actual):
                    return False
                continue
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
                continue
            if actual != expected:
                return False
        return True

    def resolve_downloaders_for_resource(
        self,
        source_plugin_id: str,
        item: dict[str, Any],
        *,
        requested_downloader_id: str = "",
    ) -> dict[str, Any]:
        manifest = self.get_manifest(source_plugin_id)
        resource = self._normalize_resource_item(source_plugin_id, manifest.name or source_plugin_id, item)
        requirements = resource.get("requirements") if isinstance(resource.get("requirements"), dict) else {}
        item_preferences = [str(x) for x in resource.get("download_preference") or [] if str(x or "").strip()]
        source_preferences = self._normalize_plugin_downloader_preferences(source_plugin_id)

        enabled_downloaders = {str(item.get("id") or ""): item for item in self.list_enabled_downloaders()}
        ordered_downloader_ids = list(source_preferences) if source_preferences else []
        for downloader_id in enabled_downloaders:
            if downloader_id not in ordered_downloader_ids:
                ordered_downloader_ids.append(downloader_id)

        compatible: list[str] = []
        for downloader_id in ordered_downloader_ids:
            downloader = enabled_downloaders.get(downloader_id) or {}
            if not downloader_id:
                continue
            capabilities = downloader.get("capabilities") if isinstance(downloader.get("capabilities"), dict) else {}
            if self._downloader_matches_requirements(capabilities, requirements):
                compatible.append(downloader_id)

        requested = str(requested_downloader_id or "").strip()
        preferred = ""
        if requested and requested in compatible:
            preferred = requested
        else:
            for candidate in [*item_preferences, *source_preferences, *compatible]:
                if candidate in compatible:
                    preferred = candidate
                    break

        return {
            "compatible_downloaders": compatible,
            "preferred_downloader": preferred or None,
            "source_bound_downloaders": source_preferences,
        }

    async def search_resources(
        self,
        query: dict[str, Any] | str,
        *,
        provider_ids: list[str] | None = None,
        limit_per_plugin: int = 12,
        requested_downloader_id: str = "",
    ) -> dict[str, Any]:
        payload = {"keyword": str(query).strip()} if isinstance(query, str) else dict(query or {})
        provider_filter = {str(x).strip() for x in (provider_ids or []) if str(x).strip()}
        try:
            provider_timeout = max(3.0, min(float(payload.get("provider_timeout_seconds") or 12.0), 30.0))
        except Exception:
            provider_timeout = 12.0
        groups: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        providers: list[tuple[str, dict[str, Any]]] = []
        for pid, manifest in self._manifests.items():
            if not self.is_enabled(pid):
                continue
            if provider_filter and pid not in provider_filter:
                continue
            if "resource_search" not in (manifest.get("capabilities") or []):
                continue
            providers.append((pid, manifest))

        async def search_provider(pid: str, manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
            handler = self._handler(pid)
            data = None
            if handler is not None and callable(getattr(handler, "search_resources", None)):
                data = await self._call_resource_search(handler, self.get_config(pid), payload)
            elif handler is not None and callable(getattr(handler, "handle_action", None)):
                data = await self.handle_action(pid, "resource_search", {**payload, "limit": limit_per_plugin})
            else:
                return None, []
            raw_items = data.get("items") if isinstance(data, dict) else data
            if not isinstance(raw_items, list):
                return None, []
            normalized_items: list[dict[str, Any]] = []
            for raw_item in raw_items[:limit_per_plugin]:
                if not isinstance(raw_item, dict):
                    continue
                item = self._normalize_resource_item(pid, manifest.get("name") or pid, raw_item)
                item.update(self.resolve_downloaders_for_resource(pid, item, requested_downloader_id=requested_downloader_id))
                normalized_items.append(item)
            group = {
                "provider": pid,
                "provider_label": manifest.get("name") or pid,
                "provider_name": manifest.get("name") or pid,
                "items": normalized_items,
                "total": len(normalized_items),
                "has_more": (
                    bool(data.get("has_more"))
                    if isinstance(data, dict) and "has_more" in data
                    else len(normalized_items) >= limit_per_plugin
                ),
                "next_page": data.get("next_page") if isinstance(data, dict) else None,
                "max_items": data.get("max_items") if isinstance(data, dict) else None,
            }
            return group, normalized_items

        async def search_provider_with_timeout(pid: str, manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
            return await asyncio.wait_for(search_provider(pid, manifest), timeout=provider_timeout)

        tasks = [asyncio.create_task(search_provider_with_timeout(pid, manifest)) for pid, manifest in providers]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await task
            raise
        for result in results:
            if isinstance(result, Exception):
                continue
            group, normalized_items = result
            if group is None:
                continue
            groups.append(group)
            items.extend(normalized_items)
        await self._borrow_resource_covers_from_javdb(items, groups)
        return {
            "ok": True,
            "query": payload,
            "groups": groups,
            "items": items,
            "downloaders": self.list_enabled_downloaders(),
        }

    async def _borrow_resource_covers_from_javdb(self, items: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
        if not items or not self.is_enabled("javdb"):
            return

        def norm_code(value: Any) -> str:
            import re

            raw = str(value or "").strip().upper()
            if not raw:
                return ""
            match = re.search(r"\b([A-Z]{2,8}[-_ ]?\d{2,7}|FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|\d{6}[-_]\d{2,5})\b", raw, re.I)
            if not match:
                return ""
            return re.sub(r"[_ ]+", "-", match.group(1).upper())

        cover_by_code: dict[str, str] = {}
        for item in items:
            code = norm_code(item.get("query_key") or item.get("title"))
            cover = str(item.get("cover_url") or "").strip()
            if code and cover and item.get("provider") == "javdb":
                cover_by_code[code] = cover

        missing = [
            item for item in items
            if str(item.get("provider") or "") != "javdb"
            and not str(item.get("cover_url") or "").strip()
            and norm_code(item.get("query_key") or item.get("title"))
        ]
        if not missing:
            return

        for item in missing:
            code = norm_code(item.get("query_key") or item.get("title"))
            if code and code in cover_by_code:
                item["cover_url"] = cover_by_code[code]
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                item["metadata"] = {**metadata, "cover_borrowed_from": "javdb"}

    async def resolve_resource_download(self, plugin_id: str, resource: dict[str, Any]) -> dict[str, Any]:
        handler = self._handler(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        for name, args in (
            ("resolve_resource_download", (resource, self.get_config(plugin_id))),
            ("resolve_download", (resource, self.get_config(plugin_id))),
        ):
            try:
                value = await self._call(handler, name, *args)
                if isinstance(value, dict):
                    return value
            except (AttributeError, TypeError):
                continue
        return {"item": resource, "url": resource.get("url") or resource.get("download_url") or resource.get("magnet") or ""}

    async def submit_download(self, plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        manifest = self.get_manifest(plugin_id)
        if manifest.type != "downloader":
            raise ValueError("not downloader plugin")
        if not self.is_enabled(plugin_id):
            raise ValueError("下载器插件未启用")
        handler = self._handler(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        callback = getattr(handler, "submit_download", None)
        if callable(callback):
            parameters = list(inspect.signature(callback).parameters)
            if parameters and parameters[0] in {"config", "cfg", "plugin_config", "settings"}:
                value = callback(self.get_config(plugin_id), payload)
            else:
                value = callback(payload, self.get_config(plugin_id))
            value = await value if asyncio.iscoroutine(value) else value
            return value if isinstance(value, dict) else {"ok": bool(value)}
        for name, args in (
            ("submit_download", (payload, self.get_config(plugin_id))),
            ("handle_action", ("submit_download", payload, self.get_config(plugin_id))),
        ):
            try:
                value = await self._call(handler, name, *args)
                return value if isinstance(value, dict) else {"ok": bool(value)}
            except (AttributeError, TypeError):
                continue
        raise ValueError("下载器插件缺少提交接口")

    async def _start_plugin_background(self, plugin_id: str) -> None:
        if plugin_id in self._background_started or not self._is_enabled(plugin_id):
            return
        handler = self._handler(plugin_id)
        if handler is None:
            return
        try:
            await self._call(handler, "start_background", self.get_config(plugin_id))
        except AttributeError:
            return
        self._background_started.add(plugin_id)

    async def _stop_plugin_background(self, plugin_id: str) -> None:
        handler = self._handler(plugin_id)
        if handler is not None:
            try:
                await self._call(handler, "stop_background")
            except (AttributeError, Exception):
                pass
        self._background_started.discard(plugin_id)

    async def start_background_tasks(self) -> None:
        for plugin_id in sorted(self._manifests):
            if self.is_enabled(plugin_id):
                await self._start_plugin_background(plugin_id)

    async def stop_background_tasks(self) -> None:
        for plugin_id in list(self._background_started):
            await self._stop_plugin_background(plugin_id)

    async def get_background_tasks(self) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for plugin_id, manifest in self._manifests.items():
            if not self.is_enabled(plugin_id):
                continue
            handler = self._handler(plugin_id)
            callback = getattr(handler, "background_tasks", None) if handler is not None else None
            if not callable(callback):
                continue
            try:
                data = await self._call(handler, "background_tasks", self.get_config(plugin_id))
                items = data.get("items") if isinstance(data, dict) else data
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    tasks.append({
                        "plugin_id": plugin_id,
                        "plugin_name": manifest.get("name") or plugin_id,
                        **item,
                    })
            except Exception as exc:
                tasks.append({
                    "id": f"{plugin_id}.background_tasks",
                    "plugin_id": plugin_id,
                    "plugin_name": manifest.get("name") or plugin_id,
                    "title": manifest.get("name") or plugin_id,
                    "status": "failed",
                    "enabled": True,
                    "summary": "后台任务状态读取失败",
                    "detail": str(exc),
                    "metrics": {},
                })
        return sorted(tasks, key=lambda item: (str(item.get("plugin_name") or ""), str(item.get("title") or "")))

    def get_external_task_contributions(self) -> dict[str, dict[str, Any]]:
        contributions: dict[str, dict[str, Any]] = {}
        for plugin_id, manifest in self._manifests.items():
            ext = (manifest.get("contributions") or {}).get("external_task")
            if isinstance(ext, dict):
                contributions[plugin_id] = {
                    "provider_id": plugin_id,
                    "label": ext.get("label") or manifest.get("name") or plugin_id,
                    "phase_label": ext.get("phase_label") or "外部任务",
                    "can_cancel": bool(ext.get("can_cancel", False)),
                    "poll_interval": int(ext.get("poll_interval") or 10000),
                    **ext,
                }
        return contributions

    def is_external_task_cancelable(self, job: Any) -> bool:
        from app.plugins.external_tasks import is_external_task_cancelable

        return is_external_task_cancelable(job)

    async def sync_external_tasks(self, job_id: str | None = None) -> dict[str, Any]:
        updated = 0
        checked = 0
        errors: list[dict[str, str]] = []
        for plugin_id, manifest in self._manifests.items():
            if not self.is_enabled(plugin_id):
                continue
            if "external_task_provider" not in (manifest.get("capabilities") or []):
                continue
            handler = self._handler(plugin_id)
            callback = getattr(handler, "sync_external_tasks", None)
            if not callable(callback):
                continue
            checked += 1
            try:
                result = callback(self.get_config(plugin_id), job_id=job_id)
                result = await result if asyncio.iscoroutine(result) else result
                if isinstance(result, dict):
                    updated += int(result.get("updated") or 0)
            except Exception as exc:
                errors.append({"plugin_id": plugin_id, "error": str(exc)})
        return {"checked": checked, "updated": updated, "errors": errors}

    async def uninstall_plugin(self, plugin_id: str) -> None:
        async with self._lock:
            target = self.plugin_root / plugin_id
            if not target.exists():
                raise KeyError("plugin not found")
            await self._stop_plugin_background(plugin_id)
            shutil.rmtree(target)
            self.reload()

    async def test(self, plugin_id: str) -> dict[str, Any]:
        manifest = self.get_manifest(plugin_id)
        cfg = self.get_config(plugin_id)
        handler = self._handler(plugin_id)
        callback = getattr(handler, "test", None)
        if callable(callback):
            result = callback(cfg)
        else:
            result = test_plugin(manifest, cfg)
        result = await result if asyncio.iscoroutine(result) else result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if is_dataclass(result):
            return asdict(result)
        return dict(result)

    async def get_dashboard_widgets(self, plugin_ids: list[str] | None = None) -> list[dict[str, Any]]:
        wanted = set(plugin_ids or [])
        widgets: list[dict[str, Any]] = []
        for plugin_id, manifest_data in self._manifests.items():
            if wanted and plugin_id not in wanted:
                continue
            if not self.is_enabled(plugin_id):
                continue
            capabilities = set(manifest_data.get("capabilities") or [])
            if manifest_data.get("type") != "dashboard_widget" and "dashboard_widget" not in capabilities:
                continue
            handler = self._handler(plugin_id)
            callback = getattr(handler, "build_widget", None) if handler is not None else None
            try:
                if callable(callback):
                    value = callback(self.get_config(plugin_id))
                else:
                    manifest = self._manifest_model(plugin_id)
                    value = build_widget(manifest, self.get_config(plugin_id))
                value = await value if asyncio.iscoroutine(value) else value
            except Exception:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if item is None:
                    continue
                if is_dataclass(item):
                    item = asdict(item)
                elif hasattr(item, "model_dump"):
                    item = item.model_dump()
                if isinstance(item, dict):
                    widgets.append(item)
        return widgets

    async def search_subtitles(self, video_code: str, *, local_only: bool = False) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for plugin_id, manifest in self._manifests.items():
            if not self._is_enabled(plugin_id) or "subtitle_search" not in (manifest.get("capabilities") or []):
                continue
            if local_only and "subtitle_search_local" not in (manifest.get("capabilities") or []):
                continue
            handler = self._handler(plugin_id)
            callback = getattr(handler, "search_subtitles", None) if handler is not None else None
            try:
                if callable(callback):
                    value = callback(self.get_config(plugin_id), video_code)
                else:
                    value = search_subtitles_for_plugin(self._manifest_model(plugin_id), self.get_config(plugin_id), video_code)
                value = await value if asyncio.iscoroutine(value) else value
                if isinstance(value, list):
                    results.extend(item for item in value if isinstance(item, dict))
            except Exception:
                continue
        return results

    async def fetch_subtitle_content(self, plugin_id: str, subtitle_id: str) -> dict[str, Any]:
        handler = self._handler(plugin_id)
        callback = getattr(handler, "fetch_subtitle_content", None)
        if handler is None or not callable(callback) or not self._is_enabled(plugin_id):
            raise LookupError(plugin_id)
        value = callback(self.get_config(plugin_id), subtitle_id)
        value = await value if asyncio.iscoroutine(value) else value
        if not isinstance(value, dict):
            raise ValueError("invalid subtitle provider response")
        return value

    async def get_knowledge_contributions(self, *, limit: int = 100, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for plugin_id, manifest in self._manifests.items():
            if not self._is_enabled(plugin_id):
                continue
            capabilities = manifest.get("capabilities") or []
            if not ({"knowledge_provider", "knowledge_contributions"} & set(capabilities)):
                continue
            handler = self._handler(plugin_id)
            if handler is None:
                continue
            try:
                callback = getattr(handler, "build_knowledge_contributions", None)
                if callable(callback):
                    data = callback(self.get_config(plugin_id), limit=limit, context=context or {})
                    data = await data if asyncio.iscoroutine(data) else data
                else:
                    data = await self.handle_action(plugin_id, "knowledge_contributions", {"limit": limit, "context": context or {}})
                items = data.get("items") if isinstance(data, dict) and isinstance(data.get("items"), list) else data
                values = items if isinstance(items, list) else [items]
                for item in values[:limit]:
                    if isinstance(item, dict):
                        out.append({"source_plugin": plugin_id, **item})
            except Exception:
                continue
        return out

    def list_market_repos(self) -> list[dict[str, str]]:
        return list(self._market_repos)

    def add_market_repo(self, repo_url: str) -> list[dict[str, str]]:
        url = str(repo_url or "").strip()
        if not url:
            raise ValueError("插件仓库地址不能为空")
        if not any(item.get("url") == url for item in self._market_repos):
            self._market_repos.append({"url": url})
            self._persist()
        return self.list_market_repos()

    def remove_market_repo(self, repo_url: str) -> list[dict[str, str]]:
        url = str(repo_url or "").strip()
        self._market_repos = [item for item in self._market_repos if item.get("url") != url]
        self._persist()
        return self.list_market_repos()

    async def list_market_items(self) -> list[dict[str, Any]]:
        installed = set(self._manifests)
        items: list[dict[str, Any]] = []
        for repo in self.list_market_repos():
            repo_url = str(repo.get("url") or "").strip()
            if not repo_url:
                continue
            try:
                values = await fetch_repo_index(repo_url)
            except MarketError as exc:
                items.append({"repo_url": repo_url, "error": str(exc)})
                continue
            for value in values:
                plugin_id = str(value.get("id") or "").strip()
                if not plugin_id:
                    continue
                items.append({**value, "repo_url": repo_url, "installed": plugin_id in installed})
        return items

    async def install_market_plugin(self, repo_url: str, plugin_id: str) -> dict[str, Any]:
        values = await fetch_repo_index(repo_url)
        item = next((value for value in values if str(value.get("id") or "") == plugin_id), None)
        if item is None:
            raise MarketError("plugin not found in repository")
        target = await install_from_market_item({**item, "repo_url": repo_url})
        await self.reload_plugins()
        return {"ok": True, "plugin_id": plugin_id, "path": str(target)}


runtime = PluginRuntime()
