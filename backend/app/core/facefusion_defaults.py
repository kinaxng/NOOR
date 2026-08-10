from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from app.core.runtime_paths import data_path


# The recovered core configuration bytecode predates FaceFusion. This keeps
# recovered FaceFusion modules executable until the full settings API returns.
FACEFUSION_DEFAULTS: dict[str, Any] = {
    "facefusion_dir": "/volume1/facefusion/facefusion",
    "facefusion_python_path": "",
    "facefusion_model_dir": "/volume1/models/noor/facefusion",
    "facefusion_cache_dir": "/volume1/models/noor-runtime/facefusion/cache",
    "facefusion_temp_dir": "/volume1/models/noor-runtime/facefusion/temp",
    "facefusion_execution_provider": "cuda",
    "facefusion_device_ids": "0",
    "facefusion_processors": "face_swapper",
    "facefusion_thread_count": 4,
    "facefusion_video_memory_strategy": "strict",
    "facefusion_system_memory_limit": 0,
    "facefusion_download_providers": "github huggingface",
    "facefusion_face_swapper_model": "inswapper_128",
    "facefusion_face_swapper_pixel_boost": "128x128",
    "facefusion_face_swapper_weight": 100,
    "facefusion_face_enhancer_model": "gfpgan_1.4",
    "facefusion_face_enhancer_blend": 80,
    "facefusion_face_enhancer_weight": 100,
    "facefusion_frame_enhancer_model": "real_esrgan_x2plus",
    "facefusion_frame_enhancer_blend": 80,
    "facefusion_face_detector_model": "many",
    "facefusion_face_detector_size": "640x640",
    "facefusion_face_detector_score": 0.5,
    "facefusion_face_detector_angles": "0",
    "facefusion_face_detector_margin": "",
    "facefusion_face_landmarker_model": "2dfan4",
    "facefusion_face_landmarker_score": 0.5,
    "facefusion_face_selector_mode": "reference",
    "facefusion_face_selector_order": "",
    "facefusion_face_selector_gender": "",
    "facefusion_face_selector_age_start": "",
    "facefusion_face_selector_age_end": "",
    "facefusion_face_selector_race": "",
    "facefusion_reference_frame_number": 0,
    "facefusion_reference_face_position": 0,
    "facefusion_reference_face_distance": 0.3,
    "facefusion_face_mask_types": "box",
    "facefusion_face_mask_areas": "",
    "facefusion_face_mask_regions": "",
    "facefusion_face_mask_blur": 0.3,
    "facefusion_face_mask_padding": "",
    "facefusion_face_occluder_model": "xseg_1",
    "facefusion_face_parser_model": "bisenet_resnet_34",
    "facefusion_output_video_encoder": "libx264",
    "facefusion_output_video_preset": "veryfast",
    "facefusion_output_video_quality": 80,
    "facefusion_output_video_scale": "",
    "facefusion_output_video_fps": "",
    "facefusion_output_audio_encoder": "aac",
    "facefusion_output_audio_quality": 80,
    "facefusion_output_audio_volume": 100,
    "facefusion_output_image_quality": 80,
    "facefusion_output_image_scale": "",
    "facefusion_temp_frame_format": "png",
    "facefusion_log_level": "info",
}


def _settings_path() -> Path:
    return data_path("facefusion_settings.json")


def load_facefusion_overrides() -> dict[str, Any]:
    try:
        payload = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return {key: value for key, value in payload.items() if key in FACEFUSION_DEFAULTS} if isinstance(payload, dict) else {}


def save_facefusion_overrides(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_facefusion_overrides()
    current.update({key: value for key, value in updates.items() if key in FACEFUSION_DEFAULTS})
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return current


@dataclass(frozen=True)
class FaceFusionSettings:
    base: Any
    overrides: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        if name in FACEFUSION_DEFAULTS:
            return self.overrides.get(name, getattr(self.base, name, FACEFUSION_DEFAULTS[name]))
        return getattr(self.base, name)


def facefusion_settings(settings: Any) -> FaceFusionSettings:
    return FaceFusionSettings(settings, load_facefusion_overrides())


def facefusion_settings_payload(settings: Any) -> dict[str, Any]:
    resolved = facefusion_settings(settings)
    return {key: getattr(resolved, key) for key in FACEFUSION_DEFAULTS}
