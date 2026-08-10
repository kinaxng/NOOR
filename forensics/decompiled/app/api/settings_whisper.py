# Source Generated with Decompyle++
# File: settings_whisper.pyc (Python 3.13)

from __future__ import annotations
import json
from typing import Any, Callable
from app.pipeline.whisper.strategy import apply_whisper_strategy
TRANSFORMERS_MODEL_KEYS = {
    'anime-whisper': 'anime_whisper',
    'kotoba-whisper-v2.2': 'kotoba-whisper-v2.2' }
SPECIAL_MODEL_KEYS = {
    'reazonspeech-nemo-v2': 'reazon_nemo' }
DEFAULT_CUSTOM_PIPELINE_CONFIG = {
    'model': 'large-v3',
    'vad_method': 'semantic',
    'scene_detector': 'semantic',
    'enhancers': [],
    'segmenter': 'silero-v6.2',
    'timestamp_mode': 'aligner_interpolation',
    'aligner_backend': 'qwen3',
    'framer_backend': 'vad-grouped' }
DEFAULT_AUDIO_PREPROCESS_MODE = 'none'
DEFAULT_AUDIO_PREPROCESS_MODEL = 'vocal_balanced'
# WARNING: Decompyle incomplete
