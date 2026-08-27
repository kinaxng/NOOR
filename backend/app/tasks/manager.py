"""Persistent, single-worker NOOR job queue recovered from the API contract."""

from __future__ import annotations

import asyncio
import queue
import logging
import os
import re
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.facefusion_defaults import facefusion_settings
from app.core.gpu_guard import ensure_gpu_memory
from app.core.models import Job, JobCreate, JobResponse
from app.pipeline.facefusion.runner import run_facefusion_restoration
from app.pipeline.lada.runner import run_lada_restoration
from app.tasks.job_phases import (
    get_followup_phase_state,
    get_phase_display_state,
    get_phase_group,
    get_phase_label,
    is_followup_detail,
    normalize_phase_key,
)
from app.tasks.manager_helpers import (
    append_log_line,
    build_lada_output_path,
    log_file_path,
    read_log_lines,
    utcnow_naive,
)

logger = logging.getLogger(__name__)

FOLLOWUP_WAITING_DETAIL = "等待主任务完成后自动开始"
FOLLOWUP_QUEUED_DETAIL = "主任务已完成，准备开始后续任务"


class JobManager:
    """Persistent, single-worker NOOR job queue.

    The queue keeps the original single-GPU contract: one active job at a time.
    Jobs are persisted in SQLite so a backend restart can recover queued tasks.
    """

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._event_queues: dict[str, asyncio.Queue] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._cancelled_jobs: set[str] = set()
        self._logs: dict[str, list[str]] = {}
        self._db_lock = asyncio.Lock()
        self._max_concurrent = 1
        self.running_job: JobCreate | None = None
        self.running_job_id: str | None = None
        self._running_since: float | None = None

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())

    def _cancel_event_for(self, job_id: str) -> asyncio.Event:
        event = self._cancel_events.get(job_id)
        if event is None:
            event = asyncio.Event()
            self._cancel_events[job_id] = event
        return event

    async def _is_cancelled(self, job_id: str) -> bool:
        if job_id in self._cancelled_jobs:
            return True
        async with self._db_lock:
            async with async_session_maker() as session:
                result = await session.execute(select(Job.status).where(Job.id == job_id))
                return result.scalar_one_or_none() == "cancelled"

    async def _get_job_row(self, session, job_id: str) -> Job | None:
        result = await session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _apply_phase_state_to_job(job: Job, phase_state: dict[str, object]) -> None:
        if not phase_state:
            return
        if "phase_key" in phase_state:
            job.phase_key = phase_state.get("phase_key")  # type: ignore[assignment]
        if "phase_label" in phase_state:
            job.phase_label = phase_state.get("phase_label")  # type: ignore[assignment]
        if "phase_progress" in phase_state:
            job.phase_progress = phase_state.get("phase_progress")  # type: ignore[assignment]
        if "detail" in phase_state:
            job.detail = phase_state.get("detail")  # type: ignore[assignment]

    @staticmethod
    def _build_state_event_payload(
        *,
        status: str,
        success: bool | None = None,
        job_id: str | None = None,
        progress: int | None = None,
        error: str | None = None,
        phase_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"type": status}
        if job_id is not None:
            payload["job_id"] = job_id
        if success is not None:
            payload["success"] = success
        if progress is not None:
            payload["progress"] = progress
        if error is not None:
            payload["error"] = error
        phase_state = phase_state or {}
        for key in ("phase_key", "phase_group", "phase_label", "phase_progress", "detail"):
            if key in phase_state:
                payload[key] = phase_state[key]
        return payload

    @staticmethod
    def _normalize_phase_payload(*, phase_key: str | None = None, phase_label: str | None = None) -> tuple[str | None, str | None]:
        normalized_phase_key = normalize_phase_key(phase_key)
        normalized_phase_label = phase_label
        if normalized_phase_key and not normalized_phase_label:
            normalized_phase_label = get_phase_label(normalized_phase_key)
        return normalized_phase_key, normalized_phase_label

    @staticmethod
    def _apply_orphaned_failure_state(job: Job) -> None:
        error_message = "任务被系统清理（后端异常退出）"
        job.status = "failed"
        job.error_message = error_message
        phase_state = get_phase_display_state(
            job.job_type,
            "failed",
            phase_key=job.phase_key,
            phase_label=job.phase_label,
            phase_progress=job.phase_progress,
            detail=job.detail,
            error_message=error_message,
        )
        JobManager._apply_phase_state_to_job(job, phase_state)
        job.completed_at = utcnow_naive()

    async def _get_job_event_snapshot(self, job_id: str) -> dict[str, object]:
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await self._get_job_row(session, job_id)
                if not job:
                    return {}
                return {
                    "progress": job.progress,
                    **get_phase_display_state(
                        job.job_type,
                        job.status,
                        phase_key=job.phase_key,
                        phase_label=job.phase_label,
                        phase_progress=job.phase_progress,
                        detail=job.detail,
                        error_message=job.error_message,
                    ),
                }

    async def _mark_job_running(self, job_id: str) -> bool:
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await self._get_job_row(session, job_id)
                if not job or job.status == "cancelled" or job_id in self._cancelled_jobs:
                    return False
                job.status = "running"
                job.error_message = None
                running_detail = None if is_followup_detail(job.detail) else job.detail
                if running_detail is None:
                    job.detail = None
                phase_state = get_phase_display_state(
                    job.job_type,
                    "running",
                    phase_key=job.phase_key,
                    phase_label=job.phase_label,
                    phase_progress=job.phase_progress,
                    detail=running_detail,
                )
                self._apply_phase_state_to_job(job, phase_state)
                await session.commit()
                return True

    async def _set_job_progress_state(
        self,
        job_id: str,
        *,
        progress: int | None = None,
        phase_key: str | None = None,
        phase_label: str | None = None,
        phase_progress: int | None = None,
        detail: str | None = None,
    ) -> None:
        normalized_phase_key, normalized_phase_label = self._normalize_phase_payload(
            phase_key=phase_key,
            phase_label=phase_label,
        )
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await self._get_job_row(session, job_id)
                if not job or job.status == "cancelled":
                    return
                if progress is not None:
                    next_progress = max(0, min(100, int(progress)))
                    current_progress = max(0, min(100, int(job.progress or 0)))
                    if job.status == "running":
                        job.progress = max(current_progress, next_progress)
                    else:
                        job.progress = next_progress
                if normalized_phase_key is not None:
                    job.phase_key = normalized_phase_key
                if normalized_phase_label is not None:
                    job.phase_label = normalized_phase_label
                if phase_progress is not None:
                    next_phase_progress = max(0, min(100, int(phase_progress)))
                    current_phase_progress = max(0, min(100, int(job.phase_progress or 0)))
                    phase_key_for_compare = normalized_phase_key or job.phase_key
                    if job.status == "running" and phase_key_for_compare and phase_key_for_compare == job.phase_key:
                        job.phase_progress = max(current_phase_progress, next_phase_progress)
                    else:
                        job.phase_progress = next_phase_progress
                if detail is not None:
                    job.detail = detail
                await session.commit()

    async def _emit_progress_event(
        self,
        job_id: str,
        *,
        progress: int,
        phase_key: str | None = None,
        phase_label: str | None = None,
        phase_progress: int | None = None,
        detail: str | None = None,
    ) -> None:
        normalized_phase_key, normalized_phase_label = self._normalize_phase_payload(
            phase_key=phase_key,
            phase_label=phase_label,
        )
        payload: dict[str, object] = {
            "type": "progress",
            "job_id": job_id,
            "progress": progress,
        }
        if normalized_phase_key is not None:
            payload["phase_key"] = normalized_phase_key
            payload["phase_group"] = get_phase_group(normalized_phase_key)
        if normalized_phase_label is not None:
            payload["phase_label"] = normalized_phase_label
        if phase_progress is not None:
            payload["phase_progress"] = phase_progress
        if detail is not None:
            payload["detail"] = detail
        await self.get_event_queue(job_id).put(payload)
        await self._set_job_progress_state(
            job_id,
            progress=progress,
            phase_key=normalized_phase_key,
            phase_label=normalized_phase_label,
            phase_progress=phase_progress,
            detail=detail,
        )

    async def _finalize_job(
        self,
        job_id: str,
        *,
        status: str,
        output_path: str | None = None,
        error_message: str | None = None,
        progress: int | None = None,
        result_metadata: dict[str, object] | None = None,
    ) -> str | None:
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await self._get_job_row(session, job_id)
                if not job:
                    return None
                if job.status == "cancelled" and status != "cancelled":
                    return job.status

                job.status = status
                job.completed_at = utcnow_naive()
                if output_path is not None:
                    job.output_path = output_path
                if result_metadata is not None:
                    job.result_metadata = result_metadata
                if progress is None and status == "completed":
                    progress = 100
                if progress is not None:
                    job.progress = progress
                    if progress >= 100 and status == "completed":
                        job.phase_progress = 100
                if status in ("completed", "failed", "cancelled", "skipped"):
                    phase_state = get_phase_display_state(
                        job.job_type,
                        status,
                        phase_key=job.phase_key,
                        phase_label=job.phase_label,
                        phase_progress=job.phase_progress,
                        detail=job.detail,
                        error_message=error_message if status in ("failed", "skipped") else None,
                    )
                    self._apply_phase_state_to_job(job, phase_state)
                if error_message is not None:
                    job.error_message = error_message
                elif status not in ("failed", "skipped"):
                    job.error_message = None
                await session.commit()
                return job.status

    async def _emit_terminal_event(
        self,
        event_queue: asyncio.Queue,
        *,
        status: str,
        success: bool,
        job_id: str | None = None,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        snapshot = await self._get_job_event_snapshot(job_id) if job_id else {}
        payload = self._build_state_event_payload(
            status=status,
            success=success,
            progress=progress if progress is not None else snapshot.get("progress"),  # type: ignore[arg-type]
            error=error,
            phase_state=snapshot,
        )
        await event_queue.put(payload)

    async def _finalize_and_emit_terminal(
        self,
        job_id: str,
        *,
        event_queue: asyncio.Queue,
        status: str,
        success: bool,
        output_path: str | None = None,
        error_message: str | None = None,
        progress: int | None = None,
        log_message: str | None = None,
        result_metadata: dict[str, object] | None = None,
    ) -> None:
        await self._finalize_job(
            job_id,
            status=status,
            output_path=output_path,
            error_message=error_message,
            progress=progress,
            result_metadata=result_metadata,
        )
        if log_message:
            await self._append_job_log(job_id, log_message, emit_event=True)
        await self._emit_terminal_event(
            event_queue,
            status=status,
            success=success,
            job_id=job_id,
            progress=progress,
            error=error_message if not success else None,
        )

    async def _finalize_parent_job_chain(
        self,
        job_id: str,
        *,
        event_queue: asyncio.Queue,
        status: str,
        success: bool,
        log_message: str,
        output_path: str | None = None,
        error_message: str | None = None,
        progress: int | None = None,
        result_metadata: dict[str, object] | None = None,
        skipped_reason: str | None = None,
    ) -> None:
        if success:
            await self._activate_blocked_dependents(job_id)
        elif skipped_reason:
            await self._skip_blocked_dependents(job_id, skipped_reason)
        await self._finalize_and_emit_terminal(
            job_id,
            event_queue=event_queue,
            status=status,
            success=success,
            output_path=output_path,
            error_message=error_message,
            progress=progress,
            log_message=log_message,
            result_metadata=result_metadata,
        )

    async def _finish_cancelled_job(self, job_id: str, *, event_queue: asyncio.Queue, log_message: str) -> None:
        await self._finalize_parent_job_chain(
            job_id,
            event_queue=event_queue,
            status="cancelled",
            success=False,
            log_message=log_message,
            skipped_reason="上游任务已取消，后续任务跳过",
        )

    async def _wait_process_exit_with_cancellation(
        self,
        job_id: str,
        *,
        process,
        worker_cancel_event,
        consume_messages,
        cancel_log_message: str,
        force_terminate_log_message: str,
        poll_interval: float = 0.2,
        graceful_shutdown_seconds: float = 3.0,
        kill_timeout_seconds: float = 1.0,
    ) -> bool:
        cancel_logged = False
        force_terminate_logged = False
        terminate_deadline: float | None = None
        cancel_event = self._cancel_event_for(job_id)

        while process.is_alive():
            await consume_messages()
            if cancel_event.is_set() and not cancel_logged:
                cancel_logged = True
                worker_cancel_event.set()
                terminate_deadline = time.time() + graceful_shutdown_seconds
                await self.add_log(job_id, cancel_log_message)
            elif terminate_deadline is not None and time.time() >= terminate_deadline and process.is_alive():
                if not force_terminate_logged:
                    force_terminate_logged = True
                    await self.add_log(job_id, force_terminate_log_message)
                process.terminate()
                terminate_deadline = time.time() + kill_timeout_seconds
            await asyncio.sleep(poll_interval)

        process.join(timeout=kill_timeout_seconds)
        if process.is_alive():
            process.kill()
            process.join(timeout=kill_timeout_seconds)
        await consume_messages()
        return cancel_event.is_set()

    async def _run_whisper_process(
        self,
        job_id: str,
        *,
        process_handle,
        cancel_log_message: str,
    ) -> tuple[str | None, str | None, bool, dict[str, object] | None]:
        from app.pipeline.whisper.progress import AsyncProgressReporter

        process = process_handle.process
        message_queue = process_handle.message_queue
        worker_cancel_event = process_handle.cancel_event
        reporter = AsyncProgressReporter(job_id, self.get_event_queue(job_id))

        output_path: str | None = None
        error_msg: str | None = None
        cancelled = False
        result_metadata: dict[str, object] | None = None

        async def consume_messages() -> None:
            nonlocal output_path, error_msg, cancelled, result_metadata
            while True:
                try:
                    item = message_queue.get_nowait()
                except (queue.Empty, OSError, ValueError):
                    break

                item_type = item.get("type")
                if item_type == "log":
                    line = item.get("line", "")
                    if not line:
                        continue
                    update = reporter.parse_line(line)
                    if update:
                        await self._emit_progress_event(
                            job_id,
                            progress=update.overall_progress,
                            phase_key=update.phase_key,
                            phase_label=update.phase_label,
                            phase_progress=max(0, min(100, int(update.phase_progress * 100))),
                            detail=update.detail,
                        )
                    await self._append_job_log(job_id, line, emit_event=True)
                elif item_type == "result":
                    output_path = item.get("srt_path") or item.get("output_path")
                    result_metadata = item.get("result_metadata") or None
                elif item_type == "error":
                    error_msg = item.get("error") or "Whisper worker failed"
                elif item_type == "cancelled":
                    cancelled = True
                    error_msg = item.get("error") or "Whisper worker cancelled"

        cancel_requested = await self._wait_process_exit_with_cancellation(
            job_id,
            process=process,
            worker_cancel_event=worker_cancel_event,
            consume_messages=consume_messages,
            cancel_log_message=cancel_log_message,
            force_terminate_log_message="Whisper 子进程未及时退出，正在强制终止...",
        )
        close = getattr(message_queue, "close", None)
        if callable(close):
            close()
        join_thread = getattr(message_queue, "join_thread", None)
        if callable(join_thread):
            join_thread()

        if not cancelled and process.exitcode not in (None, 0):
            error_msg = error_msg or f"Whisper worker exited with code {process.exitcode}"
        elif not cancelled and output_path is None and error_msg is None:
            error_msg = "Whisper worker exited without result"
        return output_path, error_msg, cancelled or cancel_requested, result_metadata

    async def _run_translation_process(
        self,
        job_id: str,
        *,
        event_queue: asyncio.Queue,
        process_handle,
        cancel_log_message: str,
    ) -> tuple[str | None, str | None, bool]:
        process = process_handle.process
        message_queue = process_handle.message_queue
        worker_cancel_event = process_handle.cancel_event

        output_path: str | None = None
        error_msg: str | None = None
        cancelled = False

        async def consume_messages() -> None:
            nonlocal output_path, error_msg, cancelled
            while True:
                try:
                    item = message_queue.get_nowait()
                except (queue.Empty, OSError, ValueError):
                    break

                item_type = item.get("type")
                if item_type == "log":
                    line = item.get("line", "")
                    if line:
                        await self._append_job_log(job_id, line, emit_event=True)
                elif item_type == "progress":
                    progress = item.get("progress")
                    if progress is not None:
                        phase_key = item.get("phase_key") or "translate"
                        phase_label = item.get("phase_label") or get_phase_label(phase_key, "字幕翻译")
                        await self._emit_progress_event(
                            job_id,
                            progress=int(progress),
                            phase_key=phase_key,
                            phase_label=phase_label,
                            phase_progress=int(item.get("phase_progress", progress)),
                            detail=item.get("detail") or item.get("line"),
                        )
                elif item_type == "result":
                    output_path = item.get("output_path")
                elif item_type == "error":
                    error_msg = item.get("error") or "Translation worker failed"
                elif item_type == "cancelled":
                    cancelled = True
                    error_msg = item.get("error") or "Translation worker cancelled"

        cancel_requested = await self._wait_process_exit_with_cancellation(
            job_id,
            process=process,
            worker_cancel_event=worker_cancel_event,
            consume_messages=consume_messages,
            cancel_log_message=cancel_log_message,
            force_terminate_log_message="翻译子进程未及时退出，正在强制终止...",
        )
        close = getattr(message_queue, "close", None)
        if callable(close):
            close()
        join_thread = getattr(message_queue, "join_thread", None)
        if callable(join_thread):
            join_thread()

        if not cancelled and process.exitcode not in (None, 0):
            error_msg = error_msg or f"Translation worker exited with code {process.exitcode}"
        elif not cancelled and output_path is None and error_msg is None:
            error_msg = "Translation worker exited without result"
        return output_path, error_msg, cancelled or cancel_requested

    async def _activate_blocked_dependents(self, parent_job_id: str) -> list[str]:
        activated_ids: list[str] = []
        pending_jobs: list[tuple[str, JobCreate, str]] = []
        async with self._db_lock:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Job).where(
                        Job.depends_on_task_id == parent_job_id,
                        Job.status == "blocked",
                    ).order_by(Job.created_at)
                )
                jobs = result.scalars().all()
                for job in jobs:
                    job.status = "queued"
                    job.error_message = None
                    defaults = self._phase_display_state_for_job(job.job_type, "queued", followup_status="queued")
                    self._apply_phase_state_to_job(job, defaults)
                    pending_jobs.append((job.id, self._build_job_create_from_row(job), job.job_type))
                    activated_ids.append(job.id)
                await session.commit()
        for job_id, job_data, job_type in pending_jobs:
            defaults = self._phase_display_state_for_job(job_type, "queued", followup_status="queued")
            await self.queue.put(job_id)
            await self.get_event_queue(job_id).put(
                self._build_state_event_payload(status="queued", job_id=job_id, phase_state=defaults)
            )
        if pending_jobs:
            self._ensure_worker()
        return activated_ids

    async def _skip_blocked_dependents(self, parent_job_id: str, reason: str) -> list[str]:
        skipped_ids: list[str] = []
        skipped_events: list[tuple[str, dict[str, object]]] = []
        async with self._db_lock:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Job).where(
                        Job.depends_on_task_id == parent_job_id,
                        Job.status.in_(["blocked", "pending"]),
                    )
                )
                jobs = result.scalars().all()
                for job in jobs:
                    job.status = "skipped"
                    defaults = self._phase_display_state_for_job(
                        job.job_type,
                        "skipped",
                        phase_key=job.phase_key,
                        phase_label=job.phase_label,
                        phase_progress=job.phase_progress,
                        detail=reason,
                        error_message=reason,
                    )
                    self._apply_phase_state_to_job(job, defaults)
                    job.progress = 0
                    job.error_message = reason
                    job.completed_at = utcnow_naive()
                    skipped_ids.append(job.id)
                    skipped_events.append((job.id, defaults))
                await session.commit()
        for job_id, phase_state in skipped_events:
            await self.get_event_queue(job_id).put(
                self._build_state_event_payload(
                    status="skipped",
                    success=False,
                    job_id=job_id,
                    phase_state=phase_state,
                    progress=0,
                    error=reason,
                )
            )
        return skipped_ids

    def get_event_queue(self, job_id: str) -> asyncio.Queue:
        if job_id not in self._event_queues:
            self._event_queues[job_id] = asyncio.Queue()
        return self._event_queues[job_id]

    async def remove_event_queue(self, job_id: str) -> None:
        self._event_queues.pop(job_id, None)

    def _log_file_path(self, job_id: str) -> str:
        return log_file_path(job_id)

    async def get_logs(self, job_id: str) -> list[str]:
        if self._logs.get(job_id):
            return self._logs[job_id]
        return read_log_lines(job_id)

    async def add_log(self, job_id: str, log: str) -> None:
        self._logs.setdefault(job_id, []).append(log)
        try:
            append_log_line(job_id, log)
        except Exception as exc:
            logger.warning("Failed to save log for job %s: %s", job_id, exc)

    async def _append_job_log(self, job_id: str, line: str, *, emit_event: bool = False) -> None:
        await self.add_log(job_id, line)
        if emit_event:
            await self.get_event_queue(job_id).put({"type": "log", "job_id": job_id, "line": line})

    def _build_job_create_from_row(self, job: Job) -> JobCreate:
        return JobCreate(
            emby_item_id=job.emby_item_id,
            emby_item_name=job.emby_item_name,
            input_path=job.input_path,
            settings=job.settings or {},
            chain_id=job.chain_id,
            depends_on_task_id=job.depends_on_task_id,
            parent_task_id=job.parent_task_id,
        )

    def _default_followup_phase_state(self, job_type: str | None) -> dict[str, object]:
        return get_followup_phase_state(job_type or "")

    def _phase_display_state_for_job(
        self,
        job_type: str | None,
        status: str | None,
        *,
        phase_key: str | None = None,
        phase_label: str | None = None,
        phase_progress: int | None = None,
        detail: str | None = None,
        error_message: str | None = None,
        followup_status: str | None = None,
    ) -> dict[str, object]:
        if detail is None and followup_status is not None:
            detail = get_followup_phase_state(job_type or "", status=followup_status).get("detail")  # type: ignore[assignment]
        return get_phase_display_state(
            job_type,
            status,
            phase_key=phase_key,
            phase_label=phase_label,
            phase_progress=phase_progress,
            detail=detail,
            error_message=error_message,
        )

    async def create_job(
        self,
        job_data: JobCreate,
        *,
        job_type: str = "lada",
        status: str = "queued",
        enqueue_now: bool = True,
    ) -> JobResponse:
        if status not in {"queued", "blocked"}:
            raise ValueError(f"Unsupported job status: {status}")
        if enqueue_now and status != "queued":
            raise ValueError("Only queued jobs can be enqueued immediately")
        if bool(job_data.depends_on_task_id) != bool(job_data.parent_task_id):
            raise ValueError("Dependent jobs must include both depends_on_task_id and parent_task_id")
        if job_data.depends_on_task_id and job_data.parent_task_id and job_data.depends_on_task_id != job_data.parent_task_id:
            raise ValueError("depends_on_task_id and parent_task_id must match")
        if status == "blocked" and not job_data.depends_on_task_id:
            raise ValueError("Blocked jobs must depend on a parent task")

        job_id = str(uuid.uuid4())
        settings = job_data.settings.model_dump() if hasattr(job_data.settings, "model_dump") else dict(job_data.settings or {})
        async with self._db_lock:
            async with async_session_maker() as session:
                job = Job(
                    id=job_id,
                    job_type=job_type,
                    emby_item_id=job_data.emby_item_id,
                    emby_item_name=job_data.emby_item_name,
                    input_path=job_data.input_path,
                    status=status,
                    progress=0,
                    settings=settings,
                    chain_id=job_data.chain_id,
                    depends_on_task_id=job_data.depends_on_task_id,
                    parent_task_id=job_data.parent_task_id,
                    logs=[],
                    created_at=utcnow_naive(),
                )
                if status == "queued":
                    self._apply_phase_state_to_job(job, self._phase_display_state_for_job(job_type, "queued"))
                session.add(job)
                await session.commit()
                await session.refresh(job)
                response = JobResponse.model_validate(job, from_attributes=True)

        if enqueue_now and status == "queued":
            await self.queue.put(job_id)
            await self.get_event_queue(job_id).put(
                self._build_state_event_payload(
                    status="queued",
                    job_id=job_id,
                    phase_state=self._phase_display_state_for_job(job_type, "queued"),
                )
            )
            self._ensure_worker()
        elif status == "blocked":
            defaults = self._phase_display_state_for_job(job_type, "blocked", followup_status="blocked")
            if defaults:
                await self._set_job_progress_state(
                    job_id,
                    progress=0,
                    phase_key=defaults.get("phase_key"),  # type: ignore[arg-type]
                    phase_label=defaults.get("phase_label"),  # type: ignore[arg-type]
                    phase_progress=defaults.get("phase_progress"),  # type: ignore[arg-type]
                    detail=defaults.get("detail"),  # type: ignore[arg-type]
                )
                refreshed = await self.get_job(job_id)
                if refreshed:
                    response = refreshed
            await self.get_event_queue(job_id).put(
                self._build_state_event_payload(status="blocked", job_id=job_id, phase_state=defaults)
            )
        return response

    async def enqueue(self, job_data: JobCreate, job_type: str = "lada") -> JobResponse:
        return await self.create_job(job_data, job_type=job_type, status="queued", enqueue_now=True)

    async def enqueue_whisper(self, job_data: JobCreate) -> JobResponse:
        if hasattr(job_data, "model_copy") and hasattr(job_data.settings, "model_copy"):
            job_data = job_data.model_copy(
                update={
                    "settings": job_data.settings.model_copy(
                        update={
                            "translate_to": None,
                        }
                    )
                }
            )
        return await self.enqueue(job_data, job_type="whisper")

    async def enqueue_translate_srt(self, job_data: JobCreate) -> JobResponse:
        return await self.enqueue(job_data, job_type="translate-srt")

    async def enqueue_facefusion(self, job_data: JobCreate) -> JobResponse:
        return await self.enqueue(job_data, job_type="facefusion_restore")

    def set_max_concurrent(self, max_concurrent: int) -> None:
        self._max_concurrent = max(1, max_concurrent)

    async def get_job(self, job_id: str) -> JobResponse | None:
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            return JobResponse.model_validate(job, from_attributes=True) if job else None

    async def get_all_jobs(self, status: str | None = None, job_type: str | None = None, limit: int = 100) -> list[JobResponse]:
        async with async_session_maker() as session:
            statement = select(Job)
            if status:
                statement = statement.where(Job.status == status)
            if job_type:
                statement = statement.where(Job.job_type == job_type)
            result = await session.execute(
                statement.order_by(Job.created_at.desc()).limit(max(1, min(limit, 1000)))
            )
            return [JobResponse.model_validate(job, from_attributes=True) for job in result.scalars().all()]

    async def delete_job(self, job_id: str) -> bool:
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await session.get(Job, job_id)
                if not job:
                    return False
                if job.status in {"queued", "running", "blocked"}:
                    return False
                await session.delete(job)
                await session.commit()
        try:
            Path(log_file_path(job_id)).unlink(missing_ok=True)
        except OSError:
            pass
        return True

    async def cancel_job(self, job_id: str) -> JobResponse | None:
        async with self._db_lock:
            async with async_session_maker() as session:
                job = await session.get(Job, job_id)
                if not job:
                    return None
                if job.status in {"completed", "failed", "cancelled", "skipped"}:
                    return JobResponse.model_validate(job, from_attributes=True)
                job.status = "cancelled"
                job.completed_at = utcnow_naive()
                await session.commit()
                await session.refresh(job)
                response = JobResponse.model_validate(job, from_attributes=True)

        self._cancelled_jobs.add(job_id)
        cancel_event = self._cancel_event_for(job_id)
        if not cancel_event.is_set():
            cancel_event.set()
        await self._append_job_log(job_id, "任务取消请求已发送", emit_event=True)
        await self.get_event_queue(job_id).put({"type": "cancelled", "job_id": job_id, "success": False})
        return response

    async def cleanup_orphaned_jobs(self) -> int:
        count = 0
        async with self._db_lock:
            async with async_session_maker() as session:
                result = await session.execute(select(Job).where(Job.status == "running"))
                for job in result.scalars():
                    self._apply_orphaned_failure_state(job)
                    count += 1
                await session.commit()
        return count

    async def recover_queued_jobs(self) -> None:
        await self.cleanup_orphaned_jobs()
        async with async_session_maker() as session:
            result = await session.execute(
                select(Job.id).where(Job.status == "queued").order_by(Job.created_at)
            )
            queued = list(result.scalars())
        for job_id in queued:
            await self.queue.put(job_id)
        if queued:
            self._ensure_worker()

    async def _process_queue(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                cancel_event = self._cancel_event_for(job_id)
                if not await self._mark_job_running(job_id):
                    self._cancelled_jobs.discard(job_id)
                    self._cancel_events.pop(job_id, None)
                    continue
                async with async_session_maker() as session:
                    job = await session.get(Job, job_id)
                    job_type = job.job_type if job else "lada"
                    job_data = self._build_job_create_from_row(job) if job else None
                    input_path = job.input_path if job else ""
                    settings = dict(job.settings or {}) if job else {}
                    name = job.emby_item_name if job else ""
                self.running_job = job_data
                self.running_job_id = job_id
                self._running_since = time.time()
                await self._append_job_log(job_id, f"开始执行 {job_type}: {name}", emit_event=True)
                try:
                    if job_type == "whisper":
                        await self._run_whisper(job_id, input_path, settings, cancel_event)
                    elif job_type == "translate-srt":
                        await self._run_translate_srt(job_id, input_path, settings, cancel_event)
                    elif job_type == "facefusion_restore":
                        await self._run_facefusion(job_id, input_path, settings, cancel_event)
                    else:
                        await self._run_lada(job_id, input_path, settings, cancel_event)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if not await self._is_cancelled(job_id):
                        await self._append_job_log(job_id, f"任务异常: {exc}", emit_event=True)
                        await self._finalize_parent_job_chain(
                            job_id,
                            event_queue=self.get_event_queue(job_id),
                            status="failed",
                            success=False,
                            log_message=f"任务失败: {exc}",
                            error_message=str(exc),
                            skipped_reason="上游任务失败，后续任务跳过",
                        )
                finally:
                    if self.running_job_id == job_id:
                        self.running_job = None
                        self.running_job_id = None
                        self._running_since = None
                    self._cancel_events.pop(job_id, None)
                    self._cancelled_jobs.discard(job_id)
            finally:
                self.queue.task_done()

    async def _run_lada(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        runtime_settings = get_settings()
        output_path = build_lada_output_path(
            input_path,
            str(settings.get("source_dir") or runtime_settings.source_dir or ""),
            str(settings.get("output_dir") or runtime_settings.output_dir or ""),
        )
        await self._ensure_gpu_memory_for_job(job_id, "lada", "LADA", settings)
        progress_queue: asyncio.Queue = asyncio.Queue()
        reader_task = asyncio.create_task(self._read_lada_progress(job_id, progress_queue))
        success = await run_lada_restoration(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            job_settings=settings,
            progress_queue=progress_queue,
            cancel_event=cancel_event,
        )
        await self._drain_progress_queue(reader_task, progress_queue)
        if cancel_event.is_set():
            await self._finish_cancelled_job(job_id, event_queue=self.get_event_queue(job_id), log_message="LADA 任务已取消")
            return
        await self._finalize_parent_job_chain(
            job_id,
            event_queue=self.get_event_queue(job_id),
            status="completed" if success else "failed",
            success=success,
            output_path=output_path if success else None,
            error_message=None if success else "Process exited with non-zero status",
            progress=100 if success else None,
            log_message="LADA 任务完成" if success else "LADA 任务失败",
        )

    async def _read_lada_progress(self, job_id: str, progress_queue: asyncio.Queue) -> None:
        while True:
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("type")
            if msg_type == "progress":
                await self._emit_progress_event(
                    job_id,
                    progress=int(msg.get("progress") or 0),
                    phase_key=msg.get("phase_key") or "process",
                    phase_label=msg.get("phase_label") or get_phase_label(msg.get("phase_key") or "process", "LADA 处理中"),
                    phase_progress=msg.get("phase_progress"),
                    detail=msg.get("detail") or msg.get("line"),
                )
                await self._append_job_log(job_id, msg.get("line") or f"Progress: {msg.get('progress')}%", emit_event=True)
            elif msg_type == "log":
                line = msg.get("line")
                if line:
                    await self._append_job_log(job_id, line, emit_event=True)

    async def _run_facefusion(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        source = Path(input_path)
        if not source.is_file():
            raise RuntimeError(f"输入文件不存在: {input_path}")
        await self._ensure_gpu_memory_for_job(job_id, "facefusion", "FaceFusion", settings)
        configured_output_dir = str(settings.get("output_dir") or "").strip()
        output_dir = Path(configured_output_dir) if configured_output_dir else source.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{source.stem}.facefusion{source.suffix}"
        progress_queue: asyncio.Queue = asyncio.Queue()
        reader_task = asyncio.create_task(self._read_facefusion_progress(job_id, progress_queue))
        runner = asyncio.create_task(
            run_facefusion_restoration(
                job_id,
                input_path,
                str(output_path),
                settings,
                progress_queue,
                cancel_event,
            )
        )
        success = await runner
        await self._drain_progress_queue(reader_task, progress_queue)
        if cancel_event.is_set():
            await self._finish_cancelled_job(job_id, event_queue=self.get_event_queue(job_id), log_message="FaceFusion 任务已取消")
            return
        if not success:
            raise RuntimeError("FaceFusion 处理进程返回非零状态，请查看任务日志")
        if not output_path.is_file():
            raise RuntimeError(f"FaceFusion 未产生输出文件: {output_path}")
        await self._finalize_parent_job_chain(
            job_id,
            event_queue=self.get_event_queue(job_id),
            status="completed",
            success=True,
            output_path=str(output_path),
            progress=100,
            log_message=f"任务完成: {output_path}",
            result_metadata={"processor": "facefusion"},
        )

    async def _read_facefusion_progress(self, job_id: str, progress_queue: asyncio.Queue) -> None:
        while True:
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "log":
                line = msg.get("line")
                if line:
                    await self._append_job_log(job_id, line, emit_event=True)
            elif msg.get("type") == "progress":
                await self._emit_progress_event(
                    job_id,
                    progress=int(msg.get("progress") or 0),
                    phase_key=msg.get("phase_key") or "process",
                    phase_label=msg.get("phase_label") or get_phase_label(msg.get("phase_key") or "process", "FaceFusion 处理中"),
                    phase_progress=msg.get("phase_progress"),
                    detail=msg.get("detail") or msg.get("line"),
                )

    async def _drain_progress_queue(self, reader_task: asyncio.Task, progress_queue: asyncio.Queue, timeout: float = 2.0) -> None:
        deadline = time.time() + max(0.1, timeout)
        while not progress_queue.empty() and time.time() < deadline:
            await asyncio.sleep(0.05)
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass

    async def _run_whisper(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        from app.pipeline.whisper.runtime import launch_whisper_process
        from app.pipeline.whisper.types import WhisperConfig

        whisper_fields = set(WhisperConfig.__dataclass_fields__)
        config = WhisperConfig(**{key: value for key, value in settings.items() if key in whisper_fields})
        await self._ensure_gpu_memory_for_job(job_id, "whisper", "Whisper", settings)
        await self._append_job_log(job_id, "Whisper 架构: NOOR Whisper Pipeline", emit_event=True)
        await self._append_job_log(job_id, f"  Pipeline: {config.pipeline_mode.value} | 模型: {config.model.value} | 任务: {config.whisper_task}", emit_event=True)
        await self._append_job_log(job_id, "开始 Whisper 字幕生成...", emit_event=True)

        process_handle = launch_whisper_process(
            config,
            input_path,
            os.path.splitext(os.path.basename(input_path))[0],
        )
        output_path, error_msg, cancelled, result_metadata = await self._run_whisper_process(
            job_id,
            process_handle=process_handle,
            cancel_log_message="Whisper 取消请求已发送；等待当前阶段安全退出...",
        )
        if cancelled:
            await self._finish_cancelled_job(job_id, event_queue=self.get_event_queue(job_id), log_message="Whisper 任务已取消")
            return
        if error_msg:
            await self._finalize_parent_job_chain(
                job_id,
                event_queue=self.get_event_queue(job_id),
                status="failed",
                success=False,
                log_message=f"Whisper 任务失败: {error_msg}",
                error_message=error_msg,
                skipped_reason="上游任务失败，后续任务跳过",
            )
            return
        await self._finalize_parent_job_chain(
            job_id,
            event_queue=self.get_event_queue(job_id),
            status="completed",
            success=True,
            output_path=output_path,
            progress=100,
            log_message=f"Whisper 任务完成: {output_path}",
            result_metadata=result_metadata or {},
        )

    async def _run_translate_srt(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        from app.pipeline.whisper.runtime import launch_translation_process

        source_path = str(settings.get("srt_path") or input_path or "")
        if not source_path:
            raise RuntimeError("缺少待翻译字幕路径")
        source = Path(source_path)
        if not source.is_file():
            raise RuntimeError(f"SRT 文件不存在: {source_path}")
        target_lang = settings.get("target_lang") or "zh"
        model_name = settings.get("translate_model") or settings.get("model") or "gpt-4o-mini"
        base_url = settings.get("translate_base_url") or "https://api.openai.com/v1"
        api_key = settings.get("translate_api_key") or None
        translate_style = settings.get("translate_style", "adult_explicit")

        process_handle = launch_translation_process(
            source_path,
            target_lang,
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            translate_style=translate_style,
            progress_base=0,
            progress_span=100,
        )
        output_path, error_msg, cancelled = await self._run_translation_process(
            job_id,
            event_queue=self.get_event_queue(job_id),
            process_handle=process_handle,
            cancel_log_message="翻译取消请求已发送；等待当前批次安全退出...",
        )
        if cancelled:
            await self._finish_cancelled_job(job_id, event_queue=self.get_event_queue(job_id), log_message="翻译任务已取消")
            return
        if error_msg:
            await self._finalize_parent_job_chain(
                job_id,
                event_queue=self.get_event_queue(job_id),
                status="failed",
                success=False,
                log_message=f"翻译任务失败: {error_msg}",
                error_message=error_msg,
                skipped_reason="上游任务失败，后续任务跳过",
            )
            return
        await self._finalize_parent_job_chain(
            job_id,
            event_queue=self.get_event_queue(job_id),
            status="completed",
            success=True,
            output_path=output_path,
            progress=100,
            log_message=f"翻译完成: {output_path}",
        )

    async def _ensure_gpu_memory_for_job(
        self,
        job_id: str,
        task_key: str,
        task_name: str,
        job_settings: dict | None = None,
    ) -> None:
        settings = get_settings()
        if not settings.gpu_guard_enabled:
            return
        job_settings = job_settings or {}

        if task_key == "lada":
            device = str(job_settings.get("device", settings.lada_device or "")).lower()
            preset = str(job_settings.get("encoding_preset", settings.lada_encoding_preset or "")).lower()
            if "cuda" not in device and "nvidia" not in preset:
                return
        elif task_key == "facefusion":
            ff_settings = facefusion_settings(settings)
            provider = str(job_settings.get("execution_provider", ff_settings.facefusion_execution_provider or "")).lower()
            if "cuda" not in provider and "tensorrt" not in provider:
                return

        required_free_mb = int(
            {
                "lada": settings.gpu_guard_lada_required_free_mb,
                "facefusion": settings.gpu_guard_facefusion_required_free_mb,
                "whisper": settings.gpu_guard_whisper_required_free_mb,
            }.get(task_key, 0) or 0
        )
        if required_free_mb <= 0:
            return

        try:
            logs = await asyncio.to_thread(
                ensure_gpu_memory,
                task_name=task_name,
                required_free_mb=required_free_mb,
                device_index=int(settings.gpu_guard_device_index or 0),
                cleanup_policy=settings.gpu_guard_cleanup_policy,
                grace_seconds=int(settings.gpu_guard_grace_seconds or 8),
            )
        except Exception as exc:
            await self._append_job_log(job_id, f"GPU Guard: {exc}", emit_event=True)
            raise
        for line in logs:
            await self._append_job_log(job_id, line, emit_event=True)


job_manager = JobManager()
