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
    payload["subtitle_profile"] = payload.get("subtitle_profile", "standard")
    payload["model_backend"] = payload.get("model_backend") or payload.get("model") or "chickenrice-zh"
    payload["runtime_tier"] = payload.get("runtime_tier") or "gpu_standard"
    payload["whisper_task"] = payload.get("whisper_task") or ("translate" if payload["model_backend"] == "chickenrice-zh" else "transcribe")
    payload["vad_backend"] = payload.get("vad_backend", "energy")
    payload["chunker"] = payload.get("chunker", "smart_vad_chunk")
    payload["target_chunk_duration_s"] = payload.get("target_chunk_duration_s", 30.0)
    payload["max_chunk_duration_s"] = payload.get("max_chunk_duration_s", 30.0)
    payload["segment_merge_max_gap_ms"] = payload.get("segment_merge_max_gap_ms", 2000)
    payload["segment_merge_max_duration_ms"] = payload.get("segment_merge_max_duration_ms", 20000)
    payload["timing_refiner"] = payload.get("timing_refiner", "none")
    return payload


def apply_whisper_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    payload = normalize_whisper_config_payload(config)
    legacy_defaults = {
        "merge_strategy": "smart_merge",
        "language": "ja",
        "sensitivity": "balanced",
        "vad_method": "semantic",
        "audio_preprocess_mode": "none",
        "audio_preprocess_model": "vocal_balanced",
        "translate_to": "",
        "translate_model": "gpt-4o-mini",
        "translate_style": "adult_explicit",
        "translate_base_url": "https://api.openai.com/v1",
        "translate_api_key": "",
        "pass1_pipeline": payload.get("pipeline_mode", "faster"),
        "pass2_pipeline": "",
    }
    for env_key, payload_key in (
        ("WHISPER_STRATEGY", "strategy"),
        ("WHISPER_SUBTITLE_PROFILE", "subtitle_profile"),
        ("WHISPER_MODEL_BACKEND", "model_backend"),
        ("WHISPER_RUNTIME_TIER", "runtime_tier"),
        ("WHISPER_DEVICE", "device"),
        ("WHISPER_COMPUTE_TYPE", "compute_type"),
        ("WHISPER_TASK", "whisper_task"),
        ("WHISPER_VAD_BACKEND", "vad_backend"),
        ("WHISPER_CHUNKER", "chunker"),
        ("WHISPER_TARGET_CHUNK_DURATION_S", "target_chunk_duration_s"),
        ("WHISPER_MAX_CHUNK_DURATION_S", "max_chunk_duration_s"),
        ("WHISPER_SEGMENT_MERGE_MAX_GAP_MS", "segment_merge_max_gap_ms"),
        ("WHISPER_SEGMENT_MERGE_MAX_DURATION_MS", "segment_merge_max_duration_ms"),
        ("WHISPER_TIMING_REFINER", "timing_refiner"),
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
        update_env_value_fn(env_key, str(payload.get(payload_key, legacy_defaults.get(payload_key, ""))))
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
