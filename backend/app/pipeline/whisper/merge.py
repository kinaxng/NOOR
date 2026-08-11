"""字幕合并引擎 - 实现 smart_merge 策略"""
import re
from typing import List, Tuple
from dataclasses import dataclass
from .types import SubtitleSegment, TranscriptionResult, MergeStrategy


@dataclass
class Subtitle:
    """内部使用的字幕格式"""
    start_time: float
    end_time: float
    duration: float
    text: str
    source: str  # "pass1" / "pass2"


class MergeEngine:
    """合并引擎"""

    OVERLAP_THRESHOLD = 0.30  # 30% 重叠阈值
    _DIVERSITY_FLOOR = 0.20   # 重复文本判定阈值

    _PUNCT_ONLY_RE = re.compile(r"^[。、「」『』、,，.!！?？…~〜・\-\s]+$")
    _NOISE_TOKENS = tuple(sorted((
        "はぁい", "ごくごく", "ちゅるっ", "ちゅう", "ちゅぅ", "ちゅっ", "ちゅぱ", "ちゅぷ", "ちゅる", "ちゅぽ",
        "くちゅ", "ぺろっ", "じゅぽ", "はむっ", "ごくっ", "んっ", "んん", "あっ", "あん", "はぁ", "ふぅ",
        "うっ", "えっ", "おっ", "むっ", "ぺろ", "じゅる", "はむ", "ごく", "ちゅ", "ん", "あ", "む", "っ"
    ), key=len, reverse=True))

    def __init__(self, strategy: MergeStrategy = MergeStrategy.SMART):
        self.strategy = strategy

    def merge(
        self,
        pass1_result: TranscriptionResult,
        pass2_result: TranscriptionResult
    ) -> TranscriptionResult:
        """合并两遍结果"""
        if self.strategy == MergeStrategy.SMART:
            return self._smart_merge(pass1_result, pass2_result)
        elif self.strategy == MergeStrategy.FULL_MERGE:
            return self._full_merge(pass1_result, pass2_result)
        elif self.strategy == MergeStrategy.PASS1_PRIMARY:
            return self._pass_primary(pass1_result, pass2_result, primary="pass1")
        elif self.strategy == MergeStrategy.PASS2_PRIMARY:
            return self._pass_primary(pass1_result, pass2_result, primary="pass2")
        elif self.strategy == MergeStrategy.LONGEST:
            return self._longest_merge(pass1_result, pass2_result)
        elif self.strategy == MergeStrategy.PASS1_OVERLAP:
            return self._overlap_merge(pass1_result, pass2_result, primary="pass1")
        elif self.strategy == MergeStrategy.PASS2_OVERLAP:
            return self._overlap_merge(pass1_result, pass2_result, primary="pass2")
        else:
            return pass2_result  # 默认返回 pass2

    def _smart_merge(
        self,
        pass1: TranscriptionResult,
        pass2: TranscriptionResult
    ) -> TranscriptionResult:
        """智能合并 - 时序驱动 + 质量调整"""
        subs1 = [Subtitle(
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.end_time - s.start_time,
            text=s.text,
            source="pass1"
        ) for s in pass1.segments]

        subs2 = [Subtitle(
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.end_time - s.start_time,
            text=s.text,
            source="pass2"
        ) for s in pass2.segments]

        merged = []
        used1 = set()
        used2 = set()

        # 首先处理重叠的字幕
        for i, s1 in enumerate(subs1):
            best_match = None
            best_overlap_score = 0.0

            for j, s2 in enumerate(subs2):
                if j in used2:
                    continue

                overlap_dur = self._overlap_duration(s1, s2)
                if overlap_dur <= 0:
                    continue

                overlap_score = overlap_dur / max(s1.duration, s2.duration, 1e-6)
                if overlap_score > best_overlap_score:
                    best_match = (j, s2, overlap_score)
                    best_overlap_score = overlap_score

            if best_match:
                j, s2, _ = best_match
                chosen = self._choose_by_quality(s1, s2)
                merged.append(chosen)
                used1.add(i)
                used2.add(j)
            else:
                merged.append(s1)
                used1.add(i)

        # 添加未匹配的 pass2 字幕
        for j, s2 in enumerate(subs2):
            if j not in used2:
                merged.append(s2)

        # 按时间排序 + 收拢重叠重复片段 + 修复异常时间轴
        merged.sort(key=lambda x: (x.start_time, x.end_time))
        merged = self._collapse_redundant_overlaps(merged)
        merged = self._sanitize_timeline(merged)

        # 转换回 TranscriptionResult
        segments = []
        for i, sub in enumerate(merged):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                words=[]
            ))

        return TranscriptionResult(
            segments=segments,
            language=pass2.language,
            duration=pass2.duration,
            source="merged",
            metadata={"strategy": "smart_merge"}
        )

    def _full_merge(
        self,
        pass1: TranscriptionResult,
        pass2: TranscriptionResult
    ) -> TranscriptionResult:
        """合并所有字幕，按时间排序"""
        all_subs = []
        for s in pass1.segments:
            all_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source="pass1"
            ))
        for s in pass2.segments:
            all_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source="pass2"
            ))

        all_subs.sort(key=lambda x: x.start_time)

        segments = []
        for i, sub in enumerate(all_subs):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                words=[]
            ))

        return TranscriptionResult(
            segments=segments,
            language=pass2.language,
            duration=pass2.duration,
            source="merged",
            metadata={"strategy": "full_merge"}
        )

    def _pass_primary(
        self,
        pass1: TranscriptionResult,
        pass2: TranscriptionResult,
        primary: str
    ) -> TranscriptionResult:
        """以一个 pass 为主"""
        if primary == "pass1":
            primary_result = pass1
            secondary_result = pass2
        else:
            primary_result = pass2
            secondary_result = pass1

        merged = []
        primary_subs = []
        secondary_subs = []

        for s in primary_result.segments:
            primary_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source=primary
            ))

        for s in secondary_result.segments:
            secondary_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source="secondary"
            ))

        used = set()

        # 填充 primary 中没有覆盖的时间段
        for ps in primary_subs:
            merged.append(ps)
            used.add(ps.start_time)

        for ss in secondary_subs:
            # 检查是否与已有的重叠
            overlaps = False
            for ms in merged:
                if self._overlap_duration(ms, ss) > 0:
                    overlaps = True
                    break
            if not overlaps:
                merged.append(ss)

        merged.sort(key=lambda x: x.start_time)

        segments = []
        for i, sub in enumerate(merged):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                words=[]
            ))

        return TranscriptionResult(
            segments=segments,
            language=primary_result.language,
            duration=primary_result.duration,
            source="merged",
            metadata={"strategy": f"{primary}_primary"}
        )

    def _longest_merge(
        self,
        pass1: TranscriptionResult,
        pass2: TranscriptionResult
    ) -> TranscriptionResult:
        """选择文本最长的"""
        subs1 = [Subtitle(
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.end_time - s.start_time,
            text=s.text,
            source="pass1"
        ) for s in pass1.segments]

        subs2 = [Subtitle(
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.end_time - s.start_time,
            text=s.text,
            source="pass2"
        ) for s in pass2.segments]

        merged = []
        used1 = set()
        used2 = set()

        for i, s1 in enumerate(subs1):
            best_match = None
            best_len = self._quality_length(s1.text)

            for j, s2 in enumerate(subs2):
                if j in used2:
                    continue
                if self._overlap_duration(s1, s2) <= 0:
                    continue

                s2_len = self._quality_length(s2.text)
                if s2_len > best_len:
                    best_match = (j, s2)
                    best_len = s2_len

            if best_match:
                j, s2 = best_match
                if self._quality_length(s2.text) > self._quality_length(s1.text):
                    merged.append(s2)
                else:
                    merged.append(s1)
                used1.add(i)
                used2.add(j)
            else:
                merged.append(s1)
                used1.add(i)

        for j, s2 in enumerate(subs2):
            if j not in used2:
                merged.append(s2)

        merged.sort(key=lambda x: x.start_time)

        segments = []
        for i, sub in enumerate(merged):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                words=[]
            ))

        return TranscriptionResult(
            segments=segments,
            language=pass2.language,
            duration=pass2.duration,
            source="merged",
            metadata={"strategy": "longest"}
        )

    def _overlap_merge(
        self,
        pass1: TranscriptionResult,
        pass2: TranscriptionResult,
        primary: str
    ) -> TranscriptionResult:
        """重叠感知合并 - 以指定 pass 为主，允许 30% 重叠阈值"""
        if primary == "pass1":
            primary_result = pass1
            secondary_result = pass2
        else:
            primary_result = pass2
            secondary_result = pass1

        primary_subs = []
        secondary_subs = []

        for s in primary_result.segments:
            primary_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source="primary"
            ))

        for s in secondary_result.segments:
            secondary_subs.append(Subtitle(
                start_time=s.start_time,
                end_time=s.end_time,
                duration=s.end_time - s.start_time,
                text=s.text,
                source="secondary"
            ))

        merged = []
        used_secondary = set()

        # 首先添加所有 primary 字幕
        for ps in primary_subs:
            merged.append(ps)

        # 对每个 secondary 字幕，检查是否与 primary 重叠
        for ss in secondary_subs:
            overlap_found = False
            for ms in merged:
                if self._overlap_duration(ms, ss) > 0:
                    # 计算重叠覆盖率
                    overlap_dur = self._overlap_duration(ms, ss)
                    coverage = overlap_dur / ss.duration
                    if coverage > self.OVERLAP_THRESHOLD:
                        # 重叠超过阈值，替换 primary 字幕
                        merged.remove(ms)
                        merged.append(ss)
                        overlap_found = True
                        break
                    else:
                        overlap_found = True

            if not overlap_found:
                merged.append(ss)

        merged.sort(key=lambda x: x.start_time)

        segments = []
        for i, sub in enumerate(merged):
            segments.append(SubtitleSegment(
                index=i + 1,
                start_time=sub.start_time,
                end_time=sub.end_time,
                text=sub.text,
                words=[]
            ))

        return TranscriptionResult(
            segments=segments,
            language=primary_result.language,
            duration=primary_result.duration,
            source="merged",
            metadata={"strategy": f"{primary}_overlap"}
        )

    def _collapse_redundant_overlaps(self, subtitles: list[Subtitle]) -> list[Subtitle]:
        if len(subtitles) < 2:
            return subtitles

        collapsed: list[Subtitle] = [subtitles[0]]
        for current in subtitles[1:]:
            prev = collapsed[-1]
            overlap = self._overlap_duration(prev, current)
            if overlap <= 0:
                collapsed.append(current)
                continue

            overlap_ratio = overlap / max(prev.duration, current.duration, 1e-6)
            prev_norm = self._normalize_for_overlap(prev.text)
            curr_norm = self._normalize_for_overlap(current.text)
            texts_related = (
                self._is_near_duplicate(prev.text, current.text)
                or (prev_norm and prev_norm in curr_norm)
                or (curr_norm and curr_norm in prev_norm)
            )
            if overlap_ratio < 0.45 and not texts_related:
                collapsed.append(current)
                continue

            chosen = self._choose_by_quality(prev, current)
            if chosen is prev:
                prev.end_time = max(prev.end_time, current.end_time)
                continue
            current.start_time = min(prev.start_time, current.start_time)
            collapsed[-1] = current
        return collapsed

    @staticmethod
    def _normalize_for_overlap(text: str) -> str:
        return re.sub(r"\s+", "", text or "")

    def _is_near_duplicate(self, left: str, right: str) -> bool:
        lnorm = self._normalize_text(left)
        rnorm = self._normalize_text(right)
        if not lnorm or not rnorm:
            return False
        if lnorm == rnorm:
            return True
        if len(lnorm) >= 6 and (lnorm in rnorm or rnorm in lnorm):
            return True
        return False

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r"\s+", "", text or "")
        normalized = re.sub(r"[。、「」『』!！?？…~〜]+", "", normalized)
        return normalized.strip()

    def _sanitize_timeline(self, subtitles: list[Subtitle]) -> list[Subtitle]:
        if not subtitles:
            return subtitles

        sanitized: list[Subtitle] = []
        for sub in subtitles:
            if sub.end_time <= sub.start_time:
                continue

            if not sanitized:
                sanitized.append(sub)
                continue

            prev = sanitized[-1]
            overlap = self._overlap_duration(prev, sub)
            if overlap <= 0:
                sanitized.append(sub)
                continue

            prev_norm = self._normalize_for_overlap(prev.text)
            curr_norm = self._normalize_for_overlap(sub.text)
            related = (
                self._is_near_duplicate(prev.text, sub.text)
                or (prev_norm and prev_norm in curr_norm)
                or (curr_norm and curr_norm in prev_norm)
            )
            overlap_ratio = overlap / max(prev.duration, sub.duration, 1e-6)

            if related or overlap_ratio >= 0.6:
                chosen = self._choose_by_quality(prev, sub)
                if chosen is prev:
                    prev.end_time = max(prev.end_time, sub.end_time)
                else:
                    sub.start_time = min(prev.start_time, sub.start_time)
                    sanitized[-1] = sub
                continue

            if sub.start_time < prev.end_time:
                sub.start_time = prev.end_time
                if sub.end_time <= sub.start_time:
                    continue
                sub.duration = sub.end_time - sub.start_time
            sanitized.append(sub)

        for sub in sanitized:
            sub.duration = sub.end_time - sub.start_time
        return sanitized

    def _choose_by_quality(self, s1: Subtitle, s2: Subtitle) -> Subtitle:
        """根据质量选择"""
        noise1 = self._is_noise_only(s1.text)
        noise2 = self._is_noise_only(s2.text)
        if noise1 != noise2:
            return s2 if noise1 else s1

        len1 = self._quality_length(s1.text)
        len2 = self._quality_length(s2.text)
        if len1 != len2:
            return s1 if len1 > len2 else s2

        score1 = self._dialogue_score(s1.text)
        score2 = self._dialogue_score(s2.text)
        if score1 != score2:
            return s1 if score1 > score2 else s2

        # 时长短优先
        if s1.duration != s2.duration:
            return s1 if s1.duration <= s2.duration else s2

        # 早开始优先
        return s1 if s1.start_time <= s2.start_time else s2

    def _overlap_duration(self, s1: Subtitle, s2: Subtitle) -> float:
        """计算两个字幕的重叠时长"""
        start = max(s1.start_time, s2.start_time)
        end = min(s1.end_time, s2.end_time)
        return max(0, end - start)

    def _coverage_ratio(self, sub: Subtitle, overlap_dur: float) -> float:
        """计算覆盖率"""
        if overlap_dur <= 0:
            return 0
        return overlap_dur / sub.duration

    @staticmethod
    def _quality_length(text: str) -> int:
        """计算调整后的字符数，重复文本返回0"""
        stripped = text.strip()
        if not stripped:
            return 0
        unique_ratio = len(set(stripped)) / len(stripped)
        if unique_ratio < MergeEngine._DIVERSITY_FLOOR:
            return 0  # 拒绝 hallucination
        return len(stripped)
    @classmethod
    def _is_noise_only(cls, text: str) -> bool:
        compact = re.sub(r"\s+", "", text or "")
        if not compact:
            return True
        if cls._PUNCT_ONLY_RE.fullmatch(compact):
            return True

        normalized = re.sub(r"[。、「」『』、,，.!！?？…~〜・\-]", "", compact)
        if not normalized:
            return True
        if len(normalized) <= 48 and cls._consists_of_noise_tokens(normalized):
            return True

        for width in range(1, min(5, len(normalized) // 4 + 1)):
            unit = normalized[:width]
            if unit and len(normalized) >= width * 4 and normalized == unit * (len(normalized) // width):
                return True
        return False

    @classmethod
    def _consists_of_noise_tokens(cls, text: str) -> bool:
        remaining = text
        while remaining:
            matched = False
            for token in cls._NOISE_TOKENS:
                if remaining.startswith(token):
                    remaining = remaining[len(token):]
                    matched = True
                    break
            if not matched:
                return False
        return True

    @classmethod
    def _dialogue_score(cls, text: str) -> int:
        compact = re.sub(r"\s+", "", text or "")
        if not compact:
            return 0
        if cls._is_noise_only(compact):
            return 0
        score = len(compact)
        if re.search(r"[一-龯ぁ-んァ-ン]", compact):
            score += 4
        if re.search(r"[。！？?]", text or ""):
            score += 1
        return score
