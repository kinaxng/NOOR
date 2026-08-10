# Source Generated with Decompyle++
# File: local_library.pyc (Python 3.13)

__doc__ = '\nLocal Subtitle Library Search — searches configured subtitle library paths.\n\nConfiguration is env-backed through NOOR_ENV_FILE.\nIndex is stored in data/subtitle_index.db.\n'
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.settings_helpers import read_env_file, set_env_values
# WARNING: Decompyle incomplete
