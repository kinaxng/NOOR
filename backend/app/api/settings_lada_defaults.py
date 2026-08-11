"""LADA defaults persistence helper, reconstructed from bytecode."""
from __future__ import annotations

from typing import Any, Callable


def apply_lada_defaults_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("LADA_DEVICE", config.device)
    update_env_value_fn("LADA_FP16", "true" if config.fp16 else "false")
    update_env_value_fn("LADA_DETECTION_MODEL", config.detection_model)
    update_env_value_fn("LADA_RESTORATION_MODEL", config.restoration_model)
    update_env_value_fn("LADA_ENCODING_PRESET", config.encoding_preset)
    update_env_value_fn("LADA_MAX_CLIP_LENGTH", str(config.max_clip_length))
    update_env_value_fn(
        "LADA_DETECT_FACE_MOSAICS", "true" if config.detect_face_mosaics else "false"
    )
