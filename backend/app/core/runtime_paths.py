from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT

try:
    from app.core.config import DEFAULT_NOOR_DATA_DIR as CONFIG_DEFAULT_NOOR_DATA_DIR
except ImportError:
    # The recovered configuration bytecode predates this exported constant.
    CONFIG_DEFAULT_NOOR_DATA_DIR = str(PROJECT_ROOT / "data")


DEFAULT_NOOR_DATA_DIR = Path(CONFIG_DEFAULT_NOOR_DATA_DIR)


def configured_or_default(value: str | None, default_path: str | Path) -> str:
    configured = (value or "").strip()
    return configured or str(default_path)


def noor_data_dir(settings: Any | None = None) -> Path:
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    value = getattr(settings, "noor_data_dir", "") if settings is not None else ""
    return Path(configured_or_default(value, DEFAULT_NOOR_DATA_DIR))


def data_path(*parts: str | Path, settings: Any | None = None) -> Path:
    return noor_data_dir(settings).joinpath(*parts)


def plugin_cache_path(plugin_id: str | None = None, *parts: str | Path, settings: Any | None = None) -> Path:
    base = data_path("plugin_cache", settings=settings)
    if plugin_id:
        base = base / plugin_id
    return base.joinpath(*parts)


def plugin_data_path(plugin_id: str, *parts: str | Path, settings: Any | None = None) -> Path:
    return data_path(plugin_id, *parts, settings=settings)


def model_dir(settings: Any, module: str, configured: str | None = None) -> Path:
    return Path(configured_or_default(configured, noor_data_dir(settings) / "models" / module))


def runtime_dir(settings: Any, module: str, kind: str, configured: str | None = None) -> Path:
    return Path(configured_or_default(configured, noor_data_dir(settings) / "runtime" / module / kind))


def ensure_directory(path: str | Path) -> str:
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def build_whisper_cache_env(model_path: str | Path, cache_path: str | Path) -> dict[str, str]:
    model_value = str(model_path)
    cache_value = str(cache_path)
    return {
        "HF_HOME": model_value,
        "HF_HUB_CACHE": str(Path(model_value) / "hub"),
        "TORCH_HOME": str(Path(cache_value) / "torch"),
        "XDG_CACHE_HOME": cache_value,
    }


def apply_whisper_cache_env(model_path: str | Path, cache_path: str | Path) -> None:
    os.environ.pop("TRANSFORMERS_CACHE", None)
    os.environ.update(build_whisper_cache_env(model_path, cache_path))
