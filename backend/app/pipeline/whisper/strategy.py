from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .runtime_tier import apply_whisper_runtime_tier


CHICKENRICE_WHISPER_STRATEGY = {
    "strategy": "chickenrice",
    "subtitle_profile": "standard",
    "model_backend": "chickenrice-zh",
    "runtime_tier": "gpu_standard",
    "device": "cuda",
    "compute_type": "float16",
    "model": "chickenrice-zh",
    "whisper_task": "translate",
    "vad_backend": "whisper_vad_onnx",
    "chunker": "smart_vad_chunk",
    "target_chunk_duration_s": 30.0,
    "max_chunk_duration_s": 30.0,
    "segment_merge_max_gap_ms": 2000,
    "segment_merge_max_duration_ms": 20000,
    "timing_refiner": "none",
    "pipeline_mode": "faster",
    "language": "ja",
    "sensitivity": "balanced",
}

RECOMMENDED_WHISPER_STRATEGY = CHICKENRICE_WHISPER_STRATEGY

_BASELINE_ALIASES = {
    "baseline", "compare", "compat", "compatibility", "contrast",
    "experiment", "experimental", "fast", "faster", "large-v3",
}
_ANIME_ALIASES = {"anime", "anime-whisper"}


def _apply_model_backend(merged: dict[str, Any]) -> dict[str, Any]:
    backend = str(merged.get("model_backend") or merged.get("model") or "chickenrice-zh").strip()
    if backend == "anime-whisper":
        merged.update({
            "model_backend": "anime-whisper",
            "model": "anime-whisper",
            "whisper_task": "transcribe",
            "pipeline_mode": "anime",
        })
    elif backend in {"qwen", "qwen-whisper", "large-v3"}:
        merged.update({
            "model_backend": "large-v3",
            "model": "large-v3",
            "whisper_task": "transcribe",
            "pipeline_mode": "faster",
        })
    else:
        merged.update({
            "model_backend": "chickenrice-zh",
            "model": "chickenrice-zh",
            "whisper_task": "translate",
            "pipeline_mode": "faster",
        })
    return merged


def normalize_whisper_strategy(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _BASELINE_ALIASES | _ANIME_ALIASES:
        return "chickenrice"
    return "chickenrice"


@dataclass
class WhisperExecutionPlan:
    strategy: str
    executor_key: str
    runtime_settings: dict[str, Any]
    summary: str
    detail_lines: tuple[str, ...] = ()


def apply_whisper_strategy(payload: dict[str, Any], strategy: str | None) -> dict[str, Any]:
    raw_strategy = str(strategy or payload.get("strategy") or "").strip().lower()
    merged = dict(payload)
    editable_runtime_fields = {
        key: merged[key]
        for key in (
            "vad_backend",
            "chunker",
            "target_chunk_duration_s",
            "max_chunk_duration_s",
            "segment_merge_max_gap_ms",
            "segment_merge_max_duration_ms",
            "timing_refiner",
            "runtime_tier",
        )
        if key in merged and merged[key] not in (None, "")
    }
    selected_backend = merged.get("model_backend") or merged.get("model")
    if not selected_backend and raw_strategy in _BASELINE_ALIASES:
        selected_backend = "large-v3"
    elif not selected_backend and raw_strategy in _ANIME_ALIASES:
        selected_backend = "anime-whisper"

    merged.update(CHICKENRICE_WHISPER_STRATEGY)
    merged.update(editable_runtime_fields)
    if selected_backend:
        merged["model_backend"] = selected_backend
    _apply_model_backend(merged)
    apply_whisper_runtime_tier(merged)
    return merged


def is_recommended_whisper_strategy(strategy: str | None) -> bool:
    return normalize_whisper_strategy(strategy) == "chickenrice"


def build_whisper_execution_plan(
    payload: dict[str, Any], strategy: str | None = None
) -> WhisperExecutionPlan:
    runtime_settings = apply_whisper_strategy(payload, strategy or payload.get("strategy"))
    return WhisperExecutionPlan(
        strategy="chickenrice",
        executor_key="chickenrice",
        runtime_settings=runtime_settings,
        summary="NOOR ChickenRice 主字幕链路",
        detail_lines=(
            "执行分支: chickenrice",
            "主链路: Faster-Whisper + ChickenRice 日中直出模型",
            f"运行档位: {runtime_settings.get('runtime_tier')} ({runtime_settings.get('device')} / {runtime_settings.get('compute_type')})",
            "固定参数: ja -> zh / faster-whisper backend / smart VAD chunk",
        ),
    )
