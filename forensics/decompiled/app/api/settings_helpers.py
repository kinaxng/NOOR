# Source Generated with Decompyle++
# File: settings_helpers.pyc (Python 3.13)

from __future__ import annotations
import importlib.util as importlib
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from app.core.config import DEFAULT_LADA_MODEL_WEIGHTS_DIR, PROJECT_ROOT, get_settings
logger = None(__name__)
_version_cache: 'dict' = { }
_version_cache_lock = None()
_VERSION_CACHE_TTL = 3600
LADA_MODEL_WEIGHTS_ENV = 'LADA_MODEL_WEIGHTS_DIR'
ENV_FILE = os.environ.get('NOOR_ENV_FILE'(str, None(PROJECT_ROOT / '.env')))
WHISPER_MODELS = {
    'anime-whisper': {
        'name': 'Anime-Whisper',
        'size': '~3GB',
        'type': 'transformers',
        'repo': 'litagin/anime-whisper',
        'description': 'Optimized for anime vocals, Japanese' },
    'kotoba-whisper-v2.2': {
        'name': 'Kotoba Whisper v2.2',
        'size': '~3GB',
        'type': 'transformers',
        'repo': 'kotoba-tech/kotoba-whisper-v2.2',
        'description': 'Japanese-specific, high accuracy, word-level timestamps, public (no gated)' },
    'reazonspeech-nemo-v2': {
        'name': 'ReazonSpeech NeMo v2',
        'size': '~2.4GB',
        'type': 'reazon-nemo',
        'description': 'Reazon / NeMo archive, reserved for upcoming runtime integration' },
    'tiny': {
        'name': 'Tiny',
        'size': '~75MB',
        'type': 'faster-whisper' },
    'base': {
        'name': 'Base',
        'size': '~140MB',
        'type': 'faster-whisper' },
    'small': {
        'name': 'Small',
        'size': '~465MB',
        'type': 'faster-whisper' },
    'medium': {
        'name': 'Medium',
        'size': '~1.5GB',
        'type': 'faster-whisper' },
    'large-v3': {
        'name': 'Large V3',
        'size': '~3GB',
        'type': 'faster-whisper' },
    'large-v3-turbo': {
        'name': 'Large V3 Turbo',
        'size': '~1.8GB',
        'type': 'faster-whisper' } }
# WARNING: Decompyle incomplete
