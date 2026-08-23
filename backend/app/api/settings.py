"""Settings API router reconstructed from preserved Python 3.13 bytecode."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
import zlib
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.settings_directories import build_directory_browse_payload, is_allowed_directory_path, resolve_browse_path
from app.api.settings_helpers import (LADA_MODEL_WEIGHTS_ENV, WHISPER_MODELS, format_size as _format_size, get_httpx as _get_httpx, get_lada_installation_info as _get_lada_installation_info, get_lada_model_weights_dir_from_env as _get_lada_model_weights_dir_from_env, get_lada_version_info as _get_lada_version_info, get_whisper_feature_flags as _get_whisper_feature_flags, lada_cli_base_cmd as _lada_cli_base_cmd, python_executable as _python_executable, read_env_file, set_env_values, update_env_value)
from app.api.settings_lada import get_lada_info_impl
from app.api.settings_lada_defaults import apply_lada_defaults_updates
from app.api.settings_lada_upgrade import build_lada_upgrade_env, raise_for_git_pull_failure, resolve_git_branch, should_add_break_system_packages
from app.api.settings_facefusion_upgrade import get_facefusion_installation_info, upgrade_facefusion_source
from app.api.settings_response import build_settings_payload
from app.api.settings_status_helpers import build_status_payload, facefusion_model_status_path, install_status_path, model_download_status_path, read_facefusion_model_status_response, read_install_status_response, read_model_download_status_response, write_status_file
from app.api.settings_updates import apply_emby_config_updates, apply_lada_config_updates, apply_network_config_updates, build_storage_env_updates
from app.api.settings_whisper import apply_whisper_config_updates, build_whisper_models_payload, normalize_whisper_config_payload, sanitize_download_status
from app.api.settings_whisper_models import delete_whisper_model_files, resolve_whisper_model_dir
from app.api.settings_whisper_runtime import detect_install_requirements, detect_onnxruntime_gpu_requirement, inspect_whisper_model_cache, inspect_whisper_python_dependencies, log_whisper_dependency_summary
from app.api.system import SystemLogManager
from app.api.system import _save_ui_settings, _ui_settings
from app.core.config import PROJECT_ROOT, WHISPER_MODEL_DIR, clear_settings_cache, get_settings
from app.core.facefusion_defaults import FACEFUSION_DEFAULTS, facefusion_settings, facefusion_settings_payload, save_facefusion_overrides
from app.core.facefusion_paths import build_facefusion_python_env, inspect_facefusion_model_dir, resolve_embedded_facefusion_source, resolve_facefusion_model_dir, resolve_facefusion_python, resolve_facefusion_source


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class EmbyConfig(BaseModel):
    server: str
    api_key: str
    user_id: str = ""
    enabled_library_ids: list[str] = []
    mdc_ng_actor_mapping_path: str = ""


class StorageConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    source_dir: str
    output_dir: str
    noor_data_dir: str = ""
    model_root_dir: str = ""
    runtime_root_dir: str = ""
    whisper_model_dir: str = ""
    whisper_cache_dir: str = ""
    whisper_temp_dir: str = ""
    lada_model_dir: str = Field("", validation_alias="lada_model_weights_dir")
    lada_cache_dir: str = ""
    lada_temp_dir: str = ""
    facefusion_model_dir: str = ""
    facefusion_cache_dir: str = ""
    facefusion_temp_dir: str = ""


class LadaConfig(BaseModel):
    cli_path: str
    version: Optional[str] = None
    is_docker: bool = False


class LadaDefaultsConfig(BaseModel):
    device: str = "cuda:0"
    fp16: bool = True
    detection_model: str = "v4-fast"
    restoration_model: str = "basicvsrpp-v1.2"
    encoding_preset: str = "hevc-nvidia-gpu-hq"
    max_clip_length: int = 180
    detect_face_mosaics: bool = False


class WhisperConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    strategy: str = "chickenrice"
    subtitle_profile: str = "standard"
    model_backend: str = "chickenrice-zh"
    runtime_tier: str = "gpu_standard"
    whisper_task: str = "translate"
    vad_backend: str = "energy"
    chunker: str = "smart_vad_chunk"
    target_chunk_duration_s: float = 30.0
    max_chunk_duration_s: float = 30.0
    segment_merge_max_gap_ms: int = 2000
    segment_merge_max_duration_ms: int = 20000
    timing_refiner: str = "none"
    model: str = "chickenrice-zh"
    pipeline_mode: str = "faster"
    language: str = "ja"
    sensitivity: str = "balanced"
    translate_to: str = ""
    translate_model: str = "gpt-4o-mini"
    translate_style: str = "adult_explicit"
    translate_base_url: str = "https://api.openai.com/v1"
    translate_api_key: str = ""


class NetworkConfig(BaseModel):
    acceleration_mode: str = "mirror"
    http_proxy: str = ""
    github_mirror: str = "https://ghproxy.com"
    github_token: str = ""
    hf_mirror: str = "https://hf-mirror.com"
    pip_mirror: str = "https://pypi.tuna.tsinghua.edu.cn/simple"
    hf_token: str = ""
    actor_mapping_auto_update: bool = True


class UiConfig(BaseModel):
    cover_blur_enabled: bool = False


class DirectoryEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class DirectoryBrowseResponse(BaseModel):
    path: str
    parent: Optional[str]
    entries: list[DirectoryEntry]


class ModelDownloadRequest(BaseModel):
    model: str


class InstallDepsRequest(BaseModel):
    torch_variant: Literal["gpu", "cpu"] = "gpu"
    torch_current_cuda: bool = False


class FaceFusionRuntimeConfig(BaseModel):
    dir: str = ""
    python_path: str = ""


class FaceFusionDefaultsConfig(BaseModel):
    execution_provider: str = "cuda"
    device_ids: str = "0"
    thread_count: int = 8
    video_memory_strategy: str = "strict"
    system_memory_limit: int = 0
    log_level: str = "info"
    download_providers: str = "github huggingface"
    halt_on_error: bool = False
    preview_mode: str = "default"
    preview_resolution: str = "768x768"
    processors: str = ""
    face_swapper_model: str = "hyperswap_1a_256"
    face_swapper_pixel_boost: str = "256x256"
    face_swapper_weight: float = 0.5
    face_enhancer_model: str = "gfpgan_1.4"
    face_enhancer_blend: int = 80
    face_enhancer_weight: float = 0.5
    frame_enhancer_model: str = "span_kendata_x4"
    frame_enhancer_blend: int = 80
    face_detector_model: str = "yolo_face"
    face_detector_size: str = "640x640"
    face_detector_score: float = 0.5
    face_detector_angles: str = "0"
    face_detector_margin: str = "0 0 0 0"
    face_landmarker_model: str = "2dfan4"
    face_landmarker_score: float = 0.5
    face_selector_mode: str = "reference"
    face_selector_order: str = "large-small"
    face_selector_gender: str = ""
    face_selector_age_start: str = ""
    face_selector_age_end: str = ""
    face_selector_race: str = ""
    reference_frame_number: int = 0
    reference_face_position: int = 0
    reference_face_distance: float = 0.3
    face_tracker_score: float = 0.0
    face_mask_types: str = "box"
    face_mask_areas: str = ""
    face_mask_regions: str = ""
    face_mask_blur: float = 0.3
    face_mask_padding: str = "0 0 0 0"
    face_occluder_model: str = "xseg_1"
    face_parser_model: str = "bisenet_resnet_34"
    output_video_encoder: str = "libx264"
    output_video_preset: str = "veryfast"
    output_video_quality: int = 80
    output_video_scale: str = "1.0"
    output_video_fps: str = ""
    output_audio_encoder: str = "aac"
    output_audio_quality: int = 80
    output_audio_volume: int = 100
    output_image_quality: int = 80
    output_image_scale: str = "1.0"
    temp_frame_format: str = "png"
    badge_always_visible: bool = False


class FaceFusionModelDownloadRequest(BaseModel):
    scope: Literal["lite", "full"] = "lite"


def _save_config(action: str, success_log: str, success_message: str, operation) -> dict:
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", action)
    try:
        operation()
        clear_settings_cache()
        log_mgr.add_log("success", success_log)
        return {"success": True, "message": success_message}
    except HTTPException:
        raise
    except Exception as exc:
        log_mgr.add_log("error", f"{success_log.replace('已保存', '保存失败')} — {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save .env: {exc}")


@router.get("")
async def get_settings_all():
    env_data = read_env_file()
    return build_settings_payload(env_data=env_data, version_info=_get_lada_version_info(), lada_model_weights_dir=_get_lada_model_weights_dir_from_env(env_data), whisper_features=_get_whisper_feature_flags())


@router.put("/emby")
async def update_emby_config(config: EmbyConfig):
    return _save_config("[Settings] 正在保存 Emby 配置...", "[Settings] Emby 配置已保存", "Emby settings saved to .env", lambda: apply_emby_config_updates(config, update_env_value))


@router.post("/emby/test")
async def test_emby_connection():
    settings = get_settings()
    if not settings.emby_api_key or not settings.emby_server:
        raise HTTPException(status_code=400, detail="Emby server and API key are required")
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[Emby] 正在测试 Emby 连接...")
    try:
        async with _get_httpx().AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.emby_server}/emby/System/Info", headers={"X-Emby-Token": settings.emby_api_key})
            response.raise_for_status()
            data = response.json()
        server_name, version = data.get("ServerName", "Unknown"), data.get("Version", "Unknown")
        log_mgr.add_log("success", f"[Emby] 连接成功 — {server_name} v{version}")
        return {"success": True, "server_name": server_name, "version": version}
    except _get_httpx().HTTPError as exc:
        log_mgr.add_log("error", f"[Emby] 连接失败 — {exc}")
        raise HTTPException(status_code=502, detail=f"Emby connection failed: {exc}")


@router.put("/storage")
async def update_storage_config(config: StorageConfig):
    return _save_config("[Settings] 正在保存存储路径配置...", "[Settings] 存储路径配置已保存", "Storage settings saved to .env", lambda: set_env_values(build_storage_env_updates(config, LADA_MODEL_WEIGHTS_ENV)))


@router.get("/directories", response_model=DirectoryBrowseResponse)
async def browse_directory(path: str = ""):
    settings = get_settings()
    browse_path = resolve_browse_path(settings, path)
    if not os.path.isdir(browse_path):
        raise HTTPException(status_code=400, detail=f"Not a directory: {browse_path}")
    if not is_allowed_directory_path(browse_path, settings):
        raise HTTPException(status_code=403, detail="Access denied: path not within allowed directories")
    try:
        payload = build_directory_browse_payload(browse_path)
        return DirectoryBrowseResponse(path=payload["path"], parent=payload["parent"], entries=[DirectoryEntry(**entry) for entry in payload["entries"]])
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


@router.put("/lada")
async def update_lada_config(config: LadaConfig):
    return _save_config("[Settings] 正在保存 LADA CLI 配置...", "[Settings] LADA CLI 配置已保存", "Lada settings saved to .env", lambda: apply_lada_config_updates(config, update_env_value))


@router.put("/network")
async def update_network_config(config: NetworkConfig):
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[Settings] 正在保存网络加速配置...")
    try:
        apply_network_config_updates(config, update_env_value)
        clear_settings_cache()
        get_settings().apply_network_env()
        log_mgr.add_log("success", "[Settings] 网络加速配置已保存并生效")
        return {"success": True, "message": "Network settings saved and applied"}
    except Exception as exc:
        log_mgr.add_log("error", f"[Settings] 网络加速配置保存失败 — {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save .env: {exc}")


@router.put("/ui")
async def update_ui_config(config: UiConfig):
    value = _ui_settings()
    value["cover_blur"] = config.cover_blur_enabled
    _save_ui_settings(value)
    return {"success": True, "ui": {"cover_blur_enabled": config.cover_blur_enabled}}


@router.post("/lada/upgrade")
async def upgrade_lada():
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[LADA] 正在升级 LADA...")
    install_info = _get_lada_installation_info()
    if install_info["is_docker"]:
        log_mgr.add_log("warning", "[LADA] Docker 模式下不支持容器内自升级")
        raise HTTPException(status_code=409, detail="Docker 模式下不建议在容器内直接升级 LADA。请更新镜像后重建容器。")
    lada_path = install_info["repo_path"]
    if not lada_path:
        log_mgr.add_log("error", "[LADA] 升级失败：未找到可升级的 LADA 工作副本")
        raise HTTPException(status_code=400, detail="当前未检测到可自升级的 LADA 源码工作副本，请手动升级你的 lada-cli 安装来源。")
    try:
        get_settings().apply_network_env()
        env = os.environ.copy()
        no_proxy_env = build_lada_upgrade_env(env)
        branch = resolve_git_branch(subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=lada_path, capture_output=True, text=True, timeout=10, env=no_proxy_env))
        log_mgr.add_log("info", "[LADA] 正在拉取最新代码...")
        fetch = subprocess.run(["git", "fetch", "--tags", "origin"], cwd=lada_path, capture_output=True, text=True, timeout=120, env=no_proxy_env)
        if fetch.returncode != 0:
            log_mgr.add_log("error", f"[LADA] git fetch 失败 — {fetch.stderr[:100]}")
            raise HTTPException(status_code=500, detail=f"Git fetch failed: {fetch.stderr}")
        result = subprocess.run(["git", "pull", "--ff-only", "origin", branch], cwd=lada_path, capture_output=True, text=True, timeout=60, env=no_proxy_env)
        if result.returncode != 0:
            raise_for_git_pull_failure(result.stderr, lada_path=lada_path, branch=branch, log_mgr=log_mgr)
        log_mgr.add_log("info", "[LADA] 代码拉取成功，正在重新安装...")
        pip_cmd = [_python_executable(), "-m", "pip", "install", "-e", lada_path, "--no-deps"]
        if should_add_break_system_packages(sys):
            pip_cmd.append("--break-system-packages")
        reinstall = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300, env=no_proxy_env)
        if reinstall.returncode != 0:
            log_mgr.add_log("error", f"[LADA] pip 安装失败 — {reinstall.stderr[:100]}")
            raise HTTPException(status_code=500, detail=f"Reinstall failed: {reinstall.stderr}")
        version_cp = subprocess.run([_python_executable(), "-c", "import lada; print(lada.VERSION)"], capture_output=True, text=True, timeout=10)
        new_version = version_cp.stdout.strip() if version_cp.returncode == 0 else None
        log_mgr.add_log("success", f"[LADA] 升级完成 — 新版本：{new_version or '未知'}")
        return {"success": True, "version": new_version, "output": result.stdout}
    except subprocess.TimeoutExpired:
        log_mgr.add_log("error", "[LADA] 升级超时")
        raise HTTPException(status_code=500, detail="Upgrade timeout")
    except HTTPException:
        raise
    except Exception as exc:
        log_mgr.add_log("error", f"[LADA] 升级异常 — {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/facefusion/info")
async def get_facefusion_info():
    return get_facefusion_installation_info(get_settings())


@router.post("/facefusion/upgrade")
async def upgrade_facefusion():
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[FaceFusion] 正在升级内置 FaceFusion...")
    try:
        result = upgrade_facefusion_source(get_settings(), log_mgr)
        clear_settings_cache()
        return result
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="FaceFusion 升级超时")
    except Exception as exc:
        log_mgr.add_log("error", f"[FaceFusion] 升级异常 — {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/facefusion/preferences")
async def get_facefusion_preferences():
    payload = facefusion_settings_payload(get_settings())
    return {
        "badge_always_visible": bool(payload.get("facefusion_badge_always_visible", False))
    }


@router.put("/facefusion")
async def update_facefusion_runtime(config: FaceFusionRuntimeConfig):
    return _save_config(
        "[Settings] 正在保存 FaceFusion 源码配置...",
        "[Settings] FaceFusion 源码配置已保存",
        "FaceFusion settings saved",
        lambda: save_facefusion_overrides({
            "facefusion_dir": config.dir,
            "facefusion_python_path": config.python_path,
        }),
    )


@router.put("/facefusion/defaults")
async def update_facefusion_defaults(config: FaceFusionDefaultsConfig):
    updates = {
        f"facefusion_{key}": value
        for key, value in config.model_dump().items()
        if f"facefusion_{key}" in FACEFUSION_DEFAULTS
    }
    if "facefusion_badge_always_visible" not in updates:
        updates["facefusion_badge_always_visible"] = config.badge_always_visible
    return _save_config(
        "[Settings] 正在保存 FaceFusion 默认参数...",
        "[Settings] FaceFusion 默认参数已保存",
        "FaceFusion defaults saved",
        lambda: save_facefusion_overrides(updates),
    )


def _facefusion_model_context() -> tuple[str, str, dict[str, str], str, str]:
    settings = facefusion_settings(get_settings())
    source = resolve_facefusion_source(settings.facefusion_dir)
    python_path = resolve_facefusion_python(source.source_dir, settings.facefusion_python_path)
    model_dir, link_mode = resolve_facefusion_model_dir(source.source_dir, settings.facefusion_model_dir)
    env = build_facefusion_python_env(source.source_dir, os.environ.copy(), model_dir=model_dir)
    return python_path, str(source.source_dir), env, model_dir, link_mode


def _crc32_file(path: Path) -> str:
    checksum = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum = zlib.crc32(chunk, checksum)
    return format(checksum, "08x")


def _facefusion_model_status_payload() -> dict:
    _python_path, _source_dir, _env, model_dir, link_mode = _facefusion_model_context()
    model_root = Path(model_dir)
    model_root.mkdir(parents=True, exist_ok=True)
    onnx_files = sorted(model_root.rglob("*.onnx"))
    hash_files = sorted(model_root.rglob("*.hash"))
    total_size = sum(path.stat().st_size for path in onnx_files if path.is_file())
    invalid: list[dict[str, str]] = []
    missing_hash: list[str] = []
    valid_count = 0
    for model_path in onnx_files:
        hash_path = model_path.with_suffix(".hash")
        relative_name = str(model_path.relative_to(model_root))
        if not hash_path.exists():
            missing_hash.append(relative_name)
            continue
        expected = hash_path.read_text(encoding="utf-8", errors="ignore").strip().lower()
        actual = _crc32_file(model_path)
        if expected == actual:
            valid_count += 1
        else:
            invalid.append({"name": relative_name, "expected": expected, "actual": actual})
    return {
        "model_dir": str(model_root),
        "link_mode": link_mode,
        "onnx_count": len(onnx_files),
        "hash_count": len(hash_files),
        "valid_count": valid_count,
        "invalid_count": len(invalid),
        "missing_hash_count": len(missing_hash),
        "missing_hash": missing_hash[:50],
        "invalid": invalid[:50],
        "total_size": total_size,
        "total_size_label": _format_size(total_size),
    }


@router.get("/facefusion/models")
async def get_facefusion_models():
    return {
        "models": _facefusion_model_status_payload(),
        "download_status": read_facefusion_model_status_response(),
    }


@router.post("/facefusion/models/verify")
async def verify_facefusion_models():
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[FaceFusion] 正在校验模型 hash...")
    try:
        result = _facefusion_model_status_payload()
    except Exception as exc:
        log_mgr.add_log("error", f"[FaceFusion] 模型校验失败 — {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if result["invalid_count"] or result["missing_hash_count"]:
        log_mgr.add_log(
            "warning",
            f"[FaceFusion] 模型校验完成：异常 {result['invalid_count']}，缺少 hash {result['missing_hash_count']}",
        )
    else:
        log_mgr.add_log("success", f"[FaceFusion] 模型校验通过：{result['valid_count']} 个模型")
    return {"success": True, "models": result}


@router.post("/facefusion/models/download")
async def download_facefusion_models(req: FaceFusionModelDownloadRequest):
    scope = req.scope or "lite"
    status_file = facefusion_model_status_path()
    current = read_facefusion_model_status_response()
    if current.get("status") == "running":
        return {"success": True, "message": "FaceFusion 模型预下载已在运行"}

    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", f"[FaceFusion] 正在预下载模型 scope={scope}...")
    write_status_file(status_file, build_status_payload(
        status="running",
        progress=0,
        message=f"FaceFusion 模型预下载已开始 ({scope})",
        scope=scope,
        output="",
    ))

    def run_download() -> None:
        background_log = SystemLogManager.get_instance()

        def update(status: str, progress: int, message: str, output: str = "") -> None:
            write_status_file(status_file, build_status_payload(
                status=status,
                progress=progress,
                message=message,
                scope=scope,
                output=output[-8000:],
            ))

        try:
            base_settings = get_settings()
            base_settings.apply_network_env()
            resolved = facefusion_settings(base_settings)
            python_path, source_dir, env, model_dir, _link_mode = _facefusion_model_context()
            cmd = [
                python_path,
                "facefusion.py",
                "force-download",
                "--download-scope",
                scope,
                "--log-level",
                "info",
            ]
            providers = [
                item.strip()
                for item in re.split(r"[\s,]+", str(resolved.facefusion_download_providers or "github huggingface"))
                if item.strip()
            ]
            if providers:
                cmd += ["--download-providers", *providers]
            update("running", 5, f"正在下载 FaceFusion 模型到 {model_dir}")
            proc = subprocess.Popen(
                cmd,
                cwd=source_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            output_lines: list[str] = []
            if proc.stdout:
                for raw_line in proc.stdout:
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    output_lines.append(line)
                    output_lines = output_lines[-160:]
                    progress = 50
                    match = re.search(r"(\d{1,3})%", line)
                    if match:
                        progress = max(5, min(95, int(match.group(1))))
                    if "validating" in line.lower() or "验证" in line:
                        progress = max(progress, 90)
                    update("running", progress, line, "\n".join(output_lines))
            returncode = proc.wait()
            output = "\n".join(output_lines)
            if returncode == 0:
                result = _facefusion_model_status_payload()
                update("completed", 100, f"FaceFusion 模型预下载完成，已校验 {result['valid_count']} 个模型", output)
                background_log.add_log("success", f"[FaceFusion] 模型预下载完成 scope={scope}")
            else:
                update("failed", 0, f"FaceFusion 模型预下载失败，退出码 {returncode}", output)
                background_log.add_log("error", f"[FaceFusion] 模型预下载失败 scope={scope} code={returncode}")
        except Exception as exc:
            update("failed", 0, f"FaceFusion 模型预下载失败: {exc}")
            background_log.add_log("error", f"[FaceFusion] 模型预下载异常 — {exc}")

    threading.Thread(target=run_download, daemon=True).start()
    return {"success": True, "message": "FaceFusion 模型预下载已开始"}


@router.get("/facefusion/models/download-status")
async def get_facefusion_model_download_status():
    return read_facefusion_model_status_response()


@router.put("/lada/defaults")
async def update_lada_defaults(config: LadaDefaultsConfig):
    return _save_config("[Settings] 正在保存 LADA 默认参数...", "[Settings] LADA 默认参数已保存", "Lada defaults saved to .env", lambda: apply_lada_defaults_updates(config, update_env_value))


@router.get("/lada/info")
async def get_lada_info():
    return get_lada_info_impl(settings=get_settings(), project_root=PROJECT_ROOT, install_info=_get_lada_installation_info(), lada_cli_base_cmd_fn=_lada_cli_base_cmd, python_executable_fn=_python_executable, format_size_fn=_format_size)


@router.put("/whisper")
async def update_whisper_config(config: WhisperConfig):
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[Settings] 正在保存 Whisper 配置...")
    try:
        normalized_payload = normalize_whisper_config_payload(config)
        apply_whisper_config_updates(normalized_payload, update_env_value)
        clear_settings_cache()
        log_mgr.add_log("success", "[Settings] Whisper 配置已保存")
        return {"success": True, "message": "Whisper settings saved to .env"}
    except HTTPException as exc:
        log_mgr.add_log("error", f"[Settings] Whisper 配置保存失败 — {exc.detail}")
        raise
    except Exception as exc:
        log_mgr.add_log("error", f"[Settings] Whisper 配置保存失败 — {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to save .env: {exc}")


@router.post("/whisper/check")
async def check_whisper_dependencies():
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", "[Whisper] 正在检查依赖环境...")
    settings = get_settings()
    whisper_model_dir = settings.whisper_model_dir or str(WHISPER_MODEL_DIR)
    deps, cuda_available, cuda_info = inspect_whisper_python_dependencies()
    models_info = inspect_whisper_model_cache(whisper_model_dir=whisper_model_dir, whisper_models=WHISPER_MODELS)
    log_whisper_dependency_summary(log_mgr, deps=deps, cuda_available=cuda_available, cuda_info=cuda_info)
    return {"dependencies": deps, "cuda_available": cuda_available, "models": models_info, "whisper_model_dir": whisper_model_dir, "features": _get_whisper_feature_flags()}


@router.post("/whisper/models/download")
async def download_whisper_model(req: ModelDownloadRequest):
    model_name = req.model
    model_info = WHISPER_MODELS.get(model_name)
    if not model_info:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", f"[Whisper] 正在下载模型 {model_info['name']}...")
    write_status_file(model_download_status_path(), build_status_payload(status="running", progress=0, message=f"Downloading {model_info['name']}...", model=model_name, output=None))

    def download_in_background():
        bg_log_mgr = SystemLogManager.get_instance()
        def update_status(status: str, progress: int, message: str, output: str | None = None):
            write_status_file(model_download_status_path(), build_status_payload(status=status, progress=progress, message=message, model=model_name, output=output))
        settings = get_settings()
        settings.apply_network_env()
        whisper_model_dir = settings.whisper_model_dir or str(WHISPER_MODEL_DIR)
        os.environ["HF_HOME"] = whisper_model_dir
        os.environ["TRANSFORMERS_CACHE"] = whisper_model_dir
        def get_hf_endpoint() -> str | None:
            if settings.acceleration_mode == "mirror":
                return settings.hf_mirror or "https://hf-mirror.com"
            return None
        hf_endpoint = get_hf_endpoint()
        if hf_endpoint:
            os.environ["HF_ENDPOINT"] = hf_endpoint
        try:
            if model_info["type"] in {"transformers", "onnx"}:
                update_status("running", 10, f"Downloading {model_info['name']}...")
                bg_log_mgr.add_log("info", f"[Whisper] 正在下载 {model_info['name']} (transformers)...")
                from huggingface_hub import snapshot_download
                update_status("running", 30, "Downloading files...")
                snapshot_download(repo_id=model_info["repo"], cache_dir=whisper_model_dir, endpoint=hf_endpoint)
            else:
                update_status("running", 10, f"Downloading {model_info['name']} (faster-whisper, custom repo)..." if model_info.get("repo") else f"Downloading {model_info['name']} via faster-whisper...")
                bg_log_mgr.add_log("info", f"[Whisper] 正在下载 {model_info['name']} (faster-whisper{'，repo: ' + model_info['repo'] if model_info.get('repo') else ''})...")
                from faster_whisper import WhisperModel
                update_status("running", 30 if model_info.get("repo") else 50, f"Downloading {model_info['name']}...")
                WhisperModel(model_info.get("repo") or model_name, device="cpu", download_root=whisper_model_dir)
            update_status("completed", 100, f"{model_info['name']} downloaded successfully")
            bg_log_mgr.add_log("success", f"[Whisper] 模型 {model_info['name']} 下载完成")
        except Exception as exc:
            update_status("failed", 0, f"Download failed: {exc}", str(exc))
            bg_log_mgr.add_log("error", f"[Whisper] 模型 {model_info['name']} 下载失败 — {exc}")
    thread = threading.Thread(target=download_in_background)
    thread.start()
    return {"success": True, "message": "Download started in background"}


@router.get("/whisper/models/download-status")
async def get_model_download_status():
    try:
        response = read_model_download_status_response()
        return {"status": response["status"], "progress": response["progress"], "message": response["message"], "output": response["output"]}
    except Exception:
        return {"status": "idle", "progress": 0, "message": "", "output": None}


@router.delete("/whisper/models/{model_name}")
async def delete_whisper_model(model_name: str):
    model_info = WHISPER_MODELS.get(model_name)
    if not model_info:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", f"[Whisper] 正在删除模型 {model_info['name']}...")
    whisper_model_dir = resolve_whisper_model_dir(get_settings(), str(WHISPER_MODEL_DIR))
    try:
        deleted = delete_whisper_model_files(model_name=model_name, model_info=model_info, whisper_model_dir=whisper_model_dir)
        if deleted:
            log_mgr.add_log("success", f"[Whisper] 模型 {model_info['name']} 已删除")
        else:
            log_mgr.add_log("warning", f"[Whisper] 模型 {model_info['name']} 文件未找到（可能已删除）")
        return {"success": True, "deleted": deleted}
    except Exception as exc:
        log_mgr.add_log("error", f"[Whisper] 删除模型 {model_info['name']} 失败 — {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/whisper/install-deps")
async def install_whisper_deps(req: Optional[InstallDepsRequest] = None):
    if req is None:
        req = InstallDepsRequest()
    torch_variant, torch_current_cuda = req.torch_variant, req.torch_current_cuda
    log_mgr = SystemLogManager.get_instance()
    current_deps, _, _ = inspect_whisper_python_dependencies()

    def installed_outside_noor(dep_name: str) -> bool:
        dep = current_deps.get(dep_name, {})
        return bool(dep.get("installed")) and not bool(dep.get("in_noor_env", True))

    needs_torch, needs_librosa = detect_install_requirements(torch_variant, torch_current_cuda)
    needs_torch = needs_torch or installed_outside_noor("torch")
    needs_librosa = needs_librosa or installed_outside_noor("librosa")
    needs_onnxruntime_gpu = detect_onnxruntime_gpu_requirement(torch_variant, torch_current_cuda)
    needs_onnxruntime_gpu = needs_onnxruntime_gpu or installed_outside_noor("onnxruntime")
    if not needs_torch and not needs_librosa and not needs_onnxruntime_gpu:
        log_mgr.add_log("success", "[Whisper] 所有运行时依赖已就绪，无需安装")
        return {"success": True, "message": "All dependencies already installed"}
    parts = ([] if not needs_librosa else ["librosa"]) + ([] if not needs_torch else [f"torch ({torch_variant.upper()})"]) + ([] if not needs_onnxruntime_gpu else ["onnxruntime-gpu"])
    log_mgr.add_log("info", f"[Whisper] 正在安装运行时依赖: {', '.join(parts)}...")
    settings = get_settings()
    env = os.environ.copy()
    settings.apply_network_env()
    pip_base = [sys.executable, "-m", "pip", "install", "--break-system-packages", "--ignore-installed"]
    pip_extra = ["-i", settings.pip_mirror or "https://pypi.tuna.tsinghua.edu.cn/simple", "--timeout=60"] if settings.acceleration_mode == "mirror" else []
    write_status_file(install_status_path(), build_status_payload(status="running", progress=0, message="Preparing...", current_package="", output=None))
    def update_status(status: str, progress: int, message: str, current_package: str = "", output: str | None = None):
        try:
            write_status_file(install_status_path(), build_status_payload(status=status, progress=progress, message=message, current_package=current_package, output=output or ""))
        except Exception as exc:
            logger.warning("Failed to update install status: %s", exc)
    def run_install():
        bg_log_mgr = SystemLogManager.get_instance()
        def run_pip(args: list[str], pkg_name: str) -> tuple[bool, str]:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            output_lines = []
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    continue
                output_lines.append(line.strip())
                if "Downloading" in line or "Collecting" in line or "%" in line:
                    snippet = line.strip()[:100]
                    update_status("running", 0, f"Installing {pkg_name}: {snippet}", pkg_name, "\n".join(output_lines[-10:]))
            proc.stdout.close()
            return proc.wait(timeout=600) == 0, "\n".join(output_lines[-20:])
        try:
            tasks = []
            if needs_torch:
                index = "https://download.pytorch.org/whl/cu128" if torch_variant == "gpu" else "https://download.pytorch.org/whl/cpu"
                tasks.append((f"torch ({'GPU' if torch_variant == 'gpu' else 'CPU'})", pip_base + ["torch", "--index-url", index] + pip_extra, "torch"))
            if needs_librosa:
                tasks.append(("librosa", pip_base + ["librosa"] + pip_extra, "librosa"))
            if needs_onnxruntime_gpu:
                tasks.append(("onnxruntime-gpu", pip_base + ["onnxruntime-gpu"] + pip_extra, "onnxruntime"))
            total = len(tasks)
            for i, (label, args, pkg) in enumerate(tasks):
                update_status("running", int(i / total * 100), f"Installing {label}...", pkg)
                bg_log_mgr.add_log("info", f"[Whisper] 正在安装 {label}...")
                success, err_output = run_pip(args, pkg)
                if not success:
                    update_status("failed", int(i / total * 100), f"Failed to install {label}", pkg, err_output)
                    bg_log_mgr.add_log("error", f"[Whisper] 安装 {label} 失败")
                    return
                update_status("running", int((i + 1) / total * 100), f"Installed {label}", pkg, "")
                bg_log_mgr.add_log("success", f"[Whisper] {label} 安装成功")
            update_status("completed", 100, "All dependencies installed!", "", "Installation complete")
            bg_log_mgr.add_log("success", "[Whisper] 运行时依赖安装完成")
        except subprocess.TimeoutExpired:
            update_status("failed", 0, "Installation timeout")
            bg_log_mgr.add_log("error", "[Whisper] 依赖安装超时")
        except Exception as exc:
            update_status("failed", 0, f"Error: {exc}")
            bg_log_mgr.add_log("error", f"[Whisper] 依赖安装异常 — {exc}")
    thread = threading.Thread(target=run_install)
    thread.start()
    return {"success": True, "message": "Installation started in background"}


@router.get("/whisper/install-status")
async def get_install_status():
    try:
        return read_install_status_response()
    except Exception:
        return {"status": "idle", "progress": 0, "message": "", "output": None}


@router.get("/whisper/models")
async def list_whisper_models():
    check_result = await check_whisper_dependencies()
    download_status = {"status": "idle", "progress": 0, "message": "", "model": ""}
    try:
        download_status = sanitize_download_status(read_model_download_status_response())
    except Exception:
        pass
    return {"models": build_whisper_models_payload(check_result=check_result, whisper_models=WHISPER_MODELS), "downloadStatus": download_status}
