from __future__ import annotations

import os

from app.core import lada_paths


def test_lada_python_env_prepends_repo_path(monkeypatch, tmp_path):
    repo_path = tmp_path / "backend" / "app" / "pipeline" / "lada"
    monkeypatch.setattr(lada_paths, "resolve_lada_source_path", lambda: repo_path)

    env = lada_paths.build_lada_python_env({"PYTHONPATH": "/existing", "PATH": "/bin"})

    assert env["PYTHONPATH"] == f"{repo_path}{os.pathsep}/existing"
    assert env["PATH"] == "/bin"


def test_lada_python_env_preserves_env_without_repo(monkeypatch):
    monkeypatch.setattr(lada_paths, "resolve_lada_source_path", lambda: None)

    env = lada_paths.build_lada_python_env({"PYTHONPATH": "/existing"})

    assert env["PYTHONPATH"] == "/existing"


def test_lada_source_path_supports_docker_app_layout(monkeypatch, tmp_path):
    docker_lada = tmp_path / "app" / "pipeline" / "lada"
    docker_lada.mkdir(parents=True)
    (docker_lada / "pyproject.toml").write_text("[project]\nname='lada'\n")
    (docker_lada / "lada").mkdir()
    monkeypatch.setattr(lada_paths, "PROJECT_ROOT", tmp_path)

    assert lada_paths.resolve_lada_source_path() == docker_lada
