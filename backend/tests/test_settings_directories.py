from __future__ import annotations

from types import SimpleNamespace

from app.api.settings_directories import is_allowed_directory_path


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        source_dir="/mnt/videos",
        output_dir="",
        noor_data_dir="/mnt/models/noor",
        model_root_dir="/mnt/models/noor/models",
        runtime_root_dir="/mnt/models/noor-runtime/runtime",
        whisper_model_dir="/mnt/models/noor/models/whisper",
        whisper_cache_dir="/mnt/models/noor-runtime/runtime/whisper/cache",
        whisper_temp_dir="/mnt/models/noor-runtime/runtime/whisper/temp",
        lada_model_dir="/mnt/models/noor/models/lada",
        lada_cache_dir="/mnt/models/noor-runtime/runtime/lada/cache",
        lada_temp_dir="/mnt/models/noor-runtime/runtime/lada/temp",
        facefusion_model_dir="/mnt/models/noor/models/facefusion",
        facefusion_cache_dir="/mnt/models/noor-runtime/runtime/facefusion/cache",
        facefusion_temp_dir="/mnt/models/noor-runtime/runtime/facefusion/temp",
    )


def test_all_restored_runtime_roots_are_browseable():
    settings = _settings()

    allowed = [
        "/mnt/videos/AV/TEST-009",
        "/mnt/models/noor",
        "/mnt/models/noor/models/whisper/hub",
        "/mnt/models/noor-runtime/runtime/whisper/temp",
        "/mnt/models/noor-runtime/runtime/facefusion/cache",
    ]

    for path in allowed:
        assert is_allowed_directory_path(path, settings), path


def test_common_mount_prefix_and_home_remain_allowed():
    settings = _settings()

    assert is_allowed_directory_path("/mnt/subtitles", settings)
    assert is_allowed_directory_path("/mnt/media", settings)


def test_unrelated_path_is_rejected():
    settings = _settings()

    assert not is_allowed_directory_path("/etc/ssl/private", settings)
