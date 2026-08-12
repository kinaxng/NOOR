from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.runtime_cleanup import (
    DEFAULT_MIN_AGE_HOURS,
    run_runtime_cleanup,
    runtime_cleanup_status,
)


router = APIRouter(prefix='/api/runtime-cleanup', tags=['runtime-cleanup'])


class RuntimeCleanupPayload(BaseModel):
    min_age_hours: int = Field(DEFAULT_MIN_AGE_HOURS, ge=0, le=168)


@router.get('/status')
async def get_runtime_cleanup_status(min_age_hours: int =  DEFAULT_MIN_AGE_HOURS):
    return runtime_cleanup_status(min_age_hours=max(0, min(168, int(min_age_hours))))


@router.post('/run')
async def run_runtime_cleanup_now(payload: RuntimeCleanupPayload | None = None):
    min_age_hours = payload.min_age_hours if payload is not None else DEFAULT_MIN_AGE_HOURS
    return run_runtime_cleanup(min_age_hours=min_age_hours)
