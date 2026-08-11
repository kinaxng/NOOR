from __future__ import annotations

from app.pipeline.facefusion.runner import _build_env


def test_facefusion_env_splits_runtime_cache_dirs(tmp_path):
    cache_dir = tmp_path / "facefusion-cache"
    temp_dir = tmp_path / "facefusion-temp"

    env = _build_env(facefusion_cache_dir=str(cache_dir), facefusion_temp_dir=str(temp_dir))

    assert env["XDG_CACHE_HOME"] == str(cache_dir / "xdg")
    assert env["ORT_TENSORRT_CACHE_PATH"] == str(cache_dir / "onnxruntime" / "tensorrt")
    assert env["CUDA_CACHE_PATH"] == str(cache_dir / "cuda")
    assert env["TMPDIR"] == str(temp_dir)
    assert (cache_dir / "xdg").is_dir()
    assert (cache_dir / "onnxruntime" / "tensorrt").is_dir()
    assert (cache_dir / "cuda").is_dir()
