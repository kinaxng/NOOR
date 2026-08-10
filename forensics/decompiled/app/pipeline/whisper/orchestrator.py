# Source Generated with Decompyle++
# File: orchestrator.pyc (Python 3.13)

__doc__ = 'Whisper 处理管线编排器'
import asyncio
import logging
import os
import re
import uuid
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
import subprocess
from types import WhisperConfig, WhisperTask, TranscriptionResult, PipelineMode, WhisperModel, VADMethod, WhisperCancellationRequested
from engine import AudioExtractor, AnimeWhisperProcessor, FasterWhisperProcessor, KotobaWhisperProcessor, ReazonNemoProcessor, generate_srt
from enhancer import AudioEnhancer
from merge import MergeEngine
from japanese_post import JapanesePostProcessor, RecommendedSubtitlePostProcessor
from scene_detector import AudioSceneDetector
from runtime import raise_if_cancelled
from preprocess import AudioPreprocessError, preprocess_audio
from decoupled import AnimeQwen3ChainProcessor, qwen3_aligner_available
from app.api.settings_whisper_models import resolve_model_cache_candidates
logger = None(__name__)
PIPELINE_ENHANCERS: dict[(PipelineMode, list[str])] = {
    PipelineMode.SINGLE: [
        'ffmpeg-dsp'],
    PipelineMode.REAZON: [
        'ffmpeg-dsp'],
    PipelineMode.QWEN: [
        'demucs'],
    PipelineMode.TRANSFORMERS: [
        'ffmpeg-dsp',
        'demucs'],
    PipelineMode.BALANCED: [
        'ffmpeg-dsp',
        'clearvoice'],
    PipelineMode.FASTER: [
        'ffmpeg-dsp'],
    PipelineMode.ANIME: [
        'ffmpeg-dsp',
        'clearvoice'] }
# WARNING: Decompyle incomplete
