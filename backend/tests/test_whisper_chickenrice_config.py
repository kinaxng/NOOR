from __future__ import annotations

from app.api.settings_response import build_settings_payload
from app.api.settings_whisper import apply_whisper_config_updates, normalize_whisper_config_payload
from app.pipeline.whisper.types import PipelineMode, WhisperConfig, WhisperModel


def test_whisper_runtime_defaults_use_chickenrice_chain():
    config = WhisperConfig()
    assert config.strategy == "chickenrice"
    assert config.executor_key == "chickenrice"
    assert config.model == WhisperModel.CHICKENRICE_ZH
    assert config.pipeline_mode == PipelineMode.FASTER
    assert config.whisper_task == "translate"
    assert config.runtime_tier == "gpu_standard"
    assert not hasattr(config, "pass1_pipeline")
    assert not hasattr(config, "pass2_pipeline")
    assert not hasattr(config, "audio_preprocess_mode")


def test_settings_payload_defaults_match_frontend_chickenrice_profile():
    payload = build_settings_payload(
        env_data={},
        version_info={
            "version": None,
            "is_docker": False,
            "is_submodule": False,
            "install_mode": "unknown",
            "can_self_upgrade": False,
            "upgrade_strategy": "manual",
            "upgrade_hint": "",
            "repo_path": None,
        },
        lada_model_weights_dir="/models/lada",
        whisper_features={},
        custom_whisper_config={},
    )["whisper"]

    assert payload["strategy"] == "chickenrice"
    assert payload["model_backend"] == "chickenrice-zh"
    assert payload["model"] == "chickenrice-zh"
    assert payload["pipeline_mode"] == "faster"
    assert payload["runtime_tier"] == "gpu_standard"
    assert payload["device"] == "cuda"
    assert payload["compute_type"] == "float16"


def test_settings_save_persists_all_editable_runtime_fields():
    values: dict[str, str] = {}
    payload = normalize_whisper_config_payload({
        "strategy": "recommended",
        "model_backend": "large-v3",
        "runtime_tier": "gpu_low_vram",
        "vad_backend": "whisper_vad_onnx",
        "timing_refiner": "subtimer_vad",
        "target_chunk_duration_s": 24,
        "max_chunk_duration_s": 36,
        "segment_merge_max_gap_ms": 1200,
        "segment_merge_max_duration_ms": 18000,
    })
    apply_whisper_config_updates(payload, values.__setitem__)

    assert values["WHISPER_STRATEGY"] == "chickenrice"
    assert values["WHISPER_MODEL_BACKEND"] == "large-v3"
    assert values["WHISPER_RUNTIME_TIER"] == "gpu_low_vram"
    assert values["WHISPER_DEVICE"] == "cuda"
    assert values["WHISPER_COMPUTE_TYPE"] == "int8_float16"
    assert values["WHISPER_VAD_BACKEND"] == "whisper_vad_onnx"
    assert values["WHISPER_TIMING_REFINER"] == "subtimer_vad"
