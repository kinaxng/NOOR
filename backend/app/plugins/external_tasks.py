from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.models import Job, JobCreate, JobResponse
from app.tasks.job_phases import get_phase_display_state
from app.tasks.manager import job_manager


EXTERNAL_JOB_TYPE = "external_task"
ACTIVE_EXTERNAL_STATUSES = {"pending", "queued", "blocked", "running"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "skipped"}


def _value(job: Job | JobResponse | dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if isinstance(job, dict):
        return job.get(key, default)
    return getattr(job, key, default) if job is not None else default


def external_task_metadata(
    provider_id: str,
    *,
    provider_label: str | None = None,
    external_id: str | int | None = None,
    can_cancel: bool = False,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "external_provider": provider_id,
        "external_task": {
            "provider_id": provider_id,
            "provider_label": provider_label or provider_id,
            "external_id": None if external_id is None else str(external_id),
            "can_cancel": bool(can_cancel),
            "data": data or {},
        },
    }


def is_external_task_job(job: Job | JobResponse | dict[str, Any] | None) -> bool:
    metadata = _value(job, "result_metadata") or {}
    return _value(job, "job_type") == EXTERNAL_JOB_TYPE or (
        isinstance(metadata, dict) and isinstance(metadata.get("external_task"), dict)
    )


def is_external_task_cancelable(job: Job | JobResponse | dict[str, Any] | None) -> bool:
    if not is_external_task_job(job):
        return True
    metadata = _value(job, "result_metadata") or {}
    ext = metadata.get("external_task") if isinstance(metadata, dict) else None
    return bool(ext.get("can_cancel")) if isinstance(ext, dict) else False


async def set_external_task_state(
    job_id: str,
    *,
    status: str,
    progress: int,
    detail: str | None = None,
    error_message: str | None = None,
    result_metadata: dict[str, Any] | None = None,
    phase_label: str | None = None,
) -> JobResponse | None:
    async with async_session_maker() as session:
        job = await session.get(Job, job_id)
        if not job:
            return None
        job.status = status
        job.progress = max(0, min(int(progress), 100))
        job.error_message = error_message
        if result_metadata is not None:
            job.result_metadata = result_metadata
        phase_state = get_phase_display_state(
            EXTERNAL_JOB_TYPE,
            status,
            phase_key=job.phase_key,
            phase_label=phase_label or job.phase_label,
            phase_progress=job.phase_progress,
            detail=detail,
            error_message=error_message,
        )
        job.phase_key = phase_state.get("phase_key")
        job.phase_label = phase_state.get("phase_label") or phase_label
        job.phase_progress = phase_state.get("phase_progress")
        job.detail = phase_state.get("detail") or detail
        job.completed_at = datetime.utcnow() if status in TERMINAL_STATUSES else None
        await session.commit()
        await session.refresh(job)
        return JobResponse.model_validate(job)


async def create_external_task_job(
    *,
    provider_id: str,
    provider_label: str | None = None,
    name: str,
    input_path: str,
    external_id: str | int | None = None,
    status: str = "queued",
    progress: int = 0,
    detail: str | None = None,
    error_message: str | None = None,
    can_cancel: bool = False,
    data: dict[str, Any] | None = None,
    phase_label: str | None = None,
) -> JobResponse:
    metadata = external_task_metadata(
        provider_id,
        provider_label=provider_label,
        external_id=external_id,
        can_cancel=can_cancel,
        data=data,
    )
    job = await job_manager.create_job(
        JobCreate(
            emby_item_id=provider_id,
            emby_item_name=name,
            input_path=input_path,
            settings={},
        ),
        job_type=EXTERNAL_JOB_TYPE,
        status="queued",
        enqueue_now=False,
    )
    updated = await set_external_task_state(
        job.id,
        status=status,
        progress=progress,
        detail=detail,
        error_message=error_message,
        result_metadata=metadata,
        phase_label=phase_label,
    )
    return updated or job


async def list_provider_external_jobs(
    provider_id: str,
    *,
    job_id: str | None = None,
    active_only: bool = False,
) -> list[Job]:
    async with async_session_maker() as session:
        statement = select(Job).where(Job.job_type == EXTERNAL_JOB_TYPE)
        if job_id:
            statement = statement.where(Job.id == job_id)
        elif active_only:
            statement = statement.where(Job.status.in_(ACTIVE_EXTERNAL_STATUSES))
        result = await session.execute(statement.order_by(Job.created_at.desc()))
        jobs = []
        for job in result.scalars().all():
            metadata = job.result_metadata or {}
            ext = metadata.get("external_task") if isinstance(metadata, dict) else None
            if isinstance(ext, dict) and ext.get("provider_id") == provider_id:
                jobs.append(job)
        return jobs
