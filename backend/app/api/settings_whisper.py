"""Whisper settings normalization helpers.

Reconstructed from the preserved Python 3.13 bytecode.  These helpers are
kept separate from the FastAPI route so settings and queued-task payloads use
the same stable shape.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from app.pipeline.whisper.strategy import apply_whisper_strategy


TRANSFORMERS_MODEL_KEYS = {
    "anime-whisper": "anime_whisper",
    "kotoba-whisper-v2.2": "kotoba-whisper-v2.2",
}
SPECIAL_MODEL_KEYS = {"reazonspeech-nemo-v2": "reazon_nemo"}
DEFAULT_CUSTOM_PIPELINE_CONFIG = {
    "model": "large-v3",
    "vad_method": "semantic",
    "scene_detector": "semantic",
    "enhancers": [],
    "segmenter": "silero-v6.2",
    "timestamp_mode": "aligner_interpolation",
    "aligner_backend": "qwen3",
    "framer_backend": "vad-grouped",
}
DEFAULT_AUDIO_PREPROCESS_MODE = "none"
DEFAULT_AUDIO_PREPROCESS_MODEL = "vocal_balanced"


def normalize_whisper_config_payload(config: Any) -> dict[str, Any]:
    payload = config.model_dump() if hasattr(config, "model_dump") else dict(config)
    payload = apply_whisper_strategy(payload, payload.get("strategy"))

    raw_custom_config = payload.get("custom_config") or {}
    if hasattr(raw_custom_config, "model_dump"):
        raw_custom_config = raw_custom_config.model_dump()
    custom_config = {**DEFAULT_CUSTOM_PIPELINE_CONFIG, **raw_custom_config}
    custom_config["timestamp_mode"] = payload.get(
        "timestamp_mode", custom_config["timestamp_mode"]
    )
    custom_config["aligner_backend"] = payload.get(
        "aligner_backend", custom_config["aligner_backend"]
    )
    custom_config["framer_backend"] = payload.get(
        "framer_backend", custom_config["framer_backend"]
    )

    payload["custom_config"] = custom_config
    payload["timestamp_mode"] = custom_config["timestamp_mode"]
    payload["aligner_backend"] = custom_config["aligner_backend"]
    payload["framer_backend"] = custom_config["framer_backend"]
    payload["audio_preprocess_mode"] = payload.get(
        "audio_preprocess_mode", DEFAULT_AUDIO_PREPROCESS_MODE
    )
    payload["audio_preprocess_model"] = payload.get(
        "audio_preprocess_model", DEFAULT_AUDIO_PREPROCESS_MODEL
    )
    return payload


def apply_whisper_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    payload = normalize_whisper_config_payload(config)
    for env_key, payload_key in (
        ("WHISPER_STRATEGY", "strategy"),
        ("WHISPER_MODEL", "model"),
        ("WHISPER_PIPELINE_MODE", "pipeline_mode"),
        ("WHISPER_MERGE_STRATEGY", "merge_strategy"),
        ("WHISPER_LANGUAGE", "language"),
        ("WHISPER_SENSITIVITY", "sensitivity"),
        ("WHISPER_VAD_METHOD", "vad_method"),
        ("WHISPER_AUDIO_PREPROCESS_MODE", "audio_preprocess_mode"),
        ("WHISPER_AUDIO_PREPROCESS_MODEL", "audio_preprocess_model"),
        ("WHISPER_TRANSLATE_TO", "translate_to"),
        ("WHISPER_TRANSLATE_MODEL", "translate_model"),
        ("WHISPER_TRANSLATE_STYLE", "translate_style"),
        ("WHISPER_TRANSLATE_BASE_URL", "translate_base_url"),
        ("WHISPER_TRANSLATE_API_KEY", "translate_api_key"),
        ("WHISPER_PASS1_PIPELINE", "pass1_pipeline"),
        ("WHISPER_PASS2_PIPELINE", "pass2_pipeline"),
    ):
        update_env_value_fn(env_key, payload[payload_key])
    update_env_value_fn("WHISPER_CUSTOM_CONFIG", json.dumps(payload["custom_config"]))


def sanitize_download_status(download_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": download_status.get("status", "idle"),
        "progress": download_status.get("progress", 0),
        "message": download_status.get("message", ""),
        "model": download_status.get("model", ""),
    }


def build_whisper_models_payload(
    *, check_result: dict[str, Any], whisper_models: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    available_models = check_result.get("models", {})
    for key, info in whisper_models.items():
        if info["type"] == "transformers":
            check_key = TRANSFORMERS_MODEL_KEYS.get(key, key)
            downloaded = available_models.get(check_key, {}).get("downloaded", False)
        elif info["type"] == "reazon-nemo":
            check_key = SPECIAL_MODEL_KEYS.get(key, key)
            downloaded = available_models.get(check_key, {}).get("downloaded", False)
        else:
            downloaded = available_models.get(f"faster_{key}", {}).get("downloaded", False)
        models.append(
            {
                "id": key,
                "name": info["name"],
                "size": info["size"],
                "type": info["type"],
                "downloaded": downloaded,
                "description": info.get("description", ""),
                "managed_externally": info.get("type") == "reazon-nemo",
            }
        )
    return models
