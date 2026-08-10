# Source Generated with Decompyle++
# File: jobs.pyc (Python 3.13)

from fastapi import APIRouter, HTTPException
from typing import Optional
from app.core.models import JobCreate, JobResponse, JobListResponse
from app.tasks.manager import job_manager
# WARNING: Decompyle incomplete
