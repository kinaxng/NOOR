from __future__ import annotations

from types import SimpleNamespace

from app.api.settings_directories import is_allowed_directory_path


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        source_dir="/volume1/videos",
        output_dir="",
        noor_data_dir="/volume1/models/noor",
        model_root_dir="/volume1/models/noor/models",
        runtime_root_dir="/volume1/models/noor-runtime/runtime",
        whisper_model_dir="/volume1/models/noor/models/whisper",
        whisper_cache_dir="/volume1/models/noor-runtime/runtime/whisper/cache",
        whisper_temp_dir="/volume1/models/noor-runtime/runtime/whisper/temp",
        lada_model_dir="/volume1/models/noor/models/lada",
        lada_cache_dir="/volume1/models/noor-runtime/runtime/lada/cache",
        lada_temp_dir="/volume1/models/noor-runtime/runtime/lada/temp",
        facefusion_model_dir="/volume1/models/noor/models/facefusion",
        facefusion_cache_dir="/volume1/models/noor-runtime/runtime/facefusion/cache",
        facefusion_temp_dir="/volume1/models/noor-runtime/runtime/facefusion/temp",
    )


def test_all_restored_runtime_roots_are_browseable():
    settings = _settings()

    allowed = [
        "/volume1/videos/AV/DASS-927",
        "/volume1/models/noor",
        "/volume1/models/noor/models/whisper/hub",
        "/volume1/models/noor-runtime/runtime/whisper/temp",
        "/volume1/models/noor-runtime/runtime/facefusion/cache",
    ]

    for path in allowed:
        assert is_allowed_directory_path(path, settings), path


def test_common_mount_prefix_and_home_remain_allowed():
    settings = _settings()

    assert is_allowed_directory_path("/mnt/subtitles", settings)
    assert is_allowed_directory_path("/home/kinax/Videos", settings)


def test_unrelated_path_is_rejected():
    settings = _settings()

    assert not is_allowed_directory_path("/etc/ssl/private", settings)
