from __future__ import annotations

import os

from app.core import lada_paths


def test_lada_python_env_prepends_repo_path(monkeypatch, tmp_path):
    repo_path = tmp_path / "backend" / "app" / "pipeline" / "lada"
    monkeypatch.setattr(lada_paths, "resolve_lada_repo_path", lambda: repo_path)

    env = lada_paths.build_lada_python_env({"PYTHONPATH": "/existing", "PATH": "/bin"})

    assert env["PYTHONPATH"] == f"{repo_path}{os.pathsep}/existing"
    assert env["PATH"] == "/bin"


def test_lada_python_env_preserves_env_without_repo(monkeypatch):
    monkeypatch.setattr(lada_paths, "resolve_lada_repo_path", lambda: None)

    env = lada_paths.build_lada_python_env({"PYTHONPATH": "/existing"})

    assert env["PYTHONPATH"] == "/existing"
