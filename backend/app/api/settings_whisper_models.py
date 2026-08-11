"""Whisper model cache management helpers, reconstructed from bytecode."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.core.config import DEFAULT_REAZON_NEMO_MODEL_PATH


def resolve_whisper_model_dir(settings: Any, default_model_dir: str) -> str:
    return settings.whisper_model_dir or default_model_dir


def resolve_hf_cache_layout(whisper_model_dir: str) -> dict[str, Any]:
    default_hf_cache = str(Path.home() / ".cache" / "huggingface")
    return {
        "default_hf_cache": default_hf_cache,
        "is_default_hf": whisper_model_dir == default_hf_cache,
        "hf_base": Path(whisper_model_dir),
        "default_hf_base": Path(default_hf_cache),
    }


def resolve_model_cache_candidates(whisper_model_dir: str, repo_id: str) -> list[Path]:
    repo_cache_name = f"models--{repo_id.replace('/', '--')}"
    base = Path(whisper_model_dir)
    candidates: list[Path] = []

    def append(path: Path) -> None:
        if path not in candidates:
            candidates.append(path)

    append(base / repo_cache_name)
    append(base / "hub" / repo_cache_name)
    append(base / "huggingface" / "hub" / repo_cache_name)
    append(base / "hub" / repo_cache_name)
    return candidates


def delete_whisper_model_files(
    *, model_name: str, model_info: dict[str, Any], whisper_model_dir: str
) -> list[str]:
    deleted: list[str] = []
    layout = resolve_hf_cache_layout(whisper_model_dir)

    def transformers_delete(repo: str, base: Path) -> bool:
        cache = base / ("hub" if str(base) == layout["default_hf_cache"] else "huggingface/hub")
        path = cache / f"models--{repo.replace('/', '--')}"
        if path.exists():
            shutil.rmtree(path)
            deleted.append(str(path))
            return True
        return False

    def faster_delete(repo_cache_name: str, base: Path) -> bool:
        path1 = base / "hub" / f"models--{repo_cache_name}"
        path2 = base / f"models--{repo_cache_name}"
        path = path1 if path1.exists() else path2
        if path.exists():
            shutil.rmtree(path)
            deleted.append(str(path))
            return True
        return False

    if model_info["type"] == "reazon-nemo":
        nemo_path = Path(model_info.get("path") or DEFAULT_REAZON_NEMO_MODEL_PATH)
        if nemo_path.exists():
            nemo_path.unlink()
            deleted.append(str(nemo_path))
        compat_link = nemo_path.parent.parent / nemo_path.name
        if compat_link.is_symlink():
            compat_link.unlink()
            deleted.append(str(compat_link))
        return deleted
    if model_info["type"] == "transformers":
        found = transformers_delete(model_info["repo"], layout["hf_base"])
        if not found and not layout["is_default_hf"]:
            transformers_delete(model_info["repo"], layout["default_hf_base"])
        return deleted
    repo_cache_name = model_info["repo"].replace("/", "--") if model_info.get("repo") else f"Systran--faster-whisper-{model_name}"
    found = faster_delete(repo_cache_name, layout["hf_base"])
    if not found and not layout["is_default_hf"]:
        faster_delete(repo_cache_name, layout["default_hf_base"])
    mx_path = Path.home() / ".cache" / "mx Fofr" / "Faster-Whisper" / model_name
    if mx_path.exists():
        shutil.rmtree(mx_path)
        deleted.append(str(mx_path))
    return deleted
