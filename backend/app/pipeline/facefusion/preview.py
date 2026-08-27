from __future__ import annotations

import hashlib
import json
import subprocess
import time
import copy
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import PROJECT_ROOT
from app.pipeline.facefusion.runner import _build_command


PREVIEW_MODES = {"default", "frame-by-frame", "face-by-face"}
PREVIEW_RESOLUTIONS = {"512x512", "768x768", "1024x1024"}


def _stable_preview_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def _preview_cache_dir(facefusion_cache_dir: str) -> Path:
    root = Path(facefusion_cache_dir or PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache")
    return root / "previews"


def _is_cuda_oom_error(text: str) -> bool:
    lowered = text.lower()
    return "cuda" in lowered and ("out of memory" in lowered or "cuda failure 2" in lowered)


def _run_preview_worker(
    *,
    cmd: list[str],
    cwd: str,
    env: dict[str, str],
    payload: dict[str, Any],
    request_path: Path,
    timeout: int,
) -> None:
    request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [cmd[0], str(PROJECT_ROOT / "backend" / "app" / "pipeline" / "facefusion" / "preview_worker.py"), str(request_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "FaceFusion preview failed").strip()
        raise RuntimeError(detail[:2000])


def generate_facefusion_preview(
    *,
    input_path: str,
    job_settings: dict[str, Any],
    frame_number: int,
    preview_mode: str,
    preview_resolution: str,
    timeout: int = 180,
) -> dict[str, Any]:
    if preview_mode not in PREVIEW_MODES:
        raise RuntimeError("不支持的 FaceFusion 预览模式")
    if preview_resolution not in PREVIEW_RESOLUTIONS:
        raise RuntimeError("不支持的 FaceFusion 预览分辨率")

    cache_probe_output = str(PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache" / "previews" / "_probe.png")
    cmd, cwd, env, _model_dir, _model_dir_mode, facefusion_cache_dir, source_mode = _build_command(input_path, cache_probe_output, job_settings)
    preview_dir = _preview_cache_dir(facefusion_cache_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    cli_args = list(cmd[2:])
    if cli_args and cli_args[0] == "headless-run":
        cli_args[0] = "run"

    key_payload = {
        "input_path": input_path,
        "settings": job_settings,
        "frame_number": int(frame_number),
        "preview_mode": preview_mode,
        "preview_resolution": preview_resolution,
        "content_analysis": "skipped",
        "source_mode": source_mode,
    }
    preview_key = _stable_preview_key(key_payload)
    output_path = preview_dir / f"{preview_key}.png"
    if output_path.exists() and output_path.stat().st_size > 0:
        return {
            "preview_id": preview_key,
            "path": str(output_path),
            "cached": True,
            "generated_at": output_path.stat().st_mtime,
        }

    request_path = preview_dir / f"{preview_key}.{uuid4().hex}.json"
    payload = {
        "source_dir": cwd,
        "cli_args": cli_args,
        "frame_number": int(frame_number),
        "preview_mode": preview_mode,
        "preview_resolution": preview_resolution,
        "skip_content_analysis": True,
        "output_path": str(output_path),
    }
    try:
        try:
            _run_preview_worker(cmd=cmd, cwd=cwd, env=env, payload=payload, request_path=request_path, timeout=timeout)
        except RuntimeError as exc:
            if not _is_cuda_oom_error(str(exc)):
                raise
            fallback_settings = copy.deepcopy(job_settings)
            fallback_settings["execution_provider"] = "cpu"
            fallback_cmd, fallback_cwd, fallback_env, _model_dir, _model_dir_mode, _facefusion_cache_dir, _source_mode = _build_command(
                input_path,
                cache_probe_output,
                fallback_settings,
            )
            fallback_cli_args = list(fallback_cmd[2:])
            if fallback_cli_args and fallback_cli_args[0] == "headless-run":
                fallback_cli_args[0] = "run"
            fallback_payload = {
                **payload,
                "source_dir": fallback_cwd,
                "cli_args": fallback_cli_args,
            }
            _run_preview_worker(
                cmd=fallback_cmd,
                cwd=fallback_cwd,
                env=fallback_env,
                payload=fallback_payload,
                request_path=request_path,
                timeout=timeout,
            )
        return {
            "preview_id": preview_key,
            "path": str(output_path),
            "cached": False,
            "generated_at": time.time(),
        }
    finally:
        try:
            request_path.unlink()
        except FileNotFoundError:
            pass

