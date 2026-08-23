from __future__ import annotations

import httpx
import pytest

from app.pipeline.whisper.translator import OpenAILikeTranslator, _is_ollama_url


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
    assert _is_ollama_url("http://192.168.31.10:11434/v1")
    assert _is_ollama_url("http://10.0.0.8:11434/v1")
    assert not _is_ollama_url("https://api.openai.com/v1")
    assert not _is_ollama_url("https://api.example.com/v1")


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
