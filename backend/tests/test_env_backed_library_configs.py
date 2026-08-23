from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.api import local_library, settings_helpers
from app.api.endpoints import media_library_helpers


def test_media_library_config_reads_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    env_path = tmp_path / "noor.env"
    monkeypatch.setattr(settings_helpers, "ENV_FILE", env_path)
    settings_helpers.set_env_values({
        "EMBY_SERVER": "http://emby:8096",
        "EMBY_API_KEY": "token",
        "EMBY_USER_ID": "user",
        "EMBY_ENABLED_LIBRARY_IDS": "3",
        "MEDIA_LIBRARY_PATH_PREFIX": "/data/media",
        "MEDIA_LIBRARY_LOCAL_PATH_PREFIX": "/videos",
        "MEDIA_LIBRARY_SCAN_GROUPS": '[{"name":"av","source_dir":"/src","hardlink_dir":"/dst"}]',
    })

    assert media_library_helpers.load_config() == {
        "server_url": "http://emby:8096",
        "api_key": "token",
        "user_id": "user",
        "enabled_library_ids": "3",
        "path_prefix": "/data/media",
        "local_path_prefix": "/videos",
        "scan_groups": [{"name": "av", "source_dir": "/src", "hardlink_dir": "/dst"}],
        "webhook_token": "",
        "tmdb_api_key": "",
        "tmdb_api_token": "",
        "mdc_ng_actor_mapping_path": "",
    }


def test_media_library_config_save_writes_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    env_path = tmp_path / "noor.env"
    monkeypatch.setattr(settings_helpers, "ENV_FILE", env_path)

    media_library_helpers.save_config({
        "server_url": "http://emby:8096",
        "api_key": "token",
        "user_id": "user",
        "enabled_library_ids": "3",
        "path_prefix": "/data/media",
        "local_path_prefix": "/videos",
        "scan_groups": [{"name": "av", "source_dir": "/src", "hardlink_dir": "/dst"}],
    })

    env_data = settings_helpers.read_env_file()
    assert env_data["EMBY_SERVER"] == "http://emby:8096"
    assert env_data["EMBY_API_KEY"] == "token"
    assert env_data["EMBY_USER_ID"] == "user"
    assert env_data["EMBY_ENABLED_LIBRARY_IDS"] == "3"
    assert env_data["MEDIA_LIBRARY_PATH_PREFIX"] == "/data/media"
    assert env_data["MEDIA_LIBRARY_LOCAL_PATH_PREFIX"] == "/videos"
    assert json.loads(env_data["MEDIA_LIBRARY_SCAN_GROUPS"]) == [
        {"name": "av", "source_dir": "/src", "hardlink_dir": "/dst"},
    ]


def test_local_subtitle_library_config_reads_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    env_path = tmp_path / "noor.env"
    monkeypatch.setattr(settings_helpers, "ENV_FILE", env_path)
    settings_helpers.set_env_values({
        "LOCAL_LIBRARY_PATHS": '["/a","/b"]',
        "LOCAL_LIBRARY_INDEX_ENABLED": "true",
        "LOCAL_LIBRARY_MATCH_FUZZY": "false",
    })

    assert local_library._load_config() == {
        "library_paths": "/a\n/b",
        "index_enabled": True,
        "match_fuzzy": False,
    }


def test_local_subtitle_library_config_save_writes_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    env_path = tmp_path / "noor.env"
    monkeypatch.setattr(settings_helpers, "ENV_FILE", env_path)

    local_library._save_config({
        "library_paths": "/a\n/b",
        "index_enabled": True,
        "match_fuzzy": False,
    })

    env_data = settings_helpers.read_env_file()
    assert env_data["LOCAL_LIBRARY_PATHS"] == '["/a", "/b"]'
    assert env_data["LOCAL_LIBRARY_INDEX_ENABLED"] == "true"
    assert env_data["LOCAL_LIBRARY_MATCH_FUZZY"] == "false"


def test_legacy_library_files_use_noor_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(media_library_helpers, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(local_library, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    assert media_library_helpers.config_path() == tmp_path / "media_library_config.json"
    assert local_library._index_db_path() == tmp_path / "runtime" / "subtitle_library" / "subtitle_index.db"
    assert tmp_path.exists()


def test_subtitle_index_migrates_strongest_legacy_database(monkeypatch: pytest.MonkeyPatch, tmp_path):
    legacy = tmp_path / "subtitle_index.db"
    conn = sqlite3.connect(legacy)
    try:
        conn.execute("create table subtitle_index (id integer primary key, base_name text, full_path text, ext text, updated_at real)")
        conn.execute("insert into subtitle_index (base_name, full_path, ext, updated_at) values ('DASS-927', '/legacy/DASS-927.srt', 'srt', 1)")
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(local_library, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    target = local_library._index_db_path()

    assert target == tmp_path / "runtime" / "subtitle_library" / "subtitle_index.db"
    assert target.is_file()
    assert local_library._subtitle_index_count(target) == 1
    assert local_library._legacy_index_db_candidates()[0] == legacy


def test_lada_model_weights_fallback_uses_noor_data_dir():
    expected_default = str(Path(__file__).resolve().parents[2] / "data" / "models" / "lada")
    assert settings_helpers.get_lada_model_weights_dir_from_env({}) == expected_default
    assert settings_helpers.get_lada_model_weights_dir_from_env({"NOOR_DATA_DIR": "/noor-data"}) == "/noor-data/models/lada"
    assert settings_helpers.get_lada_model_weights_dir_from_env({"LADA_MODEL_WEIGHTS_DIR": "/external/lada"}) == "/external/lada"


def test_whisper_model_catalogue_is_final_single_chain_contract():
    models = settings_helpers.WHISPER_MODELS

    assert "chickenrice-zh" in models
    assert models["whisper-vad-onnx"]["type"] == "onnx-vad"
    assert models["whisper-vad-onnx"]["size"] == "~250MB"
    assert "reazonspeech-nemo-v2" not in models
    assert "kotoba-whisper-v2.2" not in models
