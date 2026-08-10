# Source Generated with Decompyle++
# File: runtime.pyc (Python 3.13)

__doc__ = 'Shared runtime helpers for cooperative Whisper cancellation.'
from __future__ import annotations
import asyncio
import multiprocessing
import subprocess
import time
from dataclasses import dataclass
from typing import Any
from typing import Callable, Optional
import httpx
from types import WhisperCancellationRequested
TRANSLATE_PROGRESS_PHASE_ORDER = ('load_subtitle', 'segment_text', 'translate', 'merge_output', 'write_output')
# WARNING: Decompyle incomplete
