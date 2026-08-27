"""Settings-page response payload assembly.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.api.endpoints.media_library_helpers import load_config as load_media_library_config
from app.api.settings_facefusion_upgrade import get_facefusion_installation_info
from app.core.config import PROJECT_ROOT, get_settings
from app.core.database_paths import sqlite_db_path_from_url
from app.core.facefusion_defaults import facefusion_settings_payload
from app.core.facefusion_paths import inspect_facefusion_model_dir, resolve_facefusion_source
from app.api.system import _ui_settings
from app.pipeline.whisper.strategy import apply_whisper_strategy, normalize_whisper_strategy


def split_enabled_library_ids(raw_value: str) -> list[str]:
    return raw_value.split(",") if raw_value else []


def database_path_for_display(database_url: str) -> str:
    path = sqlite_db_path_from_url(database_url)
    if path is None:
        return ""
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


def infer_model_root_dir(settings: Any, env_data: dict[str, str]) -> str:
    configured = env_data.get("MODEL_ROOT_DIR", "").strip()
    if configured:
        return configured
    whisper_model = Path(settings.whisper_model_dir)
    if whisper_model.name == "whisper":
        return str(whisper_model.parent)
    if any((whisper_model / name).exists() for name in ("hub", "models--Systran--faster-whisper-large-v3", "lada_model_weights")):
        return str(whisper_model)
    return str(Path(settings.noor_data_dir) / "models")


def infer_runtime_root_dir(settings: Any, env_data: dict[str, str]) -> str:
    configured = env_data.get("RUNTIME_ROOT_DIR", "").strip()
    if configured:
        return configured
    whisper_cache = Path(settings.whisper_cache_dir)
    if whisper_cache.name == "cache" and whisper_cache.parent.name == "whisper":
        return str(whisper_cache.parent.parent)
    return str(Path(settings.noor_data_dir) / "runtime")


def build_settings_payload(
    *,
    env_data: dict[str, str],
    version_info: dict[str, Any],
    lada_model_weights_dir: str,
    whisper_features: dict[str, Any],
) -> dict[str, Any]:
    media_library_config = load_media_library_config()
    settings = get_settings()
    facefusion_info = get_facefusion_installation_info(settings)
    facefusion_values = facefusion_settings_payload(settings)
    facefusion_defaults = {
        key.removeprefix("facefusion_"): value
        for key, value in facefusion_values.items()
        if key.startswith("facefusion_")
    }
    try:
        facefusion_source = resolve_facefusion_source(facefusion_values.get("facefusion_dir", ""))
        native_model_dir, model_dir_mode = inspect_facefusion_model_dir(
            facefusion_source.source_dir,
            facefusion_values.get("facefusion_model_dir", ""),
        )
    except Exception:
        native_model_dir = facefusion_values.get("facefusion_model_dir", "")
        model_dir_mode = "unavailable"
    raw_whisper_strategy = env_data.get("WHISPER_STRATEGY", "chickenrice")
    whisper_strategy = normalize_whisper_strategy(raw_whisper_strategy)
    env_model_backend = env_data.get("WHISPER_MODEL_BACKEND", "").strip()
    env_model = env_data.get("WHISPER_MODEL", "").strip()
    default_model_backend = env_model_backend or env_model or "chickenrice-zh"
    whisper_payload: dict[str, Any] = {
        "strategy": whisper_strategy,
        "subtitle_profile": env_data.get("WHISPER_SUBTITLE_PROFILE", "standard"),
        "model_backend": default_model_backend,
        "runtime_tier": env_data.get("WHISPER_RUNTIME_TIER", "gpu_standard"),
        "whisper_task": env_data.get("WHISPER_TASK", "translate"),
        "vad_backend": env_data.get("WHISPER_VAD_BACKEND", "whisper_vad_onnx"),
        "chunker": env_data.get("WHISPER_CHUNKER", "smart_vad_chunk"),
        "target_chunk_duration_s": float(env_data.get("WHISPER_TARGET_CHUNK_DURATION_S", "30") or 30),
        "max_chunk_duration_s": float(env_data.get("WHISPER_MAX_CHUNK_DURATION_S", "30") or 30),
        "segment_merge_max_gap_ms": int(env_data.get("WHISPER_SEGMENT_MERGE_MAX_GAP_MS", "2000") or 2000),
        "segment_merge_max_duration_ms": int(env_data.get("WHISPER_SEGMENT_MERGE_MAX_DURATION_MS", "20000") or 20000),
        "timing_refiner": env_data.get("WHISPER_TIMING_REFINER", "none"),
        "model": default_model_backend,
        "pipeline_mode": env_data.get("WHISPER_PIPELINE_MODE", "faster"),
        "language": env_data.get("WHISPER_LANGUAGE", "ja"),
        "sensitivity": env_data.get("WHISPER_SENSITIVITY", "balanced"),
        "translate_to": env_data.get("WHISPER_TRANSLATE_TO", ""),
        "translate_model": env_data.get("WHISPER_TRANSLATE_MODEL", "gpt-4o-mini"),
        "translate_style": env_data.get("WHISPER_TRANSLATE_STYLE", "adult_explicit"),
        "translate_base_url": env_data.get(
            "WHISPER_TRANSLATE_BASE_URL", "https://api.openai.com/v1"
        ),
        "translate_api_key": env_data.get("WHISPER_TRANSLATE_API_KEY", ""),
    }
    whisper_payload = apply_whisper_strategy(whisper_payload, whisper_strategy)
    ui_settings = _ui_settings()
    model_root_dir = infer_model_root_dir(settings, env_data)
    runtime_root_dir = infer_runtime_root_dir(settings, env_data)

    return {
        "emby": {
            "server": env_data.get("EMBY_SERVER", "")
            or media_library_config.get("server_url", ""),
            "api_key": env_data.get("EMBY_API_KEY", "")
            or media_library_config.get("api_key", ""),
            "user_id": env_data.get("EMBY_USER_ID", "")
            or media_library_config.get("user_id", ""),
            "enabled_library_ids": split_enabled_library_ids(
                env_data.get("EMBY_ENABLED_LIBRARY_IDS", "")
                or media_library_config.get("enabled_library_ids", "")
            ),
            "mdc_ng_actor_mapping_path": media_library_config.get("mdc_ng_actor_mapping_path", ""),
        },
        "storage": {
            "source_dir": settings.source_dir,
            "output_dir": settings.output_dir,
            "noor_data_dir": settings.noor_data_dir,
            "model_root_dir": model_root_dir,
            "runtime_root_dir": runtime_root_dir,
            "database_url": settings.database_url,
            "database_path": database_path_for_display(settings.database_url),
            "whisper_model_dir": settings.whisper_model_dir,
            "whisper_cache_dir": settings.whisper_cache_dir,
            "whisper_temp_dir": settings.whisper_temp_dir,
            "lada_model_dir": settings.lada_model_dir or lada_model_weights_dir,
            "lada_model_weights_dir": settings.lada_model_dir or lada_model_weights_dir,
            "lada_cache_dir": settings.lada_cache_dir,
            "lada_temp_dir": settings.lada_temp_dir,
            "facefusion_model_dir": settings.facefusion_model_dir,
            "facefusion_cache_dir": settings.facefusion_cache_dir,
            "facefusion_temp_dir": settings.facefusion_temp_dir,
        },
        "lada": {
            "cli_path": env_data.get("LADA_CLI_PATH", "python3 -m lada.cli.main"),
            "version": version_info["version"],
            "is_docker": version_info["is_docker"],
            "is_submodule": version_info["is_submodule"],
            "install_mode": version_info["install_mode"],
            "can_self_upgrade": version_info["can_self_upgrade"],
            "upgrade_strategy": version_info["upgrade_strategy"],
            "upgrade_hint": version_info["upgrade_hint"],
            "repo_path": version_info["repo_path"],
        },
        "lada_defaults": {
            "device": env_data.get("LADA_DEVICE", "cuda:0"),
            "fp16": env_data.get("LADA_FP16", "true").lower() == "true",
            "detection_model": env_data.get("LADA_DETECTION_MODEL", "v4-fast"),
            "restoration_model": env_data.get(
                "LADA_RESTORATION_MODEL", "basicvsrpp-v1.2"
            ),
            "encoding_preset": env_data.get(
                "LADA_ENCODING_PRESET", "hevc-nvidia-gpu-hq"
            ),
            "max_clip_length": int(env_data.get("LADA_MAX_CLIP_LENGTH", "180")),
            "detect_face_mosaics": env_data.get(
                "LADA_DETECT_FACE_MOSAICS", "false"
            ).lower()
            == "true",
        },
        "facefusion": {
            **facefusion_info,
            "dir": facefusion_values.get("facefusion_dir", ""),
            "python_path": facefusion_values.get("facefusion_python_path", ""),
            "native_model_dir": native_model_dir,
            "model_dir_mode": model_dir_mode,
            "resolved_dir": facefusion_info.get("source_dir", ""),
            "execution_providers": facefusion_info.get("execution_providers", []),
            "python_executable": facefusion_info.get("python_executable", ""),
            "runtime_versions": facefusion_info.get("runtime_versions", {}),
        },
        "facefusion_defaults": facefusion_defaults,
        "whisper": {**whisper_payload, "features": whisper_features},
        "network": {
            "acceleration_mode": env_data.get("ACCELERATION_MODE", "mirror"),
            "http_proxy": env_data.get("HTTP_PROXY", ""),
            "github_mirror": env_data.get("GITHUB_MIRROR", "https://ghproxy.com"),
            "github_token": env_data.get("GITHUB_TOKEN", ""),
            "hf_mirror": env_data.get("HF_MIRROR", "https://hf-mirror.com"),
            "pip_mirror": env_data.get(
                "PIP_MIRROR", "https://pypi.tuna.tsinghua.edu.cn/simple"
            ),
            "hf_token": env_data.get("HF_TOKEN", ""),
            "actor_mapping_auto_update": env_data.get(
                "ACTOR_MAPPING_AUTO_UPDATE", "true"
            ).lower()
            != "false",
        },
        "ui": {
            "cover_blur_enabled": bool(ui_settings.get("cover_blur", False)),
        },
    }
