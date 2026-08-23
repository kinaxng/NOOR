from app.pipeline.whisper.japanese_post import JapanesePostProcessor, SubtitleSafetyPostProcessor
from app.pipeline.whisper.types import SubtitleSegment, TranscriptionResult


def test_postprocessor_keeps_timeline_order_and_reindexes():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(index=9, start_time=0, end_time=2, text="これはテストです。"),
            SubtitleSegment(index=4, start_time=2.1, end_time=4, text="次の文章です。"),
        ],
        language="ja",
        duration=4,
        source="test",
    )

    processed = JapanesePostProcessor().process(result)

    assert processed.segments
    assert [segment.index for segment in processed.segments] == list(range(1, len(processed.segments) + 1))
    assert [segment.start_time for segment in processed.segments] == sorted(segment.start_time for segment in processed.segments)


def test_postprocessor_handles_empty_result():
    result = TranscriptionResult([], "ja", 0, "test")
    assert JapanesePostProcessor().process(result) is result


def test_safety_postprocessor_merges_close_segments_and_caps_duration():
    result = TranscriptionResult(
        segments=[
            SubtitleSegment(index=1, start_time=0.0, end_time=1.0, text="第一句"),
            SubtitleSegment(index=2, start_time=1.2, end_time=2.2, text="第二句"),
            SubtitleSegment(index=3, start_time=10.0, end_time=30.0, text="长片段"),
        ],
        language="zh",
        duration=30.0,
        source="test",
    )

    processed = SubtitleSafetyPostProcessor(max_segment_duration=5.0).process(result)

    assert processed.metadata["safety_post_processed"] is True
    assert processed.segments
    first_two = [seg for seg in processed.segments if "第一句" in seg.text or "第二句" in seg.text]
    assert len(first_two) == 1
    long_segment = next(seg for seg in processed.segments if "长片段" in seg.text)
    assert long_segment.end_time - long_segment.start_time <= 5.0
    assert all(segment.end_time > segment.start_time for segment in processed.segments)
