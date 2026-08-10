# Source Generated with Decompyle++
# File: config.pyc (Python 3.13)

import os
from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
ENV_FILE_PATH = os.environ.get('NOOR_ENV_FILE'(str, None(PROJECT_ROOT / '.env')))
WHISPER_MODEL_DIR = None() / '.cache' / 'huggingface'
DEFAULT_LADA_MODEL_WEIGHTS_DIR = '/volume1/models/lada_model_weights'
DEFAULT_AUDIO_SEPARATOR_MODEL_DIR = '/volume1/models/audio-separator'
DEFAULT_REAZON_MODEL_DIR = '/volume1/models/reazon'
# WARNING: Decompyle incomplete
