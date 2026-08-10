# Source Generated with Decompyle++
# File: settings_whisper_runtime.pyc (Python 3.13)

from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
from app.core.config import DEFAULT_REAZON_NEMO_MODEL_PATH, get_settings
FASTER_WHISPER_MODELS = [
    ('tiny', 'Systran--faster-whisper-tiny'),
    ('base', 'Systran--faster-whisper-base'),
    ('small', 'Systran--faster-whisper-small'),
    ('medium', 'Systran--faster-whisper-medium'),
    ('large-v3', 'Systran--faster-whisper-large-v3'),
    ('large-v3-turbo', 'Systran--faster-whisper-large-v3-turbo')]
TRANSFORMERS_MODELS = [
    ('anime_whisper', 'litagin/anime-whisper', '~3GB'),
    ('kotoba-whisper-v2.2', 'kotoba-tech/kotoba-whisper-v2.2', '~3GB')]
OPTIONAL_MODULES = [
    ('soundfile', 'soundfile'),
    ('stable_whisper', 'stable_whisper'),
    ('qwen_asr', 'qwen_asr'),
    ('audio_separator', 'audio_separator'),
    ('pydub', 'pydub'),
    ('onnx', 'onnx')]
# WARNING: Decompyle incomplete
