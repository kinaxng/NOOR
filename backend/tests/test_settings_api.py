from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import settings as settings_api


@pytest.mark.asyncio
async def test_upgrade_lada_native_reinstall_uses_imported_sys(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []

    class FakeSettings:
        def apply_network_env(self) -> None:
            return None

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args[:4] == ["git", "fetch", "--tags", "origin"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[:3] == ["git", "pull", "--ff-only"]:
            return SimpleNamespace(returncode=0, stdout="updated", stderr="")
        if args[:3] == [settings_api._python_executable(), "-m", "pip"]:
            return SimpleNamespace(returncode=0, stdout="installed", stderr="")
        if args[:2] == [settings_api._python_executable(), "-c"]:
            return SimpleNamespace(returncode=0, stdout="1.2.3\n", stderr="")
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(settings_api, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        settings_api,
        "_get_lada_installation_info",
        lambda: {"is_docker": False, "repo_path": "/tmp/lada"},
    )
    monkeypatch.setattr(settings_api, "sys", SimpleNamespace(prefix="/usr", base_prefix="/usr"))
    monkeypatch.setattr(settings_api.subprocess, "run", fake_run)

    result = await settings_api.upgrade_lada()

    assert result == {"success": True, "version": "1.2.3", "output": "updated"}
    pip_call = next(args for args in calls if args[:3] == [settings_api._python_executable(), "-m", "pip"])
    assert "--break-system-packages" in pip_call
