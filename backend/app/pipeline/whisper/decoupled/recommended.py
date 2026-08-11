from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
import re

from .qwen3 import (
    Qwen3ForcedAligner,
    Qwen3TextGenerator,
    qwen3_aligner_available,
    split_aligned_words_into_segments,
)
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult, WhisperConfig


class RecommendedDecoupledProcessor:
    def __init__(
        self,
        config: WhisperConfig,
        *,
        progress_logger: Optional[Callable[[str, int | None], None]] = None,
    ) -> None:
        self.config = config
        self.progress_logger = progress_logger
        self._aligner = None
        self._text_generator = None

    @staticmethod
    def is_available() -> bool:
        return qwen3_aligner_available()

    _KANJI_RE = re.compile(r"[一-龯々]")
    _VOICE_ONLY_RE = re.compile(r"^[ぁ-んァ-ヶーっッ゛゜ゃゅょゎゐゑをん]+$")
    _LONG_REPEAT_RE = re.compile(r"る{8,}|じゅる{3,}|(?:んむ){3,}|(?:んぐ){3,}|(?:ごく){3,}")
    _NOISE_TOKENS = tuple(sorted((
        "じゅる", "ちゅる", "ごく", "んむ", "んぐ", "んっ", "はぁ",
        "あっ", "うっ", "ちゅ", "る", "ん", "っ",
    ), key=len, reverse=True))

    def _log(self, message: str, progress: int | None = None) -> None:
        if self.progress_logger is not None:
            self.progress_logger(message, progress)

    def _ensure_aligner(self) -> Qwen3ForcedAligner:
        if self._aligner is None:
            self._aligner = Qwen3ForcedAligner(device=self.config.device)
            self._aligner.load()
        return self._aligner

    def _ensure_text_generator(self) -> Qwen3TextGenerator:
        if self._text_generator is None:
            self._text_generator = Qwen3TextGenerator(device=self.config.device)
            self._text_generator.load()
        return self._text_generator

    @classmethod
    def _noise_ratio(cls, text: str) -> float:
        remaining = text
        matched = 0
        while remaining:
            found = False
            for token in cls._NOISE_TOKENS:
                if remaining.startswith(token):
                    matched += len(token)
                    remaining = remaining[len(token):]
                    found = True
                    break
            if not found:
                remaining = remaining[1:]
        return matched / max(len(text), 1)

    @classmethod
    def _should_retry_with_qwen(cls, text: str, duration: float) -> bool:
        compact = re.sub(r"[\s。、「」『』、,，.!！?？…~〜・\-]", "", text or "")
        if len(compact) < 6:
            return False
        has_kanji = bool(cls._KANJI_RE.search(compact))
        unique_ratio = len(set(compact)) / max(len(compact), 1)
        noise_ratio = cls._noise_ratio(compact)
        voice_like = bool(cls._VOICE_ONLY_RE.fullmatch(compact))
        if cls._LONG_REPEAT_RE.search(compact):
            return True
        if not has_kanji and noise_ratio >= 0.5 and duration <= 20.0:
            return True
        if voice_like and len(compact) >= 8 and unique_ratio <= 0.45:
            return True
        return False

    def _maybe_retry_with_qwen(
        self,
        audio_path: str,
        pass1_result: TranscriptionResult,
    ) -> TranscriptionResult:
        text = "".join(segment.text for segment in pass1_result.segments).strip()
        if not self._should_retry_with_qwen(text, pass1_result.duration):
            return pass1_result

        self._log("[Recommended] 命中污染段，切 Qwen3-ASR 二次识别...")
        if self._aligner is not None:
            self._aligner.unload()
            self._aligner = None
        if self._text_generator is not None:
            self._text_generator.unload()
            self._text_generator = None

        generator = self._ensure_text_generator()
        retry_text = generator.transcribe_one(
            Path(audio_path),
            language=pass1_result.language or self.config.language,
        )
        generator.unload()
        self._text_generator = None
        retry_text = retry_text.strip()
        if not retry_text:
            self._log("[Recommended] Qwen3-ASR 二次识别为空，保留 Anime 结果")
            return pass1_result
        if len(re.sub(r"\s+", "", retry_text)) < 4:
            self._log("[Recommended] Qwen3-ASR 二次识别过短，保留 Anime 结果")
            return pass1_result

        return TranscriptionResult(
            segments=[SubtitleSegment(
                index=1,
                start_time=0.0,
                end_time=pass1_result.duration,
                text=retry_text,
            )],
            language=pass1_result.language,
            duration=pass1_result.duration,
            source="qwen3-asr-fallback",
            metadata={
                **pass1_result.metadata,
                "recommended_qwen_retry": True,
                "recommended_qwen_retry_original_text": text,
            },
        )

    def cleanup(self) -> None:
        if self._aligner is not None:
            self._aligner.unload()
            self._aligner = None
        if self._text_generator is not None:
            self._text_generator.unload()
            self._text_generator = None

    def align_pass1_result(
        self,
        audio_path: str,
        pass1_result: TranscriptionResult,
    ) -> TranscriptionResult:
        pass1_result = self._maybe_retry_with_qwen(audio_path, pass1_result)
        text = "".join(segment.text for segment in pass1_result.segments).strip()
        if not text:
            return pass1_result

        aligner = self._ensure_aligner()
        self._log("[Recommended] Qwen3 ForcedAligner 对齐中...")
        alignment = aligner.align_batch(
            audio_paths=[Path(audio_path)],
            texts=[text],
            language=pass1_result.language or self.config.language,
            audio_durations=[pass1_result.duration],
        )[0]
        if not alignment.words:
            return TranscriptionResult(
                segments=pass1_result.segments,
                language=pass1_result.language,
                duration=pass1_result.duration,
                source=pass1_result.source,
                metadata={**pass1_result.metadata, "recommended_decoupled": "aligner_empty"},
            )

        regrouped = split_aligned_words_into_segments(alignment.words)
        segments = [
            SubtitleSegment(index=index + 1, start_time=start, end_time=end, text=text)
            for index, (start, end, text) in enumerate(regrouped)
        ]
        return TranscriptionResult(
            segments=segments or pass1_result.segments,
            language=pass1_result.language,
            duration=pass1_result.duration,
            source="anime-qwen3-aligned",
            metadata={
                **pass1_result.metadata,
                "recommended_decoupled": "qwen3_forced_aligner",
                "aligned_word_count": len(alignment.words),
                "aligned_segment_count": len(segments),
            },
        )
