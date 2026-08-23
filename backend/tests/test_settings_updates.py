from __future__ import annotations

from pathlib import Path

from app.api.settings import EmbyConfig, LadaConfig, NetworkConfig, StorageConfig
from app.api.settings_updates import (
    apply_emby_config_updates,
    apply_lada_config_updates,
    apply_network_config_updates,
    build_storage_env_updates,
)


def test_apply_emby_config_updates_serializes_enabled_library_ids():
    calls: list[tuple[str, str]] = []
    config = EmbyConfig(server='http://emby', api_key='token', user_id='user', enabled_library_ids=['1', '2'])

    apply_emby_config_updates(config, lambda key, value: calls.append((key, value)))

    assert dict(calls) == {
        'EMBY_SERVER': 'http://emby',
        'EMBY_API_KEY': 'token',
        'EMBY_USER_ID': 'user',
        'EMBY_ENABLED_LIBRARY_IDS': '1,2',
        'MDC_NG_ACTOR_MAPPING_PATH': '',
    }


def test_build_storage_env_updates_uses_model_and_runtime_roots():
    config = StorageConfig(
        source_dir='/media/in',
        output_dir='/media/out',
        noor_data_dir='/data',
        whisper_model_dir='/models/whisper',
        whisper_cache_dir='/runtime/whisper/cache',
        whisper_temp_dir='/runtime/whisper/temp',
        lada_model_dir='/models/lada',
        lada_cache_dir='/runtime/lada/cache',
        lada_temp_dir='/runtime/lada/temp',
        facefusion_model_dir='/models/facefusion',
        facefusion_cache_dir='/runtime/facefusion/cache',
        facefusion_temp_dir='/runtime/facefusion/temp',
    )

    assert build_storage_env_updates(config, 'LADA_MODEL_WEIGHTS_DIR') == {
        'SOURCE_DIR': '/media/in',
        'OUTPUT_DIR': '/media/out',
        'NOOR_DATA_DIR': '/data',
        'MODEL_ROOT_DIR': '/data/models',
        'RUNTIME_ROOT_DIR': '/data/runtime',
        'WHISPER_MODEL_DIR': '/data/models/whisper',
        'WHISPER_CACHE_DIR': '/data/runtime/whisper/cache',
        'WHISPER_TEMP_DIR': '/data/runtime/whisper/temp',
        'AUDIO_SEPARATOR_MODEL_DIR': '/data/models/whisper/audio-separator',
        'REAZON_MODEL_DIR': '/data/models/whisper/reazon',
        'REAZON_NEMO_MODEL_PATH': '/data/models/whisper/reazon/reazonspeech-nemo-v2.nemo',
        'LADA_MODEL_WEIGHTS_DIR': '/data/models/lada',
        'LADA_CACHE_DIR': '/data/runtime/lada/cache',
        'LADA_TEMP_DIR': '/data/runtime/lada/temp',
        'FACEFUSION_MODEL_DIR': '/data/models/facefusion',
        'FACEFUSION_CACHE_DIR': '/data/runtime/facefusion/cache',
        'FACEFUSION_TEMP_DIR': '/data/runtime/facefusion/temp',
    }


def test_build_storage_env_updates_detects_legacy_flat_model_root(tmp_path: Path):
    (tmp_path / "hub").mkdir()

    config = StorageConfig(
        source_dir='',
        output_dir='',
        noor_data_dir='/data',
        model_root_dir=str(tmp_path),
        runtime_root_dir='/data/runtime',
    )

    updates = build_storage_env_updates(config, 'LADA_MODEL_WEIGHTS_DIR')

    assert updates['WHISPER_MODEL_DIR'] == str(tmp_path)
    assert updates['AUDIO_SEPARATOR_MODEL_DIR'] == str(tmp_path / 'audio-separator')
    assert updates['REAZON_MODEL_DIR'] == str(tmp_path / 'reazon')
    assert updates['REAZON_NEMO_MODEL_PATH'] == str(tmp_path / 'reazon' / 'reazonspeech-nemo-v2.nemo')
    assert updates['LADA_MODEL_WEIGHTS_DIR'] == str(tmp_path / 'lada_model_weights')


def test_apply_lada_config_updates_sets_cli_path():
    calls: list[tuple[str, str]] = []
    apply_lada_config_updates(LadaConfig(cli_path='python -m lada.cli.main'), lambda key, value: calls.append((key, value)))
    assert calls == [('LADA_CLI_PATH', 'python -m lada.cli.main')]


def test_apply_network_config_updates_writes_all_network_fields():
    calls: list[tuple[str, str]] = []
    config = NetworkConfig(
        acceleration_mode='proxy',
        http_proxy='http://127.0.0.1:7890',
        github_mirror='https://ghproxy.com',
        github_token='github_pat_xxx',
        hf_mirror='https://hf-mirror.com',
        pip_mirror='https://pypi.tuna.tsinghua.edu.cn/simple',
        hf_token='hf_xxx',
    )

    apply_network_config_updates(config, lambda key, value: calls.append((key, value)))

    assert dict(calls) == {
        'ACCELERATION_MODE': 'proxy',
        'HTTP_PROXY': 'http://127.0.0.1:7890',
        'GITHUB_MIRROR': 'https://ghproxy.com',
        'GITHUB_TOKEN': 'github_pat_xxx',
        'HF_MIRROR': 'https://hf-mirror.com',
        'PIP_MIRROR': 'https://pypi.tuna.tsinghua.edu.cn/simple',
        'HF_TOKEN': 'hf_xxx',
        'ACTOR_MAPPING_AUTO_UPDATE': 'true',
    }


def test_settings_helpers_env_file_respects_noor_env_file(monkeypatch, tmp_path):
    from app.api import settings_helpers

    env_path = tmp_path / 'docker-data.env'
    monkeypatch.setattr(settings_helpers, 'ENV_FILE', env_path)

    settings_helpers.set_env_values({'EMBY_SERVER': 'http://emby', 'PORT': '9898'})

    assert env_path.read_text() == 'EMBY_SERVER=http://emby\nPORT=9898\n'
    assert settings_helpers.read_env_file() == {'EMBY_SERVER': 'http://emby', 'PORT': '9898'}
