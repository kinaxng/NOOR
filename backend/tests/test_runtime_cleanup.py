from __future__ import annotations

import os
import time
from types import SimpleNamespace

from app.core import runtime_cleanup


def _isolate_status_file(monkeypatch, tmp_path):
    status_path = tmp_path / "runtime_cleanup_status.json"
    monkeypatch.setattr(runtime_cleanup, "_status_path", lambda: status_path)


def test_runtime_cleanup_removes_old_noor_runtime_items(monkeypatch, tmp_path):
    _isolate_status_file(monkeypatch, tmp_path)
    facefusion_temp = tmp_path / "facefusion" / "temp"
    whisper_temp = tmp_path / "whisper" / "temp"
    lada_temp = tmp_path / "lada" / "temp"
    old_task = facefusion_temp / "tasks" / "old-job"
    new_task = facefusion_temp / "tasks" / "new-job"
    old_whisper = whisper_temp / "whisper_jav" / "old-work"
    for path in (old_task, new_task, old_whisper):
        path.mkdir(parents=True)
        (path / "temp.bin").write_bytes(b"x" * 8)
    old_time = time.time() - 10 * 3600
    os.utime(old_task, (old_time, old_time))
    os.utime(old_whisper, (old_time, old_time))

    monkeypatch.setattr(
        runtime_cleanup,
        "get_settings",
        lambda: SimpleNamespace(
            facefusion_temp_dir=str(facefusion_temp),
            whisper_temp_dir=str(whisper_temp),
            lada_temp_dir=str(lada_temp),
        ),
    )
    monkeypatch.setattr(runtime_cleanup, "TMP_ROOT", tmp_path / "empty-tmp")

    status = runtime_cleanup.runtime_cleanup_status(min_age_hours=6)
    assert status["candidate_count"] == 2

    result = runtime_cleanup.run_runtime_cleanup(min_age_hours=6)

    assert result["deleted_count"] == 2
    assert not old_task.exists()
    assert not old_whisper.exists()
    assert new_task.exists()


def test_runtime_cleanup_does_not_collect_unowned_tmp_dirs(monkeypatch, tmp_path):
    _isolate_status_file(monkeypatch, tmp_path)
    fake_tmp = tmp_path / "tmp"
    fake_tmp.mkdir()
    (fake_tmp / "chromium-shared").mkdir()
    (fake_tmp / "llama.cpp-cuda").mkdir()
    noor_dir = fake_tmp / "noor-owned"
    noor_dir.mkdir()
    old_time = time.time() - 10 * 3600
    for path in fake_tmp.iterdir():
        os.utime(path, (old_time, old_time))

    monkeypatch.setattr(runtime_cleanup, "TMP_ROOT", fake_tmp)
    monkeypatch.setattr(
        runtime_cleanup,
        "get_settings",
        lambda: SimpleNamespace(
            facefusion_temp_dir=str(tmp_path / "ff"),
            whisper_temp_dir=str(tmp_path / "whisper"),
            lada_temp_dir=str(tmp_path / "lada"),
        ),
    )

    candidates = runtime_cleanup.collect_runtime_cleanup_candidates(min_age_hours=6)
    paths = {item.path.name for item in candidates}

    assert "noor-owned" in paths
    assert "chromium-shared" not in paths
    assert "llama.cpp-cuda" not in paths
