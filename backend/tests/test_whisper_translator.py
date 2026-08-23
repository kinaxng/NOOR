from __future__ import annotations

import httpx
import pytest

from app.pipeline.whisper.translator import (
    OpenAILikeTranslator,
    _is_ollama_native_chat_url,
    _is_ollama_url,
    _resolve_chat_completions_url,
    _resolve_ollama_root_url,
)


def test_chat_endpoint_preserves_full_user_endpoint():
    translator = OpenAILikeTranslator(base_url="http://ollama:11434/v1/chat")
    assert translator._chat_endpoint() == "http://ollama:11434/v1/chat"

    translator = OpenAILikeTranslator(base_url="http://ollama:11434/v1/chat/completions")
    assert translator._chat_endpoint() == "http://ollama:11434/v1/chat/completions"

    translator = OpenAILikeTranslator(base_url="http://ollama:11434/v1/")
    assert translator._chat_endpoint() == "http://ollama:11434/v1/chat/completions"

    translator = OpenAILikeTranslator(base_url="http://ollama:11434")
    assert translator._chat_endpoint() == "http://ollama:11434/v1/chat/completions"


def test_is_ollama_url_detects_local_and_ollama_endpoints():
    assert _is_ollama_url("http://localhost:11434/v1")
    assert _is_ollama_url("http://ollama:11434/v1/chat")
    assert _is_ollama_url("http://127.0.0.1:11434/v1")
    assert _is_ollama_url("http://192.168.31.10:11434/v1")
    assert _is_ollama_url("http://10.0.0.8:11434/v1")
    assert not _is_ollama_url("https://api.openai.com/v1")
    assert not _is_ollama_url("https://api.example.com/v1")


def test_resolve_chat_completions_url_preserves_full_user_endpoint():
    assert _resolve_chat_completions_url("http://ollama:11434/v1/chat") == "http://ollama:11434/v1/chat"
    assert _resolve_chat_completions_url("http://ollama:11434/v1/chat/completions") == "http://ollama:11434/v1/chat/completions"
    assert _resolve_chat_completions_url("http://ollama:11434/v1/") == "http://ollama:11434/v1/chat/completions"
    assert _resolve_chat_completions_url("http://ollama:11434") == "http://ollama:11434/v1/chat/completions"


def test_detects_ollama_native_chat_endpoint():
    assert _is_ollama_native_chat_url("http://ollama:11434/api/chat")
    assert _is_ollama_native_chat_url("http://ollama:11434/api/chat/")
    assert not _is_ollama_native_chat_url("http://ollama:11434/v1")
    assert _resolve_ollama_root_url("http://ollama:11434/api/chat") == "http://ollama:11434"


def test_translate_batch_posts_to_resolved_chat_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "[1] 你好\n[2] 今天天气很好",
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            captured["json"] = kwargs["json"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="test-model",
        base_url="http://192.168.31.3:11434/v1/chat/completions",
        api_key="test-key",
        translate_style="standard",
    )
    result = translator.translate_batch(["こんにちは", "今日はいい天気ですね"], "zh")

    assert captured["url"] == "http://192.168.31.3:11434/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["thinking"] is False
    assert result == ["你好", "今天天气很好"]


def test_translate_batch_rejects_refusal_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "抱歉，我无法翻译这段内容",
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="test-model",
        base_url="https://api.example.com/v1",
        translate_style="standard",
    )

    with pytest.raises(RuntimeError, match="拒绝翻译"):
        translator.translate_batch(["テスト"], "zh")


def test_translate_batch_supports_ollama_native_chat(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "qwen3.5:9b",
                "message": {
                    "role": "assistant",
                    "content": "[1] 你好\n[2] 今天天气很好",
                },
                "done": True,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *args, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs["json"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="qwen3.5:9b",
        base_url="http://127.0.0.1:11434/api/chat",
        translate_style="standard",
    )

    result = translator.translate_batch(["こんにちは", "今日はいい天気ですね"], "zh")

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["stream"] is False
    assert captured["json"]["think"] is False
    assert captured["json"]["format"]["required"] == ["translations"]
    assert captured["json"]["options"]["num_predict"] == 16384
    assert result == ["你好", "今天天气很好"]


def test_translate_batch_uses_structured_ollama_output(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": '{"translations":[{"index":1,"text":"你好"},{"index":2,"text":"今天天气很好"}]}'
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *args, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs["json"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="qwen3.5:9b",
        base_url="http://127.0.0.1:11434",
        translate_style="standard",
    )

    result = translator.translate_batch(["こんにちは", "今日はいい天気ですね"], "zh")

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["format"]["properties"]["translations"]["type"] == "array"
    assert result == ["你好", "今天天气很好"]


def test_translate_batch_skips_non_dialogue_lines_before_model(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": '{"translations":[{"index":1,"text":"等一下"}]}'
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, *args, **kwargs):
            captured["content"] = kwargs["json"]["messages"][1]["content"]
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="qwen3.5:9b",
        base_url="http://127.0.0.1:11434",
        translate_style="standard",
    )

    result = translator.translate_batch(["…", "待って", "じゅ" + ("る" * 80)], "zh")

    assert result == ["...", "等一下", "啾噜、啾噜..."]
    assert "待って" in captured["content"]
    assert "じゅ" not in captured["content"]


def test_translate_batch_accepts_single_unnumbered_translation(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "你好，今天天气很好。"
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="test-model",
        base_url="https://api.example.com/v1",
        translate_style="standard",
    )

    result = translator.translate_batch(["こんにちは、今日はいい天気ですね。"], "zh")

    assert result == ["你好，今天天气很好。"]


def test_translate_batch_collapses_runaway_repetitive_translation(monkeypatch):
    repeated = "啊嗯、" * 3000

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": f"[1] {repeated}"
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    translator = OpenAILikeTranslator(
        model="test-model",
        base_url="https://api.example.com/v1",
        translate_style="standard",
    )

    result = translator.translate_batch(["テスト"], "zh")

    assert result == ["啊嗯、啊嗯..."]


def test_sanitize_translation_keeps_non_repetitive_long_text():
    source = "これは長い説明文です。" * 10
    translated = "这是一段正常的长说明文本，用来确认清洗逻辑不会误伤非重复内容。" * 8

    assert OpenAILikeTranslator._sanitize_translation(source, translated) == translated
