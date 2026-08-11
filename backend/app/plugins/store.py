from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.runtime_paths import data_path


def _state_file() -> Path:
    return data_path("plugins_state.json")


def _config_file() -> Path:
    return data_path("plugins_config.json")


def _market_repos_file() -> Path:
    return data_path("plugins_market_repos.json")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state() -> dict[str, Any]:
    return _read_json(_state_file())


def save_state(state: dict[str, Any]) -> None:
    _write_json(_state_file(), state)


def load_config() -> dict[str, Any]:
    return _read_json(_config_file())


def save_config(cfg: dict[str, Any]) -> None:
    _write_json(_config_file(), cfg)


def load_market_repos() -> list[dict[str, str]]:
    raw = _read_json(_market_repos_file())
    repos = raw.get("repos")
    if not isinstance(repos, list):
        return []
    return [{"url": str(item["url"]).strip()} for item in repos if isinstance(item, dict) and item.get("url")]


def save_market_repos(repos: list[dict[str, str]]) -> None:
    _write_json(_market_repos_file(), {"repos": repos})
