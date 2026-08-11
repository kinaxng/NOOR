"""Whisper 处理管线编排器"""
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

from .types import (
    WhisperConfig,
    WhisperTask,
    TranscriptionResult,
    PipelineMode,
    WhisperModel,
    VADMethod,
    WhisperCancellationRequested,
)
from .engine import (
    AudioExtractor, AnimeWhisperProcessor, FasterWhisperProcessor,
    KotobaWhisperProcessor, ReazonNemoProcessor, generate_srt
)
from .enhancer import AudioEnhancer
from .merge import MergeEngine
from .japanese_post import JapanesePostProcessor, RecommendedSubtitlePostProcessor
from .scene_detector import AudioSceneDetector, WhisperVadOnnxSceneDetector
from .runtime import raise_if_cancelled
from .timing_refiner import SubtimerVadTimingRefiner
from .decoupled import AnimeQwen3ChainProcessor, qwen3_aligner_available
from app.api.settings_whisper_models import resolve_model_cache_candidates

logger = logging.getLogger(__name__)
WHISPER_VAD_ONNX_REPO_ID = "TransWithAI/Whisper-Vad-EncDec-ASMR-onnx"


# 各预设 pipeline 的推荐增强器组合（仅用于 balanced/faster 等旧架构 pipeline）
# anime / transformers / qwen(large-v3 baseline) / custom 走新架构，enhancers 从 self.config.enhancers 获取
# 设计原则：
#   - ffmpeg-dsp: 仅 loudnorm 响度标准化（CPU快）
#   - clearvoice: WebRTC VAD 静音移除 + 轻降噪（CPU）
#   - silero-vad: Silero VAD 静音检测（不增强）
#   - demucs: GPU 神经人声分离（最强）
PIPELINE_ENHANCERS: dict[PipelineMode, list[str]] = {
    PipelineMode.ANIME:        ['ffmpeg-dsp', 'clearvoice'],    # 响度标准化 + 人声提取
    PipelineMode.FASTER:        ['ffmpeg-dsp'],                   # 清洁音频，仅响度标准化
    PipelineMode.BALANCED:     ['ffmpeg-dsp', 'clearvoice'],    # 嘈杂对话均衡
    PipelineMode.TRANSFORMERS: ['ffmpeg-dsp', 'demucs'],        # 响度标准化 + GPU 人声分离
    PipelineMode.QWEN:         ['demucs'],                      # GPU 人声分离，对齐优化
    PipelineMode.REAZON:       ['ffmpeg-dsp'],                   # Reazon / NeMo 实验路径
    PipelineMode.SINGLE:        ['ffmpeg-dsp'],                   # 仅响度标准化
}


@dataclass
class _PreparedSegment:
    index: int
    audio_path: str
    start: float
    end: float
    duration: float
    pass1_result: Optional[TranscriptionResult] = None
    pass2_result: Optional[TranscriptionResult] = None



class WhisperPipeline:
    """Whisper 字幕生成管线"""

    def __init__(
        self,
        config: WhisperConfig,
        progress_callback: Optional[Callable] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback
        self._log_lines = []
        # 跨段落缓存 processor 实例，避免重复加载模型
        self._anime_processor: Optional[AnimeWhisperProcessor] = None
        self._faster_processor: Optional[FasterWhisperProcessor] = None
        self._balanced_processor: Optional[FasterWhisperProcessor] = None
        self._kotoba_processor: Optional[KotobaWhisperProcessor] = None
        self._qwen_processor: Optional[FasterWhisperProcessor] = None
        self._reazon_processor: Optional[ReazonNemoProcessor] = None
        self._anime_qwen3_chain: Optional[AnimeQwen3ChainProcessor] = None

    def log(self, msg: str, progress: int = None):
        """记录日志"""
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)
            except Exception as e:
                logger.warning("Progress callback error: %s", e)

    def _raise_if_cancelled(self):
        raise_if_cancelled(self.cancel_callback)

    def _get_output_dir(self) -> Path:
        """获取输出目录"""
        if self.config.output_dir:
            return Path(self.config.output_dir)
        return Path(tempfile.gettempdir()) / "whisper_jav"

    def _get_enhancers(self) -> list[str]:
        """根据 pipeline 模式获取增强器组合"""
        if getattr(self.config, "executor_key", "advanced") in {"recommended", "baseline"}:
            # 产品默认链路明确声明 speech_enhancer=none。
            # 不要再因为 anime preset 的旧默认表而隐式注入 loudnorm / clearvoice。
            return []

        mode = self.config.pipeline_mode

        # Ensemble 模式：用 pass1 的增强器组合
        if mode == PipelineMode.ENSEMBLE and self.config.pass1_pipeline:
            pass1_mode = PipelineMode(self.config.pass1_pipeline.value)
            return PIPELINE_ENHANCERS.get(pass1_mode, [])

        return PIPELINE_ENHANCERS.get(mode, [])

    @staticmethod
    def _pipeline_display_name(mode: PipelineMode) -> str:
        if mode == PipelineMode.QWEN:
            return "large-v3-baseline"
        return mode.value

    _PASS2_GATING_PUNCT_RE = re.compile(r"[。、「」『』、,，.!！?？…~〜・\-\s]")
    _PASS2_GATING_KANJI_RE = re.compile(r"[一-龯々]")
    _PASS2_GATING_JA_RE = re.compile(r"[ぁ-んァ-ヶー一-龯々]")
    _STEPDOWN_SENTENCE_RE = re.compile(r"[。！？?!]")

    @classmethod
    def _normalize_pass_text(cls, text: str) -> str:
        return cls._PASS2_GATING_PUNCT_RE.sub("", text or "").strip()

    @classmethod
    def _is_likely_noise_only_text(cls, text: str) -> bool:
        normalized = cls._normalize_pass_text(text)
        if not normalized:
            return True

        if not cls._PASS2_GATING_JA_RE.search(normalized):
            return False

        unique_ratio = len(set(normalized)) / max(len(normalized), 1)
        repeated_voice_like = unique_ratio <= 0.35 and len(normalized) >= 6
        moan_tokens = ("あ", "ぁ", "ん", "っ", "は", "う", "え", "お", "ぅ", "ふ", "む", "ら", "ちゅ", "ぷ", "る")
        token_ratio = sum(normalized.count(token) * len(token) for token in moan_tokens) / max(len(normalized), 1)

        return token_ratio >= 0.72 or repeated_voice_like

    def _should_run_pass2(
        self,
        seg_duration: float,
        pass1_result: TranscriptionResult,
        pass2_mode: PipelineMode,
    ) -> tuple[bool, str]:
        """Low-risk gating to avoid obviously low-value Pass2 work.

        Current scope intentionally narrow:
        - only for recommended executor
        - only for anime -> large-v3 baseline style second pass
        - only skip when pass1 already produced a short, non-noise result
        """
        if getattr(self.config, "executor_key", "advanced") != "recommended":
            return True, "advanced-mode"

        if pass2_mode != PipelineMode.QWEN:
            return True, "pass2-not-large-v3-baseline"

        if not pass1_result.segments:
            return True, "pass1-empty"

        combined_text = "".join(seg.text for seg in pass1_result.segments)
        normalized = self._normalize_pass_text(combined_text)
        if len(normalized) < 4:
            return True, "pass1-too-short"

        if self._is_likely_noise_only_text(combined_text):
            return True, "pass1-noise-like"

        has_kanji = bool(self._PASS2_GATING_KANJI_RE.search(normalized))
        if seg_duration <= 4.5 and len(pass1_result.segments) <= 2:
            return False, "short-segment-pass1-sufficient"

        if seg_duration <= 7.0 and len(pass1_result.segments) == 1 and has_kanji and len(normalized) >= 10:
            return False, "compact-narration-pass1-sufficient"

        if seg_duration <= 10.0 and len(pass1_result.segments) <= 2 and len(normalized) >= 8:
            return False, "short-scene-pass1-sufficient"

        if seg_duration <= 12.0 and len(pass1_result.segments) == 1 and has_kanji and len(normalized) >= 14:
            return False, "mid-scene-pass1-sufficient"

        return True, "needs-pass2"

    def _get_model_cache_path(self, model_id: str) -> Path:
        """Get the HuggingFace cache path for a model."""
        from app.core.config import get_settings
        settings = get_settings()
        whisper_model_dir = settings.whisper_model_dir or "/volume1/models"
        return resolve_model_cache_candidates(whisper_model_dir, model_id)[0]

    def _check_model_cached(self, model_id: str) -> bool:
        """Check if a model is cached. Supports both snapshot_download style
        (direct under whisper_model_dir) and legacy huggingface hub style."""
        from app.core.config import get_settings
        settings = get_settings()
        whisper_model_dir = settings.whisper_model_dir or "/volume1/models"
        for candidate in resolve_model_cache_candidates(whisper_model_dir, model_id):
            if candidate.exists() and any(candidate.iterdir()):
                return True
        return False

    def _whisper_vad_onnx_cache_dir(self) -> Path:
        whisper_model_dir, _, _ = _get_whisper_runtime_paths()
        candidates = resolve_model_cache_candidates(whisper_model_dir, WHISPER_VAD_ONNX_REPO_ID)
        for candidate in candidates:
            if candidate.exists() and any(candidate.rglob("model.onnx")):
                return candidate
        return candidates[0]

    def _reazon_model_display_path(self) -> str:
        from app.core.config import DEFAULT_REAZON_NEMO_MODEL_PATH, get_settings
        settings = get_settings()
        return getattr(settings, "reazon_nemo_model_path", DEFAULT_REAZON_NEMO_MODEL_PATH) or DEFAULT_REAZON_NEMO_MODEL_PATH

    def _check_reazon_nemo_cached(self) -> bool:
        model_path = Path(self._reazon_model_display_path())
        return model_path.exists() and model_path.is_file()

    @classmethod
    def _evaluate_recommended_stepdown(
        cls,
        seg_duration: float,
        result: TranscriptionResult,
    ) -> tuple[bool, str]:
        if not result.segments:
            return False, "empty-result"
        chain_state = str(result.metadata.get("anime_qwen3_chain") or "")
        normalized = cls._normalize_pass_text("".join(seg.text for seg in result.segments))
        if len(normalized) < 12:
            return False, "text-too-short"
        if chain_state == "aligner_empty":
            return (seg_duration >= 14.0, "aligner-empty" if seg_duration >= 14.0 else "aligner-empty-too-short")

        if result.metadata.get("recommended_qwen_retry") and seg_duration < 28.0:
            return False, "recent-qwen-retry"

        if len(result.segments) != 1 or seg_duration < 20.0:
            return False, "not-collapsed-long-single"

        text = (result.segments[0].text or "").strip()

        sentence_breaks = len(cls._STEPDOWN_SENTENCE_RE.findall(text))
        if sentence_breaks >= 2:
            return True, "multi-sentence-collapsed"

        if bool(cls._PASS2_GATING_KANJI_RE.search(normalized)) and len(normalized) >= 36:
            return True, "long-kanji-dense-single"
        return False, "single-segment-accepted"

    @classmethod
    def _should_retry_recommended_stepdown(
        cls,
        seg_duration: float,
        result: TranscriptionResult,
    ) -> bool:
        return cls._evaluate_recommended_stepdown(seg_duration, result)[0]

    @staticmethod
    def _build_stepdown_windows(duration: float, *, target_window: float = 12.0, min_window: float = 6.0) -> list[tuple[float, float]]:
        if duration <= target_window * 1.35:
            mid = duration / 2
            if mid < min_window:
                return [(0.0, duration)]
            return [(0.0, mid), (mid, duration)]

        window_count = max(2, int((duration + target_window - 1) // target_window))
        window = duration / window_count
        if window < min_window:
            return [(0.0, duration)]

        windows: list[tuple[float, float]] = []
        cursor = 0.0
        for idx in range(window_count):
            end = duration if idx == window_count - 1 else min(duration, cursor + window)
            windows.append((cursor, end))
            cursor = end
        return windows

    @staticmethod
    def _collect_recommended_segment_diagnostics(results: list[TranscriptionResult]) -> dict:
        if not results:
            return {
                "segment_count": 0,
                "aligned_segments": 0,
                "large_v3_retry_segments": 0,
                "qwen_retry_segments": 0,
                "stepdown_segments": 0,
                "aligner_empty_segments": 0,
                "hardened_segments": 0,
                "stepdown_window_total": 0,
                "segments": [],
            }

        segment_rows: list[dict] = []
        aligned_segments = 0
        large_v3_retry_segments = 0
        qwen_retry_segments = 0
        stepdown_segments = 0
        aligner_empty_segments = 0
        hardened_segments = 0
        stepdown_window_total = 0

        for idx, result in enumerate(results, start=1):
            metadata = result.metadata or {}
            chain_state = str(metadata.get("anime_qwen3_chain") or "")
            aligned = chain_state == "qwen3_forced_aligner"
            large_v3_retry = bool(metadata.get("recommended_large_v3_retry"))
            qwen_retry = bool(metadata.get("recommended_qwen_retry") or metadata.get("anime_qwen3_retry"))
            stepdown = bool(metadata.get("recommended_stepdown_retry"))
            aligner_empty = chain_state == "aligner_empty"
            hardened = bool(metadata.get("hardening_applied"))
            window_count = int(metadata.get("recommended_stepdown_window_count") or 0)
            qwen_reason = str(metadata.get("recommended_qwen_retry_reason") or "")
            stepdown_reason = str(metadata.get("recommended_stepdown_reason") or "")

            aligned_segments += int(aligned)
            large_v3_retry_segments += int(large_v3_retry)
            qwen_retry_segments += int(qwen_retry)
            stepdown_segments += int(stepdown)
            aligner_empty_segments += int(aligner_empty)
            hardened_segments += int(hardened)
            stepdown_window_total += window_count

            segment_rows.append({
                "index": idx,
                "source": result.source,
                "subtitle_count": len(result.segments),
                "chain_state": chain_state or metadata.get("chain_stage") or "",
                "large_v3_retry": large_v3_retry,
                "qwen_retry": qwen_retry,
                "large_v3_retry_reason": str(metadata.get("recommended_large_v3_retry_reason") or ""),
                "qwen_retry_reason": qwen_reason,
                "stepdown": stepdown,
                "stepdown_reason": stepdown_reason,
                "stepdown_window_count": window_count,
                "aligner_empty": aligner_empty,
                "hardened": hardened,
            })

        return {
            "segment_count": len(results),
            "aligned_segments": aligned_segments,
            "large_v3_retry_segments": large_v3_retry_segments,
            "qwen_retry_segments": qwen_retry_segments,
            "stepdown_segments": stepdown_segments,
            "aligner_empty_segments": aligner_empty_segments,
            "hardened_segments": hardened_segments,
            "stepdown_window_total": stepdown_window_total,
            "segments": segment_rows,
        }

    def _validate_required_models(self):
        """Pre-flight check: verify all required models are downloaded.

        Raises RuntimeError with a clear message if any model is missing.
        """
        from app.core.config import get_settings
        settings = get_settings()
        whisper_model_dir = settings.whisper_model_dir or "/volume1/models"

        missing = []

        if self.config.pipeline_mode == PipelineMode.ENSEMBLE:
            # Resolve actual model from pipeline mode (NOT from pass1_model.value
            # which holds the default, not the user-selected override)
            pass1_mode = PipelineMode(self.config.pass1_pipeline.value) if self.config.pass1_pipeline else PipelineMode.ANIME
            pass2_mode = PipelineMode(self.config.pass2_pipeline.value) if self.config.pass2_pipeline else PipelineMode.FASTER

            # pipeline mode → model value → HF repo ID
            pipeline_model_map = {
                PipelineMode.ANIME: "anime-whisper",
                PipelineMode.TRANSFORMERS: "kotoba-whisper-v2.2",
                PipelineMode.FASTER: "tiny",
                PipelineMode.BALANCED: "large-v3",
                PipelineMode.QWEN: "large-v3",
                PipelineMode.REAZON: "reazonspeech-nemo-v2",
                PipelineMode.SINGLE: self.config.model.value,
            }
            repo_map = {
                "anime-whisper": "litagin/anime-whisper",
                "kotoba-whisper-v2.2": "kotoba-tech/kotoba-whisper-v2.2",
                "tiny": "Systran/faster-whisper-tiny",
                "base": "Systran/faster-whisper-base",
                "small": "Systran/faster-whisper-small",
                "medium": "Systran/faster-whisper-medium",
                "large-v3": "Systran/faster-whisper-large-v3",
                "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
            }

            p1_model = pipeline_model_map.get(pass1_mode, "anime-whisper")
            p2_model = pipeline_model_map.get(pass2_mode, "large-v3")
            p1_repo = repo_map.get(p1_model)
            p2_repo = repo_map.get(p2_model)

            if p1_model == "reazonspeech-nemo-v2" and not self._check_reazon_nemo_cached():
                missing.append(f"[reazonspeech-nemo-v2] (Pass1，请先准备 {self._reazon_model_display_path()})")
            elif p1_repo and not self._check_model_cached(p1_repo):
                missing.append(f"[{p1_model}] (Pass1，请到 设置 → Whisper → 模型 下载)")
            if p2_model == "reazonspeech-nemo-v2" and not self._check_reazon_nemo_cached():
                missing.append(f"[reazonspeech-nemo-v2] (Pass2，请先准备 {self._reazon_model_display_path()})")
            elif p2_repo and not self._check_model_cached(p2_repo):
                missing.append(f"[{p2_model}] (Pass2，请到 设置 → Whisper → 模型 下载)")
        else:
            # Single pipeline — determine model from pipeline mode
            mode = self.config.pipeline_mode
            if mode == PipelineMode.ANIME:
                repo_id = "litagin/anime-whisper"
            elif mode == PipelineMode.TRANSFORMERS:
                repo_id = "kotoba-tech/kotoba-whisper-v2.2"
            elif mode == PipelineMode.FASTER:
                repo_id = {
                    "chickenrice-zh": "chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2",
                    "large-v3": "Systran/faster-whisper-large-v3",
                    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
                }.get(self.config.model.value)
            elif mode == PipelineMode.BALANCED:
                repo_id = "Systran/faster-whisper-large-v3"
            elif mode == PipelineMode.QWEN:
                repo_id = "Systran/faster-whisper-large-v3"
            elif mode == PipelineMode.REAZON:
                repo_id = None
                if not self._check_reazon_nemo_cached():
                    missing.append(f"[reazonspeech-nemo-v2] (请先准备 {self._reazon_model_display_path()})")
            elif mode == PipelineMode.SINGLE:
                repo_id_map = {
                    "anime-whisper": "litagin/anime-whisper",
                    "kotoba-whisper-v2.2": "kotoba-tech/kotoba-whisper-v2.2",
                }
                repo_id = repo_id_map.get(self.config.model.value)
            else:
                repo_id = None

            if repo_id and not self._check_model_cached(repo_id):
                missing.append(f"[{self.config.model.value}] (请到 设置 → Whisper → 模型 下载)")

        if missing:
            raise RuntimeError(
                f"模型未下载: {', '.join(missing)}。"
                f"请先在 设置 → Whisper → 模型 中下载对应模型，"
                f"然后重试任务。"
            )

    async def process(
        self,
        video_path: str,
        video_name: str = ""
    ) -> tuple[TranscriptionResult, str]:
        """
        处理视频文件生成字幕

        Returns:
            (transcription_result, srt_path)
        """
        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._raise_if_cancelled()

        if not video_name:
            video_name = Path(video_path).stem

        audio_path = output_dir / f"{video_name}_audio.wav"

        # ========== 需要模型验证和场景检测 ==========
        # Pre-flight: verify all required models are downloaded
        self._validate_required_models()
        self._raise_if_cancelled()

        # Phase 1: 音频提取
        self.log("=" * 50)
        self.log("Phase 1: 提取音频")
        self.log("=" * 50)

        try:
            _, duration = AudioExtractor.extract(
                str(video_path),
                str(audio_path),
                sample_rate=16000,
                cancel_callback=self.cancel_callback,
            )
            self.log(f"音频提取完成，时长: {duration:.1f}s", 5)
        except Exception as e:
            self.log(f"音频提取失败: {e}")
            raise

        # Phase 1.5: 语音增强（根据 pipeline 预设组合）
        enhancers = self._get_enhancers()
        if enhancers:
            self.log("=" * 50)
            self.log(f"Phase 1.5: 语音增强 [{', '.join(enhancers)}]")
            self.log("=" * 50)
            try:
                self._raise_if_cancelled()
                enhancer = AudioEnhancer(enhancers, self.progress_callback, self.cancel_callback)
                enhanced_path = output_dir / f"{video_name}_audio_enhanced.wav"
                final_audio_path = enhancer.enhance(str(audio_path), str(enhanced_path), sample_rate=16000)
                # 清理原始提取的音频，保留增强版
                if final_audio_path != str(audio_path):
                    self.log(f"增强音频已生成: {final_audio_path}")
                    audio_path = Path(final_audio_path)
                else:
                    self.log("增强未改变音频（使用原始音频）")
            except Exception as e:
                self.log(f"语音增强失败（跳过）: {e}")

        # Phase: ChickenRice Smart VAD chunking
        all_segments: list[tuple[str, float, float]] = []  # (audio_path, start, end)
        if duration > self.config.target_chunk_duration_s:
            self.log("=" * 50)
            self.log(f"Smart VAD: {self.config.vad_backend}")
            self.log("=" * 50)
            try:
                self._raise_if_cancelled()
                if self.config.vad_backend == "whisper_vad_onnx":
                    detector = WhisperVadOnnxSceneDetector(
                        repo_dir=self._whisper_vad_onnx_cache_dir(),
                        min_segment_duration=max(3.0, min(10.0, self.config.target_chunk_duration_s * 0.35)),
                        max_segment_duration=self.config.max_chunk_duration_s,
                    )
                else:
                    detector = AudioSceneDetector(
                        mode="energy",
                        min_silence_duration=0.1,
                        min_segment_duration=max(3.0, min(10.0, self.config.target_chunk_duration_s * 0.35)),
                        energy_threshold=0.01,
                        max_segment_duration=self.config.max_chunk_duration_s,
                    )
                scenes = detector.detect(str(audio_path))
                self.log(f"Smart VAD 生成 {len(scenes)} 个安全连续块")
                all_segments = [(str(audio_path), scene.start, scene.end) for scene in scenes]
            except Exception as e:
                if self.config.vad_backend == "whisper_vad_onnx":
                    self.log(f"Whisper-VAD ONNX 失败，回退 energy: {e}")
                    detector = AudioSceneDetector(
                        mode="energy",
                        min_silence_duration=0.1,
                        min_segment_duration=max(3.0, min(10.0, self.config.target_chunk_duration_s * 0.35)),
                        energy_threshold=0.01,
                        max_segment_duration=self.config.max_chunk_duration_s,
                    )
                    scenes = detector.detect(str(audio_path))
                    all_segments = [(str(audio_path), scene.start, scene.end) for scene in scenes]
                else:
                    self.log(f"Smart VAD 失败，使用整段音频: {e}")
                    all_segments = [(str(audio_path), 0.0, duration)]
        else:
            all_segments = [(str(audio_path), 0.0, duration)]

        # Phase: 转写
        if (
            getattr(self.config, "executor_key", "advanced") == "recommended"
            and self.config.pipeline_mode == PipelineMode.ENSEMBLE
        ):
            if qwen3_aligner_available():
                all_results = await self._process_anime_qwen3_chain_segments(all_segments)
            else:
                self.log("[Recommended] qwen-asr 未安装，回退到旧推荐链路", 28)
                all_results = await self._process_recommended_phase_based_segments(all_segments)
        else:
            all_results = []
            for idx, (audio_file, seg_start, seg_end) in enumerate(all_segments):
                self._raise_if_cancelled()
                seg_duration = seg_end - seg_start
                seg_weight = 1.0 / len(all_segments)
                seg_start_pct = int(28 + idx * seg_weight * 57)
                seg_end_pct = int(28 + (idx + 1) * seg_weight * 57)
                self.log(
                    f"处理段落 {idx + 1}/{len(all_segments)}: {seg_start:.1f}s - {seg_end:.1f}s ({seg_duration:.1f}s)",
                    seg_start_pct
                )

                if self.config.pipeline_mode == PipelineMode.ENSEMBLE:
                    seg_result = await self._process_ensemble_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.FASTER:
                    seg_result = await self._process_faster_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.BALANCED:
                    seg_result = await self._process_balanced_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.TRANSFORMERS:
                    seg_result = await self._process_transformers_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.ANIME:
                    seg_result = await self._process_anime_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.QWEN:
                    seg_result = await self._process_qwen_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.REAZON:
                    seg_result = await self._process_reazon_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                elif self.config.pipeline_mode == PipelineMode.CUSTOM:
                    seg_result = await self._process_single_segment(
                        audio_file, seg_start, seg_end, idx
                    )
                else:
                    seg_result = await self._process_single_segment(
                        audio_file, seg_start, seg_end, idx
                    )

                self.log(f"段落 {idx + 1} 完成: {len(seg_result.segments)} 片段", seg_end_pct)

                for seg in seg_result.segments:
                    seg.start_time += seg_start
                    seg.end_time += seg_start

                all_results.append(seg_result)

        # 合并所有段落结果
        self._raise_if_cancelled()
        recommended_segment_diagnostics = None
        if getattr(self.config, "executor_key", "advanced") == "recommended":
            recommended_segment_diagnostics = self._collect_recommended_segment_diagnostics(all_results)
            self.log(
                "[Recommended] 诊断: "
                f"对齐 {recommended_segment_diagnostics['aligned_segments']}/{recommended_segment_diagnostics['segment_count']} · "
                f"large-v3 retry {recommended_segment_diagnostics['large_v3_retry_segments']} · "
                f"Qwen fallback {recommended_segment_diagnostics['qwen_retry_segments']} · "
                f"step-down {recommended_segment_diagnostics['stepdown_segments']}",
            )
        if len(all_results) == 1:
            result = all_results[0]
        else:
            result = self._merge_all_results(all_results)
            self.log(f"段落合并完成: {len(result.segments)} 片段", 90)
        if recommended_segment_diagnostics is not None:
            result.metadata = {
                **result.metadata,
                "recommended_segment_diagnostics": recommended_segment_diagnostics,
            }

        # Phase: 日语后处理
        self.log("=" * 50)
        self.log("日语后处理: 断句优化 & 格式整理", 92)
        self.log("=" * 50)
        try:
            self._raise_if_cancelled()
            if getattr(self.config, "executor_key", "advanced") == "recommended":
                post_processor = RecommendedSubtitlePostProcessor()
                self.log("后处理策略: recommended-cleanup")
            else:
                post_processor = JapanesePostProcessor(
                    min_segment_duration=0.8,
                    max_segment_duration=8.0,
                    min_gap_threshold=0.3,
                    merge_below=1.2,
                )
            result = post_processor.process(result)
            if result.metadata.get("recommended_strategy_post_processed"):
                before_count = result.metadata.get("recommended_cleanup_before_segments", len(result.segments))
                after_count = result.metadata.get("recommended_cleanup_after_segments", len(result.segments))
                deduped_count = result.metadata.get("recommended_cleanup_deduped_segments", 0)
                diagnostics = result.metadata.get("recommended_segment_diagnostics") or {}
                cleanup_summary = {
                    "before_segments": before_count,
                    "after_segments": after_count,
                    "deduped_segments": deduped_count,
                    "noise_only_segments": result.metadata.get("recommended_cleanup_noise_only_segments", 0),
                    "trimmed_noise_chars": result.metadata.get("recommended_cleanup_trimmed_noise_chars", 0),
                    "particle_merged_segments": result.metadata.get("recommended_cleanup_particle_merged_segments", 0),
                    "window_echo_segments": result.metadata.get("recommended_cleanup_window_echo_segments", 0),
                }
                result.metadata["recommended_diagnostics"] = {
                    **diagnostics,
                    "cleanup": cleanup_summary,
                }
                self.log(
                    f"recommended-cleanup 统计: {before_count} → {after_count} 片段，去重 {deduped_count} 条"
                )
            self.log(f"后处理完成: {len(result.segments)} 片段", 95)
        except Exception as e:
            self.log(f"后处理失败（跳过）: {e}")

        timing_refiner = str(getattr(self.config, "timing_refiner", "none") or "none").strip().lower()
        if timing_refiner == "subtimer_vad":
            try:
                self._raise_if_cancelled()
                scene_bounds = [(start, end) for _, start, end in all_segments]
                result, changed = SubtimerVadTimingRefiner().refine(result, scene_bounds)
                self.log(f"实验时间轴微调: subtimer-vad 调整 {changed}/{len(result.segments)} 段", 96)
            except Exception as e:
                self.log(f"实验时间轴微调失败（跳过）: {e}")
        elif timing_refiner not in {"", "none"}:
            self.log(f"未知时间轴微调模式，已跳过: {timing_refiner}")

        # Phase: 生成 SRT
        self.log("=" * 50)
        self.log("生成 SRT 文件", 97)
        self.log("=" * 50)

        # 清理视频名用于字幕文件
        self._raise_if_cancelled()
        clean_name = self._clean_video_name(video_name)

        # 生成原始字幕 SRT
        srt_path = output_dir / f"{clean_name}.ja.srt"
        generate_srt(result.segments, str(srt_path))
        self.log(f"原始字幕已保存: {srt_path}", 97)

        # 翻译由 manager 统一调用 translate_srt 任务处理（不在 pipeline 内 inline 翻译）
        self.log(f"SRT 已保存: {srt_path}", 97)

        # 清理临时音频
        try:
            os.remove(audio_path)
        except:
            pass

        return result, str(srt_path)

    async def _process_single(self, audio_path: str, duration: float) -> TranscriptionResult:
        """单遍处理"""
        self._raise_if_cancelled()
        if self.config.model.value == "anime-whisper":
            if self._anime_processor is None:
                self._anime_processor = AnimeWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
            return await asyncio.to_thread(self._anime_processor.process, audio_path, "")
        else:
            if self._faster_processor is None:
                self._faster_processor = FasterWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
            return await asyncio.to_thread(self._faster_processor.process, audio_path, "")

    async def _process_ensemble(
        self,
        audio_path: str,
        duration: float
    ) -> TranscriptionResult:
        """两遍处理 + 合并"""

        # ========== Pass 1: Anime-Whisper ==========
        self._raise_if_cancelled()
        self.log("=" * 50)
        self.log("Pass 1: Anime-Whisper (快速，广覆盖)")
        self.log("=" * 50)

        pass1_config = WhisperConfig(
            model=self.config.pass1_model,
            device=self.config.device,
            language=self.config.language
        )

        try:
            if self._anime_processor is None:
                self._anime_processor = AnimeWhisperProcessor(pass1_config, self.progress_callback, self.cancel_callback)
            pass1_result = await asyncio.to_thread(self._anime_processor.process, audio_path, "")
            self.log(f"Pass 1 完成: {len(pass1_result.segments)} 片段")
        except Exception as e:
            self.log(f"Pass 1 失败: {e}，跳过...")
            pass1_result = TranscriptionResult(
                segments=[],
                language="ja",
                duration=duration,
                source="anime-whisper-failed",
                metadata={"error": str(e)}
            )

        # ========== Pass 2: Faster-Whisper ==========
        self._raise_if_cancelled()
        self.log("=" * 50)
        self.log("Pass 2: Faster-Whisper (高质量)")
        self.log("=" * 50)

        try:
            if self._faster_processor is None:
                self._faster_processor = FasterWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
            pass2_result = await asyncio.to_thread(self._faster_processor.process, audio_path, "")
            self.log(f"Pass 2 完成: {len(pass2_result.segments)} 片段")
        except Exception as e:
            self.log(f"Pass 2 失败: {e}")
            return pass1_result

        # ========== 合并 ==========
        self.log("=" * 50)
        self.log(f"合并策略: {self.config.merge_strategy.value}")
        self.log("=" * 50)

        merge_engine = MergeEngine(self.config.merge_strategy)
        merged_result = merge_engine.merge(pass1_result, pass2_result)

        self.log(f"合并完成: {len(merged_result.segments)} 片段")
        self.log(f"来源: {merged_result.source}")

        return merged_result

    async def _process_single_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """单遍处理（指定音频段落）"""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        # 提取段落音频
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                 offset=seg_start, duration=seg_end - seg_start)
            sf.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_end - seg_start,
                source="single-segment-failed",
                metadata={"error": str(e)}
            )

        try:
            if self.config.model.value == "anime-whisper":
                if self._anime_processor is None:
                    self._anime_processor = AnimeWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
                result = await asyncio.to_thread(self._anime_processor.process, tmp_path, "")
            else:
                if self._faster_processor is None:
                    self._faster_processor = FasterWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
                result = await asyncio.to_thread(self._faster_processor.process, tmp_path, "")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    def _extract_audio_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> tuple[str, float] | tuple[None, None]:
        """Extract audio segment to temp file. Returns (tmp_path, duration) or (None, None) on failure."""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        seg_duration = seg_end - seg_start
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                 offset=seg_start, duration=seg_duration)
            sf.write(tmp_path, y, sr)
            return tmp_path, seg_duration
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {type(e).__name__}: {e}")
            self.log(f"[DEBUG] librosa import check: {dir()[:5]}")
            self.log(f"[DEBUG] audio_file={audio_file}, exists={os.path.exists(audio_file)}")
            self.log(f"[DEBUG] librosa error traceback:\n{tb[:500]}")
            try:
                os.remove(tmp_path)
            except:
                pass
            return None, None

    def _build_pass_config(self, pipeline_mode: PipelineMode) -> WhisperConfig:
        """Build WhisperConfig for a specific pipeline mode."""
        if pipeline_mode == PipelineMode.ANIME:
            config = WhisperConfig(
                model=WhisperModel.ANIME,
                device=self.config.device,
                language=self.config.language,
            )
        elif pipeline_mode == PipelineMode.FASTER:
            config = WhisperConfig(
                model=WhisperModel.TINY,
                device=self.config.device,
                language=self.config.language,
                vad_filter=False,
            )
        elif pipeline_mode == PipelineMode.BALANCED:
            config = WhisperConfig(
                model=WhisperModel.LARGE_V3,
                device=self.config.device,
                language=self.config.language,
                vad_filter=True,
                vad_min_silence_ms=1500,
            )
        elif pipeline_mode == PipelineMode.TRANSFORMERS:
            config = WhisperConfig(
                model=WhisperModel.KOTOBA_V2,
                device=self.config.device,
                language=self.config.language,
            )
        elif pipeline_mode == PipelineMode.QWEN:
            config = WhisperConfig(
                model=WhisperModel.LARGE_V3,
                device=self.config.device,
                language=self.config.language,
            )
        elif pipeline_mode == PipelineMode.REAZON:
            config = WhisperConfig(
                model=WhisperModel.REAZON_NEMO_V2,
                device=self.config.device,
                language=self.config.language,
            )
        elif pipeline_mode == PipelineMode.CUSTOM:
            # Custom pipeline: 使用 self.config 中的 vad_method, enhancers 和模型
            config = WhisperConfig(
                model=self.config.pass1_model,
                device=self.config.device,
                language=self.config.language,
                vad_method=self.config.vad_method,
                vad_filter=self.config.vad_method != VADMethod.NONE,
                enhancers=self.config.enhancers,
            )
        else:
            # Default: faster-whisper large-v3
            config = WhisperConfig(
                model=self.config.pass2_model,
                device=self.config.device,
                language=self.config.language,
            )
        return config

    async def _run_pipeline_pass(
        self,
        tmp_path: str,
        pipeline_mode: PipelineMode,
        pass_name: str,
        seg_idx: int
    ) -> TranscriptionResult:
        """Run a specific pipeline on pre-extracted audio and return TranscriptionResult.

        processor 实例在 WhisperPipeline 级别缓存，只在首次使用时加载模型。
        """
        if pipeline_mode == PipelineMode.ANIME:
            config = self._build_pass_config(PipelineMode.ANIME)
            try:
                if self._anime_processor is None:
                    self._anime_processor = AnimeWhisperProcessor(config, self.progress_callback, self.cancel_callback)
                result = await asyncio.to_thread(self._anime_processor.process, tmp_path, "")
                self.log(f"段落 {seg_idx + 1} {pass_name} 完成: {len(result.segments)} 片段")
                return result
            except Exception as e:
                self.log(f"段落 {seg_idx + 1} {pass_name} 失败: {e}")
                return TranscriptionResult(
                    segments=[], language="ja", duration=0.0,
                    source=f"{pass_name}-failed", metadata={"error": str(e)}
                )
        elif pipeline_mode == PipelineMode.TRANSFORMERS:
            # Kotoba-Whisper-v2.2 独立处理（不走 WhisperJAV bridge）
            try:
                if self._kotoba_processor is None:
                    self._kotoba_processor = KotobaWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
                result = await asyncio.to_thread(self._kotoba_processor.process, tmp_path, "")
                self.log(f"段落 {seg_idx + 1} {pass_name} 完成: {len(result.segments)} 片段")
                return result
            except Exception as e:
                self.log(f"段落 {seg_idx + 1} {pass_name} 失败: {e}")
                return TranscriptionResult(
                    segments=[], language="ja", duration=0.0,
                    source=f"{pass_name}-failed", metadata={"error": str(e)}
                )
        elif pipeline_mode == PipelineMode.REAZON:
            try:
                if self._reazon_processor is None:
                    self._reazon_processor = ReazonNemoProcessor(
                        self._build_pass_config(PipelineMode.REAZON),
                        self.progress_callback,
                        self.cancel_callback,
                    )
                result = await asyncio.to_thread(self._reazon_processor.process, tmp_path, "")
                self.log(f"段落 {seg_idx + 1} {pass_name} 完成: {len(result.segments)} 片段")
                return result
            except Exception as e:
                self.log(f"段落 {seg_idx + 1} {pass_name} 失败: {e}")
                return TranscriptionResult(
                    segments=[], language="ja", duration=0.0,
                    source=f"{pass_name}-failed", metadata={"error": str(e)}
                )
        else:
            # All other pipelines use FasterWhisperProcessor with appropriate config
            config = self._build_pass_config(pipeline_mode)
            try:
                if self._faster_processor is None:
                    self._faster_processor = FasterWhisperProcessor(config, self.progress_callback, self.cancel_callback)
                result = await asyncio.to_thread(self._faster_processor.process, tmp_path, "")
                self.log(f"段落 {seg_idx + 1} {pass_name} 完成: {len(result.segments)} 片段")
                return result
            except Exception as e:
                self.log(f"段落 {seg_idx + 1} {pass_name} 失败: {e}")
                return TranscriptionResult(
                    segments=[], language="ja", duration=0.0,
                    source=f"{pass_name}-failed", metadata={"error": str(e)}
                )

    async def _process_ensemble_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """两遍处理（指定音频段落）"""
        self._raise_if_cancelled()
        # 解析 pipeline 模式
        pass1_mode = PipelineMode(self.config.pass1_pipeline.value) if self.config.pass1_pipeline else PipelineMode.ANIME
        pass2_mode = PipelineMode(self.config.pass2_pipeline.value) if self.config.pass2_pipeline else PipelineMode.FASTER

        # 提取段落音频
        tmp_result = self._extract_audio_segment(audio_file, seg_start, seg_end, seg_idx)
        if tmp_result[0] is None:
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_end - seg_start,
                source="ensemble-segment-failed",
                metadata={"error": "audio extraction failed"}
            )
        tmp_path, seg_duration = tmp_result

        try:
            # ========== Pass 1 ==========
            self.log("=" * 50)
            self.log(f"Pass 1: {self._pipeline_display_name(pass1_mode)} ({pass1_mode.name})")
            self.log("=" * 50)
            pass1_result = await self._run_pipeline_pass(tmp_path, pass1_mode, "Pass1", seg_idx)

            should_run_pass2, reason = self._should_run_pass2(seg_duration, pass1_result, pass2_mode)
            if not should_run_pass2:
                self.log(f"段落 {seg_idx + 1} 跳过 Pass2: {reason}")
                return pass1_result

            # ========== Pass 2 ==========
            self.log("=" * 50)
            self.log(f"Pass 2: {self._pipeline_display_name(pass2_mode)} ({pass2_mode.name})")
            self.log("=" * 50)
            pass2_result = await self._run_pipeline_pass(tmp_path, pass2_mode, "Pass2", seg_idx)

            if not pass2_result.segments:
                self.log(f"段落 {seg_idx + 1} Pass2 无结果，返回 Pass1")
                return pass1_result

            # 调整时间戳为全局时间（由调用方处理）

            # ========== 合并 ==========
            self.log("=" * 50)
            self.log(f"合并策略: {self.config.merge_strategy.value}")
            self.log("=" * 50)
            merge_engine = MergeEngine(self.config.merge_strategy)
            merged = merge_engine.merge(pass1_result, pass2_result)
            self.log(f"段落 {seg_idx + 1} 合并完成: {len(merged.segments)} 片段")
            return merged
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    async def _process_anime_qwen3_chain_segments(
        self,
        all_segments: list[tuple[str, float, float]],
    ) -> list[TranscriptionResult]:
        """Anime-Whisper + Qwen3-ASR fallback + Qwen3 ForcedAligner 链路。"""
        framed_segments = all_segments
        if self._anime_qwen3_chain is None:
            self._anime_qwen3_chain = AnimeQwen3ChainProcessor(self.config, progress_logger=self.log)
        if hasattr(self._anime_qwen3_chain, 'frame_segments'):
            framed_segments = self._anime_qwen3_chain.frame_segments(all_segments)

        prepared: list[_PreparedSegment] = []
        for idx, (audio_file, seg_start, seg_end) in enumerate(framed_segments):
            self._raise_if_cancelled()
            seg_duration = seg_end - seg_start
            prep_progress = int(28 + ((idx + 1) / max(len(framed_segments), 1)) * 8)
            self.log(
                f"准备段落 {idx + 1}/{len(framed_segments)}: {seg_start:.1f}s - {seg_end:.1f}s ({seg_duration:.1f}s)",
                prep_progress,
            )
            tmp_path, _ = self._extract_audio_segment(audio_file, seg_start, seg_end, idx)
            if tmp_path is None:
                prepared.append(
                    _PreparedSegment(
                        index=idx,
                        audio_path="",
                        start=seg_start,
                        end=seg_end,
                        duration=seg_duration,
                        pass1_result=TranscriptionResult(
                            segments=[],
                            language="ja",
                            duration=seg_duration,
                            source="recommended-decoupled-prep-failed",
                            metadata={"error": "audio extraction failed"},
                        ),
                    )
                )
                continue
            prepared.append(_PreparedSegment(index=idx, audio_path=tmp_path, start=seg_start, end=seg_end, duration=seg_duration))

        try:
            if not self._anime_qwen3_chain.is_available():
                self.log("[Recommended] Qwen3 对齐不可用，回退到旧推荐链路", 36)
                return await self._process_recommended_phase_based_segments(framed_segments)
            self.log("=" * 50)
            self.log("Phase 2: Anime-Whisper + Qwen3 ForcedAligner", 36)
            self.log("=" * 50)
            final_results: list[TranscriptionResult] = []
            for seg in prepared:
                self._raise_if_cancelled()
                if seg.pass1_result is not None:
                    result = seg.pass1_result
                else:
                    run_progress = int(36 + ((seg.index + 1) / max(len(prepared), 1)) * 48)
                    self.log(
                        f"链路段落 {seg.index + 1}/{len(prepared)}: Anime 转写 + Qwen3 对齐 ({self.config.framer_backend})",
                        run_progress,
                    )
                    pass1_result = await self._run_pipeline_pass(seg.audio_path, PipelineMode.ANIME, "Pass1", seg.index)
                    try:
                        result = await asyncio.to_thread(
                            self._anime_qwen3_chain.align_pass1_result,
                            seg.audio_path,
                            pass1_result,
                        )
                    except Exception as exc:
                        self.log(f"[Recommended] 段落 {seg.index + 1} Qwen3 对齐失败，回退 Anime 结果: {exc}")
                        result = pass1_result
                should_stepdown, stepdown_reason = self._evaluate_recommended_stepdown(seg.duration, result)
                result.metadata = {
                    **result.metadata,
                    "recommended_stepdown_reason": stepdown_reason,
                }
                if should_stepdown:
                    result = await self._retry_anime_qwen3_with_stepdown(seg, result)
                else:
                    for item in result.segments:
                        item.start_time += seg.start
                        item.end_time += seg.start
                final_results.append(result)

            aligned_count = sum(1 for result in final_results if result.metadata.get('anime_qwen3_chain') == 'qwen3_forced_aligner')
            retry_count = sum(1 for result in final_results if result.metadata.get('anime_qwen3_retry'))
            hardened_count = sum(1 for result in final_results if result.metadata.get('hardening_applied'))
            self.log(f"Anime+Qwen3 链路完成: 对齐 {aligned_count}/{len(final_results)} · fallback {retry_count} · hardening {hardened_count}", 85)
            return final_results
        finally:
            if self._anime_qwen3_chain is not None:
                self._anime_qwen3_chain.cleanup()
            for seg in prepared:
                if seg.audio_path:
                    try:
                        os.remove(seg.audio_path)
                    except Exception:
                        pass

    async def _retry_anime_qwen3_with_stepdown(
        self,
        segment: _PreparedSegment,
        base_result: TranscriptionResult,
    ) -> TranscriptionResult:
        windows = self._build_stepdown_windows(segment.duration)
        if len(windows) <= 1:
            return base_result

        self.log(
            f"[Recommended] 段落 {segment.index + 1} 命中 step-down，收紧为 {len(windows)} 个子段重试",
        )
        retried_results: list[TranscriptionResult] = []
        retry_temp_paths: list[str] = []
        try:
            for retry_idx, (rel_start, rel_end) in enumerate(windows, start=1):
                self._raise_if_cancelled()
                retry_tmp, _ = self._extract_audio_segment(segment.audio_path, rel_start, rel_end, retry_idx - 1)
                if retry_tmp is None:
                    return base_result
                retry_temp_paths.append(retry_tmp)
                pass1_result = await self._run_pipeline_pass(retry_tmp, PipelineMode.ANIME, "Pass1", retry_idx - 1)
                retried = await asyncio.to_thread(
                    self._anime_qwen3_chain.align_pass1_result,
                    retry_tmp,
                    pass1_result,
                )
                offset = segment.start + rel_start
                for item in retried.segments:
                    item.start_time += offset
                    item.end_time += offset
                retried_results.append(retried)

            merged = self._merge_all_results(retried_results)
            merged.metadata = {
                **base_result.metadata,
                **merged.metadata,
                "recommended_stepdown_retry": True,
                "recommended_stepdown_window_count": len(windows),
            }
            self.log(
                f"[Recommended] 段落 {segment.index + 1} step-down 完成: {len(base_result.segments)} → {len(merged.segments)} 片段"
            )
            return merged
        finally:
            for path in retry_temp_paths:
                try:
                    os.remove(path)
                except Exception:
                    pass

    async def _process_recommended_phase_based_segments(
        self,
        all_segments: list[tuple[str, float, float]],
    ) -> list[TranscriptionResult]:
        """Product-default execution:
        1) prepare all segment audio
        2) run pass1 for all segments
        3) gate + run pass2 only on selected segments
        4) merge final results
        """
        pass1_mode = PipelineMode(self.config.pass1_pipeline.value) if self.config.pass1_pipeline else PipelineMode.ANIME
        pass2_mode = PipelineMode(self.config.pass2_pipeline.value) if self.config.pass2_pipeline else PipelineMode.QWEN

        framed_segments = all_segments
        if self._anime_qwen3_chain is None:
            self._anime_qwen3_chain = AnimeQwen3ChainProcessor(self.config, progress_logger=self.log)
        if hasattr(self._anime_qwen3_chain, 'frame_segments'):
            framed_segments = self._anime_qwen3_chain.frame_segments(all_segments)

        prepared: list[_PreparedSegment] = []
        for idx, (audio_file, seg_start, seg_end) in enumerate(framed_segments):
            self._raise_if_cancelled()
            seg_duration = seg_end - seg_start
            prep_progress = int(28 + ((idx + 1) / max(len(all_segments), 1)) * 6)
            self.log(
                f"准备段落 {idx + 1}/{len(framed_segments)}: {seg_start:.1f}s - {seg_end:.1f}s ({seg_duration:.1f}s)",
                prep_progress,
            )
            tmp_path, _ = self._extract_audio_segment(audio_file, seg_start, seg_end, idx)
            if tmp_path is None:
                prepared.append(
                    _PreparedSegment(
                        index=idx,
                        audio_path="",
                        start=seg_start,
                        end=seg_end,
                        duration=seg_duration,
                        pass1_result=TranscriptionResult(
                            segments=[],
                            language="ja",
                            duration=seg_duration,
                            source="recommended-phase-prep-failed",
                            metadata={"error": "audio extraction failed"},
                        ),
                    )
                )
                continue
            prepared.append(
                _PreparedSegment(
                    index=idx,
                    audio_path=tmp_path,
                    start=seg_start,
                    end=seg_end,
                    duration=seg_duration,
                )
            )

        try:
            self.log("=" * 50)
            self.log(f"Phase 2A: Pass1 全量转写 ({self._pipeline_display_name(pass1_mode)})", 34)
            self.log("=" * 50)
            for seg in prepared:
                self._raise_if_cancelled()
                if seg.pass1_result is not None:
                    continue
                pass1_progress = int(34 + ((seg.index + 1) / max(len(prepared), 1)) * 22)
                self.log(
                    f"Pass1 段落 {seg.index + 1}/{len(prepared)}: {seg.start:.1f}s - {seg.end:.1f}s ({seg.duration:.1f}s)",
                    pass1_progress,
                )
                seg.pass1_result = await self._run_pipeline_pass(seg.audio_path, pass1_mode, "Pass1", seg.index)

            pass2_candidates: list[_PreparedSegment] = []
            skipped = 0
            for seg in prepared:
                self._raise_if_cancelled()
                pass1_result = seg.pass1_result or TranscriptionResult(
                    segments=[],
                    language="ja",
                    duration=seg.duration,
                    source="pass1-missing",
                    metadata={},
                )
                should_run_pass2, reason = self._should_run_pass2(seg.duration, pass1_result, pass2_mode)
                if should_run_pass2:
                    pass2_candidates.append(seg)
                else:
                    skipped += 1
                    self.log(f"段落 {seg.index + 1} 跳过 Pass2: {reason}")

            self.log(f"Pass2 gating: {len(pass2_candidates)}/{len(prepared)} 段需要二次识别，跳过 {skipped} 段", 57)

            if pass2_candidates:
                self.log("=" * 50)
                self.log(f"Phase 2B: Pass2 选择性转写 ({self._pipeline_display_name(pass2_mode)})", 58)
                self.log("=" * 50)
            for order, seg in enumerate(pass2_candidates):
                self._raise_if_cancelled()
                pass2_progress = int(58 + ((order + 1) / max(len(pass2_candidates), 1)) * 21)
                self.log(
                    f"Pass2 段落 {order + 1}/{len(pass2_candidates)} (原段 {seg.index + 1})",
                    pass2_progress,
                )
                seg.pass2_result = await self._run_pipeline_pass(seg.audio_path, pass2_mode, "Pass2", seg.index)

            self.log("=" * 50)
            self.log(f"Phase 2C: 合并阶段 ({self.config.merge_strategy.value})", 80)
            self.log("=" * 50)
            merge_engine = MergeEngine(self.config.merge_strategy)
            final_results: list[TranscriptionResult] = []
            merged_count = 0
            for seg in prepared:
                pass1_result = seg.pass1_result or TranscriptionResult(
                    segments=[],
                    language="ja",
                    duration=seg.duration,
                    source="pass1-missing",
                    metadata={},
                )
                if seg.pass2_result and seg.pass2_result.segments:
                    merged = merge_engine.merge(pass1_result, seg.pass2_result)
                    merged_count += 1
                else:
                    merged = pass1_result

                for item in merged.segments:
                    item.start_time += seg.start
                    item.end_time += seg.start
                final_results.append(merged)

            self.log(f"Phase-based 推荐链路完成: Pass2 实跑 {len(pass2_candidates)} 段，成功合并 {merged_count} 段", 85)
            return final_results
        finally:
            for seg in prepared:
                if seg.audio_path:
                    try:
                        os.remove(seg.audio_path)
                    except Exception:
                        pass

    async def _process_faster_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """Faster 模式: Faster-Whisper turbo，适合清洁音频"""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        seg_duration = seg_end - seg_start

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                 offset=seg_start, duration=seg_duration)
            sf.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="faster-segment-failed",
                metadata={"error": str(e)}
            )

        try:
            # Faster 模式使用 turbo 模型（使用缓存的 processor）
            if self._faster_processor is None:
                faster_config = WhisperConfig(
                    model=WhisperModel.TINY,  # 使用小模型快速处理
                    device=self.config.device,
                    language=self.config.language,
                    vad_filter=False,  # 清洁音频不需要 VAD
                )
                self._faster_processor = FasterWhisperProcessor(faster_config, self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(self._faster_processor.process, tmp_path, "")
            self.log(f"Faster 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    async def _process_balanced_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """Balanced 模式: Faster-Whisper + Silero VAD，适合嘈杂对话"""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        seg_duration = seg_end - seg_start

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                 offset=seg_start, duration=seg_duration)
            sf.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="balanced-segment-failed",
                metadata={"error": str(e)}
            )

        try:
            # Balanced 使用 large-v3 + Silero VAD（使用缓存的 processor）
            if self._balanced_processor is None:
                balanced_config = WhisperConfig(
                    model=WhisperModel.LARGE_V3,
                    device=self.config.device,
                    language=self.config.language,
                    vad_filter=True,
                    vad_min_silence_ms=1500,
                )
                self._balanced_processor = FasterWhisperProcessor(balanced_config, self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(self._balanced_processor.process, tmp_path, "")
            self.log(f"Balanced 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    async def _process_qwen_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """Large-v3 baseline 模式: Faster-Whisper large-v3 + Silero VAD（历史 qwen 键）"""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        seg_duration = seg_end - seg_start

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                  offset=seg_start, duration=seg_duration)
            sf.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="large-v3-baseline-segment-failed",
                metadata={"error": str(e)}
            )

        try:
            if self._qwen_processor is None:
                qwen_config = WhisperConfig(
                    model=WhisperModel.LARGE_V3,
                    device=self.config.device,
                    language=self.config.language,
                    vad_filter=True,
                    vad_min_silence_ms=1500,
                )
                self._qwen_processor = FasterWhisperProcessor(qwen_config, self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(self._qwen_processor.process, tmp_path, "")
            self.log(f"Large-v3 baseline 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    async def _process_anime_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int
    ) -> TranscriptionResult:
        """Anime 模式: anime-whisper + TEN VAD，JAV 优化"""
        import tempfile
        import soundfile as sf
        import librosa
        self._raise_if_cancelled()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        seg_duration = seg_end - seg_start

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                 offset=seg_start, duration=seg_duration)
            sf.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="anime-segment-failed",
                metadata={"error": str(e)}
            )

        try:
            # Anime 模式使用 anime-whisper（Transformers ASR pipeline）
            if self._anime_processor is None:
                anime_config = WhisperConfig(
                    model=WhisperModel.ANIME,
                    device=self.config.device,
                    language=self.config.language,
                    vad_filter=True,
                )
                self._anime_processor = AnimeWhisperProcessor(anime_config, self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(self._anime_processor.process, tmp_path, "")
            self.log(f"Anime 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    async def _process_reazon_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int,
    ) -> TranscriptionResult:
        """Reazon / NeMo 单段处理。"""
        self._raise_if_cancelled()
        tmp_path, seg_duration = self._extract_audio_segment(audio_file, seg_start, seg_end, seg_idx)
        if tmp_path is None:
            return TranscriptionResult(segments=[], language="ja", duration=seg_end - seg_start, source="reazon-segment-failed", metadata={"error": "extract-failed"})
        try:
            if self._reazon_processor is None:
                self._reazon_processor = ReazonNemoProcessor(self._build_pass_config(PipelineMode.REAZON), self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(self._reazon_processor.process, tmp_path, "")
            self.log(f"[Reazon] 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段")
            return result
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    # ─── Kotoba Transformers Pipeline（自实现，不走 WhisperJAV）──────────────

    async def _process_transformers_segment(
        self,
        audio_file: str,
        seg_start: float,
        seg_end: float,
        seg_idx: int,
    ) -> TranscriptionResult:
        """
        Kotoba-Whisper-v2.2 独立处理段落（不走 WhisperJAV bridge）。

        数据流：音频段落 → Enhancers → KotobaWhisperProcessor → 结果
        """
        import tempfile, soundfile, librosa
        self._raise_if_cancelled()

        seg_duration = seg_end - seg_start

        # 1. 提取段落音频到临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as tmp:
            tmp_path = tmp.name

        try:
            y, sr = librosa.load(audio_file, sr=16000, mono=True,
                                  offset=seg_start, duration=seg_duration)
            soundfile.write(tmp_path, y, sr)
        except Exception as e:
            self.log(f"[Kotoba] 段落 {seg_idx + 1} 音频提取失败: {e}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="kotoba-segment-failed",
                metadata={"error": str(e)},
            )

        try:
            self.log(f"[Kotoba] 段落 {seg_idx + 1}: {seg_start:.1f}s - {seg_end:.1f}s ({seg_duration:.1f}s)", 25)

            # 2. 应用 enhancers（如有）
            audio_for_asr = tmp_path
            enhancers = self.config.enhancers or []
            if enhancers:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, mode="wb") as enh_tmp:
                        enh_path = enh_tmp.name
                    enhancer = AudioEnhancer(enhancers, self.progress_callback, self.cancel_callback)
                    audio_for_asr = enhancer.enhance(tmp_path, enh_path, sample_rate=16000)
                    self.log(f"[Kotoba] Enhancers applied: {enhancers}")
                except Exception as e:
                    self.log(f"[Kotoba] Enhancer failed, using raw audio: {e}")
                    audio_for_asr = tmp_path

            # 3. KotobaWhisperProcessor ASR
            if self._kotoba_processor is None:
                self._kotoba_processor = KotobaWhisperProcessor(self.config, self.progress_callback, self.cancel_callback)
            result = await asyncio.to_thread(
                self._kotoba_processor.process, audio_for_asr, ""
            )

            self.log(f"[Kotoba] 段落 {seg_idx + 1} 完成: {len(result.segments)} 片段", 85)
            return result

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log(f"[Kotoba] 段落 {seg_idx + 1} 失败: {e}\n{tb[:300]}")
            return TranscriptionResult(
                segments=[],
                language="ja",
                duration=seg_duration,
                source="kotoba-segment-error",
                metadata={"error": str(e)},
            )
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass


    def _merge_all_results(self, results: list[TranscriptionResult]) -> TranscriptionResult:
        """合并多个段落的结果（按时间排序拼接）"""
        all_segments = []
        for r in results:
            all_segments.extend(r.segments)

        # 按 start_time 排序
        all_segments.sort(key=lambda s: s.start_time)

        # 重新编号
        for i, seg in enumerate(all_segments):
            seg.index = i + 1

        return TranscriptionResult(
            segments=all_segments,
            language=results[0].language if results else "ja",
            duration=sum(r.duration for r in results),
            source="scene-merged",
            metadata={"n_segments": len(results), "n_subtitles": len(all_segments)}
        )

    def _clean_video_name(self, name: str) -> str:
        """清理视频名用于字幕文件"""
        import re
        # 移除常见后缀
        name = re.sub(r'[-_]?(破解|流出|中文|字幕|ch|chs|cht|cn|tw|z[ah]?[-_]?.*)', '', name, flags=re.IGNORECASE)
        # 移除扩展名
        name = re.sub(r'\.(mp4|mkv|avi|mov|wmv|flv|m4v)$', '', name, flags=re.IGNORECASE)
        return name.strip()


# 全局任务存储
_tasks = {}


def create_task(video_path: str, config: WhisperConfig) -> WhisperTask:
    """创建 Whisper 任务"""
    task_id = str(uuid.uuid4())
    task = WhisperTask(
        id=task_id,
        video_path=video_path,
        config=config
    )
    _tasks[task_id] = task
    return task


def get_task(task_id: str) -> Optional[WhisperTask]:
    """获取任务"""
    return _tasks.get(task_id)


async def run_whisper_task(
    task_id: str,
    progress_callback: Optional[Callable] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> tuple[TranscriptionResult, str]:
    """运行 Whisper 任务"""
    task = _tasks.get(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    task.status = "running"

    def log_callback(msg: str):
        task.log_lines.append(msg)
        if progress_callback:
            progress_callback(msg)

    pipeline = WhisperPipeline(task.config, log_callback, cancel_callback=cancel_callback)

    try:
        result, srt_path = await pipeline.process(task.video_path)
        task.result = result
        task.status = "completed"
        return result, srt_path
    except WhisperCancellationRequested as e:
        task.status = "cancelled"
        task.error = str(e)
        raise
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        raise
