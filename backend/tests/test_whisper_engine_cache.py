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
