from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.core.runtime_paths import data_path
from app.plugins.contracts import PluginManifest
from app.plugins.handlers import clear_handler_cache, get_plugin_handler
from app.plugins.market import MarketError, fetch_repo_index, install_from_market_item
from app.plugins.runtime_paths import PLUGINS_DIR
from app.plugins.store import load_market_repos, save_market_repos


class PluginRuntime:
    def __init__(self) -> None:
        self.plugin_root = PLUGINS_DIR
        self._manifests: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Any] = {}
        self._background_started: set[str] = set()
        self._lock = asyncio.Lock()

    def _config_path(self) -> Path:
        path = data_path('plugins_config.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _state_path(self) -> Path:
        path = data_path('plugins_state.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else default
        except (OSError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def _configs(self) -> dict[str, Any]:
        return self._read_json(self._config_path(), {})

    def _states(self) -> dict[str, Any]:
        return self._read_json(self._state_path(), {})

    def _is_enabled(self, plugin_id: str) -> bool:
        state = self._states().get(plugin_id, {})
        default = bool((self._manifests.get(plugin_id) or {}).get('enabled_by_default', True))
        return bool(state.get('enabled', default)) if isinstance(state, dict) else default

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._manifests and self._is_enabled(plugin_id)

    async def reload_plugins(self) -> list[dict[str, Any]]:
        async with self._lock:
            clear_handler_cache()
            self._manifests.clear()
            self._handlers.clear()
            if not self.plugin_root.is_dir():
                return []
            for manifest_path in sorted(self.plugin_root.glob('*/plugin.json')):
                try:
                    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                    plugin_id = str(manifest.get('id') or manifest_path.parent.name)
                except (OSError, json.JSONDecodeError):
                    continue
                manifest['id'] = plugin_id
                manifest['_directory'] = str(manifest_path.parent)
                self._manifests[plugin_id] = manifest
                handler = get_plugin_handler(plugin_id)
                if handler is not None:
                    self._handlers[plugin_id] = handler
            return self.list_plugins()

    def list_plugins(self) -> list[dict[str, Any]]:
        configs, states = self._configs(), self._states()
        items = []
        for plugin_id, manifest in self._manifests.items():
            state = states.get(plugin_id, {}) if isinstance(states.get(plugin_id), dict) else {}
            default = bool(manifest.get('enabled_by_default', True))
            item = {key: value for key, value in manifest.items() if key != '_directory'}
            item.update({
                'enabled': bool(state.get('enabled', default)),
                'loaded': plugin_id in self._handlers,
                'config': configs.get(plugin_id, {}),
            })
            items.append(item)
        return items

    def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list_plugins() if item['id'] == plugin_id), None)

    def list_market_repos(self) -> list[dict[str, str]]:
        return load_market_repos()

    def add_market_repo(self, repo_url: str) -> list[dict[str, str]]:
        url = str(repo_url or '').strip()
        if not url:
            raise ValueError('插件仓库地址不能为空')
        repos = self.list_market_repos()
        if not any(item.get('url') == url for item in repos):
            repos.append({'url': url})
            save_market_repos(repos)
        return repos

    def remove_market_repo(self, repo_url: str) -> list[dict[str, str]]:
        url = str(repo_url or '').strip()
        repos = [item for item in self.list_market_repos() if item.get('url') != url]
        save_market_repos(repos)
        return repos

    async def list_market_items(self) -> list[dict[str, Any]]:
        installed = set(self._manifests)
        items: list[dict[str, Any]] = []
        for repo in self.list_market_repos():
            repo_url = str(repo.get('url') or '').strip()
            if not repo_url:
                continue
            try:
                values = await fetch_repo_index(repo_url)
            except MarketError as exc:
                items.append({'repo_url': repo_url, 'error': str(exc)})
                continue
            for value in values:
                plugin_id = str(value.get('id') or '').strip()
                if not plugin_id:
                    continue
                items.append({**value, 'repo_url': repo_url, 'installed': plugin_id in installed})
        return items

    async def install_market_plugin(self, repo_url: str, plugin_id: str) -> dict[str, Any]:
        values = await fetch_repo_index(repo_url)
        item = next((value for value in values if str(value.get('id') or '') == plugin_id), None)
        if item is None:
            raise MarketError('plugin not found in repository')
        target = await install_from_market_item({**item, 'repo_url': repo_url})
        await self.reload_plugins()
        return {'ok': True, 'plugin_id': plugin_id, 'path': str(target)}

    def get_config(self, plugin_id: str) -> dict[str, Any]:
        manifest = self._manifests.get(plugin_id) or {}
        defaults = manifest.get('default_config') if isinstance(manifest.get('default_config'), dict) else {}
        saved = self._configs().get(plugin_id, {})
        config = {**defaults, **(saved if isinstance(saved, dict) else {})}
        handler = self._handlers.get(plugin_id)
        resolver = getattr(handler, 'resolve_config', None)
        if callable(resolver):
            resolved = resolver(config)
            if isinstance(resolved, dict):
                return resolved
        return config

    async def update_config(self, plugin_id: str, config: dict[str, Any]) -> dict[str, Any]:
        if plugin_id not in self._manifests:
            raise KeyError(plugin_id)
        configs = self._configs()
        configs[plugin_id] = config
        self._write_json(self._config_path(), configs)
        handler = self._handlers.get(plugin_id)
        callback = getattr(handler, 'on_config_updated', None)
        if callable(callback):
            result = callback(config)
            if asyncio.iscoroutine(result):
                await result
        return config

    async def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        if plugin_id not in self._manifests:
            raise KeyError(plugin_id)
        states = self._states()
        states[plugin_id] = {**(states.get(plugin_id) or {}), 'enabled': enabled}
        self._write_json(self._state_path(), states)
        if not enabled:
            await self._stop_plugin_background(plugin_id)
        elif plugin_id in self._handlers:
            await self._start_plugin_background(plugin_id)
        return enabled

    async def _call(self, handler: Any, name: str, *args: Any, **kwargs: Any) -> Any:
        callback = getattr(handler, name, None)
        if not callable(callback):
            raise AttributeError(name)
        result = callback(*args, **kwargs)
        return await result if asyncio.iscoroutine(result) else result

    async def handle_action(self, plugin_id: str, action: str, payload: dict[str, Any] | None = None) -> Any:
        handler = self._handlers.get(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        config = self.get_config(plugin_id)
        payload = payload or {}
        callback = getattr(handler, 'handle_action', None)
        if callable(callback):
            parameters = list(inspect.signature(callback).parameters)
            args = (action, config, payload) if len(parameters) >= 2 and parameters[1] == 'config' else (action, payload, config)
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
        raise LookupError(f'Plugin action not found: {plugin_id}/{action}')

    async def get_rss_items(self, plugin_id: str, *, limit: int = 30, force_refresh: bool = False) -> Any:
        handler = self._handlers.get(plugin_id)
        manifest_data = self._manifests.get(plugin_id)
        if handler is None or manifest_data is None:
            raise LookupError(plugin_id)
        callback = getattr(handler, 'fetch_rss_items', None)
        if not callable(callback):
            raise LookupError(f'Plugin RSS provider not found: {plugin_id}')
        fields = PluginManifest.__dataclass_fields__
        manifest = PluginManifest(**{key: value for key, value in manifest_data.items() if key in fields})
        result = callback(manifest, self.get_config(plugin_id), limit=limit, force_refresh=force_refresh)
        return await result if asyncio.iscoroutine(result) else result

    async def push_rss_download(self, plugin_id: str, item: dict[str, Any]) -> dict[str, Any]:
        config = self.get_config(plugin_id)
        downloader_id = str(config.get('downloader_binding') or 'none')
        if downloader_id == 'none':
            raise ValueError('M-Team 尚未绑定下载器')
        url = str(item.get('download_url') or item.get('enclosure_url') or item.get('url') or '')
        if not url:
            raise ValueError('RSS 条目没有可用下载地址')
        result = await self.submit_download(downloader_id, {
            'url': url,
            'urls': url,
            'name': item.get('title') or '',
            'source_plugin': plugin_id,
        })
        return {'ok': True, 'downloader': downloader_id, 'result': result}

    async def search_resources(self, query: dict[str, Any], *, limit_per_plugin: int = 24) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for plugin_id, handler in self._handlers.items():
            if not self._is_enabled(plugin_id) or not callable(getattr(handler, 'search_resources', None)):
                continue
            try:
                result = await self._call(handler, 'search_resources', query, self.get_config(plugin_id))
                items = result.get('items', result) if isinstance(result, dict) else result
                if not isinstance(items, list):
                    continue
                manifest = self._manifests.get(plugin_id, {})
                groups.append({'provider': plugin_id, 'provider_name': manifest.get('name', plugin_id), 'items': items[:limit_per_plugin]})
            except Exception as exc:
                groups.append({'provider': plugin_id, 'provider_name': self._manifests.get(plugin_id, {}).get('name', plugin_id), 'items': [], 'error': str(exc)})
        return groups

    async def get_dashboard_widgets(self, plugin_ids: list[str] | None = None) -> list[dict[str, Any]]:
        wanted = set(plugin_ids or [])
        widgets: list[dict[str, Any]] = []
        for plugin_id, handler in self._handlers.items():
            if wanted and plugin_id not in wanted:
                continue
            if not self._is_enabled(plugin_id):
                continue
            callback = getattr(handler, 'build_widget', None)
            if not callable(callback):
                continue
            try:
                value = callback(self.get_config(plugin_id))
                value = await value if asyncio.iscoroutine(value) else value
            except Exception:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if item is None:
                    continue
                if is_dataclass(item):
                    item = asdict(item)
                elif hasattr(item, 'model_dump'):
                    item = item.model_dump()
                if isinstance(item, dict):
                    widgets.append(item)
        return widgets

    async def search_subtitles(self, video_code: str, *, local_only: bool = False) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for plugin_id, handler in self._handlers.items():
            manifest = self._manifests.get(plugin_id) or {}
            if not self._is_enabled(plugin_id) or 'subtitle_search' not in (manifest.get('capabilities') or []):
                continue
            if local_only and 'subtitle_search_local' not in (manifest.get('capabilities') or []):
                continue
            callback = getattr(handler, 'search_subtitles', None)
            if not callable(callback):
                continue
            try:
                value = callback(self.get_config(plugin_id), video_code)
                value = await value if asyncio.iscoroutine(value) else value
                if isinstance(value, list):
                    results.extend(item for item in value if isinstance(item, dict))
            except Exception:
                continue
        return results

    async def fetch_subtitle_content(self, plugin_id: str, subtitle_id: str) -> dict[str, Any]:
        handler = self._handlers.get(plugin_id)
        callback = getattr(handler, 'fetch_subtitle_content', None)
        if handler is None or not callable(callback) or not self._is_enabled(plugin_id):
            raise LookupError(plugin_id)
        value = callback(self.get_config(plugin_id), subtitle_id)
        value = await value if asyncio.iscoroutine(value) else value
        if not isinstance(value, dict):
            raise ValueError('invalid subtitle provider response')
        return value

    async def get_knowledge_contributions(self, *, limit: int = 100, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for plugin_id, manifest in self._manifests.items():
            if not self._is_enabled(plugin_id):
                continue
            capabilities = manifest.get('capabilities') or [] if isinstance(manifest, dict) else []
            if not ({'knowledge_provider', 'knowledge_contributions'} & set(capabilities)):
                continue
            handler = self._handlers.get(plugin_id)
            if handler is None:
                continue
            try:
                callback = getattr(handler, 'build_knowledge_contributions', None)
                if callable(callback):
                    data = callback(self.get_config(plugin_id), limit=limit, context=context or {})
                    data = await data if asyncio.iscoroutine(data) else data
                else:
                    data = await self.handle_action(plugin_id, 'knowledge_contributions', {'limit': limit, 'context': context or {}})
                items = data.get('items') if isinstance(data, dict) and isinstance(data.get('items'), list) else data
                values = items if isinstance(items, list) else [items]
                for item in values[:limit]:
                    if isinstance(item, dict):
                        out.append({'source_plugin': plugin_id, **item})
            except Exception:
                continue
        return out

    async def resolve_resource_download(self, plugin_id: str, resource: dict[str, Any]) -> dict[str, Any]:
        """Ask a recovered provider to resolve a download URL when supported."""
        handler = self._handlers.get(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        for name, args in (
            ('resolve_resource_download', (resource, self.get_config(plugin_id))),
            ('resolve_download', (resource, self.get_config(plugin_id))),
        ):
            try:
                value = await self._call(handler, name, *args)
                if isinstance(value, dict):
                    return value
            except (AttributeError, TypeError):
                continue
        return {'item': resource, 'url': resource.get('url') or resource.get('download_url') or resource.get('magnet') or ''}

    async def submit_download(self, plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled(plugin_id):
            raise ValueError('下载器插件未启用')
        handler = self._handlers.get(plugin_id)
        if handler is None:
            raise LookupError(plugin_id)
        for name, args in (
            ('submit_download', (payload, self.get_config(plugin_id))),
            ('handle_action', ('submit_download', payload, self.get_config(plugin_id))),
        ):
            try:
                value = await self._call(handler, name, *args)
                return value if isinstance(value, dict) else {'ok': bool(value)}
            except (AttributeError, TypeError):
                continue
        raise ValueError('下载器插件缺少提交接口')

    async def _start_plugin_background(self, plugin_id: str) -> None:
        if plugin_id in self._background_started or not self._is_enabled(plugin_id):
            return
        handler = self._handlers.get(plugin_id)
        if handler is None:
            return
        try:
            await self._call(handler, 'start_background', self.get_config(plugin_id))
        except AttributeError:
            return
        self._background_started.add(plugin_id)

    async def _stop_plugin_background(self, plugin_id: str) -> None:
        handler = self._handlers.get(plugin_id)
        if handler is not None:
            try:
                await self._call(handler, 'stop_background')
            except (AttributeError, Exception):
                pass
        self._background_started.discard(plugin_id)

    async def start_background_tasks(self) -> None:
        if not self._manifests:
            await self.reload_plugins()
        for plugin_id in self._handlers:
            await self._start_plugin_background(plugin_id)

    async def stop_background_tasks(self) -> None:
        for plugin_id in list(self._background_started):
            await self._stop_plugin_background(plugin_id)

    async def get_background_tasks(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for plugin_id, handler in self._handlers.items():
            if not self._is_enabled(plugin_id):
                continue
            try:
                result = await self._call(handler, 'background_tasks', self.get_config(plugin_id))
            except (AttributeError, Exception):
                continue
            values = result if isinstance(result, list) else [result]
            for value in values:
                if isinstance(value, dict):
                    items.append({'plugin_id': plugin_id, 'plugin_name': self._manifests.get(plugin_id, {}).get('name', plugin_id), **value})
        return items

    def get_external_task_contributions(self) -> dict[str, dict[str, Any]]:
        contributions: dict[str, dict[str, Any]] = {}
        for plugin_id, manifest in self._manifests.items():
            ext = (manifest.get('contributions') or {}).get('external_task')
            if isinstance(ext, dict):
                contributions[plugin_id] = {
                    'provider_id': plugin_id,
                    'label': ext.get('label') or manifest.get('name') or plugin_id,
                    'phase_label': ext.get('phase_label') or '外部任务',
                    'can_cancel': bool(ext.get('can_cancel', False)),
                    'poll_interval': int(ext.get('poll_interval') or 10000),
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
            if 'external_task_provider' not in (manifest.get('capabilities') or []):
                continue
            handler = self._handlers.get(plugin_id)
            callback = getattr(handler, 'sync_external_tasks', None)
            if not callable(callback):
                continue
            checked += 1
            try:
                result = callback(self.get_config(plugin_id), job_id=job_id)
                result = await result if asyncio.iscoroutine(result) else result
                if isinstance(result, dict):
                    updated += int(result.get('updated') or 0)
            except Exception as exc:
                errors.append({'plugin_id': plugin_id, 'error': str(exc)})
        return {'checked': checked, 'updated': updated, 'errors': errors}


runtime = PluginRuntime()
