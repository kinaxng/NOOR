from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from app.api import settings_lada


def test_lada_settings_uses_bundled_python_env(monkeypatch, tmp_path):
    calls: list[tuple[list[str], dict]] = []

    def fake_run(args, **kwargs):
        calls.append((list(args), kwargs.get("env") or {}))
        if "--list-devices" in args:
            return SimpleNamespace(returncode=0, stdout="Device\n----\ncpu CPU\n")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"detection": [], "restoration": []}))

    monkeypatch.setattr(settings_lada.subprocess, "run", fake_run)
    monkeypatch.setattr(
        settings_lada,
        "build_lada_python_env",
        lambda base: {**base, "__NOOR_LADA_ENV__": "1"},
    )

    result = settings_lada.get_lada_info_impl(
        settings=SimpleNamespace(lada_model_dir=""),
        project_root=tmp_path,
        install_info={"install_mode": "external-cli", "can_self_upgrade": False, "upgrade_strategy": "manual", "upgrade_hint": ""},
        lada_cli_base_cmd_fn=lambda: ["lada-cli"],
        python_executable_fn=lambda: sys.executable,
        format_size_fn=lambda value: str(value),
    )

    assert result["devices"] == [{"id": "cpu", "name": "CPU"}]
    script_call = next(args for args, _env in calls if "-c" in args)
    assert script_call[0] == sys.executable
    assert script_call[1] == "-c"
    assert "import lada" in script_call[2]
    assert calls[1][1]["__NOOR_LADA_ENV__"] == "1"
    assert calls[1][1]["LADA_MODEL_WEIGHTS_DIR"]
