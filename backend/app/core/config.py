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


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ENV_FILE_PATH = Path(os.environ.get("NOOR_ENV_FILE", str(PROJECT_ROOT / ".env")))
DEFAULT_NOOR_DATA_DIR = str(PROJECT_ROOT / "data")
WHISPER_MODEL_DIR = Path(
    os.environ.get("WHISPER_MODEL_DIR", str(Path.home() / ".cache" / "huggingface"))
)
DEFAULT_LADA_MODEL_WEIGHTS_DIR = "/volume1/models/lada_model_weights"
DEFAULT_AUDIO_SEPARATOR_MODEL_DIR = "/volume1/models/audio-separator"
DEFAULT_REAZON_MODEL_DIR = "/volume1/models/reazon"
DEFAULT_REAZON_NEMO_MODEL_PATH = f"{DEFAULT_REAZON_MODEL_DIR}/reazonspeech-nemo-v2.nemo"


class Settings(BaseSettings):
    lada_cli_path: str = "python3 -m lada.cli.main"

    emby_server: str = "http://localhost:8096"
    emby_api_key: str = ""
    emby_user_id: str = ""
    emby_enabled_library_ids: str = ""

    noor_data_dir: str = DEFAULT_NOOR_DATA_DIR
    source_dir: str = ""
    output_dir: str = ""
    whisper_model_dir: str = ""
    whisper_cache_dir: str = ""
    whisper_temp_dir: str = ""
    audio_separator_model_dir: str = ""
    reazon_model_dir: str = ""
    reazon_nemo_model_path: str = ""
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
    hf_mirror: str = "https://hf-mirror.com"
    pip_mirror: str = "https://pypi.tuna.tsinghua.edu.cn/simple"
    hf_token: str = ""

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
    whisper_merge_strategy: str = "smart_merge"
    whisper_language: str = "ja"
    whisper_sensitivity: str = "balanced"

    lada_device: str = "cuda:0"
    lada_fp16: bool = True
    lada_detection_model: str = "v4-fast"
    lada_restoration_model: str = "basicvsrpp-v1.2"
    lada_encoding_preset: str = "hevc-nvidia-gpu-hq"
    lada_max_clip_length: int = 180
    lada_detect_face_mosaics: bool = False

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

        def fill(attr: str, path: Path) -> None:
            if not (getattr(self, attr, "") or "").strip():
                setattr(self, attr, str(path))

        fill("whisper_model_dir", data_dir / "models" / "whisper")
        fill("whisper_cache_dir", data_dir / "runtime" / "whisper" / "cache")
        fill("whisper_temp_dir", data_dir / "runtime" / "whisper" / "temp")
        fill("audio_separator_model_dir", data_dir / "models" / "whisper" / "audio-separator")
        fill("reazon_model_dir", data_dir / "models" / "whisper" / "reazon")
        fill("reazon_nemo_model_path", Path(self.reazon_model_dir) / "reazonspeech-nemo-v2.nemo")
        fill("lada_model_dir", data_dir / "models" / "lada")
        fill("lada_cache_dir", data_dir / "runtime" / "lada" / "cache")
        fill("lada_temp_dir", data_dir / "runtime" / "lada" / "temp")
        fill("facefusion_model_dir", data_dir / "models" / "facefusion")
        fill("facefusion_cache_dir", data_dir / "runtime" / "facefusion" / "cache")
        fill("facefusion_temp_dir", data_dir / "runtime" / "facefusion" / "temp")
        fill("database_url", data_dir / "noor.db")
        if "://" not in self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.database_url}"
        return self

    @property
    def emby_headers(self) -> dict:
        return {"X-Emby-Token": self.emby_api_key}

    def apply_network_env(self) -> None:
        import subprocess

        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "HF_ENDPOINT",
            "HF_TOKEN",
        ):
            os.environ.pop(key, None)

        if self.hf_token:
            os.environ["HF_TOKEN"] = self.hf_token
            os.environ["HF_ENDPOINT"] = "https://huggingface.co"
        elif self.acceleration_mode == "mirror":
            os.environ["HF_ENDPOINT"] = self.hf_mirror or "https://hf-mirror.com"

        if self.acceleration_mode == "proxy" and self.http_proxy:
            os.environ["HTTP_PROXY"] = self.http_proxy
            os.environ["HTTPS_PROXY"] = self.http_proxy
            os.environ["http_proxy"] = self.http_proxy
            os.environ["https_proxy"] = self.http_proxy
            subprocess.run(
                ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
                capture_output=True,
            )
            return

        if self.acceleration_mode == "mirror":
            github_mirror = self.github_mirror or "https://ghproxy.com"
            subprocess.run(
                [
                    "git",
                    "config",
                    "--global",
                    f"url.https://{github_mirror.replace('https://', '')}/.insteadOf",
                    "https://github.com/",
                ],
                capture_output=True,
            )
            return

        subprocess.run(
            ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
            capture_output=True,
        )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
