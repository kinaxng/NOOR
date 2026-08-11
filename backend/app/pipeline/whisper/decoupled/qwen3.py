from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from typing import Any

from .types import AlignmentResult, WordTimestamp

logger = logging.getLogger(__name__)
_SENTENCE_END_RE = re.compile(r"[。！？?!]$")
_SOFT_BREAK_RE = re.compile(r"[、，,]$")
_HARD_BREAK_RE = re.compile(r"[。！？?!」』\"]$")


def _iter_hf_repo_paths(base_dir: str, model_id: str) -> list[Path]:
    base = Path(base_dir)
    repo_dir = f"models--{model_id.replace('/', '--')}"
    return [base / repo_dir, base / "hub" / repo_dir, base / "huggingface" / "hub" / repo_dir]


def _resolve_hf_model_source(base_dir: str, model_id: str) -> tuple[str, dict[str, Any]]:
    for repo_path in _iter_hf_repo_paths(base_dir, model_id):
        if not repo_path.exists():
            continue
        ref_file = repo_path / "refs" / "main"
        if ref_file.exists():
            revision = ref_file.read_text().strip()
            snapshot_path = repo_path / "snapshots" / revision
            if snapshot_path.exists() and any(snapshot_path.iterdir()):
                return str(snapshot_path), {"local_files_only": True}
        if any(repo_path.iterdir()):
            return str(repo_path), {"local_files_only": True}
    return model_id, {"cache_dir": base_dir}


def _get_whisper_model_dir() -> str:
    from app.core.config import get_settings
    from app.core.runtime_paths import apply_whisper_cache_env, ensure_directory

    settings = get_settings()
    whisper_model_dir = ensure_directory(settings.whisper_model_dir)
    whisper_cache_dir = ensure_directory(settings.whisper_cache_dir)
    apply_whisper_cache_env(whisper_model_dir, whisper_cache_dir)
    return whisper_model_dir


def _normalize_language(language: str) -> str:
    normalized = (language or "").strip().lower()
    if normalized in {"ja", "jp", "japanese", "日本語"}:
        return "Japanese"
    if normalized in {"zh", "zh-cn", "zh-tw", "chinese", "中文"}:
        return "Chinese"
    if normalized in {"en", "english"}:
        return "English"
    return language or "Japanese"


def qwen3_aligner_available() -> bool:
    try:
        return importlib.util.find_spec("qwen_asr") is not None
    except Exception:
        return False


def merge_master_with_timestamps(master_text: str, timestamps: list[Any]) -> list[dict[str, float | str]]:
    if not master_text or not master_text.strip():
        return []
    if not timestamps:
        return [{"word": master_text.strip(), "start": 0.0, "end": 0.0}]

    def get_attr(obj: Any, attr: str):
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr)
        return None

    result: list[dict[str, float | str]] = []
    master_pos = 0
    for timestamp in timestamps:
        timestamp_word = get_attr(timestamp, "text")
        timestamp_start = get_attr(timestamp, "start_time")
        timestamp_end = get_attr(timestamp, "end_time")
        if not timestamp_word:
            continue
        word_start = master_text.find(timestamp_word, master_pos)
        if word_start == -1:
            result.append({
                "word": timestamp_word,
                "start": float(timestamp_start) if timestamp_start is not None else 0.0,
                "end": float(timestamp_end) if timestamp_end is not None else 0.0,
            })
            continue
        word_end = word_start + len(timestamp_word)
        if word_start > master_pos:
            gap = master_text[master_pos:word_start]
            if result:
                result[-1]["word"] += gap
            else:
                timestamp_word = gap + timestamp_word
        result.append({
            "word": timestamp_word,
            "start": float(timestamp_start) if timestamp_start is not None else 0.0,
            "end": float(timestamp_end) if timestamp_end is not None else 0.0,
        })
        master_pos = word_end
    if master_pos < len(master_text):
        trailing = master_text[master_pos:]
        if result:
            result[-1]["word"] += trailing
        elif trailing.strip():
            result.append({"word": trailing, "start": 0.0, "end": 0.0})
    return result


class Qwen3ForcedAligner:
    def __init__(self, *, aligner_id: str = "Qwen/Qwen3-ForcedAligner-0.6B", device: str = "auto", dtype: str = "auto") -> None:
        self.aligner_id = aligner_id
        self.device = device
        self.dtype = dtype
        self._aligner = None
        self._resolved_device = None
        self._resolved_dtype = None

    def _resolve_device_dtype(self) -> tuple[str, Any]:
        import torch
        if self.device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        elif self.device == "cuda":
            device = "cuda:0"
        else:
            device = self.device
        if self.dtype == "auto":
            if device.startswith("cuda"):
                dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            else:
                dtype = torch.float32
        else:
            dtype = getattr(torch, self.dtype)
        return device, dtype

    def load(self) -> None:
        if self._aligner is not None:
            return
        if not qwen3_aligner_available():
            raise RuntimeError("qwen-asr 未安装，无法使用 Qwen3 ForcedAligner")
        from qwen_asr.inference.qwen3_forced_aligner import Qwen3ForcedAligner as Aligner
        device, dtype = self._resolve_device_dtype()
        self._resolved_device, self._resolved_dtype = device, dtype
        source, kwargs = _resolve_hf_model_source(_get_whisper_model_dir(), self.aligner_id)
        logger.info("[Qwen3Aligner] loading %s (%s, %s)", source, device, dtype)
        self._aligner = Aligner.from_pretrained(source, dtype=dtype, device_map=device, **kwargs)

    def unload(self) -> None:
        if self._aligner is None:
            return
        self._aligner = None
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass

    def align_batch(self, *, audio_paths: list[Path], texts: list[str], language: str = "ja", audio_durations: list[float] | None = None) -> list[AlignmentResult]:
        if self._aligner is None:
            raise RuntimeError("Qwen3ForcedAligner.align_batch() called before load()")
        raw_results = self._aligner.align(audio=[str(path) for path in audio_paths], text=texts, language=_normalize_language(language))
        final_results = []
        for index, (raw, text) in enumerate(zip(raw_results, texts)):
            items = getattr(raw, "items", None)
            if items is None:
                try:
                    items = list(raw)
                except Exception:
                    items = []
            merged = merge_master_with_timestamps(text, items or [])
            final_results.append(AlignmentResult(
                words=[WordTimestamp(word=str(word["word"]), start=float(word["start"]), end=float(word["end"])) for word in merged],
                metadata={"scene_index": index, "aligner": "qwen3", "raw_word_count": len(items or []), "merged_word_count": len(merged)},
            ))
        return final_results


def split_aligned_words_into_segments(
    words: list[WordTimestamp], *, max_chars: int = 24, max_duration: float = 6.5,
    comma_break_chars: int = 14, min_chars: int = 6, min_duration: float = 1.0,
    gap_split_threshold: float = 1.5, merge_gap_threshold: float = 1.5,
    merge_char_limit: int = 42,
) -> list[tuple[float, float, str]]:
    if not words:
        return []
    segments = []
    bucket = []
    def flush() -> None:
        if not bucket:
            return
        text = "".join(item.word for item in bucket).strip()
        if text:
            segments.append((bucket[0].start, bucket[-1].end, text))
        bucket.clear()
    for word in words:
        if bucket:
            gap = max(0.0, word.start - bucket[-1].end)
            current_text = "".join(item.word for item in bucket)
            if gap >= gap_split_threshold and (_HARD_BREAK_RE.search(bucket[-1].word) or len(current_text) >= min_chars):
                flush()
        bucket.append(word)
        text = "".join(item.word for item in bucket)
        duration = max(0.0, bucket[-1].end - bucket[0].start)
        should_break = False
        if _SENTENCE_END_RE.search(word.word):
            should_break = True
        elif _SOFT_BREAK_RE.search(word.word) and len(text) >= comma_break_chars:
            should_break = True
        elif len(text) >= max_chars or duration >= max_duration:
            should_break = True
        if should_break:
            flush()
    flush()
    segments = _merge_tiny_segments(segments, max_chars=max_chars, max_duration=max_duration, min_chars=min_chars, min_duration=min_duration)
    return _merge_close_segments(segments, max_chars=max_chars, max_duration=max_duration, min_chars=min_chars, min_duration=min_duration, merge_gap_threshold=merge_gap_threshold, merge_char_limit=merge_char_limit)


def _merge_tiny_segments(segments, *, max_chars, max_duration, min_chars, min_duration):
    if len(segments) < 2:
        return segments
    merged = []
    for start, end, text in segments:
        cleaned = (text or "").strip()
        duration = max(0.0, end - start)
        is_tiny = len(cleaned) < min_chars or duration < min_duration
        punctuation_only = bool(cleaned) and all(char in "、，,。.!！？?…・" for char in cleaned)
        if merged and (is_tiny or punctuation_only):
            prev_start, prev_end, prev_text = merged[-1]
            combined_text = f"{prev_text}{cleaned}"
            combined_duration = max(0.0, end - float(prev_start))
            if len(combined_text) <= max_chars + 6 and combined_duration <= max_duration + 1.5:
                merged[-1] = [prev_start, end, combined_text]
                continue
        merged.append([start, end, cleaned])
    if len(merged) >= 2:
        last_start, last_end, last_text = merged[-1]
        last_duration = max(0.0, float(last_end) - float(last_start))
        if len(str(last_text)) < min_chars or last_duration < min_duration:
            prev_start, prev_end, prev_text = merged[-2]
            merged[-2] = [prev_start, last_end, f"{prev_text}{last_text}"]
            merged.pop()
    return [(float(start), float(end), str(text)) for start, end, text in merged if str(text).strip()]


def _merge_close_segments(segments, *, max_chars, max_duration, min_chars, min_duration, merge_gap_threshold, merge_char_limit):
    if len(segments) < 2:
        return segments
    merged = [[start, end, text] for start, end, text in segments]
    index = 1
    while index < len(merged):
        prev_start, prev_end, prev_text = merged[index - 1]
        cur_start, cur_end, cur_text = merged[index]
        gap = max(0.0, float(cur_start) - float(prev_end))
        combined_text = f"{prev_text}{cur_text}"
        combined_duration = max(0.0, float(cur_end) - float(prev_start))
        prev_tiny = len(str(prev_text).strip()) < min_chars or float(prev_end) - float(prev_start) < min_duration
        cur_tiny = len(str(cur_text).strip()) < min_chars or float(cur_end) - float(cur_start) < min_duration
        if (gap <= merge_gap_threshold and (prev_tiny or cur_tiny or _SOFT_BREAK_RE.search(str(prev_text))) and len(combined_text) <= max(merge_char_limit, max_chars) and combined_duration <= max_duration + merge_gap_threshold):
            merged[index - 1] = [prev_start, cur_end, combined_text]
            merged.pop(index)
            continue
        index += 1
    return [(float(start), float(end), str(text)) for start, end, text in merged if str(text).strip()]


class Qwen3TextGenerator:
    def __init__(self, *, model_id: str = "Qwen/Qwen3-ASR-1.7B", device: str = "auto", dtype: str = "auto", batch_size: int = 1, max_new_tokens: int = 512) -> None:
        self.model_id, self.device, self.dtype = model_id, device, dtype
        self.batch_size, self.max_new_tokens, self._model = batch_size, max_new_tokens, None

    def _resolve_device_dtype(self) -> tuple[str, Any]:
        import torch
        device = "cuda:0" if self.device == "auto" and torch.cuda.is_available() else ("cpu" if self.device == "auto" else ("cuda:0" if self.device == "cuda" else self.device))
        if self.dtype == "auto":
            dtype = (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16) if device.startswith("cuda") else torch.float32
        else:
            dtype = getattr(torch, self.dtype)
        return device, dtype

    def load(self) -> None:
        if self._model is not None:
            return
        from qwen_asr import Qwen3ASRModel
        device, dtype = self._resolve_device_dtype()
        source, kwargs = _resolve_hf_model_source(_get_whisper_model_dir(), self.model_id)
        logger.info("[Qwen3TextGen] loading %s (%s, %s)", source, device, dtype)
        self._model = Qwen3ASRModel.from_pretrained(source, dtype=dtype, device_map=device, max_inference_batch_size=self.batch_size, max_new_tokens=self.max_new_tokens, **kwargs)

    def unload(self) -> None:
        if self._model is None:
            return
        self._model = None
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache(); torch.cuda.synchronize()
        except Exception:
            pass

    def transcribe_one(self, audio_path: Path, *, language: str = "ja", context: str = "") -> str:
        if self._model is None:
            raise RuntimeError("Qwen3TextGenerator.transcribe_one() called before load()")
        result = self._model.transcribe(audio=[str(audio_path)], context=[context], language=_normalize_language(language), return_time_stamps=False)
        if not result:
            return ""
        return (getattr(result[0], "text", "") or "").strip()
