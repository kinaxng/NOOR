from __future__ import annotations

import re
from dataclasses import dataclass

from app.tasks.job_phases import get_phase_label, normalize_phase_key


@dataclass(frozen=True)
class ProgressPhase:
    key: str
    label: str
    start_pct: int
    end_pct: int
    description: str = ""


PHASES = {
    "prepare": ProgressPhase("prepare", "准备任务", 0, 3, "读取配置和准备运行环境"),
    "extract_audio": ProgressPhase("extract_audio", "提取音频", 3, 10, "从视频提取音频流"),
    "segment": ProgressPhase("segment", "音频分段", 10, 20, "Smart VAD 准备连续音频块"),
    "transcribe_primary": ProgressPhase("transcribe_primary", "生成字幕", 20, 88, "执行所选 ASR 模型"),
    "postprocess": ProgressPhase("postprocess", "后处理", 88, 94, "整理字幕文本与断句"),
    "align": ProgressPhase("align", "调整时间轴", 94, 97, "可选 Subtimer VAD 时间轴微调"),
    "write_output": ProgressPhase("write_output", "写出字幕", 97, 100, "输出最终字幕文件"),
}
WHISPER_PROGRESS_PHASE_ORDER = tuple(PHASES)


@dataclass
class ProgressUpdate:
    phase_key: str
    phase_label: str
    phase_progress: float
    overall_progress: int
    detail: str
    line: str = ""


class AsyncProgressReporter:
    PHASE_PATTERNS = (
        (r"开始 Whisper 字幕生成|Whisper 架构", "prepare"),
        (r"Phase 1: 提取音频|音频提取", "extract_audio"),
        (r"Smart VAD|安全连续块", "segment"),
        (r"处理段落|\[Faster\]|\[Anime\]|开始转写|转写完成", "transcribe_primary"),
        (r"日语后处理|后处理完成", "postprocess"),
        (r"subtimer-vad|时间轴微调", "align"),
        (r"字幕已保存|生成 SRT|SRT 已保存", "write_output"),
    )

    def __init__(self, job_id: str, event_queue, audio_duration: float = 0.0):
        self.job_id = job_id
        self.event_queue = event_queue
        self.audio_duration = audio_duration
        self.current_phase_key = "prepare"

    def _update_phase(self, line: str) -> None:
        for pattern, key in self.PHASE_PATTERNS:
            if re.search(pattern, line, re.I):
                self.current_phase_key = key
                return

    def parse_line(self, line: str) -> ProgressUpdate | None:
        self._update_phase(line)
        return self._build_update(line)

    def _build_update(self, line: str) -> ProgressUpdate | None:
        phase = PHASES.get(self.current_phase_key)
        if not phase:
            return None
        progress = self._infer_phase_progress(phase.key, line)
        overall = min(100, max(phase.start_pct, int(phase.start_pct + (phase.end_pct - phase.start_pct) * progress)))
        if phase.key == "write_output" and progress >= 1:
            overall = 100
        normalized = normalize_phase_key(phase.key) or phase.key
        return ProgressUpdate(
            phase_key=normalized,
            phase_label=get_phase_label(phase.key, phase.label) or phase.label,
            phase_progress=progress,
            overall_progress=overall,
            detail=self._infer_detail(phase.key, line, progress),
            line=line,
        )

    @staticmethod
    def _infer_phase_progress(phase_key: str, line: str) -> float:
        match = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if match and phase_key in {"segment", "transcribe_primary"}:
            return min(1.0, max(0.0, int(match.group(1)) / max(1, int(match.group(2)))))
        if phase_key == "write_output" and re.search(r"字幕已保存|SRT 已保存", line):
            return 1.0
        if phase_key == "postprocess" and "完成" in line:
            return 1.0
        if phase_key == "align" and ("调整" in line or "失败" in line):
            return 1.0
        if phase_key == "extract_audio" and "完成" in line:
            return 1.0
        return 0.0

    @staticmethod
    def _infer_detail(phase_key: str, line: str, phase_progress: float) -> str:
        match = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if match and phase_key == "transcribe_primary":
            return f"已转写 {match.group(1)} / {match.group(2)} 段"
        return {
            "prepare": "初始化字幕任务",
            "extract_audio": "提取视频音频流",
            "segment": "Smart VAD 准备音频块",
            "transcribe_primary": "执行所选 ASR 模型",
            "postprocess": "整理字幕文本与格式",
            "align": "调整字幕时间轴",
            "write_output": "写出最终字幕文件",
        }.get(phase_key, f"{int(phase_progress * 100)}%")
