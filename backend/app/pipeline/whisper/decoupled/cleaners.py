from __future__ import annotations


class AnimeWhisperCleaner:
    def clean(self, text: str) -> str:
        return (text or '').strip()

    def process(self, text: str) -> str:
        return self.clean(text)


class Qwen3TextCleaner(AnimeWhisperCleaner):
    pass
