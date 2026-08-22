"""Persistent status payload helpers used by settings background actions.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT
from app.core.runtime_paths import data_path


def status_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_download_status_path() -> Path:
    return PROJECT_ROOT / "model_download_status.json"


def install_status_path() -> Path:
    return PROJECT_ROOT / "install_status.json"


def facefusion_model_status_path() -> Path:
    return data_path("runtime", "status", "facefusion_model_status.json")


def write_status_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def read_status_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def read_install_status_response() -> dict[str, Any]:
    status = read_status_file(install_status_path())
    if status is None:
        return {"status": "idle", "progress": 0, "message": "", "output": None}
    return {
        "status": status.get("status", "idle"),
        "progress": status.get("progress", 0),
        "message": status.get("message", ""),
        "output": status.get("output"),
    }


def read_model_download_status_response() -> dict[str, Any]:
    status = read_status_file(model_download_status_path())
    if status is None:
        return {
            "status": "idle",
            "progress": 0,
            "message": "",
            "model": "",
            "output": None,
        }
    return {
        "status": status.get("status", "idle"),
        "progress": status.get("progress", 0),
        "message": status.get("message", ""),
        "model": status.get("model", ""),
        "output": status.get("output"),
    }


def read_facefusion_model_status_response() -> dict[str, Any]:
    status = read_status_file(facefusion_model_status_path())
    if status is None:
        return {
            "status": "idle",
            "progress": 0,
            "message": "",
            "scope": "",
            "output": None,
        }
    return {
        "status": status.get("status", "idle"),
        "progress": status.get("progress", 0),
        "message": status.get("message", ""),
        "scope": status.get("scope", ""),
        "output": status.get("output"),
    }


def build_status_payload(
    *,
    status: str,
    progress: int,
    message: str,
    output: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "progress": progress,
        "message": message,
        "output": output,
        "updated_at": status_timestamp(),
    }
    payload.update(extra)
    return payload
