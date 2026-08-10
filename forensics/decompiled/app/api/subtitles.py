# Source Generated with Decompyle++
# File: subtitles.pyc (Python 3.13)

import os
import re
import shutil
import asyncio
import logging
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from app.core.config import get_settings
from app.api.local_library import search_local_library
# WARNING: Decompyle incomplete
