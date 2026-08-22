from __future__ import annotations

from app.pipeline.whisper.timing_refiner import SubtimerVadTimingRefiner
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult


def test_subtimer_vad_refiner_snaps_edges_and_removes_overlap():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(index=1, start_time=0.18, end_time=2.82, text="第一句"),
            SubtitleSegment(index=2, start_time=2.80, end_time=5.72, text="第二句"),
        ],
        language="zh",
        duration=6.0,
        source="test",
    )

    refined, changed = SubtimerVadTimingRefiner().refine(result, [(0.0, 2.9), (2.95, 5.8)])

    assert changed == 2
    assert refined.segments[0].start_time == 0.0
    assert refined.segments[0].end_time == 2.9
    assert refined.segments[1].start_time >= refined.segments[0].end_time + 0.04
    assert refined.segments[1].end_time == 5.8
    assert refined.metadata["timing_refiner"] == "subtimer_vad"


def test_subtimer_vad_refiner_splits_long_subtitle_text():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(
                index=1,
                start_time=0.0,
                end_time=12.0,
                text="这是第一句非常长的中文字幕，需要被拆开，第二句也很长，需要继续拆分，第三句用于验证标点优先。",
            ),
        ],
        language="zh",
        duration=12.0,
        source="test",
    )

    refined, changed = SubtimerVadTimingRefiner(max_chars=18).refine(
        result,
        [(0.0, 12.0)],
    )

    assert changed >= 1
    assert len(refined.segments) > 1
    assert all(len(segment.text) <= 22 for segment in refined.segments)
    assert refined.segments[0].start_time == 0.0
    assert refined.segments[-1].end_time == 12.0
    assert [segment.index for segment in refined.segments] == list(range(1, len(refined.segments) + 1))


def test_subtimer_vad_refiner_does_not_split_short_text_by_duration():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(index=1, start_time=0.0, end_time=20.0, text="短句不要切"),
        ],
        language="zh",
        duration=20.0,
        source="test",
    )

    refined, _ = SubtimerVadTimingRefiner(max_chars=18).refine(result, [(0.0, 20.0)])

    assert len(refined.segments) == 1
    assert refined.segments[0].text == "短句不要切"
    assert refined.segments[0].start_time == 0.0
    assert refined.segments[0].end_time == 20.0
