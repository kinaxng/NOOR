from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WhisperRuntimeTier:
    value: str
    device: str
    compute_type: str


WHISPER_RUNTIME_TIERS: dict[str, WhisperRuntimeTier] = {
    "gpu_standard": WhisperRuntimeTier("gpu_standard", "cuda", "float16"),
    "gpu_low_vram": WhisperRuntimeTier("gpu_low_vram", "cuda", "int8_float16"),
    "cpu": WhisperRuntimeTier("cpu", "cpu", "int8"),
}

_ALIASES = {
    "gpu": "gpu_standard",
    "cuda": "gpu_standard",
    "standard": "gpu_standard",
    "float16": "gpu_standard",
    "low_vram": "gpu_low_vram",
    "low-vram": "gpu_low_vram",
    "int8_float16": "gpu_low_vram",
    "cpu_int8": "cpu",
}


def normalize_whisper_runtime_tier(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    return _ALIASES.get(
        normalized,
        normalized if normalized in WHISPER_RUNTIME_TIERS else "gpu_standard",
    )


def resolve_whisper_runtime_tier(value: str | None) -> WhisperRuntimeTier:
    return WHISPER_RUNTIME_TIERS[normalize_whisper_runtime_tier(value)]


def apply_whisper_runtime_tier(payload: dict) -> dict:
    tier = resolve_whisper_runtime_tier(payload.get("runtime_tier"))
    payload["runtime_tier"] = tier.value
    payload["device"] = tier.device
    payload["compute_type"] = tier.compute_type
    return payload
