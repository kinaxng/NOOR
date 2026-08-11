from pathlib import Path

import pytest

from app.pipeline.whisper import orchestrator
from app.pipeline.whisper.progress import AsyncProgressReporter
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult, WhisperConfig


@pytest.mark.asyncio
async def test_run_task_forwards_numeric_progress(monkeypatch, tmp_path: Path):
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"")
    task = orchestrator.create_task(str(video), WhisperConfig())
    updates = []

    async def fake_process(self, video_path, video_name=""):
        self.log("正在转写", 42)
        result = TranscriptionResult(
            segments=[SubtitleSegment(index=1, start_time=0, end_time=1, text="测试")],
            language="zh",
            duration=1,
            source="test",
        )
        return result, str(tmp_path / "sample.zh.srt")

    monkeypatch.setattr(orchestrator.WhisperPipeline, "process", fake_process)

    await orchestrator.run_whisper_task(
        task.id,
        progress_callback=lambda **payload: updates.append(payload),
    )

    assert updates == [{"progress": 42, "detail": "正在转写"}]
    assert task.progress == 100
    assert task.status == "completed"


def test_progress_reporter_maps_faster_logs_to_transcribe_phase():
    reporter = AsyncProgressReporter("job", None)
    update = reporter.parse_line("处理段落 2/4: 30.0s - 60.0s")

    assert update is not None
    assert update.phase_key == "transcribe"
    assert update.phase_progress == 0.5
    assert update.detail == "已转写 2 / 4 段"


def test_progress_reporter_marks_saved_subtitle_complete():
    reporter = AsyncProgressReporter("job", None)
    update = reporter.parse_line("字幕已保存: /tmp/sample.zh.srt")

    assert update is not None
    assert update.phase_key == "output"
    assert update.overall_progress == 100
