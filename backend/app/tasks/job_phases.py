"""Stable task-phase labels and progress payload helpers.

Reconstructed from the preserved Python 3.13 bytecode.  These values are part
of the API contract consumed by task lists and server-sent progress events.
"""
from __future__ import annotations

from typing import Any


PHASE_PREPARE = "prepare"
PHASE_ANALYZE = "analyze"
PHASE_TRANSCRIBE = "transcribe"
PHASE_RETRY = "retry"
PHASE_ALIGN = "align"
PHASE_TRANSLATE = "translate"
PHASE_PROCESS = "process"
PHASE_ENCODE = "encode"
PHASE_OUTPUT = "output"

PHASE_LABELS = {
    "prepare": "准备任务",
    "analyze": "分析内容",
    "transcribe": "生成字幕",
    "retry": "补救识别",
    "align": "对齐时间轴",
    "translate": "字幕翻译",
    "process": "处理中",
    "encode": "编码输出文件",
    "output": "整理输出",
}
TERMINAL_STATUS_LABELS = {
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
    "skipped": "已跳过",
}
TERMINAL_STATUS_DETAILS = {
    "lada": {
        "completed": "视频修复完成",
        "failed": "视频修复失败",
        "cancelled": "视频修复已取消",
        "skipped": "视频修复已跳过",
    },
    "lada_restore": {
        "completed": "视频修复完成",
        "failed": "视频修复失败",
        "cancelled": "视频修复已取消",
        "skipped": "视频修复已跳过",
    },
    "whisper": {
        "completed": "字幕生成完成",
        "failed": "字幕生成失败",
        "cancelled": "字幕生成已取消",
        "skipped": "字幕生成已跳过",
    },
    "whisper_transcribe": {
        "completed": "字幕生成完成",
        "failed": "字幕生成失败",
        "cancelled": "字幕生成已取消",
        "skipped": "字幕生成已跳过",
    },
    "translate-srt": {
        "completed": "字幕翻译完成",
        "failed": "字幕翻译失败",
        "cancelled": "字幕翻译已取消",
        "skipped": "字幕翻译已跳过",
    },
    "external_task": {
        "completed": "外部任务完成",
        "failed": "外部任务失败",
        "cancelled": "外部任务已取消",
        "skipped": "外部任务已跳过",
    },
}
FOLLOWUP_STATUS_DETAILS = {
    "blocked": "等待主任务完成后自动开始",
    "queued": "主任务已完成，准备开始后续任务",
}
FOLLOWUP_DETAIL_VALUES = frozenset(FOLLOWUP_STATUS_DETAILS.values())
JOB_TYPE_PHASE_DEFAULTS = {
    "lada": {"phase_key": "prepare", "phase_label": "准备任务"},
    "lada_restore": {"phase_key": "prepare", "phase_label": "准备任务"},
    "whisper": {"phase_key": "prepare", "phase_label": "准备任务"},
    "whisper_transcribe": {"phase_key": "prepare", "phase_label": "准备任务"},
    "translate-srt": {"phase_key": "translate", "phase_label": "字幕翻译"},
    "external_task": {"phase_key": "output", "phase_label": "外部任务"},
}
PHASE_NORMALIZATION = {
    "prepare": "prepare",
    "extract_audio": "prepare",
    "load_subtitle": "prepare",
    "detect": "analyze",
    "segment": "analyze",
    "segment_text": "analyze",
    "transcribe_primary": "transcribe",
    "retry": "retry",
    "align": "align",
    "translate": "translate",
    "restore": "process",
    "postprocess": "process",
    "merge_output": "process",
    "encode": "encode",
    "write_output": "output",
    "finalize": "output",
}
PHASE_GROUPS = {
    "prepare": "prepare",
    "extract_audio": "prepare",
    "load_subtitle": "prepare",
    "analyze": "analyze",
    "detect": "analyze",
    "segment": "analyze",
    "segment_text": "analyze",
    "transcribe": "transcribe",
    "transcribe_primary": "transcribe",
    "retry": "retry",
    "align": "align",
    "translate": "translate",
    "process": "process",
    "restore": "process",
    "postprocess": "process",
    "merge_output": "process",
    "encode": "encode",
    "output": "output",
    "write_output": "output",
    "finalize": "output",
}


def normalize_phase_key(phase_key: str | None) -> str | None:
    if not phase_key:
        return None
    return PHASE_NORMALIZATION.get(phase_key, phase_key)


def get_phase_label(phase_key: str | None, fallback: str | None = None) -> str | None:
    normalized = normalize_phase_key(phase_key)
    if normalized and normalized in PHASE_LABELS:
        return PHASE_LABELS[normalized]
    return fallback


def get_phase_group(phase_key: str | None) -> str | None:
    if not phase_key:
        return None
    normalized = normalize_phase_key(phase_key) or phase_key
    return PHASE_GROUPS.get(phase_key) or PHASE_GROUPS.get(normalized) or normalized


def get_job_type_phase_defaults(job_type: str | None) -> dict[str, Any]:
    if not job_type:
        return {}
    return dict(JOB_TYPE_PHASE_DEFAULTS.get(job_type, {}))


def get_queued_phase_state(job_type: str | None, *, detail: str | None = None) -> dict[str, Any]:
    payload = get_job_type_phase_defaults(job_type)
    if not payload:
        return {}
    payload["phase_progress"] = 0
    if detail is not None:
        payload["detail"] = detail
    return payload


def get_running_phase_state(job_type: str | None, *, detail: str | None = None) -> dict[str, Any]:
    payload = get_job_type_phase_defaults(job_type)
    if not payload:
        return {}
    if detail is not None:
        payload["detail"] = detail
    return payload


def get_terminal_phase_label(
    status: str | None, *, phase_key: str | None = None, fallback: str | None = None
) -> str | None:
    phase_label = get_phase_label(phase_key)
    if phase_label:
        return phase_label
    if status and status in TERMINAL_STATUS_LABELS:
        return TERMINAL_STATUS_LABELS[status]
    return fallback


def get_terminal_detail(
    job_type: str | None,
    status: str | None,
    *,
    error_message: str | None = None,
    detail: str | None = None,
) -> str | None:
    if status in frozenset({"failed", "skipped"}) and error_message:
        return error_message
    if detail:
        return detail
    if job_type and status:
        terminal_detail = TERMINAL_STATUS_DETAILS.get(job_type, {}).get(status)
        if terminal_detail:
            return terminal_detail
    if status and status in TERMINAL_STATUS_LABELS:
        return TERMINAL_STATUS_LABELS[status]
    return detail or error_message


def get_followup_phase_state(
    job_type: str | None, *, status: str | None = None, detail: str | None = None
) -> dict[str, Any]:
    payload = get_job_type_phase_defaults(job_type)
    if not payload:
        return {}
    payload["phase_progress"] = 0
    if detail is not None:
        payload["detail"] = detail
    elif status and status in FOLLOWUP_STATUS_DETAILS:
        payload["detail"] = FOLLOWUP_STATUS_DETAILS[status]
    return payload


def is_followup_detail(detail: str | None) -> bool:
    return bool(detail and detail in FOLLOWUP_DETAIL_VALUES)


def get_phase_display_state(
    job_type: str | None,
    status: str | None,
    *,
    phase_key: str | None = None,
    phase_label: str | None = None,
    phase_progress: int | None = None,
    detail: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    normalized_phase_key = normalize_phase_key(phase_key)
    normalized_phase_label = phase_label or get_phase_label(normalized_phase_key)

    if not normalized_phase_key and not normalized_phase_label:
        if status == "queued":
            defaults = get_queued_phase_state(job_type)
        elif status == "running":
            defaults = get_running_phase_state(job_type)
        elif status == "blocked":
            defaults = get_followup_phase_state(job_type, status="blocked")
        elif status in frozenset({"completed", "failed", "cancelled", "skipped"}):
            defaults = get_job_type_phase_defaults(job_type)
        else:
            defaults = {}
        normalized_phase_key = defaults.get("phase_key")
        normalized_phase_label = defaults.get("phase_label")
        if phase_progress is None:
            phase_progress = defaults.get("phase_progress")
        if detail is None:
            detail = defaults.get("detail")

    if status in frozenset({"completed", "failed", "cancelled", "skipped"}):
        phase_progress = 100 if status == "completed" else 0
        detail = get_terminal_detail(
            job_type,
            status,
            error_message=error_message if status in frozenset({"failed", "skipped"}) else None,
            detail=None if status in frozenset({"completed", "failed", "cancelled"}) else detail,
        )

    payload: dict[str, Any] = {}
    if normalized_phase_key is not None:
        payload["phase_key"] = normalized_phase_key
        payload["phase_group"] = get_phase_group(normalized_phase_key)
    if normalized_phase_label is not None:
        payload["phase_label"] = normalized_phase_label
    if phase_progress is not None:
        payload["phase_progress"] = phase_progress
    if detail is not None:
        payload["detail"] = detail
    return payload
