# Source Generated with Decompyle++
# File: anime_qwen3_chain.pyc (Python 3.13)

from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional
import re
from cleaners import AnimeWhisperCleaner, Qwen3TextCleaner
from framers import apply_framer_backend
from hardening import harden_transcription_result
from qwen3 import Qwen3ForcedAligner, Qwen3TextGenerator, qwen3_aligner_available, split_aligned_words_into_segments
from app.pipeline.whisper.engine import _iter_hf_repo_paths
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult, WhisperConfig
# WARNING: Decompyle incomplete
