from pathlib import Path

from app.pipeline.whisper.engine import _resolve_faster_whisper_model_source, _resolve_hf_model_source


def test_transformers_cache_resolves_huggingface_hub_snapshot(tmp_path: Path):
    repository = tmp_path / "huggingface" / "hub" / "models--litagin--anime-whisper"
    snapshot = repository / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    (repository / "refs").mkdir()
    (repository / "refs" / "main").write_text("revision")
    (snapshot / "model.safetensors").write_bytes(b"model")

    source, options = _resolve_hf_model_source(str(tmp_path), "litagin/anime-whisper")

    assert source == str(snapshot)
    assert options == {"local_files_only": True}


def test_faster_cache_resolves_direct_ctranslate2_snapshot(tmp_path: Path):
    repository = tmp_path / "models--Systran--faster-whisper-large-v3"
    snapshot = repository / "snapshots" / "revision"
    snapshot.mkdir(parents=True)
    (repository / "refs").mkdir()
    (repository / "refs" / "main").write_text("revision")
    (snapshot / "model.bin").write_bytes(b"model")

    source, options = _resolve_faster_whisper_model_source(str(tmp_path), "large-v3")

    assert source == str(snapshot)
    assert options == {}


def test_resolve_whisper_storage_returns_noor_runtime_dirs(monkeypatch):
    import os
    from app.pipeline.whisper import engine

    class FakeSettings:
        whisper_model_dir = "/tmp/noor-test-models"
        whisper_cache_dir = "/tmp/noor-test-cache"
        whisper_temp_dir = "/tmp/noor-test-temp"

        def apply_network_env(self):
            pass

    monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
    model_dir, cache_dir, temp_dir = engine._resolve_whisper_storage()

    assert model_dir == "/tmp/noor-test-models"
    assert cache_dir == "/tmp/noor-test-cache"
    assert temp_dir == "/tmp/noor-test-temp"
    assert os.environ.get("HF_HOME") == "/tmp/noor-test-models"
    assert os.environ.get("HF_HUB_CACHE") == "/tmp/noor-test-models/hub"
    assert os.environ.get("XDG_CACHE_HOME") == "/tmp/noor-test-cache"


def test_orchestrator_output_dir_uses_noor_whisper_temp(monkeypatch):
    from types import SimpleNamespace
    from app.pipeline.whisper import orchestrator

    monkeypatch.setattr(
        "app.pipeline.whisper.orchestrator._get_whisper_runtime_paths",
        lambda: ("/tmp/noor-test-models", "/tmp/noor-test-cache", "/tmp/noor-test-temp"),
    )
    pipeline = orchestrator.WhisperPipeline.__new__(orchestrator.WhisperPipeline)
    pipeline.config = SimpleNamespace(output_dir="")
    assert pipeline._get_output_dir() == Path("/tmp/noor-test-temp/whisper_jav")
