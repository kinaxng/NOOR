from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.models import Job, JobCreate, JobResponse
from app.pipeline.facefusion.runner import run_facefusion_restoration
from app.pipeline.lada.runner import run_lada_restoration
from app.tasks.manager_helpers import append_log_line, build_lada_output_path, log_file_path, read_log_lines, utcnow_naive


class JobManager:
    """Persistent, single-worker NOOR job queue recovered from the API contract."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._events: dict[str, asyncio.Queue] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())

    def get_event_queue(self, job_id: str) -> asyncio.Queue:
        return self._events.setdefault(job_id, asyncio.Queue())

    async def remove_event_queue(self, job_id: str) -> None:
        self._events.pop(job_id, None)

    async def _emit(self, job_id: str, kind: str, **payload: Any) -> None:
        await self.get_event_queue(job_id).put({'type': kind, 'job_id': job_id, **payload})

    async def _log(self, job_id: str, line: str) -> None:
        append_log_line(job_id, line)
        await self._emit(job_id, 'log', line=line)

    @staticmethod
    def _response(job: Job) -> JobResponse:
        return JobResponse.model_validate(job, from_attributes=True)

    async def create_job(self, job_data: JobCreate, *, job_type: str = 'lada', status: str = 'queued', enqueue_now: bool = True) -> JobResponse:
        job_id = str(uuid.uuid4())
        settings = job_data.settings.model_dump() if hasattr(job_data.settings, 'model_dump') else dict(job_data.settings or {})
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
            session.add(job)
            await session.commit()
            await session.refresh(job)
            response = self._response(job)
        if enqueue_now and status == 'queued':
            await self.queue.put(job_id)
            self._ensure_worker()
            await self._emit(job_id, 'queued', detail='任务已加入队列')
        elif status == 'blocked':
            await self._emit(job_id, 'blocked', detail='等待前置任务完成')
        return response

    async def enqueue(self, job_data: JobCreate) -> JobResponse:
        return await self.create_job(job_data, job_type='lada')

    async def enqueue_whisper(self, job_data: JobCreate) -> JobResponse:
        return await self.create_job(job_data, job_type='whisper')

    async def enqueue_translate_srt(self, job_data: JobCreate) -> JobResponse:
        return await self.create_job(job_data, job_type='translate-srt')

    async def enqueue_facefusion(self, job_data: JobCreate) -> JobResponse:
        return await self.create_job(job_data, job_type='facefusion_restore')

    async def get_job(self, job_id: str) -> JobResponse | None:
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            return self._response(job) if job else None

    async def get_all_jobs(self, status: str | None = None, limit: int = 100) -> list[JobResponse]:
        async with async_session_maker() as session:
            statement = select(Job)
            if status:
                statement = statement.where(Job.status == status)
            result = await session.execute(statement.order_by(Job.created_at.desc()).limit(max(1, min(limit, 1000))))
            return [self._response(job) for job in result.scalars().all()]

    async def get_logs(self, job_id: str) -> list[str]:
        return read_log_lines(job_id)

    async def delete_job(self, job_id: str) -> bool:
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            if not job:
                return False
            if job.status in {'queued', 'running', 'blocked'}:
                return False
            await session.delete(job)
            await session.commit()
        try:
            Path(log_file_path(job_id)).unlink(missing_ok=True)
        except OSError:
            pass
        return True

    async def cancel_job(self, job_id: str) -> JobResponse | None:
        self._cancel_events.setdefault(job_id, asyncio.Event()).set()
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            if not job:
                return None
            if job.status not in {'completed', 'failed', 'cancelled', 'skipped'}:
                job.status = 'cancelled'
                job.completed_at = utcnow_naive()
                job.detail = '任务已取消'
                await session.commit()
                await session.refresh(job)
            response = self._response(job)
        await self._log(job_id, '任务已取消')
        await self._emit(job_id, 'cancelled', success=False, progress=response.progress, detail=response.detail)
        return response

    async def cleanup_orphaned_jobs(self) -> int:
        count = 0
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.status == 'running'))
            for job in result.scalars():
                job.status = 'failed'
                job.error_message = '后端异常退出，任务已停止'
                job.completed_at = utcnow_naive()
                count += 1
            await session.commit()
        return count

    async def recover_queued_jobs(self) -> None:
        await self.cleanup_orphaned_jobs()
        async with async_session_maker() as session:
            result = await session.execute(select(Job.id).where(Job.status == 'queued'))
            queued = list(result.scalars())
        for job_id in queued:
            await self.queue.put(job_id)
        if queued:
            self._ensure_worker()

    async def _set_state(self, job_id: str, *, status: str | None = None, progress: int | None = None, detail: str | None = None, error: str | None = None, output_path: str | None = None, result_metadata: dict | None = None) -> Job | None:
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
                if status in {'completed', 'failed', 'cancelled', 'skipped'}:
                    job.completed_at = utcnow_naive()
            if progress is not None:
                job.progress = max(0, min(100, int(progress)))
            if detail is not None:
                job.detail = detail
            if error is not None:
                job.error_message = error
            if output_path is not None:
                job.output_path = output_path
            if result_metadata is not None:
                job.result_metadata = result_metadata
            await session.commit()
            await session.refresh(job)
            return job

    async def _progress(self, job_id: str, progress: int, detail: str | None = None) -> None:
        job = await self._set_state(job_id, progress=progress, detail=detail)
        if job:
            await self._emit(job_id, 'progress', progress=job.progress, phase_progress=job.progress, detail=job.detail)

    async def _process_queue(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self._run_job(job_id)
            finally:
                self.queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        async with async_session_maker() as session:
            job = await session.get(Job, job_id)
            if not job or job.status != 'queued':
                return
            job.status = 'running'
            job.detail = '任务执行中'
            await session.commit()
            job_type = job.job_type
            input_path = job.input_path
            settings = dict(job.settings or {})
            name = job.emby_item_name
        cancel_event = self._cancel_events.setdefault(job_id, asyncio.Event())
        await self._log(job_id, f'开始执行 {job_type}: {name}')
        await self._emit(job_id, 'progress', progress=0, detail='任务执行中')
        try:
            if job_type == 'lada':
                output_path = build_lada_output_path(input_path, settings)
                progress_queue: asyncio.Queue = asyncio.Queue()
                runner = asyncio.create_task(run_lada_restoration(job_id, input_path, output_path, settings, progress_queue, cancel_event))
                while not runner.done():
                    try:
                        update = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(update, dict):
                        await self._progress(job_id, int(update.get('progress', 0)), update.get('detail') or update.get('message'))
                success = await runner
                if not success:
                    raise RuntimeError('LADA 处理失败')
                await self._complete(job_id, output_path)
            elif job_type == 'whisper':
                await self._run_whisper(job_id, input_path, settings, cancel_event)
            elif job_type == 'translate-srt':
                await self._run_translation(job_id, settings)
            elif job_type == 'facefusion_restore':
                await self._run_facefusion(job_id, input_path, settings, cancel_event)
            else:
                raise RuntimeError(f'不支持的任务类型: {job_type}')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if cancel_event.is_set():
                await self.cancel_job(job_id)
            else:
                await self._fail(job_id, str(exc))

    async def _run_whisper(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        from app.pipeline.whisper.orchestrator import create_task, run_whisper_task
        from app.pipeline.whisper.types import WhisperConfig
        config = WhisperConfig(**settings)
        task = create_task(input_path, config)

        def progress_callback(*args: Any, **kwargs: Any) -> None:
            value = kwargs.get('progress', args[0] if args else 0)
            detail = kwargs.get('detail') or kwargs.get('message')
            asyncio.get_running_loop().create_task(self._progress(job_id, int(value), detail))

        result, srt_path = await run_whisper_task(task.id, progress_callback=progress_callback, cancel_callback=cancel_event.is_set)
        await self._complete(job_id, srt_path, {'segments': len(result.segments)})

    async def _run_translation(self, job_id: str, settings: dict) -> None:
        from app.pipeline.whisper.translator import get_translator
        source = Path(settings['srt_path'])
        text = source.read_text(encoding='utf-8-sig')
        translator = get_translator(settings.get('translate_model'), settings.get('translate_base_url'), settings.get('translate_api_key'), settings.get('translate_style', 'adult_explicit'))
        lines = text.splitlines()
        content_indexes = [index for index, line in enumerate(lines) if line.strip() and not line.strip().isdigit() and '-->' not in line]
        translated = translator.translate_batch([lines[index] for index in content_indexes], settings.get('target_lang', 'zh'))
        for index, value in zip(content_indexes, translated):
            lines[index] = value
        target = source.with_name(f'{source.stem}.{settings.get("target_lang", "zh")}.srt')
        target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        await self._complete(job_id, str(target))

    async def _run_facefusion(self, job_id: str, input_path: str, settings: dict, cancel_event: asyncio.Event) -> None:
        source = Path(input_path)
        if not source.is_file():
            raise RuntimeError(f'输入文件不存在: {input_path}')
        configured_output_dir = str(settings.get('output_dir') or '').strip()
        output_dir = Path(configured_output_dir) if configured_output_dir else source.parent
        output_path = output_dir / f'{source.stem}.facefusion{source.suffix}'
        progress_queue: asyncio.Queue = asyncio.Queue()
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
        while not runner.done():
            try:
                update = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._consume_facefusion_update(job_id, update)
        while not progress_queue.empty():
            await self._consume_facefusion_update(job_id, progress_queue.get_nowait())
        success = await runner
        if cancel_event.is_set():
            await self.cancel_job(job_id)
            return
        if not success:
            raise RuntimeError('FaceFusion 处理失败')
        if not output_path.is_file():
            raise RuntimeError(f'FaceFusion 未产生输出文件: {output_path}')
        await self._complete(job_id, str(output_path), {'processor': 'facefusion'})

    async def _consume_facefusion_update(self, job_id: str, update: Any) -> None:
        if not isinstance(update, dict):
            return
        if update.get('type') == 'log':
            await self._log(job_id, str(update.get('line') or ''))
            return
        if update.get('type') == 'progress':
            await self._progress(job_id, int(update.get('progress', 0)), update.get('detail') or update.get('message'))

    async def _complete(self, job_id: str, output_path: str, metadata: dict | None = None) -> None:
        job = await self._set_state(job_id, status='completed', progress=100, detail='任务完成', output_path=output_path, result_metadata=metadata)
        await self._log(job_id, f'任务完成: {output_path}')
        await self._emit(job_id, 'completed', success=True, progress=100, detail='任务完成')
        if job:
            await self._release_dependents(job.id)

    async def _fail(self, job_id: str, error: str) -> None:
        await self._set_state(job_id, status='failed', detail='任务失败', error=error)
        await self._log(job_id, f'任务失败: {error}')
        await self._emit(job_id, 'failed', success=False, error=error, detail='任务失败')

    async def _release_dependents(self, job_id: str) -> None:
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.depends_on_task_id == job_id, Job.status == 'blocked'))
            children = list(result.scalars())
            for child in children:
                child.status = 'queued'
                child.detail = '前置任务完成，已加入队列'
            await session.commit()
        for child in children:
            await self.queue.put(child.id)
            await self._emit(child.id, 'queued', detail='前置任务完成，已加入队列')
        if children:
            self._ensure_worker()


job_manager = JobManager()
