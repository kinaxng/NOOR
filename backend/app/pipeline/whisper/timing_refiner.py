from __future__ import annotations

from dataclasses import replace

from .types import SubtitleSegment, TranscriptionResult


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _best_scene_for_segment(
    segment: SubtitleSegment,
    scenes: list[tuple[float, float]],
) -> tuple[float, float] | None:
    if not scenes:
        return None
    midpoint = (segment.start_time + segment.end_time) / 2.0
    for start, end in scenes:
        if start <= midpoint <= end:
            return start, end
    return max(scenes, key=lambda scene: _overlap(segment.start_time, segment.end_time, *scene))


class SubtimerVadTimingRefiner:
    def __init__(self, *, snap_window: float = 0.45, min_gap: float = 0.04, min_duration: float = 0.35) -> None:
        self.snap_window = snap_window
        self.min_gap = min_gap
        self.min_duration = min_duration

    def refine(
        self,
        result: TranscriptionResult,
        scenes: list[tuple[float, float]],
    ) -> tuple[TranscriptionResult, int]:
        normalized = [(max(0.0, float(start)), max(0.0, float(end))) for start, end in scenes if end > start]
        if not normalized or not result.segments:
            return result, 0

        changed = 0
        previous_end = 0.0
        refined: list[SubtitleSegment] = []
        for segment in result.segments:
            scene = _best_scene_for_segment(segment, normalized)
            start = float(segment.start_time)
            end = max(start + self.min_duration, float(segment.end_time))
            if scene:
                scene_start, scene_end = scene
                if abs(start - scene_start) <= self.snap_window:
                    start = scene_start
                if abs(end - scene_end) <= self.snap_window:
                    end = scene_end
            if start < previous_end + self.min_gap:
                start = previous_end + self.min_gap
            end = max(end, start + self.min_duration)
            if abs(start - segment.start_time) > 0.001 or abs(end - segment.end_time) > 0.001:
                changed += 1
            refined.append(replace(segment, start_time=start, end_time=end))
            previous_end = end

        for index, segment in enumerate(refined, start=1):
            segment.index = index
        return TranscriptionResult(
            segments=refined,
            language=result.language,
            duration=result.duration,
            source=result.source,
            metadata={**result.metadata, "timing_refiner": "subtimer_vad", "timing_refiner_changed": changed},
        ), changed
