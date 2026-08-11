from __future__ import annotations

import os
from pathlib import Path

from app.core.config import PROJECT_ROOT


def resolve_lada_repo_path() -> Path | None:
    candidates = [
        PROJECT_ROOT / "backend" / "app" / "pipeline" / "lada",
        PROJECT_ROOT / "app" / "pipeline" / "lada",
        PROJECT_ROOT / "lada",
    ]
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_lada_source_path() -> Path | None:
    repo_path = resolve_lada_repo_path()
    if repo_path:
        return repo_path
    candidates = [
        PROJECT_ROOT / "backend" / "app" / "pipeline" / "lada",
        PROJECT_ROOT / "app" / "pipeline" / "lada",
        PROJECT_ROOT / "lada",
    ]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "lada").is_dir():
            return candidate
    return None


def build_lada_python_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    source_path = resolve_lada_source_path()
    if source_path:
        existing = env.get("PYTHONPATH", "")
        entries = [str(source_path)]
        if existing:
            entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(entries)
    return env
