from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import events, jobs
from app.core.models import JobResponse


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(jobs.router)
    app.include_router(events.router)
    return app


def _job(status: str = "queued") -> JobResponse:
    return JobResponse(
        id="job-1",
        emby_item_id="item-1",
        emby_item_name="示例作品",
        input_path="/tmp/source.mp4",
        output_path=None,
        status=status,
        progress=0,
        created_at="2026-08-23T00:00:00Z",
    )


class _JobsManager:
    async def get_all_jobs(self, status=None):
        return [_job(status or "queued")]

    async def get_job(self, job_id):
        return _job()

    async def delete_job(self, job_id):
        return True

    async def cancel_job(self, job_id):
        return {"id": job_id, "status": "cancelled"}

    async def cleanup_orphaned_jobs(self):
        return 1

    async def enqueue(self, job_data, job_type="lada"):
        return _job("queued")


def test_jobs_api_contract(monkeypatch):
    manager = _JobsManager()
    monkeypatch.setattr(jobs, "job_manager", manager)

    async def no_sync(*args, **kwargs):
        return None

    monkeypatch.setattr(jobs.runtime, "sync_external_tasks", no_sync)
    monkeypatch.setattr(jobs.runtime, "is_external_task_cancelable", lambda job: True)
    client = TestClient(_app())

    listed = client.get("/api/jobs")
    assert listed.status_code == 200
    listed_json = listed.json()
    assert listed_json["total"] == 1
    assert listed_json["jobs"][0]["id"] == "job-1"
    assert listed_json["jobs"][0]["status"] == "queued"

    detail = client.get("/api/jobs/job-1")
    assert detail.status_code == 200
    assert detail.json()["id"] == "job-1"

    cancelled = client.post("/api/jobs/job-1/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json() == {"success": True}

    deleted = client.delete("/api/jobs/job-1")
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}

    cleaned = client.post("/api/jobs/cleanup")
    assert cleaned.status_code == 200
    assert cleaned.json() == 1

    created = client.post("/api/jobs", json={
        "emby_item_id": "item-1",
        "emby_item_name": "示例作品",
        "input_path": "/tmp/source.mp4",
        "job_type": "facefusion_restore",
    })
    assert created.status_code == 200
    assert created.json()["id"] == "job-1"

    unsupported = client.post("/api/jobs", json={
        "emby_item_id": "item-2",
        "emby_item_name": "不支持的任务",
        "input_path": "/tmp/source.mp4",
        "job_type": "whisper",
    })
    assert unsupported.status_code == 400
    assert unsupported.json()["detail"] == "Unsupported job type"


class _TerminalQueue:
    async def get(self):
        return {
            "type": "completed",
            "job_id": "job-1",
            "success": True,
            "progress": 100,
            "phase_key": "write_output",
            "phase_group": "whisper",
            "phase_label": "写出字幕",
            "phase_progress": 100,
            "detail": "字幕已保存",
        }


class _EventsManager:
    async def get_job(self, job_id):
        return {"id": job_id}

    def get_event_queue(self, job_id):
        return _TerminalQueue()

    async def remove_event_queue(self, job_id):
        return None


def test_job_events_emits_connected_and_terminal_done(monkeypatch):
    monkeypatch.setattr(events, "job_manager", _EventsManager())

    with TestClient(_app()).stream("GET", "/api/jobs/job-1/events") as response:
        lines = list(response.iter_lines())

    joined = "\n".join(lines)
    assert "event: connected" in joined
    assert "event: done" in joined
    data_lines = [line.split(":", 1)[1].strip() for line in lines if line.startswith("data:")]
    done_payload = json.loads(data_lines[-1])
    assert done_payload["type"] == "completed"
    assert done_payload["success"] is True
    assert done_payload["progress"] == 100
