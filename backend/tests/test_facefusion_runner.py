from __future__ import annotations

from types import SimpleNamespace

from app.pipeline.facefusion import runner
from app.pipeline.facefusion.runner import (
    _build_env,
    _cleanup_task_runtime,
    _prepare_task_runtime_settings,
    _release_process_memory,
)


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


def test_facefusion_task_runtime_uses_isolated_temp_dir(monkeypatch, tmp_path):
    base_temp_dir = tmp_path / "facefusion-temp"
    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: SimpleNamespace(facefusion_temp_dir=str(base_temp_dir)),
    )

    runtime_settings, task_temp_dir = _prepare_task_runtime_settings(
        "job/with:unsafe chars",
        {"source_paths": ["/face.jpg"]},
    )

    assert runtime_settings["facefusion_temp_dir"] == str(task_temp_dir)
    assert runtime_settings["facefusion_jobs_dir"] == str(task_temp_dir / "jobs")
    assert task_temp_dir == base_temp_dir / "tasks" / "job_with_unsafe_chars"
    assert task_temp_dir.is_dir()


def test_facefusion_cleanup_removes_task_temp_only(tmp_path):
    base_temp_dir = tmp_path / "facefusion-temp"
    task_temp_dir = base_temp_dir / "tasks" / "job-1"
    task_temp_dir.mkdir(parents=True)
    (task_temp_dir / "frame.png").write_text("temp")

    _cleanup_task_runtime(task_temp_dir)

    assert not task_temp_dir.exists()
    assert base_temp_dir.exists()


def test_facefusion_memory_release_uses_loaded_torch(monkeypatch):
    calls = []
    cuda = SimpleNamespace(
        is_available=lambda: True,
        empty_cache=lambda: calls.append("empty_cache"),
        ipc_collect=lambda: calls.append("ipc_collect"),
    )
    monkeypatch.setitem(runner.sys.modules, "torch", SimpleNamespace(cuda=cuda))
    monkeypatch.setattr(runner.gc, "collect", lambda: calls.append("gc"))

    _release_process_memory()

    assert calls == ["gc", "empty_cache", "ipc_collect"]
