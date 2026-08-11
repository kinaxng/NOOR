"""日语字幕后处理 - 智能断句、语气词过滤、格式优化"""
import re
from typing import Optional
from .types import SubtitleSegment, TranscriptionResult


class JapanesePostProcessor:
    """
    日语字幕后处理器

    Pass 1: 净化 - 移除填充词、无意义内容
    Pass 2: 层级断句 - 按句号、问号、感叹号、敬语结构分割
    Pass 3: 孤立助词合并 - 避免单字助词独立成行
    Pass 4: 微小片段合并 - 合并过短的片段
    Pass 5: 格式化 - 清理多余空格、统一标点
    """

    # 填充词/嗯呀词 (第一轮移除)
    AIZUCHI_PATTERNS = [
        # 常见嗯呀词
        r"^(あ|あー|ああ|あの|ん|んー|んん|うん|え|えー|ええ|えええ|お・お|おお|おー|おっ|哟|よお)$",
        # 重复语气词
        r"^(も|もぐもぐ|もふもふ|にゃ|にゃん|喵|呜|呜哇)$",
        # 停顿填充
        r"^(えっと|あの|すると|そう|そうそう|あら|哎呀|咦|咦咦)$",
    ]

    # 日语句尾模式（用于断句）
    SENTENCE_END_PATTERNS = [
        # 敬语/礼貌形结尾
        r"[です|ですけ|でした|します|しました|しますよ|ですよね|でしたか|でしたか|でございます]$",
        r"[ございます|いただきました|もらいました|かけました|してきました]$",
        # 疑问形
        r"[ですか|ですかね|ですかよ|だろうか|だろうかね|だろうか|なのか|なのかな|呀|かい|かいな|だい|でい]$",
        # 感叹形
        r"[だな|だなあ|だね|だねえ|呀|や|やん|やだ|やんか|よ|よね|よな|の|だね|ため息|った|ったあ]$",
        # 一般句尾
        r"[。|？|？|！|！]$",
        # 命令形/请求
        r"[给我|给我呀|给我吧|好不好|好吗|行不行|一下下|好不好嘛]$",
    ]

    # 助词模式（不能独立成句）
    PARTICLE_PATTERNS = [
        r"^[のはがをともにとでねなよれそ它们那里]$",
        r"^は$", r"^が$", r"^を$", r"^に$", r"^で$", r"^と$",
        r"^は$", r"^も$", r"^な$", r"^ね$", r"^よ$", r"^な$",
        r"^だ$", r"^れ$", r"^そ$", r"^か$", r"^の$",
    ]

    def __init__(
        self,
        min_segment_duration: float = 0.8,
        max_segment_duration: float = 8.0,
        min_gap_threshold: float = 0.3,
        merge_below: float = 1.2,
    ):
        """
        Args:
            min_segment_duration: 最小片段时长（秒）
            max_segment_duration: 最大片段时长（秒），超过则尝试进一步拆分
            min_gap_threshold: 最小间隙阈值（秒），小于此值则合并相邻片段
            merge_below: 时长小于此值（秒）则尝试与相邻片段合并
        """
        self.min_segment_duration = min_segment_duration
        self.max_segment_duration = max_segment_duration
        self.min_gap_threshold = min_gap_threshold
        self.merge_below = merge_below

        # 编译正则
        self._aizuchi_re = [re.compile(p) for p in self.AIZUCHI_PATTERNS]
        self._particle_re = [re.compile(p) for p in self.PARTICLE_PATTERNS]

    def process(self, result: TranscriptionResult) -> TranscriptionResult:
        """对转写结果进行后处理"""
        segments = list(result.segments)
        if not segments:
            return result

        # Pass 1: 净化 - 清理文本
        segments = self._pass1_sanitize(segments)

        # Pass 2: 层级断句
        segments = self._pass2_split(segments)

        # Pass 3: 孤立助词合并
        segments = self._pass3_particle_merge(segments)

        # Pass 4: 微小片段合并
        segments = self._pass4_tiny_merge(segments)

        # Pass 5: 格式化
        segments = self._pass5_format(segments)

        # 重新编号
        for i, seg in enumerate(segments):
            seg.index = i + 1

        return TranscriptionResult(
            segments=segments,
            language=result.language,
            duration=result.duration,
            source=result.source,
            metadata={**result.metadata, "post_processed": True}
        )

    def _pass1_sanitize(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """移除填充词和噪音"""
        for seg in segments:
            text = seg.text.strip()
            # 移除行首填充词
            for aizuchi_re in self._aizuchi_re:
                text = aizuchi_re.sub('', text)
            # 清理多余空格
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'^\s+|\s+$', '', text)
            seg.text = text
        # 移除空片段
        segments = [s for s in segments if s.text.strip()]
        return segments

    def _pass2_split(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """按日语句式结构层级断句"""
        result = []
        for seg in segments:
            sub_segments = self._split_segment(seg)
            result.extend(sub_segments)
        return result

    def _split_segment(self, seg: SubtitleSegment) -> list[SubtitleSegment]:
        """对单个片段尝试按句式断句"""
        text = seg.text
        duration = seg.end_time - seg.start_time

        # 如果片段时长合适，不拆分
        if duration <= self.max_segment_duration:
            return [seg]

        # 按标点断句
        split_points = []
        for pattern in self.SENTENCE_END_PATTERNS:
            for m in re.finditer(pattern, text):
                split_points.append(m.end())

        split_points = sorted(set(split_points))
        sub_texts = []
        start = 0
        for sp in split_points:
            if sp - start > 5:  # 至少5个字符
                sub_texts.append((start, sp))
            start = sp

        # Fallback: 如果没有找到断句点，或片段仍然超长，按固定时长强制分段
        if not sub_texts or (len(sub_texts) <= 1 and duration > self.max_segment_duration):
            # 按 max_segment_duration 等分，确保不超过上限
            num_splits = max(2, int(duration / self.max_segment_duration) + 1)
            chunk_len = len(text) // num_splits
            if chunk_len < 10:
                # 文本太短无法拆分
                return [seg]
            sub_texts = []
            for i in range(num_splits):
                s = i * chunk_len
                e = (i + 1) * chunk_len if i < num_splits - 1 else len(text)
                sub_texts.append((s, e))

        # 按比例分配时间
        total_len = len(text)
        sub_segments = []
        for idx, (s, e) in enumerate(sub_texts):
            ratio = (e - s) / total_len
            sub_start = seg.start_time + duration * sum(
                (len(text[sub_texts[i][0]:sub_texts[i][1]]) / total_len)
                for i in range(idx)
            )
            sub_end = sub_start + duration * ratio
            sub_seg = SubtitleSegment(
                index=0,
                start_time=sub_start,
                end_time=sub_end,
                text=text[s:e].strip(),
                words=[]
            )
            sub_segments.append(sub_seg)

        return sub_segments

    def _pass3_particle_merge(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """将孤立助词与前一个片段合并"""
        merged = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            text = seg.text.strip()

            # 检查是否是孤立助词
            is_particle = any(p.match(text) for p in self._particle_re)

            if is_particle and merged:
                # 合并到前一个
                prev = merged[-1]
                gap = seg.start_time - prev.end_time
                if gap <= self.min_gap_threshold:
                    prev.text = prev.text + seg.text
                    prev.end_time = seg.end_time
                else:
                    merged.append(seg)
            else:
                merged.append(seg)
            i += 1

        return merged

    def _pass4_tiny_merge(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """合并时长过短的片段"""
        if len(segments) < 2:
            return segments

        merged = [segments[0]]
        for seg in segments[1:]:
            duration = seg.end_time - seg.start_time
            prev = merged[-1]
            prev_duration = prev.end_time - prev.start_time
            gap = seg.start_time - prev.end_time

            # 如果当前片段很短且与前一片段间隔小，合并
            if duration < self.merge_below and gap < self.min_gap_threshold:
                # 合并
                prev.text = prev.text + " " + seg.text
                prev.end_time = seg.end_time
            # 如果前一片段很短，尝试与当前合并
            elif prev_duration < self.merge_below and gap < self.min_gap_threshold:
                prev.text = prev.text + " " + seg.text
                prev.end_time = seg.end_time
            else:
                merged.append(seg)

        return merged

    def _pass5_format(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        """最终格式化"""
        for seg in segments:
            text = seg.text.strip()
            # 清理连续空格
            text = re.sub(r'\s+', ' ', text)
            # 统一引号
            text = text.replace('「「', '「').replace('」」', '」')
            # 去除行首行尾标点
            text = re.sub(r'^[。、？?！!]\s*', '', text)
            text = re.sub(r'\s*[。、？?！!]$', '', text)
            seg.text = text

        # 移除空片段
        return [s for s in segments if s.text.strip()]


class RecommendedSubtitlePostProcessor:
    _LONG_REPEAT_CHAR_RE = re.compile(r"(る{10,}|じゅる{4,}|ごく(?:ごく){3,}|んぐ(?:んぐ){3,}|んむ(?:んむ){3,})")
    _LONG_SYLLABLE_RUN_RE = re.compile(r"((?:じゅ|ちゅ|んっ|はぁ|る|んむ|ごく){6,})")
    _MOAN_SPAN_RE = re.compile(r"(?:(?:んっ|はぁ|あっ|うっ|じゅる|ちゅ|くちゅ|ごく|る|んぐ|んむ){8,})")
    _NOISE_EDGE_RE = re.compile(r"^(?:じゅる|る|ごく|んぐ|んむ){4,}|(?:じゅる|る|ごく|んぐ|んむ){4,}$")
    _SHORT_ROMAN_HALLUCINATION_RE = re.compile(r"^[A-Za-z][A-Za-z .,'!?-]{0,24}$")
    _SHORT_NUMERIC_HALLUCINATION_RE = re.compile(r"^[0-9]+(?:[.,][0-9]+)?(?:ページ)?$")
    _SHORT_MOAN_SEGMENT_RE = re.compile(r"^(?:[ぁ-んァ-ヶーっッ゛゜ゃゅょゎゐゑをん。、，,.!！?？…~〜・\-\s]+)$")
    _EDGE_MOAN_PREFIX_RE = re.compile(r"^(?:\s|[、，,.!！?？…~〜・\-]|なぁ|いやぁ|あぁ|うぅ|はぁ|んっ|あっ|うっ|じゅるるっ?|じゅる|んぐっ?|んむっ?|ごくっ?|ちゅるっ?|ちゅっ|ちゅ)+")
    _EDGE_MOAN_SUFFIX_RE = re.compile(r"(?:\s|[、，,.!！?？…~〜・\-]|なぁ|いやぁ|あぁ|うぅ|はぁ|んっ|あっ|うっ|じゅるるっ?|じゅる|んぐっ?|んむっ?|ごくっ?|ちゅるっ?|ちゅっ|ちゅ)+$")
    _MEANINGFUL_SHORT_DIALOGUE_RE = re.compile(
        r"(?:やめて|やだ|いやだ|だめ|ダメ|無理|むり|痛い|いたい|待って|まって|離して|はなして|来ないで|こないで|許して|ゆるして|ごめん|違う|ちがう|何|なに)"
    )
    _SHORT_DIALOGUE_EXTRACT_RE = re.compile(
        r"(やめて|やだ|いやだ|だめ|ダメ|無理|むり|痛い|いたい|待って|まって|離して|はなして|来ないで|こないで|許して|ゆるして|ごめん|違う|ちがう|何|なに)"
    )
    _SHORT_DIALOGUE_WHITELIST = frozenset({
        'やめて', 'やだ', 'いやだ', 'だめ', 'ダメ', '無理', 'むり', '痛い', 'いたい',
        '待って', 'まって', '離して', 'はなして', '来ないで', 'こないで', '許して', 'ゆるして',
        'ごめん', '違う', 'ちがう', '何', 'なに', 'そう', 'そうよ', 'そうだよ', 'ほんと', '本当',
        'うそ', '嘘', 'いや', 'うん', 'ええ', 'はい'
    })
    _SHORT_DIALOGUE_BLACKLIST = frozenset({
        'あっ', 'うっ', 'えっ', 'おっ', 'んっ', 'ん', 'あ', 'う', 'え', 'お',
        'あの', 'あのー', 'えっと', 'ええと', 'えー', 'あー', 'うー', 'はぁ', 'ふぅ',
        'うんうん', 'えええ', 'あああ', 'www'
    })
    _LOW_INFO_EDGE_RE = re.compile(r"^[ぁ-んァ-ヶーっッ゛゜ゃゅょゎゐゑをん、，,.!！?？…~〜・\-\s]+$")
    _META_PATTERNS = (
        re.compile(r"\([^)]+\)\s*"),
        re.compile(r"【[^】]+】"),
        re.compile(r"※この動画の字幕は視聴者によって作成されました。?"),
        re.compile(r"(?:ご|お)?視聴(?:して)?(?:いただき|くれて)?(?:ありがとうございました|ありがとうございます|ありがとう|ございました)"),
        re.compile(r"見てくれて(?:ありがとう|ございました)[!！]?"),
        re.compile(r"また(?:ね|次の動画でお会いしましょう)[!！]?"),
        re.compile(r"チャンネル登録[をお]?(?:願い|ねがい)(?:し|い)(?:ます|してください|いたします|たします)?"),
        re.compile(r"(?:www|ｗｗｗ)[wｗ]*"),
        re.compile(r"(?:拍手|笑|音楽)"),
    )
    _ISOLATED_PARTICLE_RE = re.compile(r"^(?:よ|ね|な|わ|の|さ|ぞ|ぜ|よね|よな|わね|わよ|のよ|のね|ですよ|ですね|ますよ|ますね|だよ|だね|だな|かな|っけ)$")
    _EMBEDDED_PARTICLE_SPACE_RE = re.compile(r"(です|ます|だ)\s+(よね|よな|よ|ね|な|かな|っけ)$")
    _EXACT_HALLUCINATION_STRINGS = frozenset({
        'ご視聴ありがとうございました',
        '※この動画の字幕は視聴者によって作成されました',
        'thank you for watching',
        'thanks for watching',
        'for watching',
        'follow me on',
        'my channel',
        'our channel',
        'the channel',
        'next video',
        'see you next week',
        'translated by',
        'translation by',
        'amara',
        'www',
        'wwwww',
        '[音楽]',
        '(音楽)',
        '(拍手)',
        '(笑)',
        '1',
        '1.5ページ',
        '2.5ページ',
        '3ページ',
        '4ページ',
        '5ページ',
    })
    _EXACT_HALLUCINATION_NORMALIZED = frozenset(re.sub(r"\s+", "", item.lower()) for item in _EXACT_HALLUCINATION_STRINGS)

    """Recommended-strategy specific subtitle cleanup.

    Goal: low-risk quality gains for the product default path:
    - remove exact / near-exact adjacent duplicates
    - merge tiny repeated tails
    - suppress punctuation-only / onomatopoeia-only noise spans
    - apply slightly stricter Japanese post-processing parameters
    """

    _PUNCT_ONLY_RE = re.compile(r"^[。、「」『』、,，.!！?？…~〜・\-\s]+$")
    _KANJI_RE = re.compile(r"[一-龯々]")
    _VOICE_CHAR_RE = re.compile(r"^[ぁ-んァ-ヶーっッ゛゜ゃゅょゎゐゑをん]+$")
    _NOISE_TOKENS = tuple(sorted((
        "はぁい", "ごくごく", "ちゅるっ", "ちゅう", "ちゅぅ", "ちゅっ", "ちゅぱ", "ちゅぷ", "ちゅる", "ちゅぽ",
        "くちゅ", "ぺろっ", "じゅぽ", "はむっ", "ごくっ", "んっ", "んん", "あっ", "あん", "はぁ", "ふぅ",
        "うっ", "えっ", "おっ", "むっ", "ぺろ", "じゅる", "はむ", "ごく", "んぐ", "んむ", "ゴク", "ちゅ", "ん", "あ", "む", "っ"
    ), key=len, reverse=True))

    def __init__(self):
        self._base = JapanesePostProcessor(
            min_segment_duration=0.8,
            max_segment_duration=7.0,
            min_gap_threshold=0.25,
            merge_below=0.8,
        )

    def process(self, result: TranscriptionResult) -> TranscriptionResult:
        processed = self._base.process(result)
        before_count = len(processed.segments)
        meta_scrubbed, meta_trimmed_chars, meta_empty_removed = self._trim_meta_hallucinations(processed.segments)
        collapsed_particle_segments, collapsed_particle_count = self._collapse_embedded_particle_spaces(meta_scrubbed)
        trimmed_segments, trimmed_chars, trimmed_empty_removed = self._trim_embedded_noise_spans(collapsed_particle_segments)
        particle_merged, particle_removed = self._merge_isolated_particles(trimmed_segments)
        adjacent_deduped, adjacent_removed = self._dedupe_adjacent_segments(particle_merged)
        echoed_segments, echo_removed = self._suppress_short_window_echoes(adjacent_deduped)
        segments, noise_removed = self._suppress_noise_only_segments(echoed_segments)
        after_count = len(segments)
        for i, seg in enumerate(segments):
            seg.index = i + 1
        return TranscriptionResult(
            segments=segments,
            language=processed.language,
            duration=processed.duration,
            source=processed.source,
            metadata={
                **processed.metadata,
                "post_processed": True,
                "recommended_strategy_post_processed": True,
                "recommended_cleanup_before_segments": before_count,
                "recommended_cleanup_after_segments": after_count,
                "recommended_cleanup_deduped_segments": max(0, before_count - after_count),
                "recommended_cleanup_adjacent_deduped_segments": adjacent_removed,
                "recommended_cleanup_particle_merged_segments": particle_removed + collapsed_particle_count,
                "recommended_cleanup_window_echo_segments": echo_removed,
                "recommended_cleanup_noise_only_segments": noise_removed + trimmed_empty_removed + meta_empty_removed,
                "recommended_cleanup_trimmed_noise_chars": trimmed_chars + meta_trimmed_chars,
            },
        )

    def _trim_meta_hallucinations(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int, int]:
        cleaned: list[SubtitleSegment] = []
        trimmed_chars = 0
        dropped = 0
        for seg in segments:
            original = seg.text or ''
            updated = original
            for pattern in self._META_PATTERNS:
                updated = pattern.sub(' ', updated)
            updated = re.sub(r'([、，]{2,}|[。．]{2,}|[!！]{2,}|[?？]{2,})', ' ', updated)
            updated = re.sub(r'\s+', ' ', updated).strip(' 、，。!！?？')
            removed = max(0, len(original) - len(updated))
            if removed > 0:
                trimmed_chars += removed
                seg.text = updated
            if seg.text.strip():
                cleaned.append(seg)
            else:
                dropped += 1
        return cleaned, trimmed_chars, dropped

    @classmethod
    def _collapse_embedded_particle_space(cls, text: str) -> str:
        updated = text or ''
        while True:
            collapsed = cls._EMBEDDED_PARTICLE_SPACE_RE.sub(r"\1\2", updated)
            if collapsed == updated:
                return collapsed
            updated = collapsed

    def _collapse_embedded_particle_spaces(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int]:
        changed = 0
        for seg in segments:
            collapsed = self._collapse_embedded_particle_space(seg.text)
            if collapsed != seg.text:
                seg.text = collapsed
                changed += 1
        return segments, changed

    def _trim_embedded_noise_spans(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int, int]:
        cleaned: list[SubtitleSegment] = []
        trimmed_chars = 0
        dropped = 0
        for seg in segments:
            trimmed_text, removed = self._trim_noise_from_text(seg.text)
            if removed > 0:
                trimmed_chars += removed
                seg.text = trimmed_text
            if seg.text.strip():
                cleaned.append(seg)
            else:
                dropped += 1
        return cleaned, trimmed_chars, dropped

    @classmethod
    def _trim_noise_from_text(cls, text: str) -> tuple[str, int]:
        original = text or ''
        updated = original

        def repl(match: re.Match[str]) -> str:
            chunk = match.group(0)
            normalized = re.sub(r"\s+", "", chunk)
            if len(normalized) < 12:
                return chunk
            return ' '

        for pattern in (cls._LONG_REPEAT_CHAR_RE, cls._LONG_SYLLABLE_RUN_RE, cls._MOAN_SPAN_RE):
            updated = pattern.sub(repl, updated)

        updated = re.sub(r"(?:じゅる){4,}", ' ', updated)
        updated = re.sub(r"(?:ごく|ゴク){5,}", ' ', updated)
        updated = re.sub(r"(?:んぐ){4,}", ' ', updated)
        updated = re.sub(r"(?:んむ){4,}", ' ', updated)
        updated = re.sub(r"る{12,}", ' ', updated)
        updated = cls._trim_moan_edges(updated)
        updated = cls._extract_meaningful_short_dialogue(updated)
        updated = cls._NOISE_EDGE_RE.sub('', updated)
        updated = re.sub(r"\s+", ' ', updated).strip(' 、,')
        return updated, max(0, len(original) - len(updated))

    @classmethod
    def _trim_moan_edges(cls, text: str) -> str:
        updated = text or ''
        compact = re.sub(r"\s+", "", updated)
        has_dialogue_core = (
            bool(cls._KANJI_RE.search(compact))
            or len(re.sub(r"[ぁ-んァ-ヶーっッ゛゜ゃゅょゎゐゑをん。、，,.!！?？…~〜・\-]", "", compact)) > 0
            or bool(cls._MEANINGFUL_SHORT_DIALOGUE_RE.search(compact))
        )
        if not has_dialogue_core:
            return updated
        previous = None
        while previous != updated:
            previous = updated
            updated = cls._EDGE_MOAN_PREFIX_RE.sub('', updated)
            updated = cls._EDGE_MOAN_SUFFIX_RE.sub('', updated)
            updated = updated.strip()
        return updated

    @classmethod
    def _extract_meaningful_short_dialogue(cls, text: str) -> str:
        updated = (text or '').strip()
        compact = re.sub(r"\s+", "", updated)
        if not compact or len(compact) > 18:
            return updated
        match = cls._SHORT_DIALOGUE_EXTRACT_RE.search(compact)
        if not match:
            return updated
        prefix = compact[:match.start()]
        suffix = compact[match.end():]
        if prefix and not cls._LOW_INFO_EDGE_RE.fullmatch(prefix):
            return updated
        if suffix and not cls._LOW_INFO_EDGE_RE.fullmatch(suffix):
            return updated
        return match.group(1)

    def _dedupe_adjacent_segments(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int]:
        if not segments:
            return segments, 0

        deduped: list[SubtitleSegment] = [segments[0]]
        removed = 0
        for seg in segments[1:]:
            prev = deduped[-1]
            if self._is_near_duplicate(prev.text, seg.text):
                prev.end_time = max(prev.end_time, seg.end_time)
                removed += 1
                continue
            deduped.append(seg)
        return deduped, removed

    def _merge_isolated_particles(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int]:
        if len(segments) < 2:
            return segments, 0

        merged: list[SubtitleSegment] = [segments[0]]
        removed = 0
        for seg in segments[1:]:
            text = (seg.text or '').strip()
            prev = merged[-1]
            gap = max(0.0, seg.start_time - prev.end_time)
            if self._ISOLATED_PARTICLE_RE.fullmatch(text) and gap <= 0.45:
                prev.text = f"{(prev.text or '').rstrip()}{text}"
                prev.end_time = max(prev.end_time, seg.end_time)
                removed += 1
                continue
            merged.append(seg)
        return merged, removed

    def _suppress_short_window_echoes(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int]:
        if len(segments) < 3:
            return segments, 0

        cleaned: list[SubtitleSegment] = []
        removed = 0
        for seg in segments:
            duplicate_idx = None
            for idx in range(len(cleaned) - 1, max(-1, len(cleaned) - 3), -1):
                prev = cleaned[idx]
                if seg.start_time - prev.end_time > 2.5:
                    continue
                if not self._is_near_duplicate(prev.text, seg.text):
                    continue
                if len(self._normalize_text(seg.text)) < 5:
                    continue
                duplicate_idx = idx
                break

            if duplicate_idx is None:
                cleaned.append(seg)
                continue

            cleaned[duplicate_idx].end_time = max(cleaned[duplicate_idx].end_time, seg.end_time)
            removed += 1

        return cleaned, removed

    def _suppress_noise_only_segments(self, segments: list[SubtitleSegment]) -> tuple[list[SubtitleSegment], int]:
        cleaned: list[SubtitleSegment] = []
        removed = 0
        for seg in segments:
            if self._should_drop_noise_segment(seg):
                removed += 1
                continue
            cleaned.append(seg)
        return cleaned, removed

    def _should_drop_noise_segment(self, seg: SubtitleSegment) -> bool:
        if self._is_noise_only(seg.text):
            return True

        compact = re.sub(r"\s+", "", seg.text or "")
        normalized = re.sub(r"[。、「」『』、,，.!！?？…~〜・\-]", "", compact)
        if not normalized:
            return True
        lowered = re.sub(r"\s+", "", normalized.lower())
        if lowered in self._EXACT_HALLUCINATION_NORMALIZED:
            return True
        if self._SHORT_ROMAN_HALLUCINATION_RE.fullmatch(normalized) and lowered in self._EXACT_HALLUCINATION_NORMALIZED:
            return True
        if self._SHORT_NUMERIC_HALLUCINATION_RE.fullmatch(normalized):
            return True

        duration = max(0.0, seg.end_time - seg.start_time)
        noise_ratio = self._noise_token_ratio(normalized)
        unique_ratio = len(set(normalized)) / max(len(normalized), 1)
        has_kanji = bool(self._KANJI_RE.search(normalized))
        voice_like = bool(self._VOICE_CHAR_RE.fullmatch(normalized))
        short_dialogue = self._classify_short_dialogue(normalized)

        if short_dialogue == 'blacklist':
            return True
        if short_dialogue == 'whitelist':
            return False

        if not has_kanji and len(normalized) >= 6 and noise_ratio >= 0.72 and duration <= 10.0:
            return True
        if (
            not has_kanji
            and len(normalized) <= 24
            and duration <= 5.5
            and noise_ratio >= 0.42
            and self._SHORT_MOAN_SEGMENT_RE.fullmatch(compact)
        ):
            return True
        if not has_kanji and voice_like and len(normalized) >= 8 and unique_ratio <= 0.34 and duration <= 12.0:
            return True
        if not has_kanji and voice_like and len(normalized) >= 12 and noise_ratio >= 0.55:
            return True
        return False

    @classmethod
    def _classify_short_dialogue(cls, text: str) -> str | None:
        normalized = re.sub(r"[。、「」『』、,，.!！?？…~〜・\-\s]", "", text or '')
        if not normalized or len(normalized) > 8:
            return None
        if normalized in cls._SHORT_DIALOGUE_BLACKLIST:
            return 'blacklist'
        if normalized in cls._SHORT_DIALOGUE_WHITELIST:
            return 'whitelist'
        return None

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
            if unit and unit * max(4, len(normalized) // width) == normalized[: len(unit) * max(4, len(normalized) // width)]:
                if len(normalized) >= width * 4 and normalized == unit * (len(normalized) // width):
                    return True
        return False

    @classmethod
    def _noise_token_ratio(cls, text: str) -> float:
        remaining = text
        matched = 0
        while remaining:
            found = False
            for token in cls._NOISE_TOKENS:
                if remaining.startswith(token):
                    matched += len(token)
                    remaining = remaining[len(token):]
                    found = True
                    break
            if not found:
                remaining = remaining[1:]
        return matched / max(len(text), 1)

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

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r"\s+", "", text or "")
        normalized = re.sub(r"[。、「」『』!！?？…~〜]+", "", normalized)
        return normalized.strip()

    def _is_near_duplicate(self, left: str, right: str) -> bool:
        lnorm = self._normalize_text(left)
        rnorm = self._normalize_text(right)
        if not lnorm or not rnorm:
            return False
        if lnorm == rnorm:
            return True
        if len(lnorm) >= 6 and (lnorm in rnorm or rnorm in lnorm):
            return True
        if len(lnorm) >= 8 and len(rnorm) >= 8:
            common = lnorm if len(lnorm) <= len(rnorm) else rnorm
            other = rnorm if common is lnorm else lnorm
            if common[: max(6, len(common) - 2)] in other:
                return True
        return False
