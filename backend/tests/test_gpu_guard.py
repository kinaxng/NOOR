from __future__ import annotations

import pytest

from app.core import gpu_guard


def _process(pid: int, command: str) -> gpu_guard.GpuProcess:
    return gpu_guard.GpuProcess(pid=pid, used_mb=2048, name=command.rsplit("/", 1)[-1], command=command)


def test_noor_process_protection_marks_restored_tree_without_current_worker():
    current = _process(gpu_guard.os.getpid(), "/home/kinax/noor-restored/backend/app/tasks/manager.py")
    restored = _process(1234, "/home/kinax/noor-restored/backend/app/pipeline/lada/worker.py")
    original = _process(1235, "/home/kinax/noor/backend/app/pipeline/facefusion/runner.py")
    unrelated = _process(1236, "/usr/bin/python script.py")

    assert not gpu_guard._is_noor_process(current)
    assert gpu_guard._is_noor_process(restored)
    assert gpu_guard._is_noor_process(original)
    assert not gpu_guard._is_noor_process(unrelated)


def test_ensure_gpu_memory_only_terminates_noor_and_model_service_processes(monkeypatch):
    noor_proc = _process(1001, "/home/kinax/noor-restored/backend/app/pipeline/lada/worker.py")
    service_proc = _process(1002, "/usr/bin/llama-server")
    unrelated_proc = _process(1003, "/usr/bin/vlc")
    initial = gpu_guard.GpuSnapshot(
        index=0,
        total_mb=8192,
        used_mb=7168,
        free_mb=1024,
        processes=[noor_proc, service_proc, unrelated_proc],
    )
    still_low = gpu_guard.GpuSnapshot(
        index=0,
        total_mb=8192,
        used_mb=7168,
        free_mb=1024,
        processes=[],
    )
    snapshots = iter([initial, still_low])
    terminated: list[int] = []
    monkeypatch.setattr(gpu_guard, "read_gpu_snapshot", lambda device_index: next(snapshots))
    monkeypatch.setattr(
        gpu_guard,
        "_terminate_processes",
        lambda processes, grace_seconds: terminated.extend(proc.pid for proc in processes) or [proc.pid for proc in processes],
    )
    monkeypatch.setattr(gpu_guard.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="GPU 显存不足"):
        gpu_guard.ensure_gpu_memory(
            task_name="facefusion",
            required_free_mb=4096,
            cleanup_policy="managed",
        )

    assert terminated == [1001, 1002]
