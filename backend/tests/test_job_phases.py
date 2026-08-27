from __future__ import annotations

from app.tasks.job_phases import (
    get_job_type_phase_defaults,
    get_terminal_detail,
)


def test_facefusion_restore_has_terminal_and_phase_defaults():
    assert get_terminal_detail("facefusion_restore", "completed") == "FaceFusion 处理完成"
    assert get_terminal_detail("facefusion_restore", "failed") == "FaceFusion 处理失败"
    assert get_terminal_detail("facefusion_restore", "cancelled") == "FaceFusion 处理已取消"
    assert get_terminal_detail("facefusion_restore", "skipped") == "FaceFusion 处理已跳过"
    assert get_job_type_phase_defaults("facefusion_restore") == {
        "phase_key": "prepare",
        "phase_label": "准备任务",
    }
