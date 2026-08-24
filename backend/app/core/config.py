"""Application settings and runtime network configuration.

This module is reconstructed from the preserved Python 3.13 bytecode.  Its
public fields and environment aliases intentionally retain the legacy names so
existing `.env` files and queued jobs continue to work unchanged.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Or use PROJECT_ROOT env var (useful for Docker).
if "PROJECT_ROOT" in os.environ:
    PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
else:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

ENV_FILE_PATH = Path(os.environ.get("NOOR_ENV_FILE", str(PROJECT_ROOT / ".env")))
DEFAULT_NOOR_DATA_DIR = str(PROJECT_ROOT / "data")
WHISPER_MODEL_DIR = Path(
    os.environ.get("WHISPER_MODEL_DIR", str(Path.home() / ".cache" / "huggingface"))
)
DEFAULT_LADA_MODEL_WEIGHTS_DIR = "/volume1/models/lada_model_weights"
DEFAULT_FACEFUSION_DIR = ""

def _normalize_github_mirror_instead_of_prefix(mirror: str) -> str:
    """Return the git `url.<prefix>.insteadOf` value for GitHub mirrors.

    Proxy mirrors such as ghproxy expect the original GitHub URL to remain in the
    path, e.g.:
        https://ghproxy.com/https://github.com/ladaapp/lada.git

    The previous implementation used `https://ghproxy.com/` as the replacement
    prefix, producing `https://ghproxy.com/ladaapp/lada.git`, which ghproxy then
    rejects with "unable to update url base from redirection".
    """
    value = (mirror or "https://ghproxy.com").strip().rstrip("/")
    if not value:
        value = "https://ghproxy.com"
    if "github.com" in value:
        return value.rstrip("/") + "/"
    return value + "/https://github.com/"


class Settings(BaseSettings):
    lada_cli_path: str = "python3 -m lada.cli.main"
    facefusion_dir: str = DEFAULT_FACEFUSION_DIR
    facefusion_python_path: str = ""

    emby_server: str = "http://localhost:8096"
    emby_api_key: str = ""
    emby_user_id: str = ""
    emby_enabled_library_ids: str = ""

    noor_data_dir: str = DEFAULT_NOOR_DATA_DIR
    model_root_dir: str = ""
    runtime_root_dir: str = ""
    source_dir: str = ""
    output_dir: str = ""
    whisper_model_dir: str = ""
    whisper_cache_dir: str = ""
    whisper_temp_dir: str = ""
    lada_model_dir: str = Field(
        "", validation_alias="LADA_MODEL_WEIGHTS_DIR"
    )
    lada_cache_dir: str = ""
    lada_temp_dir: str = ""
    facefusion_model_dir: str = ""
    facefusion_cache_dir: str = ""
    facefusion_temp_dir: str = ""
    enable_dev_endpoints: bool = Field(
        False,
        validation_alias=AliasChoices("NOOR_ENABLE_DEV_ENDPOINTS", "ENABLE_DEV_ENDPOINTS"),
    )

    acceleration_mode: str = "mirror"
    http_proxy: str = ""
    github_mirror: str = "https://ghproxy.com"
    github_token: str = ""
    hf_mirror: str = "https://hf-mirror.com"
    pip_mirror: str = "https://pypi.tuna.tsinghua.edu.cn/simple"
    hf_token: str = ""
    actor_mapping_auto_update: bool = True

    whisper_strategy: str = "chickenrice"
    whisper_subtitle_profile: str = "standard"
    whisper_model_backend: str = "chickenrice-zh"
    whisper_runtime_tier: str = "gpu_standard"
    whisper_task: str = "translate"
    whisper_vad_backend: str = "energy"
    whisper_chunker: str = "smart_vad_chunk"
    whisper_target_chunk_duration_s: float = 30.0
    whisper_max_chunk_duration_s: float = 30.0
    whisper_segment_merge_max_gap_ms: int = 2000
    whisper_segment_merge_max_duration_ms: int = 20000
    whisper_timing_refiner: str = "none"
    whisper_model: str = "chickenrice-zh"
    whisper_pipeline_mode: str = "faster"
    whisper_language: str = "ja"
    whisper_sensitivity: str = "balanced"

    gpu_guard_enabled: bool = True
    gpu_guard_device_index: int = 0
    gpu_guard_cleanup_policy: str = "services"
    gpu_guard_grace_seconds: int = 8
    gpu_guard_lada_required_free_mb: int = 6144
    gpu_guard_facefusion_required_free_mb: int = 8192
    gpu_guard_whisper_required_free_mb: int = 4096

    lada_device: str = "cuda:0"
    lada_fp16: bool = True
    lada_detection_model: str = "v4-fast"
    lada_restoration_model: str = "basicvsrpp-v1.2"
    lada_encoding_preset: str = "hevc-nvidia-gpu-hq"
    lada_max_clip_length: int = 180
    lada_detect_face_mosaics: bool = False

    facefusion_execution_provider: str = "cuda"
    facefusion_device_ids: str = "0"
    facefusion_thread_count: int = 8
    facefusion_video_memory_strategy: str = "strict"
    facefusion_system_memory_limit: int = 0
    facefusion_log_level: str = "info"
    facefusion_download_providers: str = "github huggingface"
    facefusion_halt_on_error: bool = False
    facefusion_badge_always_visible: bool = False
    facefusion_preview_mode: str = "default"
    facefusion_preview_resolution: str = "768x768"
    facefusion_processors: str = ""
    facefusion_face_swapper_model: str = "hyperswap_1a_256"
    facefusion_face_swapper_pixel_boost: str = "256x256"
    facefusion_face_swapper_weight: float = 0.5
    facefusion_face_enhancer_model: str = "gfpgan_1.4"
    facefusion_face_enhancer_blend: int = 80
    facefusion_face_enhancer_weight: float = 0.5
    facefusion_frame_enhancer_model: str = "span_kendata_x4"
    facefusion_frame_enhancer_blend: int = 80
    facefusion_face_detector_model: str = "yolo_face"
    facefusion_face_detector_size: str = "640x640"
    facefusion_face_detector_score: float = 0.5
    facefusion_face_detector_angles: str = "0"
    facefusion_face_detector_margin: str = "0 0 0 0"
    facefusion_face_landmarker_model: str = "2dfan4"
    facefusion_face_landmarker_score: float = 0.5
    facefusion_face_selector_mode: str = "reference"
    facefusion_face_selector_order: str = "large-small"
    facefusion_face_selector_gender: str = ""
    facefusion_face_selector_age_start: str = ""
    facefusion_face_selector_age_end: str = ""
    facefusion_face_selector_race: str = ""
    facefusion_reference_frame_number: int = 0
    facefusion_reference_face_position: int = 0
    facefusion_reference_face_distance: float = 0.3
    facefusion_face_tracker_score: float = 0.0
    facefusion_face_mask_types: str = "box"
    facefusion_face_mask_areas: str = ""
    facefusion_face_mask_regions: str = ""
    facefusion_face_mask_blur: float = 0.3
    facefusion_face_mask_padding: str = "0 0 0 0"
    facefusion_face_occluder_model: str = "xseg_1"
    facefusion_face_parser_model: str = "bisenet_resnet_34"
    facefusion_output_video_encoder: str = "libx264"
    facefusion_output_video_preset: str = "veryfast"
    facefusion_output_video_quality: int = 80
    facefusion_output_video_scale: str = "1.0"
    facefusion_output_video_fps: str = ""
    facefusion_output_audio_encoder: str = "aac"
    facefusion_output_audio_quality: int = 80
    facefusion_output_audio_volume: int = 100
    facefusion_output_image_quality: int = 80
    facefusion_output_image_scale: str = "1.0"
    facefusion_temp_frame_format: str = "png"

    host: str = "0.0.0.0"
    port: int = 9898
    reload: bool = Field(
        default_factory=lambda: not os.path.exists("/.dockerenv"),
        validation_alias=AliasChoices("RELOAD", "UVICORN_RELOAD"),
    )
    database_url: str = ""

    @model_validator(mode="after")
    def apply_storage_defaults(self):
        data_dir = Path(self.noor_data_dir or DEFAULT_NOOR_DATA_DIR)
        model_root = Path(self.model_root_dir or data_dir / "models")
        runtime_root = Path(self.runtime_root_dir or data_dir / "runtime")

        def fill(attr: str, path: Path) -> None:
            if not (getattr(self, attr, "") or "").strip():
                setattr(self, attr, str(path))

        fill("model_root_dir", model_root)
        fill("runtime_root_dir", runtime_root)
        fill("whisper_model_dir", model_root / "whisper")
        fill("whisper_cache_dir", runtime_root / "whisper" / "cache")
        fill("whisper_temp_dir", runtime_root / "whisper" / "temp")
        fill("lada_model_dir", model_root / "lada")
        fill("lada_cache_dir", runtime_root / "lada" / "cache")
        fill("lada_temp_dir", runtime_root / "lada" / "temp")
        fill("facefusion_model_dir", model_root / "facefusion")
        fill("facefusion_cache_dir", runtime_root / "facefusion" / "cache")
        fill("facefusion_temp_dir", runtime_root / "facefusion" / "temp")
        fill("database_url", data_dir / "noor.db")
        if "://" not in self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.database_url}"
        return self

    @property
    def emby_headers(self) -> dict:
        return {"X-Emby-Token": self.emby_api_key}

    def apply_network_env(self):
        """Apply network settings to the long-running process environment.

        Mirror and proxy can be configured at the same time. For one-shot
        operations that can retry (for example LADA upgrade), the actual
        fallback order is implemented by the caller: mirror -> proxy -> direct.
        """
        import subprocess

        # Reset all
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "HF_ENDPOINT", "HF_TOKEN", "GITHUB_TOKEN"]:
            os.environ.pop(k, None)

        if self.github_token:
            os.environ["GITHUB_TOKEN"] = self.github_token

        # HF token is only authentication, not a routing switch. Keep mirror as
        # the default endpoint; callers can fallback to official HF when needed.
        if self.hf_token:
            os.environ["HF_TOKEN"] = self.hf_token
        if self.hf_mirror:
            os.environ["HF_ENDPOINT"] = self.hf_mirror or "https://hf-mirror.com"

        if self.http_proxy:
            os.environ["HTTP_PROXY"] = self.http_proxy
            os.environ["HTTPS_PROXY"] = self.http_proxy
            os.environ["http_proxy"] = self.http_proxy
            os.environ["https_proxy"] = self.http_proxy

        if self.github_mirror:
            # Configure git to use GitHub mirror
            mirror_prefix = _normalize_github_mirror_instead_of_prefix(self.github_mirror)
            # Remove the old malformed ghproxy rewrite before writing the fixed
            # prefix. Git config keys are case-insensitive, so either spelling is
            # fine for cleanup.
            subprocess.run(
                ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "--global", f"url.{mirror_prefix}.insteadOf", "https://github.com/"],
                capture_output=True
            )
        else:
            # Reset git mirror config
            subprocess.run(
                ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "--global", "--unset", "url.https://ghproxy.com/https://github.com/.insteadOf"],
                capture_output=True
            )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
