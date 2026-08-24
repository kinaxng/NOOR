from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
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


def test_normalize_github_mirror_preserves_original_github_path():
    from app.core.config import _normalize_github_mirror_instead_of_prefix

    assert _normalize_github_mirror_instead_of_prefix("https://ghproxy.com") == (
        "https://ghproxy.com/https://github.com/"
    )
    assert _normalize_github_mirror_instead_of_prefix("https://gh.example.com/") == (
        "https://gh.example.com/https://github.com/"
    )
    assert _normalize_github_mirror_instead_of_prefix("https://github.com") == (
        "https://github.com/"
    )
    assert _normalize_github_mirror_instead_of_prefix("") == (
        "https://ghproxy.com/https://github.com/"
    )


def test_apply_network_env_sets_token_and_fixed_git_mirror(monkeypatch):
    from app.core.config import Settings

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "HF_ENDPOINT", "HF_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    Settings.apply_network_env(
        SimpleNamespace(
            github_token="ghp_test",
            hf_token="hf_test",
            hf_mirror="https://hf.example",
            http_proxy="http://proxy:7890",
            github_mirror="https://ghproxy.com",
        )
    )

    assert calls == [
        ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
        ["git", "config", "--global", "url.https://ghproxy.com/https://github.com/.insteadOf", "https://github.com/"],
    ]
    assert os.environ["GITHUB_TOKEN"] == "ghp_test"
    assert os.environ["HF_TOKEN"] == "hf_test"
    assert os.environ["HF_ENDPOINT"] == "https://hf.example"
    assert os.environ["HTTPS_PROXY"] == "http://proxy:7890"


def test_apply_network_env_clears_old_malformed_mirror_key(monkeypatch):
    from app.core.config import Settings

    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    Settings.apply_network_env(
        SimpleNamespace(
            github_token="",
            hf_token="",
            hf_mirror="",
            http_proxy="",
            github_mirror="",
        )
    )

    assert calls == [
        ["git", "config", "--global", "--unset", "url.https://ghproxy.com/.insteadOf"],
        ["git", "config", "--global", "--unset", "url.https://ghproxy.com/https://github.com/.insteadOf"],
    ]
    assert "GITHUB_TOKEN" not in os.environ


def test_config_project_root_env_controls_runtime_paths():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PROJECT_ROOT"] = "/tmp/noor-test-project"
    env["PYTHONPATH"] = str(repo_root / "backend")
    env.pop("NOOR_ENV_FILE", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.config import ENV_FILE_PATH, PROJECT_ROOT; print(PROJECT_ROOT); print(ENV_FILE_PATH)",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = proc.stdout.strip().splitlines()

    assert lines[0] == "/tmp/noor-test-project"
    assert lines[1] == "/tmp/noor-test-project/.env"
