"""Task queue API router reconstructed from preserved bytecode."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.models import JobCreate, JobListResponse, JobResponse
from app.plugins.runtime import runtime
from app.tasks.manager import job_manager


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _sync_external_jobs(job_id: str | None = None) -> None:
    try:
        await runtime.sync_external_tasks(job_id=job_id)
    except Exception:
        return


@router.post("", response_model=JobResponse)
async def create_job(job_data: JobCreate):
    job_type = job_data.job_type or "lada"
    if job_type not in {"lada", "lada_restore", "facefusion_restore"}:
        raise HTTPException(status_code=400, detail="Unsupported job type")
    return await job_manager.enqueue(job_data, job_type=job_type)


@router.get("", response_model=JobListResponse)
async def list_jobs(status: Optional[str] = None):
    await _sync_external_jobs()
    jobs = await job_manager.get_all_jobs(status=status)
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    await _sync_external_jobs(job_id=job_id)
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not await job_manager.delete_job(job_id):
        raise HTTPException(status_code=400, detail="Job cannot be deleted")
    return {"success": True}


@router.get("/{job_id}/logs")
async def get_job_logs(job_id: str):
    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "logs": await job_manager.get_logs(job_id)}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    await _sync_external_jobs(job_id=job_id)
    job = await job_manager.get_job(job_id)
    if job and not runtime.is_external_task_cancelable(job):
        raise HTTPException(status_code=400, detail="External task cannot be cancelled from NOOR")
    if not await job_manager.cancel_job(job_id):
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    return {"success": True}


@router.get("/{job_id}/download")
async def download_output(job_id: str):
    from fastapi.responses import FileResponse
    import os

    job = await job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.output_path:
        raise HTTPException(status_code=400, detail="Output not available")
    output_path = job.output_path
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=output_path, filename=os.path.basename(output_path), media_type="video/mp4")


@router.post("/cleanup")
async def cleanup_jobs():
    return await job_manager.cleanup_orphaned_jobs()
