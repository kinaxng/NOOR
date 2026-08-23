from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.core.models import Job, JobCreate, JobSettings
from app.tasks import manager as manager_module
from app.tasks.manager import JobManager


@pytest_asyncio.fixture
async def job_db(monkeypatch, tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(manager_module, "async_session_maker", factory)
    monkeypatch.setattr(JobManager, "_ensure_worker", lambda self: None)
    yield factory
    await engine.dispose()


def _job_data(name: str = "test-job") -> JobCreate:
    return JobCreate(
        emby_item_id="emby-1",
        emby_item_name=name,
        input_path="/tmp/input.mp4",
        settings=JobSettings(),
    )


@pytest.mark.asyncio
async def test_create_job_initializes_phase_state(job_db):
    manager = JobManager()
    response = await manager.create_job(_job_data(), job_type="whisper", enqueue_now=False)

    assert response.status == "queued"
    assert response.phase_key == "prepare"
    assert response.phase_label == "准备任务"
    assert response.phase_progress == 0


@pytest.mark.asyncio
async def test_cancel_queued_job_returns_cancelled_and_emits_event(job_db):
    manager = JobManager()
    created = await manager.create_job(_job_data(), job_type="translate-srt", enqueue_now=False)
    queue = manager.get_event_queue(created.id)

    cancelled = await manager.cancel_job(created.id)

    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert cancelled.completed_at is not None
    events = []
    while not queue.empty():
        events.append(await queue.get())
    assert events[-1]["type"] == "cancelled"
    assert events[-1]["success"] is False


@pytest.mark.asyncio
async def test_completed_parent_activates_blocked_dependents(job_db):
    manager = JobManager()
    parent = await manager.create_job(_job_data("parent"), job_type="whisper", enqueue_now=False)
    child_data = _job_data("child")
    child_data.chain_id = "chain-1"
    child_data.depends_on_task_id = parent.id
    child_data.parent_task_id = parent.id
    child = await manager.create_job(
        child_data,
        job_type="translate-srt",
        status="blocked",
        enqueue_now=False,
    )

    activated = await manager._activate_blocked_dependents(parent.id)

    assert activated == [child.id]
    async with job_db() as session:
        row = await session.get(Job, child.id)
        assert row is not None
        assert row.status == "queued"
        assert row.detail == "主任务已完成，准备开始后续任务"
    event_queue = manager.get_event_queue(child.id)
    while not event_queue.empty():
        event = await event_queue.get()
    assert event["type"] == "queued"


@pytest.mark.asyncio
async def test_failed_parent_skips_blocked_dependents(job_db):
    manager = JobManager()
    parent = await manager.create_job(_job_data("parent"), job_type="whisper", enqueue_now=False)
    child_data = _job_data("child")
    child_data.depends_on_task_id = parent.id
    child_data.parent_task_id = parent.id
    child = await manager.create_job(
        child_data,
        job_type="translate-srt",
        status="blocked",
        enqueue_now=False,
    )

    skipped = await manager._skip_blocked_dependents(parent.id, "上游任务失败，后续任务跳过")

    assert skipped == [child.id]
    async with job_db() as session:
        row = await session.get(Job, child.id)
        assert row is not None
        assert row.status == "skipped"
        assert row.error_message == "上游任务失败，后续任务跳过"


@pytest.mark.asyncio
async def test_cleanup_orphaned_running_job_marks_failed(job_db):
    manager = JobManager()
    created = await manager.create_job(_job_data(), job_type="lada", enqueue_now=False)
    async with job_db() as session:
        job = await session.get(Job, created.id)
        assert job is not None
        job.status = "running"
        await session.commit()

    cleaned = await manager.cleanup_orphaned_jobs()

    assert cleaned == 1
    async with job_db() as session:
        row = await session.get(Job, created.id)
        assert row is not None
        assert row.status == "failed"
        assert row.error_message == "任务被系统清理（后端异常退出）"
        assert row.phase_key == "prepare"
        assert row.phase_label == "准备任务"


@pytest.mark.asyncio
async def test_whisper_job_runs_through_worker_process(job_db, monkeypatch, tmp_path):
    manager = JobManager()
    created = await manager.create_job(_job_data(), job_type="whisper", enqueue_now=False)
    launch_calls = []

    async def no_gpu_guard(*args, **kwargs):
        return None

    async def fake_run_process(*args, **kwargs):
        return str(tmp_path / "output.zh.srt"), None, False, {"segments": 1}

    def fake_launch(config, input_path, video_name):
        launch_calls.append((config, input_path, video_name))
        return object()

    monkeypatch.setattr(JobManager, "_ensure_gpu_memory_for_job", no_gpu_guard)
    monkeypatch.setattr(JobManager, "_run_whisper_process", fake_run_process)
    monkeypatch.setattr("app.pipeline.whisper.runtime.launch_whisper_process", fake_launch)

    await manager._run_whisper(
        created.id,
        "/tmp/input.mp4",
        {
            "model": "chickenrice-zh",
            "whisper_task": "translate",
            "vad_backend": "energy",
        },
        asyncio.Event(),
    )

    assert len(launch_calls) == 1
    assert launch_calls[0][1] == "/tmp/input.mp4"
    assert launch_calls[0][2] == "input"
    async with job_db() as session:
        row = await session.get(Job, created.id)
        assert row is not None
        assert row.status == "completed"
        assert row.output_path == str(tmp_path / "output.zh.srt")


@pytest.mark.asyncio
async def test_translate_job_runs_through_worker_process(job_db, monkeypatch, tmp_path):
    manager = JobManager()
    created = await manager.create_job(_job_data(), job_type="translate-srt", enqueue_now=False)
    srt_path = tmp_path / "source.srt"
    srt_path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n",
        encoding="utf-8",
    )
    launch_calls = []

    async def fake_run_process(*args, **kwargs):
        return str(tmp_path / "source.zh.srt"), None, False

    def fake_launch(path, target_lang, **kwargs):
        launch_calls.append((path, target_lang, kwargs))
        return object()

    monkeypatch.setattr(JobManager, "_run_translation_process", fake_run_process)
    monkeypatch.setattr("app.pipeline.whisper.runtime.launch_translation_process", fake_launch)

    await manager._run_translate_srt(
        created.id,
        str(srt_path),
        {
            "srt_path": str(srt_path),
            "target_lang": "zh",
            "translate_model": "gpt-4o-mini",
            "translate_base_url": "https://api.openai.com/v1",
            "translate_api_key": None,
            "translate_style": "adult_explicit",
        },
        asyncio.Event(),
    )

    assert len(launch_calls) == 1
    assert launch_calls[0][0] == str(srt_path)
    assert launch_calls[0][1] == "zh"
    async with job_db() as session:
        row = await session.get(Job, created.id)
        assert row is not None
        assert row.status == "completed"
        assert row.output_path == str(tmp_path / "source.zh.srt")
