# Source Generated with Decompyle++
# File: events.pyc (Python 3.13)

import asyncio
import json
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from app.tasks.manager import job_manager
# WARNING: Decompyle incomplete
