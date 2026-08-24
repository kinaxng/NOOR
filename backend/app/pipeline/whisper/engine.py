"""Whisper 字幕生成引擎"""
import os
import asyncio
import subprocess
import warnings
from pathlib import Path
from typing import Optional, Callable
import tempfile

warnings.filterwarnings("ignore", message=".*chunk_length_s.*is very experimental.*")

from .types import WhisperConfig, WhisperModel, SubtitleSegment, TranscriptionResult
from .runtime import raise_if_cancelled, run_cancellable_subprocess


def _model_cache_candidates(base_dir: str, model_id: str) -> list[Path]:
    from app.api.settings_whisper_models import resolve_model_cache_candidates

    return resolve_model_cache_candidates(base_dir, model_id)


def _resolve_whisper_storage() -> tuple[str, str, str]:
    from app.core.config import get_settings
    from app.core.runtime_paths import apply_whisper_cache_env, ensure_directory

    settings = get_settings()
    model_dir = ensure_directory(settings.whisper_model_dir)
    cache_dir = ensure_directory(settings.whisper_cache_dir)
    temp_dir = ensure_directory(settings.whisper_temp_dir)
    settings.apply_network_env()
    apply_whisper_cache_env(model_dir, cache_dir)
    return model_dir, cache_dir, temp_dir


def _iter_hf_repo_paths(base_dir: str, model_id: str) -> list[Path]:
    return _model_cache_candidates(base_dir, model_id)


def _hf_model_cached(base_dir: str, model_id: str) -> bool:
    return any(path.exists() and any(path.iterdir()) for path in _iter_hf_repo_paths(base_dir, model_id))


def _resolve_hf_model_source(base_dir: str, model_id: str) -> tuple[str, dict]:
    for repo_path in _iter_hf_repo_paths(base_dir, model_id):
        if not repo_path.exists():
            continue
        ref_file = repo_path / "refs" / "main"
        if ref_file.exists():
            revision = ref_file.read_text().strip()
            snapshot_path = repo_path / "snapshots" / revision
            if snapshot_path.exists() and any(
                (snapshot_path / filename).exists()
                for filename in ("model.safetensors", "pytorch_model.bin", "model.safetensors.index.json")
            ):
                return str(snapshot_path), {"local_files_only": True}
        if any(
            (repo_path / filename).exists()
            for filename in ("model.safetensors", "pytorch_model.bin", "model.safetensors.index.json")
        ):
            return str(repo_path), {"local_files_only": True}

    return model_id, {"cache_dir": base_dir}


_FASTER_WHISPER_REPO_IDS = {
    "chickenrice-zh": "chickenrice0721/whisper-large-v2-translate-zh-v0.2-st-ct2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
}


def _resolve_faster_whisper_model_source(base_dir: str, model_size: str) -> tuple[str, dict]:
    repo_id = _FASTER_WHISPER_REPO_IDS.get(model_size)
    if not repo_id:
        return model_size, {"download_root": base_dir}

    for repo_path in _iter_hf_repo_paths(base_dir, repo_id):
        if not repo_path.exists():
            continue
        ref_file = repo_path / "refs" / "main"
        if ref_file.exists():
            revision = ref_file.read_text().strip()
            snapshot_path = repo_path / "snapshots" / revision
            if snapshot_path.exists() and (snapshot_path / "model.bin").exists():
                return str(snapshot_path), {}
        if (repo_path / "model.bin").exists():
            return str(repo_path), {}

    return model_size, {"download_root": base_dir}


class AudioExtractor:
    """音频提取器"""

    @staticmethod
    def extract(
        audio_path: str,
        output_path: str,
        sample_rate: int = 16000,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> tuple[str, float]:
        """使用 FFmpeg 提取音频"""
        cmd = [
            "ffmpeg", "-i", audio_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "1",
            "-threads", "8",
            "-y", output_path
        ]
        result = run_cancellable_subprocess(cmd, cancel_callback=cancel_callback)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

        # 获取时长
        raise_if_cancelled(cancel_callback)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
        return output_path, duration


class AnimeWhisperProcessor:
    """Anime-Whisper processor using the low-level Transformers API."""

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
        self._processor = None  # 缓存 processor 实例
        self._model = None       # 缓存 model 实例
        self._device = None
        self._dtype = None

    def log(self, msg: str, progress: int = None):
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)

    def _ensure_model(self):
        """延迟加载并缓存模型（只加载一次）"""
        if self._model is not None:
            return
        raise_if_cancelled(self.cancel_callback)

        import os
        from app.core.config import get_settings
        settings = get_settings()
        whisper_model_dir = settings.whisper_model_dir or "/volume1/models"
        os.environ["HF_HOME"] = whisper_model_dir
        os.environ["TRANSFORMERS_CACHE"] = whisper_model_dir
        settings.apply_network_env()

        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch
        except ImportError:
            self.log("[Anime] 错误: 需要安装 transformers 和 torch")
            raise RuntimeError("anime-whisper 需要 transformers 库")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model_id = "litagin/anime-whisper"
        self.log(f"[Anime] 加载模型: {model_id} (device: {device}), cache: {whisper_model_dir}")
        load_source, load_kwargs = _resolve_hf_model_source(whisper_model_dir, model_id)
        if load_kwargs.get("local_files_only"):
            self.log("[Anime] 检测到本地缓存，离线加载 anime-whisper")

        # 尝试 accelerate（device_map 自动分配层到设备）
        try:
            import accelerate
            self._processor = AutoProcessor.from_pretrained(load_source, **load_kwargs)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                load_source,
                torch_dtype=dtype,
                device_map=device,
                **load_kwargs,
            )
        except Exception:
            self.log("[Anime] 使用 fallback 加载方式（device 参数）")
            self._processor = AutoProcessor.from_pretrained(load_source, **load_kwargs)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                load_source,
                torch_dtype=dtype,
                **load_kwargs,
            ).to(device)

        self._device = device
        self._dtype = dtype

        if torch.cuda.is_available():
            self.log(f"[Anime] GPU: {torch.cuda.get_device_name(0)}")
        self.log("[Anime] 模型加载完成", 10)

    def process(self, audio_path: str, output_srt: str) -> TranscriptionResult:
        """同步处理音频文件"""
        import traceback
        import torch
        import numpy as np

        raise_if_cancelled(self.cancel_callback)
        self._ensure_model()

        self.log(f"[Anime] 开始转写: {audio_path}", 20)

        try:
            raise_if_cancelled(self.cancel_callback)
            # 用 librosa 加载音频
            import librosa
            try:
                y, _sr = librosa.load(audio_path, sr=16000, mono=True)
            except Exception:
                import soundfile as sf
                y, sr = sf.read(audio_path)
                if sr != 16000:
                    y = librosa.resample(y, orig_sr=sr, target_sr=16000)
                if y.ndim > 1:
                    y = y.mean(axis=1)
                y = y.astype(float)
            audio_duration = len(y) / 16000.0

            # 提取特征
            raise_if_cancelled(self.cancel_callback)
            inputs = self._processor(
                y, sampling_rate=16000, return_tensors="pt"
            )
            input_features = inputs.input_features.to(self._device, dtype=self._dtype)

            # 直接调用 model.generate()（不用 pipeline，避免 3000 mel feature 限制）
            # 使用 greedy 解码（anime-whisper 推荐参数）
            with torch.no_grad():
                output_ids = self._model.generate(
                    input_features,
                    language="ja",
                    task="transcribe",
                    do_sample=False,
                    num_beams=1,
                    max_new_tokens=440,
                )

            raise_if_cancelled(self.cancel_callback)
            text = self._processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

            self.log(f"[Anime] 转写完成，文本长度: {len(text)} 字符", 90)

            # anime-whisper 不返回时间戳，用整个音频时长作为单一段落
            # JapanesePostProcessor 会做断句处理

            raise_if_cancelled(self.cancel_callback)
            text = self._processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

            self.log(f"[Anime] 转写完成，文本长度: {len(text)} 字符", 90)

            # anime-whisper 不返回时间戳，用整个音频时长作为单一段落
            # JapanesePostProcessor 会做断句处理
            segments = [SubtitleSegment(
                index=1,
                start_time=0.0,
                end_time=audio_duration,
                text=text,
            )]

            return TranscriptionResult(
                segments=segments,
                language="ja",
                duration=audio_duration,
                source="anime-whisper",
                metadata={},
            )

        except Exception as e:
            self.log(f"[Anime] 异常: {type(e).__name__}: {e}\n{traceback.format_exc()[:500]}")
            raise




class FasterWhisperProcessor:
    """Faster-Whisper / CTranslate2 processor."""

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
        self._max_end_time = 0.0
        self._model = None
        self._model_signature: tuple[str, str, str, str] | None = None

    def log(self, msg: str, progress: int = None):
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)

    def _report_duration_progress(self, current_time: float, total_duration: float):
        """基于音频时长覆盖率报告进度"""
        if total_duration <= 0:
            return
        coverage = min(1.0, current_time / total_duration)
        # Transcription stage maps to 28-85%.
        pct = int(28 + coverage * 57)
        pct = min(84, pct)
        self.log(f"[Faster] 音频覆盖 {current_time:.0f}s / {total_duration:.0f}s", pct)

    def _get_sensitivity_params(self) -> dict:
        """获取敏感度参数"""
        if self.config.sensitivity.value == "conservative":
            return {
                "beam_size": 1,
                "best_of": 1,
                "no_speech_threshold": 0.7,
                "repetition_penalty": 1.8,
            }
        elif self.config.sensitivity.value == "aggressive":
            return {
                "beam_size": 3,
                "best_of": 3,
                "no_speech_threshold": 0.22,
            }
        else:  # balanced
            return {
                "beam_size": 2,
                "best_of": 2,
                "no_speech_threshold": 0.4,
                "repetition_penalty": 1.5,
            }

    def _get_model_runtime(self) -> tuple[object, str]:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            self.log("[Faster] 错误: 需要安装 faster-whisper")
            raise RuntimeError("faster-whisper 库未安装")

        model_size = self.config.model.value

        whisper_model_dir, _, _ = _resolve_whisper_storage()

        device = "cuda" if self.config.device == "auto" else self.config.device
        compute_type = self.config.compute_type if self.config.compute_type != "default" else "float16"
        signature = (model_size, device, compute_type, whisper_model_dir)

        if self._model is None or self._model_signature != signature:
            self.log(f"[Faster] 加载模型: {model_size} (dir: {whisper_model_dir})")
            self.log(f"[Faster] 使用设备: {device}, compute: {compute_type}")
            load_source, load_kwargs = _resolve_faster_whisper_model_source(whisper_model_dir, model_size)
            if not load_kwargs:
                self.log(f"[Faster] 检测到本地 CTranslate2 缓存，离线加载: {load_source}")
            self._model = WhisperModel(
                load_source,
                device=device,
                compute_type=compute_type,
                **load_kwargs,
            )
            self._model_signature = signature

            import torch
            if device == "cuda" and torch.cuda.is_available():
                self.log(f"[Faster] GPU 已激活: {torch.cuda.get_device_name(0)}")
            else:
                self.log("[Faster] 警告: 使用 CPU 计算")
            self.log("[Faster] 模型加载完成")
        else:
            self.log(f"[Faster] 复用已加载模型: {model_size}")

        return self._model, model_size

    def process(self, audio_path: str, output_srt: str) -> TranscriptionResult:
        """处理音频文件"""
        raise_if_cancelled(self.cancel_callback)
        self._max_end_time = 0.0
        model, model_size = self._get_model_runtime()

        # 获取敏感度参数
        params = self._get_sensitivity_params()

        self.log("[Faster] 开始转写...")

        # 转写 - 边收片段边处理，不等全部完成
        raise_if_cancelled(self.cancel_callback)
        segments, info = model.transcribe(
            audio_path,
            task=self.config.whisper_task,
            language=self.config.language if self.config.language != "auto" else None,
            beam_size=params.get("beam_size", self.config.beam_size),
            best_of=params.get("best_of", self.config.best_of),
            vad_filter=self.config.vad_filter,
            vad_parameters=dict(
                min_silence_duration_ms=self.config.vad_min_silence_ms,
                min_speech_duration_ms=self.config.vad_min_speech_ms,
            ),
            word_timestamps=True,  # 启用词级时间戳用于 REGROUP_JAV
        )

        self.log(f"[Faster] 检测语言: {info.language}，时长: {info.duration:.1f}s")

        # 流式收集片段并实时报告进度
        result_segments = []
        import itertools
        seg_iter = iter(segments)
        last_progress_time = 0.0
        for i, seg in enumerate(itertools.chain(seg_iter, [None]), start=1):
            raise_if_cancelled(self.cancel_callback)
            if seg is None:
                break
            result_segments.append(SubtitleSegment(
                index=i,
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text.strip(),
            ))
            # 更新最大时间
            if seg.end > self._max_end_time:
                self._max_end_time = seg.end
            # 每 2 秒音频覆盖报告一次进度
            if self._max_end_time - last_progress_time >= 2.0:
                self._report_duration_progress(self._max_end_time, info.duration)
                last_progress_time = self._max_end_time

        total_segments = len(result_segments)
        self.log(f"[Faster] 转写完成，共 {total_segments} 个片段", 84)

        return TranscriptionResult(
            segments=result_segments,
            language=info.language,
            duration=info.duration,
            source="faster-whisper",
            metadata={"model": model_size}
        )


def generate_srt(segments: list[SubtitleSegment], output_path: str):
    """生成 SRT 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            start = _ms_to_srt_time(seg.start_time * 1000)
            end = _ms_to_srt_time(seg.end_time * 1000)
            f.write(f"{seg.index}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{seg.text}\n\n")


def _ms_to_srt_time(ms: float) -> str:
    """毫秒转换为 SRT 时间格式"""
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int(ms % 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
