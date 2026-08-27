"""Small filesystem helpers used by the task manager.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.runtime_paths import data_path


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def logs_dir() -> Path:
    path = data_path("runtime", "jobs", "logs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_file_path(job_id: str) -> str:
    return str(logs_dir() / f"{job_id}.log")


def read_log_lines(job_id: str) -> list[str]:
    log_file = log_file_path(job_id)
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as handle:
                return [line.rstrip("\n") for line in handle.readlines()]
        except Exception:
            return []
    return []


def append_log_line(job_id: str, log: str) -> None:
    log_file = log_file_path(job_id)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(log + "\n")


def build_lada_output_path(input_path: str, source_dir: str, output_dir: str) -> str:
    if source_dir and output_dir and input_path.startswith(source_dir):
        relative_path = input_path[len(source_dir) :].lstrip(os.sep)
        mirrored_dir = os.path.join(output_dir, os.path.dirname(relative_path))
        os.makedirs(mirrored_dir, exist_ok=True)
        base_name = os.path.join(
            mirrored_dir,
            os.path.splitext(os.path.basename(input_path))[0],
        )
    else:
        base_name = input_path.rsplit(".", 1)[0] if "." in input_path else input_path
    return f"{base_name}.restored-u.mp4"
