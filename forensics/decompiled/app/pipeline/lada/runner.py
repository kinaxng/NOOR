# Source Generated with Decompyle++
# File: runner.pyc (Python 3.13)

import asyncio
import concurrent.futures as concurrent
import os
import re
import signal
import subprocess
import threading
from app.core.config import get_settings
from app.tasks.job_phases import get_phase_label
default_settings = None()
LADA_PROGRESS_PHASE_ORDER = ('prepare', 'detect', 'restore', 'encode', 'finalize')
# WARNING: Decompyle incomplete
