from __future__ import annotations

import re
from dataclasses import replace

from .types import SubtitleSegment, TranscriptionResult


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _best_scene_for_segment(segment: SubtitleSegment, scenes: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not scenes:
        return None
    midpoint = (segment.start_time + segment.end_time) / 2.0
    for start, end in scenes:
        if start <= midpoint <= end:
            return start, end
    return max(scenes, key=lambda scene: _overlap(segment.start_time, segment.end_time, scene[0], scene[1]))


def _split_text_ranges(text: str, max_chars: int) -> list[tuple[int, int]]:
    text_len = len(text)
    if text_len <= max_chars:
        return [(0, text_len)]

    ranges: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[。！？!?；;，、,]\s*", text):
        end = match.end()
        if end - start >= 6:
            ranges.append((start, end))
            start = end
    if text_len - start >= 1:
        ranges.append((start, text_len))

    if len(ranges) <= 1 or any(end - start > max_chars * 1.6 for start, end in ranges):
        ranges = []
        start = 0
        while start < text_len:
            end = min(text_len, start + max_chars)
            if end < text_len:
                soft_end = max(
                    text.rfind("，", start, end),
                    text.rfind("、", start, end),
                    text.rfind(",", start, end),
                    text.rfind(" ", start, end),
                )
                if soft_end > start + max(8, max_chars // 2):
                    end = soft_end + 1
            ranges.append((start, end))
            start = end

    return [(start, end) for start, end in ranges if text[start:end].strip()]


class SubtimerVadTimingRefiner:
    """Experimental VAD-boundary timing refinement inspired by subtimer.

    The upstream subtimer project combines multiple VAD/aligner stages. NOOR keeps
    this deliberately narrow: use the VAD chunk boundaries we already computed,
    then snap nearby subtitle edges and remove tiny overlaps.
    """

    def __init__(
        self,
        *,
        snap_window: float = 0.45,
        min_gap: float = 0.04,
        min_duration: float = 0.35,
        max_chars: int = 32,
    ) -> None:
        self.snap_window = snap_window
        self.min_gap = min_gap
        self.min_duration = min_duration
        self.max_chars = max_chars

    def refine(
        self,
        result: TranscriptionResult,
        scenes: list[tuple[float, float]],
    ) -> tuple[TranscriptionResult, int]:
        normalized_scenes = [
            (max(0.0, float(start)), max(0.0, float(end)))
            for start, end in scenes
            if float(end) > float(start)
        ]
        if not normalized_scenes or not result.segments:
            return result, 0

        changed = 0
        refined: list[SubtitleSegment] = []
        previous_end = -self.min_gap

        for segment in result.segments:
            scene = _best_scene_for_segment(segment, normalized_scenes)
            start = float(segment.start_time)
            end = max(start + self.min_duration, float(segment.end_time))

            if scene is not None:
                scene_start, scene_end = scene
                if abs(start - scene_start) <= self.snap_window:
                    start = scene_start
                elif scene_start > start and scene_start - start <= self.snap_window:
                    start = scene_start

                if abs(end - scene_end) <= self.snap_window:
                    end = scene_end
                elif end > scene_end and end - scene_end <= self.snap_window:
                    end = scene_end

            if start < previous_end + self.min_gap:
                start = previous_end + self.min_gap
            if end < start + self.min_duration:
                end = start + self.min_duration

            if abs(start - segment.start_time) > 0.001 or abs(end - segment.end_time) > 0.001:
                changed += 1

            split_ranges = _split_text_ranges(segment.text.strip(), self.max_chars)
            duration = max(self.min_duration, end - start)

            if len(split_ranges) > 1:
                changed += 1

            total_chars = sum(max(1, end_idx - start_idx) for start_idx, end_idx in split_ranges)
            cursor_time = start
            for range_index, (start_idx, end_idx) in enumerate(split_ranges):
                text = segment.text[start_idx:end_idx].strip()
                if not text:
                    continue
                weight = max(1, end_idx - start_idx) / total_chars
                part_duration = duration * weight
                part_start = cursor_time
                part_end = end if range_index == len(split_ranges) - 1 else min(end, part_start + part_duration)
                if part_end < part_start + self.min_duration:
                    part_end = part_start + self.min_duration
                refined.append(replace(segment, start_time=part_start, end_time=part_end, text=text))
                cursor_time = part_end
            previous_end = refined[-1].end_time if refined else end

        for index, segment in enumerate(refined, start=1):
            segment.index = index

        return (
            TranscriptionResult(
                segments=refined,
                language=result.language,
                duration=result.duration,
                source=result.source,
                metadata={
                    **result.metadata,
                    "timing_refiner": "subtimer_vad",
                    "timing_refiner_changed": changed,
                    "timing_refiner_segments": len(refined),
                },
            ),
            changed,
        )
