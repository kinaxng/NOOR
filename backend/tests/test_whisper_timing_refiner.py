from app.pipeline.whisper.timing_refiner import SubtimerVadTimingRefiner
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult


def test_subtimer_vad_refiner_snaps_edges_and_removes_overlap():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(1, 0.2, 2.8, "第一句"),
            SubtitleSegment(2, 2.75, 5.2, "第二句"),
        ],
        language="zh",
        duration=6.0,
        source="test",
    )
    refined, changed = SubtimerVadTimingRefiner().refine(result, [(0.0, 3.0), (3.0, 5.0)])
    assert changed == 2
    assert refined.segments[0].start_time == 0.04
    assert refined.segments[0].end_time == 3.0
    assert refined.segments[1].start_time >= 3.04
    assert refined.segments[1].end_time >= refined.segments[1].start_time + 0.35
    assert refined.metadata["timing_refiner"] == "subtimer_vad"
