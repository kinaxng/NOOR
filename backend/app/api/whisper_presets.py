"""Named Whisper request presets.

Reconstructed from the preserved Python 3.13 bytecode.  The historical
``best`` preset remains for compatibility with previously saved task payloads.
"""
from __future__ import annotations

from typing import Any


BEST_WHISPER_PRESET = {
    "strategy": "chickenrice",
    "model_backend": "chickenrice-zh",
    "model": "chickenrice-zh",
    "pipeline_mode": "faster",
    "whisper_task": "translate",
    "language": "ja",
    "sensitivity": "balanced",
    "vad_backend": "whisper_vad_onnx",
}


def apply_whisper_preset(payload: dict[str, Any], preset: str | None) -> dict[str, Any]:
    normalized = (preset or "").strip().lower()
    if normalized != "best":
        return payload
    merged = dict(payload)
    merged.update(BEST_WHISPER_PRESET)
    return merged
