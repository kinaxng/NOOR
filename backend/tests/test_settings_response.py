from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.settings_response import build_settings_payload, split_enabled_library_ids


def test_split_enabled_library_ids_handles_empty_and_multiple_values():
    assert split_enabled_library_ids('') == []
    assert split_enabled_library_ids('a,b') == ['a', 'b']


def test_build_settings_payload_maps_env_and_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.settings_response.load_media_library_config", lambda: {})
    monkeypatch.setattr(
        "app.api.settings_response.get_settings",
        lambda: SimpleNamespace(
            noor_data_dir='/data',
            whisper_model_dir='/data/models/whisper',
            whisper_cache_dir='/runtime/whisper/cache',
            whisper_temp_dir='/data/runtime/whisper/temp',
            lada_model_dir='',
            lada_cache_dir='/data/runtime/lada/cache',
            lada_temp_dir='/data/runtime/lada/temp',
            facefusion_model_dir='/data/models/facefusion',
            facefusion_cache_dir='/data/runtime/facefusion/cache',
            facefusion_temp_dir='/data/runtime/facefusion/temp',
            database_url='sqlite+aiosqlite:////data/noor.db',
            source_dir='',
            output_dir='',
        ),
    )
    payload = build_settings_payload(
        env_data={
            'EMBY_SERVER': 'http://emby',
            'EMBY_ENABLED_LIBRARY_IDS': '1,2',
            'LADA_FP16': 'false',
            'LADA_MAX_CLIP_LENGTH': '240',
            'WHISPER_STRATEGY': 'chickenrice',
            'WHISPER_MODEL': 'chickenrice-zh',
            'ACCELERATION_MODE': 'proxy',
            'GITHUB_TOKEN': 'github_pat_xxx',
            'NOOR_DATA_DIR': '/data',
            'WHISPER_CACHE_DIR': '/runtime/whisper/cache',
            'FACEFUSION_MODEL_DIR': '/models/facefusion',
        },
        version_info={
            'version': '1.2.3',
            'is_docker': False,
            'is_submodule': True,
            'install_mode': 'editable-repo',
            'can_self_upgrade': True,
            'upgrade_strategy': 'git-pull-reinstall',
            'upgrade_hint': 'hint',
            'repo_path': '/tmp/lada',
        },
        lada_model_weights_dir='/models/lada',
        whisper_features={'custom_pipeline': {'available': False}},
    )

    assert payload['emby']['server'] == 'http://emby'
    assert payload['emby']['enabled_library_ids'] == ['1', '2']
    assert payload['storage']['lada_model_dir'] == '/models/lada'
    assert payload['storage']['noor_data_dir'] == '/data'
    assert payload['storage']['model_root_dir'] == '/data/models'
    assert payload['storage']['runtime_root_dir'] == '/runtime'
    assert payload['storage']['database_path'] == '/data/noor.db'
    assert payload['storage']['whisper_cache_dir'] == '/runtime/whisper/cache'
    assert payload['lada']['version'] == '1.2.3'
    assert payload['lada_defaults']['fp16'] is False
    assert payload['lada_defaults']['max_clip_length'] == 240
    assert payload['network']['acceleration_mode'] == 'proxy'
    assert payload['network']['github_token'] == 'github_pat_xxx'
    assert payload['facefusion']['model_dir_mode'] in {'native_assets', 'configured_override', 'configured_symlink', 'configured_missing', 'configured_pending_symlink'}


def test_build_settings_payload_normalizes_chickenrice_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.settings_response.load_media_library_config", lambda: {})
    payload = build_settings_payload(
        env_data={},
        version_info={
            'version': '0.0.0',
            'is_docker': False,
            'is_submodule': False,
            'install_mode': 'editable-repo',
            'can_self_upgrade': False,
            'upgrade_strategy': 'manual',
            'upgrade_hint': '',
            'repo_path': '',
        },
        lada_model_weights_dir='',
        whisper_features={},
    )

    assert payload['whisper']['strategy'] == 'chickenrice'
    assert payload['whisper']['model'] == 'chickenrice-zh'
