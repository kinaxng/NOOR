from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class WhisperCancellationRequested(Exception):
    pass


class WhisperModel(str, Enum):
    CHICKENRICE_ZH = "chickenrice-zh"
    ANIME = "anime-whisper"
    LARGE_V3 = "large-v3"


class PipelineMode(str, Enum):
    FASTER = "faster"
    ANIME = "anime"


class Sensitivity(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


@dataclass
class WhisperConfig:
    strategy: str = "chickenrice"
    executor_key: str = "chickenrice"
    subtitle_profile: str = "standard"
    model_backend: str = "chickenrice-zh"
    runtime_tier: str = "gpu_standard"
    whisper_task: str = "translate"
    vad_backend: str = "energy"
    chunker: str = "smart_vad_chunk"
    target_chunk_duration_s: float = 30.0
    max_chunk_duration_s: float = 30.0
    segment_merge_max_gap_ms: int = 2000
    segment_merge_max_duration_ms: int = 20000
    timing_refiner: str = "none"
    model: WhisperModel = WhisperModel.CHICKENRICE_ZH
    device: str = "cuda"
    compute_type: str = "float16"
    pipeline_mode: PipelineMode = PipelineMode.FASTER
    vad_filter: bool = True
    vad_min_silence_ms: int = 1500
    vad_min_speech_ms: int = 100
    language: str = "ja"
    sensitivity: Sensitivity = Sensitivity.BALANCED
    beam_size: int = 2
    best_of: int = 2
    translate_to: Optional[str] = None
    translate_base_url: str = "https://api.openai.com/v1"
    translate_api_key: str = ""
    translate_model: str = "llama3.2"
    translate_style: str = "adult_explicit"
    output_dir: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, WhisperModel):
            self.model = WhisperModel(str(self.model))
        if not isinstance(self.pipeline_mode, PipelineMode):
            self.pipeline_mode = PipelineMode(str(self.pipeline_mode))
        if not isinstance(self.sensitivity, Sensitivity):
            self.sensitivity = Sensitivity(str(self.sensitivity))


@dataclass
class SubtitleSegment:
    index: int
    start_time: float
    end_time: float
    text: str
    words: list = field(default_factory=list)


@dataclass
class TranscriptionResult:
    segments: list[SubtitleSegment]
    language: str
    duration: float
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class WhisperTask:
    id: str
    video_path: str
    config: WhisperConfig
    status: str = "pending"
    progress: float = 0.0
    current_pass: str = ""
    log_lines: list[str] = field(default_factory=list)
    result: Optional[TranscriptionResult] = None
    error: Optional[str] = None
