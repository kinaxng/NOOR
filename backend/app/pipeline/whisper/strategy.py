"""Stable Whisper strategy presets and their execution summaries.

This source is reconstructed from the preserved Python 3.13 bytecode.  Keep
the preset payloads compatible with queued jobs: the orchestration module
still consumes these keys when it builds a :class:`WhisperConfig`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RECOMMENDED_WHISPER_STRATEGY = {
    "strategy": "recommended",
    "model": "anime-whisper",
    "pipeline_mode": "ensemble",
    "merge_strategy": "smart_merge",
    "language": "ja",
    "sensitivity": "balanced",
    "vad_method": "semantic",
    "speech_enhancer": "none",
    "audio_preprocess_mode": "none",
    "audio_preprocess_model": "vocal_balanced",
    "pass1_pipeline": "anime",
    "pass2_pipeline": "qwen",
    "custom_config": None,
    "timestamp_mode": "aligner_interpolation",
    "aligner_backend": "qwen3",
    "framer_backend": "vad-grouped",
}

BASELINE_WHISPER_STRATEGY = {
    "strategy": "baseline",
    "model": "large-v3",
    "pipeline_mode": "qwen",
    "merge_strategy": "smart_merge",
    "language": "ja",
    "sensitivity": "balanced",
    "vad_method": "semantic",
    "speech_enhancer": "none",
    "audio_preprocess_mode": "none",
    "audio_preprocess_model": "vocal_balanced",
    "pass1_pipeline": "qwen",
    "pass2_pipeline": "",
    "custom_config": None,
    "timestamp_mode": "aligner_interpolation",
    "aligner_backend": "none",
    "framer_backend": "vad-grouped",
}

REAZON_NEMO_WHISPER_STRATEGY = {
    "strategy": "reazon_nemo",
    "model": "reazonspeech-nemo-v2",
    "pipeline_mode": "reazon",
    "merge_strategy": "smart_merge",
    "language": "ja",
    "sensitivity": "balanced",
    "vad_method": "semantic",
    "speech_enhancer": "none",
    "audio_preprocess_mode": "none",
    "audio_preprocess_model": "vocal_balanced",
    "pass1_pipeline": "reazon",
    "pass2_pipeline": "",
    "custom_config": None,
    "timestamp_mode": "aligner_interpolation",
    "aligner_backend": "none",
    "framer_backend": "vad-grouped",
}

_BASELINE_ALIASES = {
    "baseline",
    "compare",
    "compat",
    "compatibility",
    "contrast",
    "experiment",
    "experimental",
    "fast",
    "faster",
}
_REAZON_ALIASES = {
    "reazon",
    "reazon_nemo",
    "reazonspeech",
    "reazonspeech-nemo-v2",
    "nemo",
}


def normalize_whisper_strategy(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "best":
        return "recommended"
    if normalized in _BASELINE_ALIASES:
        return "baseline"
    if normalized in _REAZON_ALIASES:
        return "reazon_nemo"
    return normalized or "advanced"


@dataclass
class WhisperExecutionPlan:
    strategy: str
    executor_key: str
    runtime_settings: dict[str, Any]
    summary: str
    detail_lines: tuple[str, ...] = ()


def apply_whisper_strategy(payload: dict[str, Any], strategy: str | None) -> dict[str, Any]:
    normalized = normalize_whisper_strategy(strategy)
    merged = dict(payload)
    if normalized == "recommended":
        merged.update(RECOMMENDED_WHISPER_STRATEGY)
        return merged
    if normalized == "baseline":
        merged.update(BASELINE_WHISPER_STRATEGY)
        return merged
    if normalized == "reazon_nemo":
        merged.update(REAZON_NEMO_WHISPER_STRATEGY)
        return merged
    merged["strategy"] = normalized
    return merged


def is_recommended_whisper_strategy(strategy: str | None) -> bool:
    return normalize_whisper_strategy(strategy) == "recommended"


def build_whisper_execution_plan(
    payload: dict[str, Any], strategy: str | None = None
) -> WhisperExecutionPlan:
    normalized = normalize_whisper_strategy(strategy or payload.get("strategy"))
    runtime_settings = apply_whisper_strategy(payload, normalized)
    preprocess_mode = str(runtime_settings.get("audio_preprocess_mode") or "none").strip().lower()
    preprocess_model = str(runtime_settings.get("audio_preprocess_model") or "vocal_balanced").strip().lower()
    preprocess_detail_lines: tuple[str, ...] = ()
    if preprocess_mode != "none":
        preprocess_detail_lines = (
            f"实验前处理: {preprocess_mode} / {preprocess_model}",
            "注意: 音频前处理当前仅建议手动实验，不进入默认推荐链路",
        )

    if normalized == "recommended":
        return WhisperExecutionPlan(
            strategy="recommended",
            executor_key="recommended",
            runtime_settings=runtime_settings,
            summary="推荐字幕策略",
            detail_lines=(
                "执行分支: recommended",
                "主链路: Anime-Whisper + Qwen3-ASR fallback + Qwen3 ForcedAligner",
                "固定参数: ensemble / anime+qwen3-align / ja / balanced / smart_merge",
                *preprocess_detail_lines,
            ),
        )
    if normalized == "baseline":
        return WhisperExecutionPlan(
            strategy="baseline",
            executor_key="baseline",
            runtime_settings=runtime_settings,
            summary="large-v3 对照策略",
            detail_lines=(
                "执行分支: baseline",
                "主链路: faster-whisper large-v3",
                "固定参数: qwen(legacy key) / large-v3 / ja / balanced / semantic",
            ),
        )
    if normalized == "reazon_nemo":
        return WhisperExecutionPlan(
            strategy="reazon_nemo",
            executor_key="reazon_nemo",
            runtime_settings=runtime_settings,
            summary="Reazon / NeMo 实验策略",
            detail_lines=(
                "执行分支: reazon_nemo",
                "主链路: ReazonSpeech NeMo v2 单链路",
                "固定参数: reazon / ja / balanced / smart_merge",
                "注意: 当前运行时仍属实验接入，需本地准备 .nemo 包与 nemo_toolkit",
            ),
        )
    return WhisperExecutionPlan(
        strategy=normalized,
        executor_key="advanced",
        runtime_settings=runtime_settings,
        summary="高级参数策略",
        detail_lines=(
            "执行分支: advanced",
            "运行参数: 以任务保存的 pipeline / merge / custom_config 为准",
            *preprocess_detail_lines,
        ),
    )
