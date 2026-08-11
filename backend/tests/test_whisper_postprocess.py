from app.pipeline.whisper.japanese_post import JapanesePostProcessor
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
