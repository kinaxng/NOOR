# Source Generated with Decompyle++
# File: whisper.pyc (Python 3.13)

__doc__ = 'Whisper 字幕生成 API - 集成到统一任务系统'
import asyncio
import os
import re
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Optional
from app.core.config import get_settings
from app.tasks.manager import job_manager
from app.api.system import SystemLogManager
from app.pipeline.whisper.strategy import apply_whisper_strategy, normalize_whisper_strategy
# WARNING: Decompyle incomplete
