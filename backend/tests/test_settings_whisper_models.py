from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.api.settings_whisper_models import (
    delete_whisper_model_files,
    resolve_model_cache_candidates,
    resolve_whisper_model_dir,
)


def test_resolve_whisper_model_dir_prefers_setting(tmp_path: Path):
    settings = SimpleNamespace(whisper_model_dir=str(tmp_path / 'models'))
    assert resolve_whisper_model_dir(settings, '/default') == str(tmp_path / 'models')
    assert resolve_whisper_model_dir(SimpleNamespace(whisper_model_dir=''), '/default') == '/default'


def test_delete_whisper_model_files_removes_direct_transformers_cache(tmp_path: Path, monkeypatch):
    home = tmp_path / 'home'
    monkeypatch.setattr(Path, 'home', lambda: home)
    cache_root = tmp_path / 'custom-cache'
    model_path = cache_root / 'models--litagin--anime-whisper'
    model_path.mkdir(parents=True)

    deleted = delete_whisper_model_files(
        model_name='anime-whisper',
        model_info={'type': 'transformers', 'repo': 'litagin/anime-whisper'},
        whisper_model_dir=str(cache_root),
    )

    assert deleted == [str(model_path)]
    assert not model_path.exists()


def test_delete_whisper_model_files_removes_faster_whisper_current_cache_only(tmp_path: Path, monkeypatch):
    home = tmp_path / 'home'
    monkeypatch.setattr(Path, 'home', lambda: home)
    cache_root = tmp_path / 'custom-cache'
    repo_path = cache_root / 'hub' / 'models--Systran--faster-whisper-large-v3'
    repo_path.mkdir(parents=True)
    mx_path = home / '.cache' / 'mx Fofr' / 'Faster-Whisper' / 'large-v3'
    mx_path.mkdir(parents=True)

    deleted = delete_whisper_model_files(
        model_name='large-v3',
        model_info={'type': 'faster-whisper'},
        whisper_model_dir=str(cache_root),
    )

    assert deleted == [str(repo_path)]
    assert not repo_path.exists()
    assert mx_path.exists()


def test_delete_whisper_model_files_removes_direct_onnx_vad_cache(tmp_path: Path):
    repo_path = tmp_path / 'models--TransWithAI--Whisper-Vad-EncDec-ASMR-onnx'
    repo_path.mkdir(parents=True)

    deleted = delete_whisper_model_files(
        model_name='whisper-vad-onnx',
        model_info={'type': 'onnx-vad', 'repo': 'TransWithAI/Whisper-Vad-EncDec-ASMR-onnx'},
        whisper_model_dir=str(tmp_path),
    )

    assert deleted == [str(repo_path)]
    assert not repo_path.exists()


def test_resolve_model_cache_candidates_covers_models_root_and_hub_layouts(tmp_path: Path):
    candidates = resolve_model_cache_candidates(str(tmp_path / 'models'), 'Systran/faster-whisper-large-v3')
    candidate_strs = {str(path) for path in candidates}

    assert str(tmp_path / 'models' / 'models--Systran--faster-whisper-large-v3') in candidate_strs
    assert str(tmp_path / 'models' / 'hub' / 'models--Systran--faster-whisper-large-v3') in candidate_strs
    assert str(tmp_path / 'models' / 'huggingface' / 'hub' / 'models--Systran--faster-whisper-large-v3') in candidate_strs
