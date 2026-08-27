"""Whisper model cache management helpers, reconstructed from bytecode."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

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
    return candidates


def delete_whisper_model_files(
    *, model_name: str, model_info: dict[str, Any], whisper_model_dir: str
) -> list[str]:
    deleted: list[str] = []

    def delete_model_candidates(repo_id: str) -> None:
        for path in resolve_model_cache_candidates(whisper_model_dir, repo_id):
            if path.exists():
                shutil.rmtree(path)
                deleted.append(str(path))

    if model_info["type"] in {"transformers", "onnx-vad", "onnx"}:
        delete_model_candidates(model_info["repo"])
    else:
        repo_id = model_info.get("repo") or f"Systran/faster-whisper-{model_name}"
        delete_model_candidates(repo_id)

    return deleted
