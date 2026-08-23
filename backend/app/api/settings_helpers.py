"""Shared helpers used by the settings API.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from app.core.config import DEFAULT_NOOR_DATA_DIR, PROJECT_ROOT, get_settings
from app.core.lada_paths import build_lada_python_env, resolve_lada_repo_path as _resolve_lada_repo_path


logger = logging.getLogger(__name__)
_version_cache: dict[str, dict] = {}
_version_cache_lock = threading.Lock()
_VERSION_CACHE_TTL = 3600
LADA_MODEL_WEIGHTS_ENV = "LADA_MODEL_WEIGHTS_DIR"
ENV_FILE = PROJECT_ROOT / ".env"

WHISPER_MODELS = {
    "chickenrice-zh": {
        "name": "ChickenRice JA->ZH",
        "size": "~3GB",
        "type": "faster-whisper",
        "repo": "chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2",
        "description": "Japanese audio to Chinese subtitle CTranslate2 model",
    },
    "anime-whisper": {"name": "Anime-Whisper", "size": "~3GB", "type": "transformers", "repo": "litagin/anime-whisper", "description": "Optimized for anime vocals, Japanese"},
    "large-v3": {"name": "Large V3", "size": "~3GB", "type": "faster-whisper"},
    "whisper-vad-onnx": {
        "name": "Whisper-VAD ONNX",
        "size": "~250MB",
        "type": "onnx-vad",
        "repo": "TransWithAI/Whisper-Vad-EncDec-ASMR-onnx",
        "description": "Smart VAD chunk detector for Whisper subtitle pipeline",
    },
}


def clear_version_cache():
    with _version_cache_lock:
        _version_cache.clear()


def get_httpx():
    import httpx

    return httpx


def read_env_file() -> dict[str, str]:
    env_data: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env_data[key.strip()] = value.strip()
    return env_data


def write_env_file(env_data: dict[str, str]) -> None:
    lines = []
    for key, value in env_data.items():
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")


def set_env_values(updates: dict[str, str], remove_keys: tuple[str, ...] = ()) -> None:
    env_data = read_env_file()
    for key in remove_keys:
        env_data.pop(key, None)
    env_data.update(updates)
    write_env_file(env_data)


def update_env_value(key: str, value: str) -> None:
    set_env_values({key: value})


def get_lada_model_weights_dir_from_env(env_data: dict[str, str]) -> str:
    if env_data.get(LADA_MODEL_WEIGHTS_ENV):
        return env_data[LADA_MODEL_WEIGHTS_ENV]
    data_dir = Path(env_data.get("NOOR_DATA_DIR") or DEFAULT_NOOR_DATA_DIR)
    return str(data_dir / "models" / "lada")


def python_executable() -> str:
    return sys.executable or "python3"


def lada_cli_base_cmd(cli_path: Optional[str] = None) -> list[str]:
    resolved = (cli_path or get_settings().lada_cli_path or "lada-cli").strip()
    return shlex.split(resolved) if resolved else ["lada-cli"]


def resolve_lada_repo_path() -> Optional[Path]:
    return _resolve_lada_repo_path()


def get_whisper_feature_flags() -> dict:
    return {}


def get_lada_installation_info() -> dict:
    is_docker = os.path.exists("/.dockerenv")
    repo_path = resolve_lada_repo_path()
    if is_docker:
        return {"is_docker": True, "repo_path": str(repo_path) if repo_path else None, "install_mode": "docker-image", "can_self_upgrade": False, "upgrade_strategy": "docker-rebuild", "upgrade_hint": "Docker 模式下不建议在容器内执行 git pull / pip install；应更新镜像后重建容器。", "is_submodule": bool(repo_path)}
    if repo_path:
        return {"is_docker": False, "repo_path": str(repo_path), "install_mode": "editable-repo", "can_self_upgrade": True, "upgrade_strategy": "git-pull-reinstall", "upgrade_hint": "当前使用项目内 LADA 工作副本，可在设置页执行官方仓库拉取并重新安装。", "is_submodule": True}
    return {"is_docker": False, "repo_path": None, "install_mode": "external-cli", "can_self_upgrade": False, "upgrade_strategy": "manual-external", "upgrade_hint": "当前仅检测到外部 lada-cli，可手动升级该安装来源。", "is_submodule": False}


def get_lada_version_info() -> dict:
    now = time.time()
    cache_key = "lada_version"
    with _version_cache_lock:
        entry = _version_cache.get(cache_key)
        if entry and now - entry["ts"] < _VERSION_CACHE_TTL:
            return entry["data"]
    install_info = get_lada_installation_info()
    version = None
    try:
        result = subprocess.run(lada_cli_base_cmd() + ["--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout.strip()
            version = output.replace("Lada:", "").strip() if output else None
    except Exception:
        pass
    if not version:
        try:
            result = subprocess.run(
                [python_executable(), "-c", "import lada; print(getattr(lada, 'VERSION', ''))"],
                capture_output=True,
                text=True,
                timeout=5,
                env=build_lada_python_env(),
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
        except Exception:
            pass
    if not version and install_info["repo_path"]:
        try:
            result = subprocess.run(["git", "describe", "--tags", "--always", "HEAD"], cwd=install_info["repo_path"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
        except Exception:
            pass
    data = {"version": version, "is_docker": install_info["is_docker"], "is_submodule": install_info["is_submodule"], "install_mode": install_info["install_mode"], "can_self_upgrade": install_info["can_self_upgrade"], "upgrade_strategy": install_info["upgrade_strategy"], "upgrade_hint": install_info["upgrade_hint"], "repo_path": install_info["repo_path"]}
    with _version_cache_lock:
        _version_cache[cache_key] = {"data": data, "ts": now}
    return data


def format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "Unknown"
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.0f}MB"
    return f"{size_bytes / 1024:.0f}KB"
