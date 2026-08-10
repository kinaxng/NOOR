"""Small helpers for writing settings fields to the environment file.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

from typing import Any, Callable


def apply_emby_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("EMBY_SERVER", config.server)
    update_env_value_fn("EMBY_API_KEY", config.api_key)
    update_env_value_fn("EMBY_USER_ID", config.user_id)
    update_env_value_fn(
        "EMBY_ENABLED_LIBRARY_IDS",
        ",".join(config.enabled_library_ids) if config.enabled_library_ids else "",
    )


def build_storage_env_updates(config: Any, lada_model_weights_env: str) -> dict[str, str]:
    return {
        "SOURCE_DIR": config.source_dir,
        "OUTPUT_DIR": config.output_dir,
        "WHISPER_MODEL_DIR": config.whisper_model_dir,
        lada_model_weights_env: config.lada_model_dir,
    }


def apply_lada_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("LADA_CLI_PATH", config.cli_path)


def apply_network_config_updates(
    config: Any, update_env_value_fn: Callable[[str, str], None]
) -> None:
    update_env_value_fn("ACCELERATION_MODE", config.acceleration_mode)
    update_env_value_fn("HTTP_PROXY", config.http_proxy)
    update_env_value_fn("GITHUB_MIRROR", config.github_mirror)
    update_env_value_fn("HF_MIRROR", config.hf_mirror)
    update_env_value_fn("PIP_MIRROR", config.pip_mirror)
    update_env_value_fn("HF_TOKEN", config.hf_token)
