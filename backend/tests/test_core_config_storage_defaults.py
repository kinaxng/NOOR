from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.runtime_paths import data_path, plugin_cache_path, plugin_data_path


def test_storage_defaults_derive_from_noor_data_dir():
    settings = Settings(_env_file=None, noor_data_dir="/noor-data")

    assert settings.whisper_model_dir == "/noor-data/models/whisper"
    assert settings.whisper_cache_dir == "/noor-data/runtime/whisper/cache"
    assert settings.whisper_temp_dir == "/noor-data/runtime/whisper/temp"
    assert settings.lada_model_dir == "/noor-data/models/lada"
    assert settings.lada_cache_dir == "/noor-data/runtime/lada/cache"
    assert settings.lada_temp_dir == "/noor-data/runtime/lada/temp"
    assert settings.facefusion_model_dir == "/noor-data/models/facefusion"
    assert settings.facefusion_cache_dir == "/noor-data/runtime/facefusion/cache"
    assert settings.facefusion_temp_dir == "/noor-data/runtime/facefusion/temp"
    assert settings.database_url == "sqlite+aiosqlite:////noor-data/noor.db"


def test_storage_defaults_keep_explicit_overrides():
    settings = Settings(
        _env_file=None,
        noor_data_dir="/noor-data",
        whisper_model_dir="/external/whisper",
        lada_cache_dir="/external/lada-cache",
        database_url="postgresql+asyncpg://noor:secret@db/noor",
    )

    assert settings.whisper_model_dir == "/external/whisper"
    assert settings.lada_cache_dir == "/external/lada-cache"
    assert settings.facefusion_temp_dir == str(Path("/noor-data") / "runtime" / "facefusion" / "temp")
    assert settings.database_url == "postgresql+asyncpg://noor:secret@db/noor"


def test_runtime_data_helpers_derive_from_noor_data_dir():
    settings = Settings(_env_file=None, noor_data_dir="/noor-data")

    assert data_path("plugins_config.json", settings=settings) == Path("/noor-data/plugins_config.json")
    assert plugin_cache_path("gfriends", "images", settings=settings) == Path("/noor-data/plugin_cache/gfriends/images")
    assert plugin_data_path("av_recommend", "feedback.json", settings=settings) == Path("/noor-data/av_recommend/feedback.json")
