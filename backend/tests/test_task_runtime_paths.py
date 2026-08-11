from __future__ import annotations

from app.tasks import manager_helpers


def test_job_logs_use_runtime_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(manager_helpers, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    manager_helpers.append_log_line("job-1", "hello")

    assert manager_helpers.log_file_path("job-1") == str(tmp_path / "runtime" / "jobs" / "logs" / "job-1.log")
    assert manager_helpers.read_log_lines("job-1") == ["hello"]
