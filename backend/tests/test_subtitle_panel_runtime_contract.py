from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = ROOT / relative
    assert path.is_file(), f"missing source contract file: {path}"
    return path.read_text(encoding="utf-8")


def test_subtitle_panel_preserves_final_whisper_runtime_contract() -> None:
    source = _read("frontend/src/components/noor/SubtitlePanel.vue")

    assert "type WhisperRuntimeTier" in source
    assert "const whisperDefaultRuntimeTier = ref<WhisperRuntimeTier>('gpu_standard')" in source
    assert "whisperDefaultVadBackend" in source
    assert "whisperDefaultTimingRefiner" in source
    assert "whisperDefaultRuntimeTier.value = defaults.runtime_tier" in source
    assert "whisperDefaultVadBackend.value = defaults.vad_backend" in source
    assert "whisperDefaultTimingRefiner.value = defaults.timing_refiner" in source

    assert "runtime_tier: whisperDefaultRuntimeTier.value" in source
    assert "vad_backend: whisperDefaultVadBackend.value" in source
    assert "timing_refiner: whisperDefaultTimingRefiner.value" in source


def test_whisper_settings_keeps_runtime_tier_ui_and_payload() -> None:
    source = _read("frontend/src/views/settings/WhisperSettings.vue")

    assert "WHISPER_RUNTIME_TIERS" in source
    assert "getWhisperRuntimeTierMeta" in source
    assert "const activeRuntimeTier = ref<WhisperRuntimeTier>('gpu_standard')" in source
    assert "activeRuntimeTier.value = defaults.runtime_tier" in source
    assert "runtime_tier: activeRuntimeTier.value" in source
    assert "runtimeTierOptions" in source
    assert "settings.whisper.runtimeTierTitle" in source


def test_whisper_profiles_exports_runtime_tier_contract() -> None:
    source = _read("frontend/src/composables/useWhisperProfiles.ts")

    assert "WHISPER_RUNTIME_TIERS" in source
    assert "export function getWhisperRuntimeTierMeta" in source
    assert "normalizeWhisperRuntimeTier(runtimeTier)" in source
    assert "gpu_standard" in source
    assert "gpu_low_vram" in source
    assert "cpu" in source
