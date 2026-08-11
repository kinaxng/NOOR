"""Audio scene detection for splitting long recordings into natural segments."""

from dataclasses import dataclass

import librosa
import numpy as np


@dataclass
class AudioSegment:
    start: float
    end: float
    duration: float


class AudioSceneDetector:
    """Detect acoustic boundaries using silence energy or MFCC changes."""

    def __init__(
        self,
        mode: str = "energy",
        min_silence_duration: float = 1.0,
        min_segment_duration: float = 10.0,
        energy_threshold: float = 0.01,
        hop_length: int = 512,
        frame_length: int = 2048,
        max_segment_duration: float | None = 18.0,
    ):
        self.mode = mode
        self.min_silence_duration = min_silence_duration
        self.min_segment_duration = min_segment_duration
        self.energy_threshold = energy_threshold
        self.hop_length = hop_length
        self.frame_length = frame_length
        self.max_segment_duration = max_segment_duration

    def detect(self, audio_path: str) -> list[AudioSegment]:
        if self.mode == "semantic":
            return self._detect_semantic(audio_path)
        return self._detect_energy(audio_path)

    def _detect_energy(self, audio_path: str) -> list[AudioSegment]:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        duration = len(y) / sr
        rms = librosa.feature.rms(
            y=y,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
            center=True,
        )[0]
        times = librosa.times_like(rms, sr=sr, hop_length=self.hop_length)
        is_silence = rms < self.energy_threshold

        boundaries = []
        in_silence = False
        silence_start = 0.0
        for _, (time_position, silent) in enumerate(zip(times, is_silence)):
            if silent and not in_silence:
                in_silence = True
                silence_start = time_position
            elif not silent and in_silence:
                in_silence = False
                if time_position - silence_start >= self.min_silence_duration:
                    boundaries.append((silence_start, time_position))

        if not boundaries:
            return self._split_long_segments(
                y,
                sr,
                [AudioSegment(start=0.0, end=duration, duration=duration)],
            )

        segments = []
        segment_start = 0.0
        for boundary_start, boundary_end in boundaries:
            if boundary_start - segment_start >= 1.0:
                segments.append(AudioSegment(
                    start=segment_start,
                    end=boundary_start,
                    duration=boundary_start - segment_start,
                ))
            segment_start = boundary_end
        if duration - segment_start >= 1.0:
            segments.append(AudioSegment(
                start=segment_start,
                end=duration,
                duration=duration - segment_start,
            ))

        segments = self._merge_short_segments(segments)
        return self._split_long_segments(y, sr, segments)

    def _detect_semantic(self, audio_path: str) -> list[AudioSegment]:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        duration = len(y) / sr
        hop = int(0.5 * sr)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, hop_length=hop)
        mfcc_delta = librosa.feature.delta(mfcc)
        features = np.vstack([mfcc, mfcc_delta]).T

        norms = np.linalg.norm(features, axis=1, keepdims=True)
        norms[norms == 0] = 1
        features = features / norms

        distances = []
        for index in range(1, len(features)):
            distance = np.arccos(
                np.clip(np.dot(features[index], features[index - 1]), -1, 1)
            )
            distances.append(distance)
        distances = np.array(distances)

        window = max(3, int(2.0 / 0.5))
        if len(distances) > window:
            kernel = np.ones(window) / window
            distances_smooth = np.convolve(distances, kernel, mode="same")
        else:
            distances_smooth = distances
        threshold = np.mean(distances_smooth) + 0.8 * np.std(distances_smooth)

        peaks = []
        for index in range(1, len(distances_smooth) - 1):
            if (
                distances_smooth[index] > threshold
                and distances_smooth[index] >= distances_smooth[index - 1]
                and distances_smooth[index] >= distances_smooth[index + 1]
            ):
                peaks.append((index + 1) * 0.5)

        if not peaks:
            return self._split_long_segments(
                y,
                sr,
                [AudioSegment(start=0.0, end=duration, duration=duration)],
            )

        minimum_gap = self.min_segment_duration * 0.5
        filtered = []
        last = 0.0
        for boundary in peaks:
            if boundary - last >= minimum_gap:
                filtered.append(boundary)
                last = boundary
        if not filtered:
            return self._split_long_segments(
                y,
                sr,
                [AudioSegment(start=0.0, end=duration, duration=duration)],
            )

        segments = []
        segment_start = 0.0
        for boundary in filtered:
            if boundary - segment_start >= 1.0:
                segments.append(AudioSegment(
                    start=segment_start,
                    end=boundary,
                    duration=boundary - segment_start,
                ))
            segment_start = boundary
        if duration - segment_start >= 1.0:
            segments.append(AudioSegment(
                start=segment_start,
                end=duration,
                duration=duration - segment_start,
            ))

        segments = self._merge_short_segments(segments)
        return self._split_long_segments(y, sr, segments)

    def _merge_short_segments(self, segments: list[AudioSegment]) -> list[AudioSegment]:
        if len(segments) < 2:
            return segments

        merged = [segments[0]]
        for segment in segments[1:]:
            if segment.duration < self.min_segment_duration and merged:
                previous = merged[-1]
                previous.end = segment.end
                previous.duration = previous.end - previous.start
            else:
                merged.append(segment)
        return merged

    def _split_long_segments(
        self,
        y: np.ndarray,
        sr: int,
        segments: list[AudioSegment],
    ) -> list[AudioSegment]:
        """Split long segments near low-energy points around the target duration."""
        if not self.max_segment_duration or self.max_segment_duration <= 0:
            return segments

        rms = librosa.feature.rms(
            y=y,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
            center=True,
        )[0]
        times = librosa.times_like(rms, sr=sr, hop_length=self.hop_length)
        split_segments: list[AudioSegment] = []
        search_radius = min(4.0, self.max_segment_duration * 0.25)
        minimum_piece = max(
            3.0,
            min(self.min_segment_duration, self.max_segment_duration) * 0.5,
        )

        for segment in segments:
            if segment.duration <= self.max_segment_duration:
                split_segments.append(segment)
                continue

            segment_start = segment.start
            while segment.end - segment_start > self.max_segment_duration:
                target = segment_start + self.max_segment_duration
                window_start = max(segment_start + minimum_piece, target - search_radius)
                window_end = min(segment.end - minimum_piece, target + search_radius)

                split_point: float | None = None
                if window_end > window_start:
                    candidate_indexes = np.where(
                        (times >= window_start) & (times <= window_end)
                    )[0]
                    if len(candidate_indexes) > 0:
                        best_index = candidate_indexes[
                            int(np.argmin(rms[candidate_indexes]))
                        ]
                        split_point = float(times[best_index])

                if (
                    split_point is None
                    or split_point - segment_start < minimum_piece
                    or segment.end - split_point < minimum_piece
                ):
                    split_point = min(target, segment.end - minimum_piece)

                split_segments.append(AudioSegment(
                    start=segment_start,
                    end=split_point,
                    duration=split_point - segment_start,
                ))
                segment_start = split_point

            if segment.end - segment_start >= 1.0:
                split_segments.append(AudioSegment(
                    start=segment_start,
                    end=segment.end,
                    duration=segment.end - segment_start,
                ))
        return split_segments

    def split_audio(self, audio_path: str, output_dir: str) -> list[tuple[str, float, float]]:
        import os

        import soundfile as sf

        segments = self.detect(audio_path)
        base = os.path.splitext(os.path.basename(audio_path))[0]
        results = []
        for index, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"{base}_seg{index:03d}.wav")
            samples, _ = librosa.load(
                audio_path,
                sr=None,
                mono=True,
                offset=segment.start,
                duration=segment.duration,
            )
            sf.write(output_path, samples, 16000)
            results.append((output_path, segment.start, segment.end))
        return results
