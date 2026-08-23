import subprocess

import pytest

from app.pipeline.whisper.runtime import raise_if_cancelled, run_cancellable_subprocess
from app.pipeline.whisper.types import WhisperCancellationRequested


def test_raise_if_cancelled_accepts_missing_callback():
    raise_if_cancelled(None)


def test_raise_if_cancelled_raises_pipeline_exception():
    with pytest.raises(WhisperCancellationRequested):
        raise_if_cancelled(lambda: True)


def test_cancellable_subprocess_returns_completed_process():
    result = run_cancellable_subprocess(
        ["/bin/sh", "-c", "printf ready"],
        cancel_callback=lambda: False,
    )
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.stdout == "ready"


def test_translation_needs_line_retry_detects_untranslated_output():
    from app.pipeline.whisper.runtime import _translation_needs_line_retry

    assert _translation_needs_line_retry("こんにちは", "", "zh")
    assert _translation_needs_line_retry("こんにちは", "こんにちは", "zh")
    assert _translation_needs_line_retry("さようなら", "さようなら", "zh")
    assert not _translation_needs_line_retry("こんにちは", "你好", "zh")
    assert not _translation_needs_line_retry("今日はいい天気ですね", "今天天气很好", "zh")


def test_translation_process_recovers_failed_batch_with_single_line_retries(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.pipeline.whisper import runtime as whisper_runtime

    srt_path = tmp_path / 'sample.srt'
    srt_path.write_text(
        '1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n\n'
        '2\n00:00:03,000 --> 00:00:04,000\nさようなら\n',
        encoding='utf-8',
    )

    class FakeTranslator:
        def translate_batch(self, batch_texts, target_lang, translate_style='standard'):
            if len(batch_texts) > 1:
                raise RuntimeError('batch failed')
            return ['你好' if batch_texts[0] == 'こんにちは' else '再见']

    class FakeQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    class FakeCancelEvent:
        def is_set(self):
            return False

    monkeypatch.setattr('app.pipeline.whisper.translator.get_translator', lambda **kwargs: FakeTranslator())
    monkeypatch.setattr('app.pipeline.whisper.translator._is_ollama_url', lambda _base_url: True)

    queue = FakeQueue()
    whisper_runtime._translation_process_entry(
        str(srt_path),
        'zh',
        'demo-model',
        'http://ollama.local',
        None,
        'adult_explicit',
        0,
        100,
        queue,
        FakeCancelEvent(),
    )

    output = (tmp_path / 'sample.zh.srt').read_text(encoding='utf-8')
    assert '你好' in output
    assert '再见' in output
    assert any('尝试逐条补翻' in item.get('line', '') for item in queue.items)


def test_translation_process_repairs_untranslated_lines_in_successful_batch(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.pipeline.whisper import runtime as whisper_runtime

    srt_path = tmp_path / 'sample.srt'
    srt_path.write_text(
        '1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n\n'
        '2\n00:00:03,000 --> 00:00:04,000\nさようなら\n',
        encoding='utf-8',
    )

    class FakeTranslator:
        def translate_batch(self, batch_texts, target_lang, translate_style='standard'):
            if len(batch_texts) > 1:
                return ['こんにちは', '再见']
            return ['你好']

    class FakeQueue:
        def __init__(self):
            self.items = []

        def put(self, item):
            self.items.append(item)

    class FakeCancelEvent:
        def is_set(self):
            return False

    monkeypatch.setattr('app.pipeline.whisper.translator.get_translator', lambda **kwargs: FakeTranslator())
    monkeypatch.setattr('app.pipeline.whisper.translator._is_ollama_url', lambda _base_url: True)

    queue = FakeQueue()
    whisper_runtime._translation_process_entry(
        str(srt_path),
        'zh',
        'demo-model',
        'http://ollama.local',
        None,
        'adult_explicit',
        0,
        100,
        queue,
        FakeCancelEvent(),
    )

    output = (tmp_path / 'sample.zh.srt').read_text(encoding='utf-8')
    assert '你好' in output
    assert '再见' in output
    assert 'こんにちは' not in output
    assert any('疑似未翻译' in item.get('line', '') for item in queue.items)
