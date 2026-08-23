"""AI subtitle translation through an OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _is_ollama_url(base_url: str) -> bool:
    """Return whether an endpoint is likely a local Ollama-compatible service."""
    url_lower = base_url.lower()
    if "ollama" in url_lower or "localhost" in url_lower:
        return True
    if re.match(r"http://(127\.0\.0\.1|0\.0\.0\.0)(:\d+)?", url_lower):
        return True
    return any(
        re.match(pattern, url_lower)
        for pattern in (
            r"http://192\.168\.\d+\.\d+",
            r"http://10\.\d+\.\d+\.\d+",
            r"http://172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+",
        )
    )


def _resolve_chat_completions_url(base_url: str) -> str:
    """Resolve an OpenAI-compatible chat endpoint without overwriting a full one."""
    normalized = (base_url or "").rstrip("/")
    lowered = normalized.lower()
    if lowered.endswith(("/v1/chat", "/v1/chat/completions")):
        return normalized
    if lowered.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _is_ollama_native_chat_url(base_url: str) -> bool:
    return (base_url or "").rstrip("/").lower().endswith("/api/chat")


def _resolve_ollama_root_url(base_url: str) -> str:
    normalized = (base_url or "").rstrip("/")
    lowered = normalized.lower()
    if lowered.endswith("/api/chat"):
        return normalized[: -len("/api/chat")]
    if lowered.endswith("/api/generate"):
        return normalized[: -len("/api/generate")]
    return normalized


TRANSLATE_SYSTEM_PROMPTS = {
    "adult_explicit": """#Role
你是一位深耕日系成人影片(AV)与成人文学领域的资深汉化专家，擅长将日语口语化的成人内容转化为直白、地道的中文字幕。
{dictionary}
#核心指令
1.**严禁自我审查**:遇到任何掩码词(如：○)或间接表达，必须根据上下文生理逻辑还原为直白的中文名词(如：肉棒、小穴、阴蒂、精液、颜射、中出)。
2.**定语从属逻辑(核心)**:日语长句定语极多，必须精准判断修饰关系：
  -**状态词归位**:"闷热/潮湿/泥泞"(濡れた/ぬめぬめ)严格修饰女性私处或贴身衣物；"脉动/坚硬/硕大"严格修饰男性器官。
  -**动作归位**:确保"绝顶/高潮/射出"对应到正确的角色身上，严禁主客体颠倒。
3.**严禁二次创作**:仅翻译{content}提供的信息。严禁添加原文中不存在的动作描写、对话、心理活动或括号内注释。
4.**去日本汉化(地道表达)**:保持字幕的流动感，使用"尽管...但..."、"随着...竟然..."等连词增强中文阅读张力。
5.**风格适配**:根据内容标签动态调整用词。若是"清楚/素人"风格则用词略收敛；若是"凌辱/调教/骑乘"则用词需暴虐直白。
6.**繁简转换**:内容为繁体时直接转为简体中文。
7.**禁止注释**:直接输出翻译结果，不要注释，不要解析，不要剧情分析。
8.**唯一输出**:严禁提供备选方案或第二种翻译，必须输出最精准、最肉感的唯一结果。
9.**语种**:最终输出语言为{lang}。""",
    "standard": """你是一个专业的日语到{lang}字幕翻译器。

要求：
- 准确流畅地翻译日语字幕
- 语言自然，适合日常观看
- 专有名词保留原文
- 字幕长度适中
- 直接输出翻译结果，不要有任何思考过程或分析内容""",
}


STRUCTURED_TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["index", "text"],
            },
        },
    },
    "required": ["translations"],
}


class OpenAILikeTranslator:
    """Translator for Ollama, OpenAI, LM Studio, and compatible APIs."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        translate_style: str = "adult_explicit",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.translate_style = translate_style
        self.timeout = timeout

    def translate(self, text: str, target_lang: str = "zh") -> str:
        results = self.translate_batch([text], target_lang)
        return results[0]

    def _chat_endpoint(self) -> str:
        return _resolve_chat_completions_url(self.base_url)

    def translate_batch(
        self,
        texts: list[str],
        target_lang: str = "zh",
        translate_style: Optional[str] = None,
    ) -> list[str]:
        """Translate a numbered batch while preserving subtitle boundaries."""
        if not texts:
            return []

        local_results: list[Optional[str]] = [
            self._local_source_translation(text, target_lang)
            for text in texts
        ]
        model_positions = [
            index for index, translated in enumerate(local_results)
            if translated is None
        ]
        if not model_positions:
            return [text or "" for text in local_results]

        style = translate_style or self.translate_style
        lang_display = self._get_lang_display(target_lang)
        style_key = style if style in TRANSLATE_SYSTEM_PROMPTS else "adult_explicit"
        system_prompt = TRANSLATE_SYSTEM_PROMPTS[style_key].format(
            lang=lang_display,
            content="[序号] 日语字幕文本（见下方用户消息）",
            dictionary="（本任务无自定义字典规则）",
        )
        model_texts = [texts[index] for index in model_positions]
        formatted_content = self._format_subtitles(model_texts)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        is_ollama = _is_ollama_url(self.base_url)
        request_json = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": formatted_content},
            ],
            "temperature": 0.3,
            "max_tokens": 16384 if is_ollama else 8192,
        }
        if is_ollama:
            request_json["thinking"] = False

        try:
            with httpx.Client(timeout=self.timeout, trust_env=not is_ollama) as client:
                use_native_ollama = (
                    _is_ollama_url(self.base_url)
                    and not self.base_url.lower().rstrip("/").endswith(
                        ("/v1", "/v1/chat", "/v1/chat/completions")
                    )
                )
                if use_native_ollama:
                    native_url = (
                        self.base_url
                        if _is_ollama_native_chat_url(self.base_url)
                        else f"{_resolve_ollama_root_url(self.base_url)}/api/chat"
                    )
                    response = client.post(
                        native_url,
                        headers={"Content-Type": "application/json"},
                        json={
                            "model": self.model,
                            "messages": request_json["messages"],
                            "format": STRUCTURED_TRANSLATION_SCHEMA,
                            "stream": False,
                            "think": False,
                            "options": {
                                "temperature": request_json["temperature"],
                                "num_predict": request_json["max_tokens"],
                            },
                        },
                    )
                else:
                    response = client.post(
                        _resolve_chat_completions_url(self.base_url),
                        headers=headers,
                        json=request_json,
                    )
                response.raise_for_status()
                result = response.json()
                if use_native_ollama:
                    message = result.get("message", {})
                    if not message and result.get("choices"):
                        message = result.get("choices", [{}])[0].get("message", {})
                else:
                    message = result.get("choices", [{}])[0].get("message", {})
                generated_text = message.get("content") or ""
                reasoning = message.get("reasoning") or message.get("thinking")
                if not generated_text and reasoning:
                    generated_text = self._extract_from_reasoning(reasoning, len(model_texts))
                if not generated_text:
                    raise RuntimeError(
                        f"API 返回内容为空（model={self.model})。"
                        "可能是模型不支持此请求或 API 限流。"
                    )

            translations = self._parse_structured_translations(generated_text, len(model_texts))
            if translations is None:
                translations = self._parse_translations(generated_text, len(model_texts))
            cleaned_translations = [text.strip() for text in translations]
            has_translation_content = any(cleaned_translations)
            total_chars = sum(len(text) for text in cleaned_translations)
            source_total_chars = sum(len(text) for text in model_texts)
            is_suspiciously_short = (
                source_total_chars >= 20
                and total_chars <= max(2, len(model_texts))
            )
            refusal_phrases = [
                "无法提供", "不适合", "不能翻译", "无法翻译", "抱歉", "sorry",
                "cannot", "unable", "refuse", "过滤", "filter", "することはできません",
                "の内容が", "性的", "_TEXTCONTENT_", "cannot provide", "not appropriate",
                "unable to", "不符合", "无法生成", "内容限制",
            ]
            is_refusal = any(phrase.lower() in generated_text.lower() for phrase in refusal_phrases)
            if is_refusal or is_suspiciously_short or not has_translation_content:
                raise RuntimeError(
                    "翻译模型拒绝翻译（内容过滤或返回过短）。"
                    f"可能是批次过短（{len(model_texts)}条/{total_chars}字符）或内容被拒绝。"
                    "尝试更换翻译模型或使用 standard 翻译风格。"
                    f"原始返回: {generated_text[:200]}"
                )
            model_results = [
                self._sanitize_translation(source, translated)
                for source, translated in zip(model_texts, translations)
            ]
            for position, translated in zip(model_positions, model_results):
                local_results[position] = translated
            return [text or "" for text in local_results]
        except httpx.ConnectError as exc:
            logger.error("连接失败: %s", self.base_url)
            raise ConnectionError(f"无法连接到 {self.base_url}，请检查地址是否正确") from exc
        except httpx.TimeoutException as exc:
            logger.error("请求超时: %s", self.base_url)
            raise TimeoutError("翻译请求超时，请重试") from exc
        except Exception as exc:
            logger.error("翻译失败: %s", exc)
            raise RuntimeError(f"翻译失败: {exc}") from exc

    @staticmethod
    def _format_subtitles(texts: list[str]) -> str:
        return (
            "请只输出 JSON，不要输出解释、注释或 Markdown。"
            "JSON 格式必须为 {\"translations\":[{\"index\":1,\"text\":\"译文\"}]}。"
            "index 必须与输入编号一致，text 只能包含字幕译文。\n\n"
            + "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(texts))
        )

    @staticmethod
    def _parse_structured_translations(generated_text: str, expected_count: int) -> Optional[list[str]]:
        raw = (generated_text or "").strip()
        if not raw:
            return None
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\"translations\".*\}", raw, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        items = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return None
        translations = ["" for _ in range(expected_count)]
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                return None
            index = item.get("index")
            text = item.get("text")
            if not isinstance(index, int) or not 1 <= index <= expected_count or not isinstance(text, str):
                return None
            translations[index - 1] = text.strip()
            seen.add(index)
        if len(seen) != expected_count:
            return None
        return translations

    @staticmethod
    def _parse_translations(generated_text: str, expected_count: int) -> list[str]:
        translations: list[str] = []
        for line in generated_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("["):
                parts = line.split("]", 1)
                translations.append(parts[1].strip() if len(parts) == 2 else line)
            elif translations:
                translations[-1] += " " + line
            elif expected_count == 1:
                translations.append(line)
        while len(translations) < expected_count:
            translations.append(translations[-1] if translations else "")
        return translations[:expected_count]

    @staticmethod
    def _normalize_for_repetition(text: str) -> str:
        return re.sub(r"[\s。、，,.!?！？…~～ー\-・「」『』（）()\[\]【】\"'“”‘’]+", "", text or "")

    @staticmethod
    def _is_nonverbal_source(text: str) -> bool:
        source = (text or "").strip()
        if not source:
            return True
        return not re.search(r"[\w\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]", source)

    @staticmethod
    def _collapse_nonverbal_source(text: str) -> str:
        source = (text or "").strip()
        if "…" in source or "..." in source:
            return "..."
        return source or "..."

    @classmethod
    def _local_source_translation(cls, source: str, target_lang: str) -> Optional[str]:
        """Translate non-dialogue subtitle cues locally before sending them to an LLM."""
        if not target_lang.lower().startswith("zh"):
            return None
        if cls._is_nonverbal_source(source):
            return cls._collapse_nonverbal_source(source)
        normalized_len = len(cls._normalize_for_repetition(source))
        if normalized_len >= 12 and cls._is_repetitive_source(source):
            return cls._collapse_repetitive_source(source)
        return None

    @classmethod
    def _dominant_repetition_ratio(cls, text: str) -> float:
        normalized = cls._normalize_for_repetition(text)
        if not normalized:
            return 0.0
        counts = {}
        for ch in normalized:
            counts[ch] = counts.get(ch, 0) + 1
        return max(counts.values()) / len(normalized)

    @classmethod
    def _is_repetitive_source(cls, text: str) -> bool:
        normalized = cls._normalize_for_repetition(text)
        if len(normalized) < 8:
            return False
        if cls._dominant_repetition_ratio(normalized) >= 0.55:
            return True
        kana_noise = set("んンぐグぁァあアはハうウぅゥっッちゅチュじゅジュぶブぷプむムめメろロよヨ")
        kana_noise_count = sum(1 for ch in normalized if ch in kana_noise)
        return kana_noise_count / len(normalized) >= 0.85 and len(set(normalized)) <= 8

    @classmethod
    def _find_repeated_unit(cls, text: str) -> Optional[str]:
        normalized = cls._normalize_for_repetition(text)
        if len(normalized) < 12:
            return None
        max_unit = min(12, len(normalized) // 3)
        for unit_len in range(1, max_unit + 1):
            chunks = [
                normalized[i : i + unit_len]
                for i in range(0, min(len(normalized), unit_len * 12), unit_len)
            ]
            if len(chunks) >= 4 and len(set(chunks[:4])) == 1:
                return chunks[0]
        return None

    @classmethod
    def _is_repetitive_translation(cls, text: str) -> bool:
        normalized = cls._normalize_for_repetition(text)
        if len(normalized) < 24:
            return False
        return cls._dominant_repetition_ratio(normalized) >= 0.35 or cls._find_repeated_unit(text) is not None

    @staticmethod
    def _is_prompt_meta_translation(text: str) -> bool:
        lowered = (text or "").strip().lower()
        meta_phrases = [
            "请提供",
            "等待您提供",
            "需要汉化的",
            "需要翻译的",
            "我将根据",
            "上述规则",
            "上述指令",
            "这段日语文本似乎",
            "由于没有",
            "缺乏具体上下文",
            "如果能提供",
            "for me to translate",
            "please provide",
            "provide the text",
        ]
        return any(phrase in lowered for phrase in meta_phrases)

    @classmethod
    def _collapse_repetitive_source(cls, source: str) -> str:
        normalized = cls._normalize_for_repetition(source)
        if not normalized:
            return cls._collapse_nonverbal_source(source)
        if any(token in normalized for token in ("じゅ", "ぢゅ", "ちゅ", "ジュ", "ヂュ", "チュ")):
            return "啾噜、啾噜..."
        if set(normalized) <= set("るルろロっッ"):
            return "噜、噜..."
        if set(normalized) <= set("ぐグ"):
            return "咕、咕..."
        if any(ch in normalized for ch in "んンぐグ"):
            return "嗯、嗯..."
        if any(ch in normalized for ch in "あアぁァ"):
            return "啊、啊..."
        source_unit = cls._find_repeated_unit(source)
        if source_unit:
            return f"{source_unit}、{source_unit}..."
        return f"{normalized[:6]}..."

    @classmethod
    def _collapse_repetitive_translation(cls, source: str, translated: str) -> str:
        unit = cls._find_repeated_unit(translated)
        if unit:
            if len(unit) == 1:
                return f"{unit}、{unit}..."
            return f"{unit}、{unit}..."
        if cls._is_repetitive_source(source):
            return cls._collapse_repetitive_source(source)
        normalized = cls._normalize_for_repetition(translated)
        return (normalized[:12] + "...") if normalized else translated.strip()

    @classmethod
    def _sanitize_translation(cls, source: str, translated: str) -> str:
        if cls._is_nonverbal_source(source):
            return cls._collapse_nonverbal_source(source)

        cleaned = (translated or "").strip()
        if not cleaned:
            return cleaned

        source_repetition_len = len(cls._normalize_for_repetition(source))
        if cls._is_repetitive_source(source) and (
            cls._is_prompt_meta_translation(cleaned)
            or cls._is_repetitive_translation(cleaned)
            or source_repetition_len >= 80
        ):
            collapsed = cls._collapse_repetitive_source(source)
            logger.warning(
                "Collapsed non-dialogue translation output: source_len=%s translated_len=%s source=%r collapsed=%r",
                source_repetition_len,
                len(cls._normalize_for_repetition(cleaned)),
                source[:80],
                collapsed,
            )
            return collapsed

        if cls._is_prompt_meta_translation(cleaned) and len(cls._normalize_for_repetition(source)) <= 12:
            collapsed = cls._collapse_repetitive_source(source)
            logger.warning(
                "Collapsed prompt-meta translation output: source=%r translated=%r collapsed=%r",
                source[:80],
                cleaned[:120],
                collapsed,
            )
            return collapsed

        source_len = max(1, len(cls._normalize_for_repetition(source)))
        translated_len = len(cls._normalize_for_repetition(cleaned))
        suspiciously_expanded = translated_len > max(240, source_len * 12)
        if suspiciously_expanded and (cls._is_repetitive_source(source) or cls._is_repetitive_translation(cleaned)):
            collapsed = cls._collapse_repetitive_translation(source, cleaned)
            logger.warning(
                "Collapsed repetitive translation output: source_len=%s translated_len=%s source=%r collapsed=%r",
                source_len,
                translated_len,
                source[:80],
                collapsed,
            )
            return collapsed
        return cleaned

    @staticmethod
    def _extract_from_reasoning(reasoning: str, expected_count: int) -> str:
        lines = reasoning.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if not line.startswith("["):
                continue
            parts = line.split("]", 1)
            if len(parts) != 2 or not parts[1].strip():
                continue
            result_lines: list[str] = []
            for raw_line in lines[i:]:
                current = raw_line.strip()
                if current.startswith("["):
                    numbered = current.split("]", 1)
                    if len(numbered) == 2:
                        result_lines.append(f"[{numbered[0][1:]}] {numbered[1].strip()}")
                elif result_lines:
                    result_lines[-1] += " " + current
            if result_lines:
                return "\n".join(result_lines)

        translations: list[str] = []
        for index in range(1, expected_count + 1):
            patterns = [
                rf"\*\*\[{index}\]\*\*.*?➡️.*?\*\*中文[:：]\*\*\s*(.+?)(?:\n|$)",
                rf"\[{index}\].*?➡️.*?:\s*(.+?)(?:\n|$)",
                r"中文[:：]\s*(.+?)(?:\n|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, reasoning, re.DOTALL)
                if match:
                    translations.append(match.group(1).strip())
                    break
            else:
                translations.append("")
        if any(translations):
            return "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(translations))
        return reasoning.strip()

    @staticmethod
    def _get_lang_display(lang_code: str) -> str:
        return {
            "zh": "中文", "en": "英文", "ko": "韩文",
            "zh-CN": "简体中文", "zh-TW": "繁体中文",
        }.get(lang_code, lang_code)


def get_translator(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    translate_style: str = "adult_explicit",
    timeout: Optional[int] = None,
) -> OpenAILikeTranslator:
    settings_base_url = os.environ.get("WHISPER_TRANSLATE_BASE_URL", "https://api.openai.com/v1")
    settings_api_key = os.environ.get("WHISPER_TRANSLATE_API_KEY", "")
    resolved_base_url = base_url or settings_base_url
    if timeout is None:
        timeout = 300 if _is_ollama_url(resolved_base_url) else 120
    return OpenAILikeTranslator(
        model=model or os.environ.get("WHISPER_TRANSLATE_MODEL", "gpt-4o-mini"),
        base_url=resolved_base_url,
        api_key=api_key or settings_api_key,
        translate_style=translate_style,
        timeout=timeout,
    )


def check_translator_health(
    base_url: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> dict:
    result = {"available": False, "message": "", "models": []}
    base_url = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        try:
            with httpx.Client(timeout=10, trust_env=not _is_ollama_url(base_url)) as client:
                if _is_ollama_native_chat_url(base_url):
                    models_resp = client.get(f"{_resolve_ollama_root_url(base_url)}/api/tags")
                    models_data = models_resp.json() if models_resp.status_code == 200 else {}
                    available_models = [
                        item["name"] for item in models_data.get("models", [])
                        if not model or item["name"] == model or item["name"].startswith(model.split("-")[0])
                    ]
                else:
                    models_base = base_url
                    for suffix in ("/v1/chat/completions", "/v1/chat"):
                        if models_base.endswith(suffix):
                            models_base = models_base[: -len(suffix)]
                            break
                    models_resp = client.get(
                        f"{models_base.removesuffix('/v1')}/v1/models",
                        headers=headers,
                    )
                    models_data = models_resp.json() if models_resp.status_code == 200 else {}
                    available_models = [
                        item["id"] for item in models_data.get("data", [])
                        if not model or item["id"] == model or item["id"].startswith(model.split("-")[0])
                    ]
                if models_resp.status_code == 200:
                    result["models"] = available_models[:10]
        except Exception:
            pass

        test_timeout = 300 if _is_ollama_url(base_url) else 30
        translator = OpenAILikeTranslator(
            model=model, base_url=base_url, api_key=api_key,
            translate_style="standard", timeout=test_timeout,
        )
        translated = translator.translate_batch(["テスト"], "zh")
        if translated and translated[0]:
            result["available"] = True
            result["message"] = "连接成功，翻译功能正常"
        else:
            result["message"] = "连接成功但翻译返回为空"
    except ConnectionError as exc:
        result["message"] = f"连接失败: {exc}"
    except TimeoutError as exc:
        result["message"] = f"请求超时: {exc}"
    except Exception as exc:
        result["message"] = f"错误: {exc}"
    return result
