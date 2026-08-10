from __future__ import annotations


class AudioEnhancer:
    """Compatibility implementation for retired optional audio enhancers.

    The recovered Whisper pipeline still imports this class, but the NOOR
    configuration was consolidated to the ChickenRice path where no enhancer
    is selected by default. Returning the original audio preserves that path
    while keeping persisted jobs readable.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or ''

    def enhance(self, audio_path: str) -> str:
        return audio_path
