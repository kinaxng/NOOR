from __future__ import annotations

import importlib.util
from types import ModuleType

from .runtime_paths import PLUGINS_DIR


_cache: dict[str, ModuleType | None] = {}


def clear_handler_cache() -> None:
    _cache.clear()


def get_plugin_handler(plugin_id: str) -> ModuleType | None:
    if plugin_id in _cache:
        return _cache[plugin_id]
    backend_path = PLUGINS_DIR / plugin_id / "backend.py"
    if not backend_path.is_file():
        _cache[plugin_id] = None
        return None
    module_name = f"noor_plugin_{plugin_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, backend_path)
    if spec is None or spec.loader is None:
        _cache[plugin_id] = None
        return None
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        module = None
    _cache[plugin_id] = module
    return module
