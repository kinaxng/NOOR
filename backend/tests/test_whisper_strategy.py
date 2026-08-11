from __future__ import annotations

from app.pipeline.whisper.runtime_tier import resolve_whisper_runtime_tier
from app.pipeline.whisper.strategy import (
    CHICKENRICE_WHISPER_STRATEGY,
    apply_whisper_strategy,
    build_whisper_execution_plan,
    is_recommended_whisper_strategy,
    normalize_whisper_strategy,
)


def test_normalize_whisper_strategy_collapses_to_chickenrice():
    assert normalize_whisper_strategy("recommended") == "chickenrice"
    assert normalize_whisper_strategy("baseline") == "chickenrice"
    assert normalize_whisper_strategy("advanced") == "chickenrice"
    assert normalize_whisper_strategy("anything") == "chickenrice"


def test_apply_whisper_strategy_defaults_to_chickenrice_direct_model():
    payload = apply_whisper_strategy({"model_backend": ""}, "advanced")
    assert payload["strategy"] == "chickenrice"
    assert payload["model_backend"] == "chickenrice-zh"
    assert payload["model"] == "chickenrice-zh"
    assert payload["whisper_task"] == "translate"
    assert payload["pipeline_mode"] == "faster"
    assert payload["chunker"] == "smart_vad_chunk"
    assert payload["runtime_tier"] == "gpu_standard"
    assert payload["device"] == "cuda"
    assert payload["compute_type"] == "float16"


def test_apply_whisper_strategy_preserves_model_backend_options():
    anime = apply_whisper_strategy({"model_backend": "anime-whisper"}, "recommended")
    large = apply_whisper_strategy({"model_backend": "large-v3"}, "recommended")
    assert (anime["model"], anime["whisper_task"], anime["pipeline_mode"]) == ("anime-whisper", "transcribe", "anime")
    assert (large["model"], large["whisper_task"], large["pipeline_mode"]) == ("large-v3", "transcribe", "faster")


def test_apply_whisper_strategy_preserves_editable_runtime_settings():
    payload = apply_whisper_strategy({
        "model_backend": "chickenrice-zh",
        "vad_backend": "whisper_vad_onnx",
        "chunker": "smart_vad_chunk",
        "target_chunk_duration_s": 24,
        "max_chunk_duration_s": 36,
        "segment_merge_max_gap_ms": 1200,
        "segment_merge_max_duration_ms": 18000,
        "timing_refiner": "subtimer_vad",
        "runtime_tier": "gpu_low_vram",
    }, "chickenrice")
    assert payload["vad_backend"] == "whisper_vad_onnx"
    assert payload["target_chunk_duration_s"] == 24
    assert payload["max_chunk_duration_s"] == 36
    assert payload["segment_merge_max_gap_ms"] == 1200
    assert payload["segment_merge_max_duration_ms"] == 18000
    assert payload["timing_refiner"] == "subtimer_vad"
    assert payload["runtime_tier"] == "gpu_low_vram"
    assert payload["device"] == "cuda"
    assert payload["compute_type"] == "int8_float16"


def test_recommended_strategy_matches_current_single_chain():
    assert is_recommended_whisper_strategy("advanced") is True
    assert is_recommended_whisper_strategy("best") is True
    assert CHICKENRICE_WHISPER_STRATEGY["model_backend"] == "chickenrice-zh"


def test_build_whisper_execution_plan_has_chickenrice_summary():
    plan = build_whisper_execution_plan({"model_backend": "large-v3"}, "recommended")
    assert plan.strategy == "chickenrice"
    assert plan.executor_key == "chickenrice"
    assert plan.summary == "NOOR ChickenRice 主字幕链路"
    assert plan.runtime_settings["model_backend"] == "large-v3"
    assert "执行分支: chickenrice" in plan.detail_lines
    assert "主链路: Faster-Whisper + ChickenRice 日中直出模型" in plan.detail_lines


def test_runtime_tier_aliases_are_normalized():
    assert resolve_whisper_runtime_tier("low-vram").value == "gpu_low_vram"
    assert resolve_whisper_runtime_tier("cpu_int8").device == "cpu"
