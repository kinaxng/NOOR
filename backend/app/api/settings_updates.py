"""Small helpers for writing settings fields to the environment file.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _is_legacy_flat_model_root(path: Path) -> bool:
    return any(
        (path / name).exists()
        for name in ("hub", "models--Systran--faster-whisper-large-v3", "lada_model_weights")
    )


def apply_emby_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("EMBY_SERVER", config.server)
    update_env_value_fn("EMBY_API_KEY", config.api_key)
    update_env_value_fn("EMBY_USER_ID", config.user_id)
    update_env_value_fn(
        "EMBY_ENABLED_LIBRARY_IDS",
        ",".join(config.enabled_library_ids) if config.enabled_library_ids else "",
    )
    update_env_value_fn("MDC_NG_ACTOR_MAPPING_PATH", config.mdc_ng_actor_mapping_path)


def build_storage_env_updates(config: Any, lada_model_weights_env: str) -> dict[str, str]:
    data_dir = Path(config.noor_data_dir or "data")
    model_root = Path(config.model_root_dir or data_dir / "models")
    runtime_root = Path(config.runtime_root_dir or data_dir / "runtime")
    if _is_legacy_flat_model_root(model_root):
        whisper_model_dir = model_root
        lada_model_dir = model_root / "lada_model_weights"
    else:
        whisper_model_dir = model_root / "whisper"
        lada_model_dir = model_root / "lada"
    return {
        "SOURCE_DIR": config.source_dir,
        "OUTPUT_DIR": config.output_dir,
        "NOOR_DATA_DIR": config.noor_data_dir,
        "MODEL_ROOT_DIR": str(model_root),
        "RUNTIME_ROOT_DIR": str(runtime_root),
        "WHISPER_MODEL_DIR": str(whisper_model_dir),
        "WHISPER_CACHE_DIR": str(runtime_root / "whisper" / "cache"),
        "WHISPER_TEMP_DIR": str(runtime_root / "whisper" / "temp"),
        lada_model_weights_env: str(lada_model_dir),
        "LADA_CACHE_DIR": str(runtime_root / "lada" / "cache"),
        "LADA_TEMP_DIR": str(runtime_root / "lada" / "temp"),
        "FACEFUSION_MODEL_DIR": str(model_root / "facefusion"),
        "FACEFUSION_CACHE_DIR": str(runtime_root / "facefusion" / "cache"),
        "FACEFUSION_TEMP_DIR": str(runtime_root / "facefusion" / "temp"),
    }


def apply_lada_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("LADA_CLI_PATH", config.cli_path)


def apply_ui_config_updates(config: Any, update_env_value_fn: Callable[[str, str], None]) -> None:
    update_env_value_fn("UI_COVER_BLUR_ENABLED", "true" if config.cover_blur_enabled else "false")


def apply_facefusion_config_updates(config: Any, update_env_value_fn: Callable[[str, str], None]) -> None:
    update_env_value_fn("FACEFUSION_DIR", config.dir)
    update_env_value_fn("FACEFUSION_PYTHON_PATH", config.python_path)


def apply_facefusion_defaults_updates(config: Any, update_env_value_fn: Callable[[str, str], None]) -> None:
    update_env_value_fn("FACEFUSION_EXECUTION_PROVIDER", config.execution_provider)
    update_env_value_fn("FACEFUSION_DEVICE_IDS", config.device_ids)
    update_env_value_fn("FACEFUSION_THREAD_COUNT", str(config.thread_count))
    update_env_value_fn("FACEFUSION_VIDEO_MEMORY_STRATEGY", config.video_memory_strategy)
    update_env_value_fn("FACEFUSION_SYSTEM_MEMORY_LIMIT", str(config.system_memory_limit))
    update_env_value_fn("FACEFUSION_LOG_LEVEL", config.log_level)
    update_env_value_fn("FACEFUSION_DOWNLOAD_PROVIDERS", config.download_providers)
    update_env_value_fn("FACEFUSION_HALT_ON_ERROR", "true" if config.halt_on_error else "false")
    update_env_value_fn("FACEFUSION_PROCESSORS", config.processors)
    update_env_value_fn("FACEFUSION_FACE_SWAPPER_MODEL", config.face_swapper_model)
    update_env_value_fn("FACEFUSION_FACE_SWAPPER_PIXEL_BOOST", config.face_swapper_pixel_boost)
    update_env_value_fn("FACEFUSION_FACE_SWAPPER_WEIGHT", str(config.face_swapper_weight))
    update_env_value_fn("FACEFUSION_FACE_ENHANCER_MODEL", config.face_enhancer_model)
    update_env_value_fn("FACEFUSION_FACE_ENHANCER_BLEND", str(config.face_enhancer_blend))
    update_env_value_fn("FACEFUSION_FACE_ENHANCER_WEIGHT", str(config.face_enhancer_weight))
    update_env_value_fn("FACEFUSION_FRAME_ENHANCER_MODEL", config.frame_enhancer_model)
    update_env_value_fn("FACEFUSION_FRAME_ENHANCER_BLEND", str(config.frame_enhancer_blend))
    update_env_value_fn("FACEFUSION_FACE_DETECTOR_MODEL", config.face_detector_model)
    update_env_value_fn("FACEFUSION_FACE_DETECTOR_SIZE", config.face_detector_size)
    update_env_value_fn("FACEFUSION_FACE_DETECTOR_SCORE", str(config.face_detector_score))
    update_env_value_fn("FACEFUSION_FACE_DETECTOR_ANGLES", config.face_detector_angles)
    update_env_value_fn("FACEFUSION_FACE_DETECTOR_MARGIN", config.face_detector_margin)
    update_env_value_fn("FACEFUSION_FACE_LANDMARKER_MODEL", config.face_landmarker_model)
    update_env_value_fn("FACEFUSION_FACE_LANDMARKER_SCORE", str(config.face_landmarker_score))
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_MODE", config.face_selector_mode)
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_ORDER", config.face_selector_order)
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_GENDER", config.face_selector_gender)
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_AGE_START", config.face_selector_age_start)
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_AGE_END", config.face_selector_age_end)
    update_env_value_fn("FACEFUSION_FACE_SELECTOR_RACE", config.face_selector_race)
    update_env_value_fn("FACEFUSION_REFERENCE_FRAME_NUMBER", str(config.reference_frame_number))
    update_env_value_fn("FACEFUSION_REFERENCE_FACE_POSITION", str(config.reference_face_position))
    update_env_value_fn("FACEFUSION_REFERENCE_FACE_DISTANCE", str(config.reference_face_distance))
    update_env_value_fn("FACEFUSION_FACE_TRACKER_SCORE", str(config.face_tracker_score))
    update_env_value_fn("FACEFUSION_FACE_MASK_TYPES", config.face_mask_types)
    update_env_value_fn("FACEFUSION_FACE_MASK_AREAS", config.face_mask_areas)
    update_env_value_fn("FACEFUSION_FACE_MASK_REGIONS", config.face_mask_regions)
    update_env_value_fn("FACEFUSION_FACE_MASK_BLUR", str(config.face_mask_blur))
    update_env_value_fn("FACEFUSION_FACE_MASK_PADDING", config.face_mask_padding)
    update_env_value_fn("FACEFUSION_FACE_OCCLUDER_MODEL", config.face_occluder_model)
    update_env_value_fn("FACEFUSION_FACE_PARSER_MODEL", config.face_parser_model)
    update_env_value_fn("FACEFUSION_OUTPUT_VIDEO_ENCODER", config.output_video_encoder)
    update_env_value_fn("FACEFUSION_OUTPUT_VIDEO_PRESET", config.output_video_preset)
    update_env_value_fn("FACEFUSION_OUTPUT_VIDEO_QUALITY", str(config.output_video_quality))
    update_env_value_fn("FACEFUSION_OUTPUT_VIDEO_SCALE", config.output_video_scale)
    update_env_value_fn("FACEFUSION_OUTPUT_VIDEO_FPS", config.output_video_fps)
    update_env_value_fn("FACEFUSION_OUTPUT_AUDIO_ENCODER", config.output_audio_encoder)
    update_env_value_fn("FACEFUSION_OUTPUT_AUDIO_QUALITY", str(config.output_audio_quality))
    update_env_value_fn("FACEFUSION_OUTPUT_AUDIO_VOLUME", str(config.output_audio_volume))
    update_env_value_fn("FACEFUSION_OUTPUT_IMAGE_QUALITY", str(config.output_image_quality))
    update_env_value_fn("FACEFUSION_OUTPUT_IMAGE_SCALE", config.output_image_scale)
    update_env_value_fn("FACEFUSION_TEMP_FRAME_FORMAT", config.temp_frame_format)
    update_env_value_fn("FACEFUSION_PREVIEW_MODE", config.preview_mode)
    update_env_value_fn("FACEFUSION_PREVIEW_RESOLUTION", config.preview_resolution)
    update_env_value_fn("FACEFUSION_BADGE_ALWAYS_VISIBLE", "true" if config.badge_always_visible else "false")


def apply_network_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("ACCELERATION_MODE", config.acceleration_mode)
    update_env_value_fn("HTTP_PROXY", config.http_proxy)
    update_env_value_fn("GITHUB_MIRROR", config.github_mirror)
    update_env_value_fn("GITHUB_TOKEN", config.github_token)
    update_env_value_fn("HF_MIRROR", config.hf_mirror)
    update_env_value_fn("PIP_MIRROR", config.pip_mirror)
    update_env_value_fn("HF_TOKEN", config.hf_token)
    update_env_value_fn(
        "ACTOR_MAPPING_AUTO_UPDATE",
        "true" if config.actor_mapping_auto_update else "false",
    )
