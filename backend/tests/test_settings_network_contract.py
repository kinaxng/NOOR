from __future__ import annotations

from types import SimpleNamespace

from app.api.settings_response import build_settings_payload
from app.api.settings_updates import apply_network_config_updates


def _version_info() -> dict[str, object]:
    return {
        "version": None,
        "is_docker": False,
        "is_submodule": False,
        "install_mode": "unknown",
        "can_self_upgrade": False,
        "upgrade_strategy": "manual",
        "upgrade_hint": "",
        "repo_path": None,
    }


def test_network_settings_payload_includes_actor_mapping_and_github_token():
    payload = build_settings_payload(
        env_data={
            "GITHUB_TOKEN": "ghp_test",
            "ACTOR_MAPPING_AUTO_UPDATE": "false",
        },
        version_info=_version_info(),
        lada_model_weights_dir="/models/lada",
        whisper_features={},
    )

    assert payload["network"]["github_token"] == "ghp_test"
    assert payload["network"]["actor_mapping_auto_update"] is False


def test_network_settings_update_persists_frontend_fields():
    values: dict[str, str] = {}
    apply_network_config_updates(
        SimpleNamespace(
            acceleration_mode="mirror",
            http_proxy="http://proxy:7890",
            github_mirror="https://gh.example",
            github_token="ghp_saved",
            hf_mirror="https://hf.example",
            pip_mirror="https://pip.example/simple",
            hf_token="hf_saved",
            actor_mapping_auto_update=False,
        ),
        values.__setitem__,
    )

    assert values["GITHUB_TOKEN"] == "ghp_saved"
    assert values["ACTOR_MAPPING_AUTO_UPDATE"] == "false"
