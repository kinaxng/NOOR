"""Whisper 字幕生成引擎"""
import os
import asyncio
import subprocess
import warnings
from pathlib import Path
from typing import Optional, Callable
import tempfile

warnings.filterwarnings("ignore", message=".*chunk_length_s.*is very experimental.*")

from .types import (
    WhisperConfig, WhisperModel, PipelineMode, MergeStrategy,
    WhisperCancellationRequested,
    SubtitleSegment, TranscriptionResult, WhisperTask
)
from .runtime import raise_if_cancelled, run_cancellable_subprocess


def _iter_hf_repo_paths(base_dir: str, model_id: str) -> list[Path]:
    base = Path(base_dir)
    repo_dir = f"models--{model_id.replace('/', '--')}"
    return [
        base / repo_dir,
        base / "hub" / repo_dir,
        base / "huggingface" / "hub" / repo_dir,
    ]


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
    """Anime-Whisper 处理 (Pass1) — 直接用 transformers 低层 API，避免 pipeline 的 mel feature 限制"""

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
            self.log("[Pass1] 错误: 需要安装 transformers 和 torch")
            raise RuntimeError("anime-whisper 需要 transformers 库")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model_id = "litagin/anime-whisper"
        self.log(f"[Pass1] 加载模型: {model_id} (device: {device}), cache: {whisper_model_dir}")
        load_source, load_kwargs = _resolve_hf_model_source(whisper_model_dir, model_id)
        if load_kwargs.get("local_files_only"):
            self.log("[Pass1] 检测到本地缓存，离线加载 anime-whisper")

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
            self.log("[Pass1] 使用 fallback 加载方式（device 参数）")
            self._processor = AutoProcessor.from_pretrained(load_source, **load_kwargs)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                load_source,
                torch_dtype=dtype,
                **load_kwargs,
            ).to(device)

        self._device = device
        self._dtype = dtype

        if torch.cuda.is_available():
            self.log(f"[Pass1] GPU: {torch.cuda.get_device_name(0)}")
        self.log("[Pass1] 模型加载完成", 10)

    def process(self, audio_path: str, output_srt: str) -> TranscriptionResult:
        """同步处理音频文件"""
        import traceback
        import torch
        import numpy as np

        raise_if_cancelled(self.cancel_callback)
        self._ensure_model()

        self.log(f"[Pass1] 开始转写: {audio_path}", 20)

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

            self.log(f"[Pass1] 转写完成，文本长度: {len(text)} 字符", 90)

            # anime-whisper 不返回时间戳，用整个音频时长作为单一段落
            # JapanesePostProcessor 会做断句处理

            raise_if_cancelled(self.cancel_callback)
            text = self._processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

            self.log(f"[Pass1] 转写完成，文本长度: {len(text)} 字符", 90)

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
            self.log(f"[Pass1] 异常: {type(e).__name__}: {e}\n{traceback.format_exc()[:500]}")
            raise


class ReazonNemoProcessor:
    """ReazonSpeech NeMo v2 processor."""

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
        self._model = None
        self._model_path = None
        self._device = None

    def log(self, msg: str, progress: int = None):
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)

    def _ensure_model(self):
        if self._model is not None:
            return
        raise_if_cancelled(self.cancel_callback)

        from app.core.config import DEFAULT_REAZON_NEMO_MODEL_PATH, get_settings
        settings = get_settings()
        model_path = Path(getattr(settings, "reazon_nemo_model_path", DEFAULT_REAZON_NEMO_MODEL_PATH) or DEFAULT_REAZON_NEMO_MODEL_PATH)
        if not model_path.exists():
            raise RuntimeError(f"Reazon / NeMo model not found: {model_path}")

        try:
            from nemo.collections.asr.models import ASRModel
            import torch
        except ImportError as exc:
            raise RuntimeError("Reazon / NeMo runtime requires nemo_toolkit") from exc

        device = "cuda" if self.config.device == "auto" and torch.cuda.is_available() else (self.config.device if self.config.device != "auto" else "cpu")
        map_location = device if device != "cuda" else ("cuda" if torch.cuda.is_available() else "cpu")
        self.log(f"[Reazon] 加载模型: {model_path} (device: {map_location})")
        self._model = ASRModel.restore_from(restore_path=str(model_path), map_location=map_location)
        self._model_path = model_path
        self._device = map_location
        self.log("[Reazon] 模型加载完成", 10)

    def process(self, audio_path: str, output_srt: str) -> TranscriptionResult:
        raise_if_cancelled(self.cancel_callback)
        self._ensure_model()
        self.log(f"[Reazon] 开始转写: {audio_path}", 20)

        import soundfile as sf
        info = sf.info(audio_path)
        duration = float(info.frames) / float(info.samplerate or 16000)

        hypotheses = self._model.transcribe([audio_path], batch_size=1)
        if isinstance(hypotheses, tuple):
            hypotheses = hypotheses[0]
        if not hypotheses:
            text = ""
        else:
            first = hypotheses[0]
            text = getattr(first, "text", None) or (first if isinstance(first, str) else str(first))
        text = (text or "").strip()

        self.log(f"[Reazon] 转写完成，文本长度: {len(text)} 字符", 90)
        segments = [SubtitleSegment(index=1, start_time=0.0, end_time=duration, text=text)] if text else []
        return TranscriptionResult(
            segments=segments,
            language="ja",
            duration=duration,
            source="reazon-nemo",
            metadata={"model": str(self._model_path), "device": self._device},
        )


class FasterWhisperProcessor:
    """Faster-Whisper 处理 (Pass2)"""

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
        # Pass2 阶段映射: 28-85%
        pct = int(28 + coverage * 57)
        pct = min(84, pct)
        self.log(f"[Pass2] 音频覆盖 {current_time:.0f}s / {total_duration:.0f}s", pct)

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
            self.log("[Pass2] 错误: 需要安装 faster-whisper")
            raise RuntimeError("faster-whisper 库未安装")

        model_size = self.config.pass2_model.value

        from app.core.config import get_settings
        settings = get_settings()
        whisper_model_dir = settings.whisper_model_dir or "/volume1/models"

        device = "cuda" if self.config.device == "auto" else self.config.device
        compute_type = self.config.compute_type if self.config.compute_type != "default" else "float16"
        signature = (model_size, device, compute_type, whisper_model_dir)

        if self._model is None or self._model_signature != signature:
            self.log(f"[Pass2] 加载模型: {model_size} (dir: {whisper_model_dir})")
            self.log(f"[Pass2] 使用设备: {device}, compute: {compute_type}")
            load_source, load_kwargs = _resolve_faster_whisper_model_source(whisper_model_dir, model_size)
            if not load_kwargs:
                self.log(f"[Pass2] 检测到本地 CTranslate2 缓存，离线加载: {load_source}")
            self._model = WhisperModel(
                load_source,
                device=device,
                compute_type=compute_type,
                **load_kwargs,
            )
            self._model_signature = signature

            import torch
            if device == "cuda" and torch.cuda.is_available():
                self.log(f"[Pass2] GPU 已激活: {torch.cuda.get_device_name(0)}")
            else:
                self.log("[Pass2] 警告: 使用 CPU 计算")
            self.log("[Pass2] 模型加载完成")
        else:
            self.log(f"[Pass2] 复用已加载模型: {model_size}")

        return self._model, model_size

    def process(self, audio_path: str, output_srt: str) -> TranscriptionResult:
        """处理音频文件"""
        raise_if_cancelled(self.cancel_callback)
        self._max_end_time = 0.0
        model, model_size = self._get_model_runtime()

        # 获取敏感度参数
        params = self._get_sensitivity_params()

        self.log("[Pass2] 开始转写...")

        # 转写 - 边收片段边处理，不等全部完成
        raise_if_cancelled(self.cancel_callback)
        segments, info = model.transcribe(
            audio_path,
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

        self.log(f"[Pass2] 检测语言: {info.language}，时长: {info.duration:.1f}s")

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
        self.log(f"[Pass2] 转写完成，共 {total_segments} 个片段", 84)

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


class KotobaWhisperProcessor:
    """Kotoba-Whisper-v2.2 处理 — 直接用 transformers 低层 API，不依赖 stable_whisper"""

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
        self._processor = None
        self._model = None
        self._device = None
        self._dtype = None

    def log(self, msg: str, progress: int = None):
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)
            except Exception:
                pass

    def _ensure_model(self):
        """延迟加载模型（只加载一次）"""
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

        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model_id = "kotoba-tech/kotoba-whisper-v2.2"
        self.log(f"[Kotoba] 加载模型: {model_id} (device: {device}), cache: {whisper_model_dir}")
        load_source, load_kwargs = _resolve_hf_model_source(whisper_model_dir, model_id)
        if load_kwargs.get("local_files_only"):
            self.log("[Kotoba] 检测到本地缓存，离线加载 kotoba-whisper")

        self._processor = AutoProcessor.from_pretrained(load_source, **load_kwargs)
        self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
            load_source,
            torch_dtype=dtype,
            **load_kwargs,
        ).to(device)

        self._device = device
        self._dtype = dtype

        if torch.cuda.is_available():
            self.log(f"[Kotoba] GPU: {torch.cuda.get_device_name(0)}")
        self.log("[Kotoba] 模型加载完成", 10)

    def _load_audio(self, audio_path: str):
        """加载音频为 float32 numpy 数组，16kHz mono"""
        import librosa
        try:
            audio, _sr = librosa.load(audio_path, sr=16000)
            return audio
        except Exception:
            import soundfile as sf
            audio, sr = sf.read(audio_path)
            if sr != 16000:
                import librosa as _librosa
                audio = _librosa.resample(audio, orig_sr=sr, target_sr=16000)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            return audio.astype(float)

    def process(self, audio_path: str, output_srt: str = "") -> TranscriptionResult:
        """处理音频文件"""
        import traceback
        import torch
        import numpy as np

        raise_if_cancelled(self.cancel_callback)
        self._ensure_model()

        self.log(f"[Kotoba] 开始转写: {audio_path}", 20)

        try:
            raise_if_cancelled(self.cancel_callback)
            audio = self._load_audio(audio_path)
            audio_len = len(audio) / 16000.0

            raise_if_cancelled(self.cancel_callback)
            inputs = self._processor(
                audio, sampling_rate=16000, return_tensors="pt"
            )
            input_features = inputs.input_features.to(self._device, dtype=self._dtype)

            # 生成
            with torch.no_grad():
                output_ids = self._model.generate(
                    input_features,
                    language="ja",
                    task="transcribe",
                    do_sample=False,
                    num_beams=3,
                    max_new_tokens=440,
                )

            raise_if_cancelled(self.cancel_callback)
            self.log(f"[Kotoba] 解码中...", 70)

            # 提取 sequences tensor（先移到 CPU 再转 numpy）
            seq = output_ids
            if hasattr(output_ids, 'sequences'):
                seq = output_ids.sequences
            seq = seq.cpu().numpy()
            seq = np.atleast_1d(seq)

            text = self._processor.batch_decode(seq, skip_special_tokens=True)[0].strip()

            # 能量切分
            self.log(f"[Kotoba] 能量切分...", 75)
            boundaries = self._energy_segment(audio, sample_rate=16000)

            # 按字符数比例分配文本到各段
            total_chars = len(text) if text else 1
            segments = []
            idx = 1

            for b_start, b_end in boundaries:
                seg_dur = b_end - b_start
                seg_ratio = seg_dur / audio_len if audio_len > 0 else 1.0 / len(boundaries)
                n_chars = max(1, int(round(total_chars * seg_ratio)))

                if n_chars >= len(text):
                    seg_text = text
                    text = ""
                else:
                    seg_text = text[:n_chars]
                    text = text[n_chars:]

                if seg_text.strip():
                    segments.append(SubtitleSegment(
                        index=idx, start_time=b_start, end_time=b_end, text=seg_text,
                    ))
                    idx += 1

            self.log(f"[Kotoba] 转写完成: {len(segments)} 片段", 85)
            return TranscriptionResult(
                segments=segments,
                language="ja",
                duration=audio_len,
                source="kotoba-whisper-v2.2",
                metadata={"model": "kotoba-tech/kotoba-whisper-v2.2"},
            )

        except Exception as e:
            self.log(f"[Kotoba] 异常: {type(e).__name__}: {e}\n{traceback.format_exc()[:500]}")
            raise

    def _energy_segment(self, audio, sample_rate: int = 16000) -> list:
        """基于能量的切分 + 相邻短片段合并，返回 [(start, end), ...] 时间戳"""
        import numpy as np
        try:
            import librosa
        except Exception:
            return [(0.0, len(audio) / sample_rate)]

        try:
            rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=512)[0]
            times = librosa.times_like(rms, sr=sample_rate, hop_length=512)
            threshold = np.max(rms) * 0.15
            is_speech = rms > threshold

            raw_segments = []
            in_speech = False
            seg_start = 0.0

            for t, speech in zip(times, is_speech):
                if speech and not in_speech:
                    seg_start = t
                    in_speech = True
                elif not speech and in_speech:
                    if t - seg_start >= 0.8:
                        raw_segments.append((seg_start, t))
                    in_speech = False

            if in_speech and times[-1] - seg_start >= 0.8:
                raw_segments.append((seg_start, times[-1]))

            if not raw_segments:
                return [(0.0, len(audio) / sample_rate)]

            # 合并过短片段（< 2s）到最近邻居
            MIN_DUR = 2.0
            merged = []
            for seg in raw_segments:
                dur = seg[1] - seg[0]
                if dur >= MIN_DUR or not merged:
                    merged.append(list(seg))
                else:
                    # 合并到前一个
                    merged[-1][1] = seg[1]

            return [(m[0], m[1]) for m in merged]
        except Exception:
            return [(0.0, len(audio) / sample_rate)]

    def _vad_segment(self, audio, sample_rate: int = 16000) -> list:
        """用 Silero VAD 切分音频（备用）"""
        return []  # 暂时禁用，改用 _energy_segment




class ColiProcessor:
    """coli ASR 处理（本地离线）— 使用 sensevoice 模型"""

    MODEL_SENSEVOICE = "sensevoice"

    def __init__(self, config: WhisperConfig, progress_callback: Optional[Callable] = None):
        self.config = config
        self.progress_callback = progress_callback
        self._log_lines = []

    def log(self, msg: str, progress: int = None):
        self._log_lines.append(msg)
        if self.progress_callback:
            try:
                self.progress_callback(msg, progress)
            except TypeError:
                self.progress_callback(msg)

    @staticmethod
    def check_installed() -> tuple[bool, str]:
        """检查 coli 是否已安装"""
        try:
            r = subprocess.run(
                ["coli", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                version = r.stdout.strip() or "unknown"
                return (True, version)
            return (False, r.stderr.strip() or "exit code " + str(r.returncode))
        except FileNotFoundError:
            return (False, "coli command not found")
        except Exception as e:
            return (False, str(e))

    def process(self, audio_path: str) -> TranscriptionResult:
        """执行 coli ASR 转录"""
        import json

        # 检查 coli 是否安装
        installed, version = self.check_installed()
        if not installed:
            raise RuntimeError(f"coli 未安装: {version}。请运行: npm install -g @marswave/coli")

        self.log(f"[Coli] 使用 coli ASR 处理: {audio_path}")
        self.log(f"[Coli] 版本: {version}")
        self.log("[Coli] 开始转写...", 20)

        # 调用 coli asr -j 获取 JSON 输出
        cmd = ["coli", "asr", "-j", str(audio_path)]
        self.log(f"[Coli] 执行: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("coli ASR 执行超时（5分钟）")

        if result.returncode != 0:
            raise RuntimeError(f"coli ASR 执行失败: {result.stderr}")

        # 解析 JSON 输出
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"coli ASR 输出解析失败: {e}\n原始输出: {result.stdout[:500]}")

        self.log("[Coli] 解析完成", 80)

        # 提取转录结果
        # coli JSON 格式: { "text": "...", "segments": [{ "start": float, "end": float, "text": "..." }], "language": "..." }
        text = output.get("text", "").strip()
        segments_data = output.get("segments", [])
        detected_language = output.get("language", self.config.language or "auto")

        # 获取音频时长
        duration = 0.0
        if segments_data:
            # 从最后一个片段的 end_time 获取总时长
            duration = segments_data[-1].get("end", 0.0) if segments_data else 0.0

        # 转换为 SubtitleSegment
        segments = []
        for i, seg in enumerate(segments_data, start=1):
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            seg_text = seg.get("text", "").strip()
            if seg_text:  # 跳过空片段
                segments.append(SubtitleSegment(
                    index=i,
                    start_time=start,
                    end_time=end,
                    text=seg_text,
                ))

        # 如果没有片段但有文本，创建一个完整片段
        if not segments and text:
            segments.append(SubtitleSegment(
                index=1,
                start_time=0.0,
                end_time=duration if duration > 0 else 0.0,
                text=text,
            ))

        self.log(f"[Coli] 转写完成，共 {len(segments)} 个片段，检测语言: {detected_language}", 100)

        return TranscriptionResult(
            segments=segments,
            language=detected_language,
            duration=duration,
            source="coli-sensevoice",
            metadata={"version": version},
        )
