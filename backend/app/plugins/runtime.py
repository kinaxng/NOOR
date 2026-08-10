from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.core.runtime_paths import data_path


class PluginRuntime:
    def __init__(self) -> None:
        self.plugin_root = PROJECT_ROOT / 'plugins'
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

    def _load_handler(self, plugin_id: str, plugin_dir: Path) -> Any | None:
        backend = plugin_dir / 'backend.py'
        if not backend.is_file():
            return None
        module_name = f'noor_plugin_{plugin_id.replace("-", "_")}'
        try:
            spec = importlib.util.spec_from_file_location(module_name, backend)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None

    async def reload_plugins(self) -> list[dict[str, Any]]:
        async with self._lock:
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
                handler = self._load_handler(plugin_id, manifest_path.parent)
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

    def get_config(self, plugin_id: str) -> dict[str, Any]:
        return self._configs().get(plugin_id, {})

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
        for name, args in (
            ('handle_action', (action, payload, config)),
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


runtime = PluginRuntime()
