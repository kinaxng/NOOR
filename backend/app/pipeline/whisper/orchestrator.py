"""Whisper subtitle pipeline orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

from app.api.settings_whisper_models import resolve_model_cache_candidates

from .engine import AudioExtractor, AnimeWhisperProcessor, FasterWhisperProcessor, generate_srt, _resolve_whisper_storage
from .japanese_post import JapanesePostProcessor
from .runtime import raise_if_cancelled
from .scene_detector import AudioSceneDetector, WhisperVadOnnxSceneDetector
from .timing_refiner import SubtimerVadTimingRefiner
from .types import (
    PipelineMode,
    TranscriptionResult,
    WhisperCancellationRequested,
    WhisperConfig,
    WhisperModel,
    WhisperTask,
)

logger = logging.getLogger(__name__)


def _get_whisper_runtime_paths() -> tuple[str, str, str]:
    return _resolve_whisper_storage()


WHISPER_VAD_ONNX_REPO_ID = "TransWithAI/Whisper-Vad-EncDec-ASMR-onnx"
MODEL_REPOSITORIES = {
    WhisperModel.CHICKENRICE_ZH: "chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2",
    WhisperModel.ANIME: "litagin/anime-whisper",
    WhisperModel.LARGE_V3: "Systran/faster-whisper-large-v3",
}


class WhisperPipeline:
    """Run the selected ASR backend through NOOR's shared timing pipeline."""

    def __init__(
        self,
        config: WhisperConfig,
        progress_callback: Optional[Callable] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.config = config
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback
        self._log_lines: list[str] = []
        self._anime_processor: Optional[AnimeWhisperProcessor] = None
        self._faster_processor: Optional[FasterWhisperProcessor] = None

    def log(self, message: str, progress: int | None = None) -> None:
        self._log_lines.append(message)
        if not self.progress_callback:
            return
        try:
            self.progress_callback(message, progress)
        except TypeError:
            self.progress_callback(message)
        except Exception as exc:
            logger.warning("Progress callback error: %s", exc)

    def _raise_if_cancelled(self) -> None:
        raise_if_cancelled(self.cancel_callback)

    def _get_output_dir(self) -> Path:
        if self.config.output_dir:
            return Path(self.config.output_dir)
        _, _, temp_dir = _get_whisper_runtime_paths()
        return Path(temp_dir) / "whisper_jav"

    def _whisper_model_dir(self) -> str:
        return _get_whisper_runtime_paths()[0]

    def _check_model_cached(self, repository: str) -> bool:
        for candidate in resolve_model_cache_candidates(self._whisper_model_dir(), repository):
            if candidate.exists() and any(candidate.iterdir()):
                return True
        return False

    def _whisper_vad_onnx_cache_dir(self) -> Path:
        candidates = resolve_model_cache_candidates(self._whisper_model_dir(), WHISPER_VAD_ONNX_REPO_ID)
        for candidate in candidates:
            if candidate.exists() and any(candidate.rglob("model.onnx")):
                return candidate
        return candidates[0]

    def _validate_required_models(self) -> None:
        repository = MODEL_REPOSITORIES.get(self.config.model)
        if repository and not self._check_model_cached(repository):
            raise RuntimeError(
                f"模型未下载: [{self.config.model.value}]。"
                "请先在 设置 -> Whisper -> 模型 中下载对应模型，然后重试任务。"
            )
        if self.config.vad_backend == "whisper_vad_onnx":
            vad_dir = self._whisper_vad_onnx_cache_dir()
            if not vad_dir.exists() or not any(vad_dir.rglob("model.onnx")):
                raise RuntimeError(
                    "模型未下载: [whisper-vad-onnx]。"
                    "请先在 设置 -> Whisper -> 模型 中下载对应模型，然后重试任务。"
                )

    def _detect_chunks(self, audio_path: Path, duration: float) -> list[tuple[float, float]]:
        if duration <= self.config.target_chunk_duration_s:
            return [(0.0, duration)]

        common = {
            "min_segment_duration": max(3.0, min(10.0, self.config.target_chunk_duration_s * 0.35)),
            "max_segment_duration": self.config.max_chunk_duration_s,
        }
        try:
            self._raise_if_cancelled()
            if self.config.vad_backend == "whisper_vad_onnx":
                detector = WhisperVadOnnxSceneDetector(
                    repo_dir=self._whisper_vad_onnx_cache_dir(),
                    **common,
                )
            else:
                detector = AudioSceneDetector(
                    mode="energy",
                    min_silence_duration=0.1,
                    energy_threshold=0.01,
                    **common,
                )
            scenes = detector.detect(str(audio_path))
            self.log(f"Smart VAD 生成 {len(scenes)} 个安全连续块")
            return [(scene.start, scene.end) for scene in scenes] or [(0.0, duration)]
        except Exception as exc:
            if self.config.vad_backend != "whisper_vad_onnx":
                self.log(f"Smart VAD 失败，使用整段音频: {exc}")
                return [(0.0, duration)]

            self.log(f"Whisper-VAD ONNX 失败，回退 energy: {exc}")
            detector = AudioSceneDetector(
                mode="energy",
                min_silence_duration=0.1,
                min_segment_duration=common["min_segment_duration"],
                energy_threshold=0.01,
                max_segment_duration=common["max_segment_duration"],
            )
            scenes = detector.detect(str(audio_path))
            return [(scene.start, scene.end) for scene in scenes] or [(0.0, duration)]

    async def process(self, video_path: str, video_name: str = "") -> tuple[TranscriptionResult, str]:
        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        self._raise_if_cancelled()
        self._validate_required_models()

        video_name = video_name or Path(video_path).stem
        audio_path = output_dir / f"{video_name}_audio.wav"

        self.log("=" * 50)
        self.log("Phase 1: 提取音频")
        self.log("=" * 50)
        try:
            _, duration = AudioExtractor.extract(
                video_path,
                str(audio_path),
                sample_rate=16000,
                cancel_callback=self.cancel_callback,
            )
            self.log(f"音频提取完成，时长: {duration:.1f}s", 5)

            self.log("=" * 50)
            self.log(f"Smart VAD: {self.config.vad_backend}")
            self.log("=" * 50)
            chunks = self._detect_chunks(audio_path, duration)

            results: list[TranscriptionResult] = []
            for index, (start, end) in enumerate(chunks):
                self._raise_if_cancelled()
                start_progress = int(20 + index / len(chunks) * 65)
                end_progress = int(20 + (index + 1) / len(chunks) * 65)
                self.log(
                    f"处理段落 {index + 1}/{len(chunks)}: {start:.1f}s - {end:.1f}s ({end - start:.1f}s)",
                    start_progress,
                )
                result = await self._process_segment(str(audio_path), start, end, index)
                for segment in result.segments:
                    segment.start_time += start
                    segment.end_time += start
                results.append(result)
                self.log(f"段落 {index + 1} 完成: {len(result.segments)} 片段", end_progress)

            result = results[0] if len(results) == 1 else self._merge_all_results(results)
            if len(results) > 1:
                self.log(f"段落合并完成: {len(result.segments)} 片段", 90)

            if self.config.model != WhisperModel.CHICKENRICE_ZH:
                try:
                    self._raise_if_cancelled()
                    result = JapanesePostProcessor(
                        min_segment_duration=0.8,
                        max_segment_duration=8.0,
                        min_gap_threshold=0.3,
                        merge_below=1.2,
                    ).process(result)
                    self.log(f"日语后处理完成: {len(result.segments)} 片段", 94)
                except Exception as exc:
                    self.log(f"日语后处理失败（跳过）: {exc}")

            if self.config.timing_refiner == "subtimer_vad":
                try:
                    result, changed = SubtimerVadTimingRefiner().refine(result, chunks)
                    self.log(f"实验时间轴微调: subtimer-vad 调整 {changed}/{len(result.segments)} 段", 96)
                except Exception as exc:
                    self.log(f"实验时间轴微调失败（跳过）: {exc}")

            clean_name = self._clean_video_name(video_name)
            language_suffix = "zh" if self.config.whisper_task == "translate" else "ja"
            srt_path = output_dir / f"{clean_name}.{language_suffix}.srt"
            generate_srt(result.segments, str(srt_path))
            self.log(f"字幕已保存: {srt_path}", 97)
            return result, str(srt_path)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def _process_segment(
        self,
        audio_file: str,
        start: float,
        end: float,
        index: int,
    ) -> TranscriptionResult:
        import librosa
        import soundfile as sf

        self._raise_if_cancelled()
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            dir=_get_whisper_runtime_paths()[2],
        ) as handle:
            segment_path = handle.name
        try:
            samples, sample_rate = librosa.load(
                audio_file,
                sr=16000,
                mono=True,
                offset=start,
                duration=end - start,
            )
            sf.write(segment_path, samples, sample_rate)
            if self.config.pipeline_mode == PipelineMode.ANIME:
                if self._anime_processor is None:
                    self._anime_processor = AnimeWhisperProcessor(
                        self.config,
                        self.progress_callback,
                        self.cancel_callback,
                    )
                return await asyncio.to_thread(self._anime_processor.process, segment_path, "")

            if self._faster_processor is None:
                self._faster_processor = FasterWhisperProcessor(
                    self.config,
                    self.progress_callback,
                    self.cancel_callback,
                )
            return await asyncio.to_thread(self._faster_processor.process, segment_path, "")
        except Exception as exc:
            self.log(f"段落 {index + 1} 处理失败: {exc}")
            raise
        finally:
            try:
                os.remove(segment_path)
            except Exception:
                pass

    @staticmethod
    def _merge_all_results(results: list[TranscriptionResult]) -> TranscriptionResult:
        segments = [segment for result in results for segment in result.segments]
        segments.sort(key=lambda segment: segment.start_time)
        for index, segment in enumerate(segments, start=1):
            segment.index = index
        return TranscriptionResult(
            segments=segments,
            language=results[0].language if results else "ja",
            duration=sum(result.duration for result in results),
            source="scene-merged",
            metadata={"n_segments": len(results), "n_subtitles": len(segments)},
        )

    @staticmethod
    def _clean_video_name(name: str) -> str:
        from app.pipeline.whisper.filenames import clean_media_stem

        return clean_media_stem(name)


_tasks: dict[str, WhisperTask] = {}


def create_task(video_path: str, config: WhisperConfig) -> WhisperTask:
    task_id = str(uuid.uuid4())
    task = WhisperTask(id=task_id, video_path=video_path, config=config)
    _tasks[task_id] = task
    return task


def get_task(task_id: str) -> Optional[WhisperTask]:
    return _tasks.get(task_id)


async def run_whisper_task(
    task_id: str,
    progress_callback: Optional[Callable] = None,
    cancel_callback: Optional[Callable[[], bool]] = None,
) -> tuple[TranscriptionResult, str]:
    task = _tasks.get(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    task.status = "running"

    def log_callback(message: str, progress: int | None = None) -> None:
        task.log_lines.append(message)
        if progress is not None:
            task.progress = progress
        if progress_callback:
            if progress is None:
                progress_callback(message)
            else:
                try:
                    progress_callback(progress=progress, detail=message)
                except TypeError:
                    progress_callback(message, progress)

    pipeline = WhisperPipeline(task.config, log_callback, cancel_callback=cancel_callback)
    try:
        result, srt_path = await pipeline.process(task.video_path)
        task.result = result
        task.progress = 100
        task.status = "completed"
        return result, srt_path
    except WhisperCancellationRequested as exc:
        task.status = "cancelled"
        task.error = str(exc)
        raise
    except Exception as exc:
        task.status = "failed"
        task.error = str(exc)
        raise
