"""Safe filesystem browsing helpers for directory settings.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import os
from typing import Any


COMMON_ALLOWED_PREFIXES = ("/mnt/", "/media/", "/srv/")


def is_allowed_directory_path(path: str, settings: Any) -> bool:
    try:
        real = os.path.realpath(os.path.expanduser(path))
        home = os.path.expanduser("~")
        if real.startswith(home + "/") or real == home:
            return True

        for allowed in (
            getattr(settings, "source_dir", ""),
            getattr(settings, "output_dir", ""),
            getattr(settings, "noor_data_dir", ""),
            getattr(settings, "model_root_dir", ""),
            getattr(settings, "runtime_root_dir", ""),
            getattr(settings, "whisper_model_dir", ""),
            getattr(settings, "whisper_cache_dir", ""),
            getattr(settings, "whisper_temp_dir", ""),
            getattr(settings, "lada_model_dir", ""),
            getattr(settings, "lada_cache_dir", ""),
            getattr(settings, "lada_temp_dir", ""),
            getattr(settings, "facefusion_model_dir", ""),
            getattr(settings, "facefusion_cache_dir", ""),
            getattr(settings, "facefusion_temp_dir", ""),
        ):
            if not allowed:
                continue
            allowed_real = os.path.realpath(os.path.expanduser(allowed))
            if real.startswith(allowed_real + "/") or real == allowed_real:
                return True

        if real.startswith(COMMON_ALLOWED_PREFIXES):
            return True
        if real.startswith("/home/") or real == "/home":
            return True
        return False
    except Exception:
        return False


def resolve_browse_path(settings: Any, path: str = "") -> str:
    if not path:
        return settings.source_dir or os.path.expanduser("~")
    return os.path.expanduser(path)


def build_directory_browse_payload(path: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for entry in os.scandir(path):
        try:
            entries.append(
                {"name": entry.name, "path": entry.path, "is_dir": entry.is_dir()}
            )
        except PermissionError:
            continue
    entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))
    home = os.path.expanduser("~")
    parent = os.path.dirname(path) if path not in ("/", home) else None
    return {"path": path, "parent": parent, "entries": entries}
