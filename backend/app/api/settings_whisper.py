"""Whisper settings normalization helpers.

Reconstructed from the preserved Python 3.13 bytecode.  These helpers are
kept separate from the FastAPI route so settings and queued-task payloads use
the same stable shape.
"""
from __future__ import annotations

from typing import Any, Callable

from app.pipeline.whisper.strategy import apply_whisper_strategy


TRANSFORMERS_MODEL_KEYS = {"anime-whisper": "anime_whisper"}
ONNX_VAD_MODEL_KEYS = {"whisper-vad-onnx": "whisper_vad_onnx"}


def normalize_whisper_config_payload(config: Any) -> dict[str, Any]:
    payload = config.model_dump() if hasattr(config, "model_dump") else dict(config)
    payload = apply_whisper_strategy(payload, payload.get("strategy"))

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
        "language": "ja",
        "sensitivity": "balanced",
        "translate_to": "",
        "translate_model": "gpt-4o-mini",
        "translate_style": "adult_explicit",
        "translate_base_url": "https://api.openai.com/v1",
        "translate_api_key": "",
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
        ("WHISPER_LANGUAGE", "language"),
        ("WHISPER_SENSITIVITY", "sensitivity"),
        ("WHISPER_TRANSLATE_TO", "translate_to"),
        ("WHISPER_TRANSLATE_MODEL", "translate_model"),
        ("WHISPER_TRANSLATE_STYLE", "translate_style"),
        ("WHISPER_TRANSLATE_BASE_URL", "translate_base_url"),
        ("WHISPER_TRANSLATE_API_KEY", "translate_api_key"),
    ):
        update_env_value_fn(env_key, str(payload.get(payload_key, legacy_defaults.get(payload_key, ""))))


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
        elif info["type"] in {"onnx", "onnx-vad"}:
            check_key = ONNX_VAD_MODEL_KEYS.get(key, key)
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
                "managed_externally": False,
            }
        )
    return models
