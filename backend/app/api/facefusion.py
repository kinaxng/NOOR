from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import cv2
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import PROJECT_ROOT, get_settings
from app.core.models import JobCreate, JobResponse
from app.core.facefusion_defaults import FACEFUSION_DEFAULTS, facefusion_settings, facefusion_settings_payload, save_facefusion_overrides
from app.core.facefusion_paths import build_facefusion_python_env, resolve_facefusion_model_dir, resolve_facefusion_python, resolve_facefusion_source
from app.pipeline.facefusion.preview import generate_facefusion_preview
from app.pipeline.facefusion.runner import _build_env, _execution_providers, _split_words
from app.tasks.manager import job_manager


router = APIRouter(prefix="/api/facefusion", tags=["facefusion"])

FACEFUSION_SOURCE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FACEFUSION_DEEP_SWAPPER_MODEL_EXTENSIONS = {".dfm", ".onnx", ".pth", ".pt"}
FACEFUSION_DEEP_SWAPPER_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_deep_swapper_download_lock = threading.Lock()
_deep_swapper_downloads: dict[str, dict[str, Any]] = {}


class FaceFusionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    input_path: str
    settings: dict[str, Any] = Field(default_factory=dict)
    frame_number: int = 0
    preview_mode: str = "default"
    preview_resolution: str = "768x768"


class FaceFusionPreviewMetadataRequest(BaseModel):
    input_path: str


class FaceFusionReferenceFacesRequest(BaseModel):
    input_path: str
    settings: dict[str, Any] = Field(default_factory=dict)
    frame_number: int = 0


class FaceFusionDeepSwapperDownloadRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str


class FaceFusionJobRequest(JobCreate):
    """A normal NOOR job with an explicit FaceFusion queue destination."""

    model_config = ConfigDict(extra="allow")


class FaceFusionSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: dict[str, Any]


def _facefusion_setting(name: str, default: Any = "") -> Any:
    """Keep FaceFusion endpoints usable with pre-FaceFusion Settings bytecode."""
    return getattr(facefusion_settings(get_settings()), name, default)


@router.post("/jobs", response_model=JobResponse)
async def create_facefusion_job(job_data: FaceFusionJobRequest):
    return await job_manager.enqueue_facefusion(job_data)


@router.get("/settings")
async def get_facefusion_settings():
    return {"settings": facefusion_settings_payload(get_settings())}


@router.put("/settings")
async def update_facefusion_settings(payload: FaceFusionSettingsUpdate):
    unknown = sorted(set(payload.settings) - set(FACEFUSION_DEFAULTS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"不支持的 FaceFusion 设置项: {', '.join(unknown)}")
    for key, value in payload.settings.items():
        default = FACEFUSION_DEFAULTS[key]
        if isinstance(default, bool) and not isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"{key} 必须为布尔值")
        if isinstance(default, int) and not isinstance(default, bool) and not isinstance(value, int):
            raise HTTPException(status_code=422, detail=f"{key} 必须为整数")
        if isinstance(default, float) and not isinstance(value, (int, float)):
            raise HTTPException(status_code=422, detail=f"{key} 必须为数字")
        if isinstance(default, str) and not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{key} 必须为文本")
    save_facefusion_overrides(payload.settings)
    return {"success": True, "settings": facefusion_settings_payload(get_settings())}


def _preview_root() -> Path:
    cache_dir = _facefusion_setting("facefusion_cache_dir")
    if cache_dir:
        return Path(cache_dir) / "previews"
    return PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache" / "previews"


def _upload_root() -> Path:
    cache_dir = _facefusion_setting("facefusion_cache_dir")
    if cache_dir:
        return Path(cache_dir) / "uploads"
    return PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache" / "uploads"


def _reference_face_root() -> Path:
    cache_dir = _facefusion_setting("facefusion_cache_dir")
    if cache_dir:
        return Path(cache_dir) / "reference_faces"
    return PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache" / "reference_faces"


def _deep_swapper_custom_root() -> Path:
    source = resolve_facefusion_source(_facefusion_setting("facefusion_dir"))
    return source.source_dir / ".assets" / "models" / "custom"


def _deep_swapper_choices_path() -> Path:
    source = resolve_facefusion_source(_facefusion_setting("facefusion_dir"))
    return source.source_dir / "facefusion" / "processors" / "modules" / "deep_swapper" / "choices.py"


def _known_deep_swapper_model_ids() -> list[str]:
    choices_path = _deep_swapper_choices_path()
    try:
        tree = ast.parse(choices_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"无法读取 Deep Swapper 模型列表: {choices_path}") from exc

    for node in tree.body:
        if isinstance(node, ast.Assign):
            is_deep_swapper_assignment = any(isinstance(target, ast.Name) and target.id == "deep_swapper_models" for target in node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            is_deep_swapper_assignment = isinstance(node.target, ast.Name) and node.target.id == "deep_swapper_models"
            value = node.value
        else:
            continue
        if not is_deep_swapper_assignment or value is None:
            continue
        try:
            values = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise RuntimeError("无法解析 Deep Swapper 模型列表") from exc
        return [str(item) for item in values if isinstance(item, str) and "/" in item]
    return []


def _deep_swapper_builtin_paths(model_id: str) -> tuple[Path, Path]:
    scope, name = _split_builtin_model_id(model_id)
    source = resolve_facefusion_source(facefusion_settings(get_settings()).facefusion_dir)
    model_root = source.source_dir / ".assets" / "models" / scope
    return model_root / f"{name}.dfm", model_root / f"{name}.hash"


def _split_builtin_model_id(model_id: str) -> tuple[str, str]:
    parts = [part.strip() for part in model_id.split("/", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1] or parts[0] == "custom":
        raise HTTPException(status_code=400, detail="非法 Deep 模型 ID")
    return parts[0], parts[1]


def _deep_swapper_download_status(model_id: str) -> dict[str, Any]:
    with _deep_swapper_download_lock:
        return dict(_deep_swapper_downloads.get(model_id) or {})


def _set_deep_swapper_download_status(model_id: str, **updates: Any) -> None:
    with _deep_swapper_download_lock:
        current = dict(_deep_swapper_downloads.get(model_id) or {})
        current.update(updates)
        _deep_swapper_downloads[model_id] = current


def _deep_swapper_download_urls(model_id: str, suffix: str) -> list[str]:
    scope, name = _split_builtin_model_id(model_id)
    repo = f"facefusion/deepfacelive-models-{scope}"
    filename = f"{name}{suffix}"
    endpoints: list[str] = []
    settings = get_settings()
    if settings.hf_mirror:
        endpoints.append(settings.hf_mirror.rstrip("/"))
    if os.environ.get("HF_ENDPOINT"):
        endpoints.append(os.environ["HF_ENDPOINT"].rstrip("/"))
    endpoints.extend(["https://hf-mirror.com", "https://huggingface.co"])

    urls: list[str] = []
    for endpoint in endpoints:
        url = f"{endpoint}/{repo}/resolve/main/{filename}"
        if url not in urls:
            urls.append(url)
    return urls


def _download_file_with_progress(model_id: str, urls: list[str], target_path: Path, progress_start: int, progress_end: int) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(f"{target_path.suffix}.part")
    token = os.environ.get("HF_TOKEN")
    last_error = ""

    for url in urls:
        try:
            headers = {"User-Agent": "NOOR FaceFusion Model Downloader"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response, temp_path.open("wb") as handle:
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                while True:
                    chunk = response.read(FACEFUSION_DEEP_SWAPPER_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        progress = progress_start + int((progress_end - progress_start) * min(downloaded / total, 1))
                        _set_deep_swapper_download_status(
                            model_id,
                            status="running",
                            progress=progress,
                            message=f"正在下载 {target_path.name} · {downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB",
                        )
            temp_path.replace(target_path)
            return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            with suppress(FileNotFoundError):
                temp_path.unlink()
            continue

    raise RuntimeError(last_error or "下载失败")


def _download_deep_swapper_model(model_id: str) -> None:
    model_path, hash_path = _deep_swapper_builtin_paths(model_id)
    try:
        settings = get_settings()
        settings.apply_network_env()
        _set_deep_swapper_download_status(model_id, status="running", progress=2, message="准备下载 Deep 模型")
        _download_file_with_progress(model_id, _deep_swapper_download_urls(model_id, ".dfm"), model_path, 5, 92)
        with suppress(Exception):
            _set_deep_swapper_download_status(model_id, status="running", progress=94, message="正在下载 hash")
            _download_file_with_progress(model_id, _deep_swapper_download_urls(model_id, ".hash"), hash_path, 94, 98)
        stat = model_path.stat()
        _set_deep_swapper_download_status(
            model_id,
            status="completed",
            progress=100,
            message="下载完成",
            size=stat.st_size,
        )
    except Exception as exc:
        _set_deep_swapper_download_status(model_id, status="failed", progress=0, message=str(exc))


def _safe_model_stem(filename: str) -> str:
    stem = Path(filename or "model").stem.strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in stem)
    safe = safe.strip("._")
    if not safe:
        safe = f"model_{uuid4().hex[:8]}"
    return safe[:96]


def _source_image_path(image_id: str) -> Path:
    if not image_id or len(image_id) > 64 or not all(ch in "0123456789abcdef" for ch in image_id):
        raise HTTPException(status_code=400, detail="非法源脸图片 ID")

    upload_root = _upload_root()
    for suffix in FACEFUSION_SOURCE_IMAGE_EXTENSIONS:
        path = upload_root / f"{image_id}{suffix}"
        if path.exists():
            return path
    raise HTTPException(status_code=404, detail="源脸图片不存在")


def _source_image_payload(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "id": path.stem,
        "name": path.name,
        "path": str(path),
        "preview_url": f"/api/facefusion/source-images/{path.stem}",
        "size": stat.st_size,
        "updated_at": stat.st_mtime,
    }


def _reference_face_image_path(face_id: str) -> Path:
    if not face_id or len(face_id) > 96 or not all(ch in "0123456789abcdef_-" for ch in face_id):
        raise HTTPException(status_code=400, detail="非法参考人脸 ID")
    key, _, position = face_id.partition("_")
    if not key or not position.isdigit():
        raise HTTPException(status_code=400, detail="非法参考人脸 ID")
    root = _reference_face_root().resolve()
    path = root / key / f"{position}.jpg"
    try:
        resolved = path.resolve()
        if root not in resolved.parents:
            raise HTTPException(status_code=400, detail="非法参考人脸路径")
    except FileNotFoundError:
        resolved = path
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="参考人脸不存在")
    return resolved


def _stable_reference_faces_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def _build_reference_face_cli_args(input_path: str, job_settings: dict[str, Any], frame_number: int) -> tuple[list[str], str, dict[str, str]]:
    settings = facefusion_settings(get_settings())
    configured_dir = job_settings.get("facefusion_dir")
    if configured_dir is None:
        configured_dir = settings.facefusion_dir
    source = resolve_facefusion_source(configured_dir)
    python_path = resolve_facefusion_python(
        source.source_dir,
        job_settings.get("facefusion_python_path") or settings.facefusion_python_path,
    )
    facefusion_cache_dir = str(Path(job_settings.get("facefusion_cache_dir") or settings.facefusion_cache_dir or _preview_root().parent))
    facefusion_temp_dir = str(Path(job_settings.get("facefusion_temp_dir") or settings.facefusion_temp_dir or _preview_root().parent / "temp"))
    model_dir, _model_dir_mode = resolve_facefusion_model_dir(
        source.source_dir,
        job_settings.get("facefusion_model_dir") or getattr(settings, "facefusion_model_dir", ""),
    )

    cli_args = ["run", "-t", input_path]
    if facefusion_temp_dir:
        cli_args += ["--temp-path", facefusion_temp_dir]
    if facefusion_cache_dir:
        cli_args += ["--jobs-path", str(Path(facefusion_cache_dir) / "jobs")]

    providers = _execution_providers(job_settings)
    if providers:
        cli_args += ["--execution-providers", *providers]
    device_ids = _split_words(job_settings.get("device_ids", settings.facefusion_device_ids), ["0"])
    if device_ids:
        cli_args += ["--execution-device-ids", *device_ids]
    cli_args += ["--execution-thread-count", str(job_settings.get("thread_count", settings.facefusion_thread_count))]
    cli_args += ["--video-memory-strategy", str(job_settings.get("video_memory_strategy", settings.facefusion_video_memory_strategy))]
    download_providers = _split_words(job_settings.get("download_providers", settings.facefusion_download_providers), [])
    if download_providers:
        cli_args += ["--download-providers", *download_providers]

    cli_args += ["--face-detector-model", str(job_settings.get("face_detector_model", settings.facefusion_face_detector_model))]
    cli_args += ["--face-detector-size", str(job_settings.get("face_detector_size", settings.facefusion_face_detector_size))]
    cli_args += ["--face-detector-score", str(job_settings.get("face_detector_score", settings.facefusion_face_detector_score))]
    detector_angles = _split_words(job_settings.get("face_detector_angles", settings.facefusion_face_detector_angles), ["0"])
    if detector_angles:
        cli_args += ["--face-detector-angles", *detector_angles]
    detector_margin = _split_words(job_settings.get("face_detector_margin", settings.facefusion_face_detector_margin), [])
    if detector_margin:
        cli_args += ["--face-detector-margin", *detector_margin]
    cli_args += ["--face-landmarker-model", str(job_settings.get("face_landmarker_model", settings.facefusion_face_landmarker_model))]
    cli_args += ["--face-landmarker-score", str(job_settings.get("face_landmarker_score", settings.facefusion_face_landmarker_score))]
    cli_args += ["--face-selector-mode", "reference"]
    selector_order = job_settings.get("face_selector_order", settings.facefusion_face_selector_order)
    if selector_order:
        cli_args += ["--face-selector-order", str(selector_order)]
    gender = job_settings.get("face_selector_gender", settings.facefusion_face_selector_gender)
    if gender:
        cli_args += ["--face-selector-gender", str(gender)]
    age_start = job_settings.get("face_selector_age_start", settings.facefusion_face_selector_age_start)
    if age_start not in (None, ""):
        cli_args += ["--face-selector-age-start", str(age_start)]
    age_end = job_settings.get("face_selector_age_end", settings.facefusion_face_selector_age_end)
    if age_end not in (None, ""):
        cli_args += ["--face-selector-age-end", str(age_end)]
    race = job_settings.get("face_selector_race", settings.facefusion_face_selector_race)
    if race:
        cli_args += ["--face-selector-race", str(race)]
    cli_args += ["--reference-frame-number", str(frame_number)]
    cli_args += ["--reference-face-position", str(job_settings.get("reference_face_position", settings.facefusion_reference_face_position))]
    cli_args += ["--reference-face-distance", str(job_settings.get("reference_face_distance", settings.facefusion_reference_face_distance))]
    cli_args += ["--face-tracker-score", str(job_settings.get("face_tracker_score", settings.facefusion_face_tracker_score))]
    cli_args += ["--log-level", str(job_settings.get("log_level", settings.facefusion_log_level))]

    env = build_facefusion_python_env(source.source_dir, _build_env(
        facefusion_cache_dir=facefusion_cache_dir,
        facefusion_temp_dir=facefusion_temp_dir,
    ), model_dir=model_dir)
    return [python_path, *cli_args], str(source.source_dir), env


def _deep_swapper_model_payload(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "id": f"custom/{path.stem}",
        "name": path.stem,
        "filename": path.name,
        "path": str(path),
        "source": "custom",
        "size": stat.st_size,
        "updated_at": stat.st_mtime,
        "downloaded": True,
        "downloading": False,
        "progress": 100,
    }


def _deep_swapper_builtin_payload(model_id: str) -> dict[str, Any]:
    model_path, hash_path = _deep_swapper_builtin_paths(model_id)
    downloaded = model_path.is_file() and model_path.stat().st_size > 0
    status = _deep_swapper_download_status(model_id)
    size = model_path.stat().st_size if downloaded else status.get("size")
    return {
        "id": model_id,
        "name": model_id,
        "filename": model_path.name,
        "path": str(model_path) if downloaded else "",
        "hash_path": str(hash_path) if hash_path.exists() else "",
        "source": "known",
        "size": size,
        "updated_at": model_path.stat().st_mtime if downloaded else None,
        "downloaded": downloaded,
        "downloading": status.get("status") == "running",
        "download_status": status.get("status") or ("completed" if downloaded else "missing"),
        "progress": 100 if downloaded else int(status.get("progress") or 0),
        "message": status.get("message") or ("已下载" if downloaded else "未下载"),
    }


@router.get("/deep-swapper-models")
async def list_facefusion_deep_swapper_models():
    try:
        custom_root = _deep_swapper_custom_root()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    custom_root.mkdir(parents=True, exist_ok=True)
    custom_models = [
        _deep_swapper_model_payload(path)
        for path in sorted(custom_root.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in FACEFUSION_DEEP_SWAPPER_MODEL_EXTENSIONS
    ]
    known_models = [_deep_swapper_builtin_payload(model_id) for model_id in _known_deep_swapper_model_ids()]
    return {
        "success": True,
        "models": [*custom_models, *known_models],
    }


@router.post("/deep-swapper-models/download")
async def download_facefusion_deep_swapper_model(req: FaceFusionDeepSwapperDownloadRequest):
    model_id = (req.model_id or "").strip()
    if model_id not in set(_known_deep_swapper_model_ids()):
        raise HTTPException(status_code=404, detail="Deep 模型不存在")
    model_path, _ = _deep_swapper_builtin_paths(model_id)
    if model_path.is_file() and model_path.stat().st_size > 0:
        _set_deep_swapper_download_status(model_id, status="completed", progress=100, message="已下载", size=model_path.stat().st_size)
        return {"success": True, "message": "模型已存在", "model": _deep_swapper_builtin_payload(model_id)}

    status = _deep_swapper_download_status(model_id)
    if status.get("status") == "running":
        return {"success": True, "message": "模型下载已在运行", "model": _deep_swapper_builtin_payload(model_id)}

    _set_deep_swapper_download_status(model_id, status="running", progress=0, message="等待下载")
    threading.Thread(target=_download_deep_swapper_model, args=(model_id,), daemon=True).start()
    return {"success": True, "message": "模型下载已开始", "model": _deep_swapper_builtin_payload(model_id)}


@router.post("/deep-swapper-models")
async def upload_facefusion_deep_swapper_model(file: UploadFile = File(...)):
    original_name = Path(file.filename or "model").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in FACEFUSION_DEEP_SWAPPER_MODEL_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的 Deep 模型格式: {original_name}")

    custom_root = _deep_swapper_custom_root()
    custom_root.mkdir(parents=True, exist_ok=True)
    target_path = custom_root / f"{_safe_model_stem(original_name)}{suffix}"
    if target_path.exists():
        target_path = custom_root / f"{target_path.stem}_{uuid4().hex[:8]}{suffix}"
    try:
        with target_path.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                handle.write(chunk)
    finally:
        await file.close()
    return {
        "success": True,
        "model": _deep_swapper_model_payload(target_path),
    }


@router.post("/source-images")
async def upload_facefusion_source_images(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="请选择源脸图片")

    upload_root = _upload_root()
    upload_root.mkdir(parents=True, exist_ok=True)
    saved_files: list[dict[str, str]] = []
    for upload in files:
        original_name = Path(upload.filename or "source").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in FACEFUSION_SOURCE_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的源脸图片格式: {original_name}")
        target_path = upload_root / f"{uuid4().hex}{suffix}"
        try:
            with target_path.open("wb") as handle:
                while chunk := await upload.read(1024 * 1024):
                    handle.write(chunk)
        finally:
            await upload.close()
        image_id = target_path.stem
        saved_files.append({
            "id": image_id,
            "name": original_name,
            "path": str(target_path),
            "preview_url": f"/api/facefusion/source-images/{image_id}",
        })
    # Keep ``files`` for callers that use the native FaceFusion-shaped response,
    # and expose ``items`` for the NOOR media-panel contract.
    return {"success": True, "files": saved_files, "items": saved_files}


@router.get("/source-images")
async def list_facefusion_source_images():
    upload_root = _upload_root()
    upload_root.mkdir(parents=True, exist_ok=True)
    files = [
        path for path in upload_root.iterdir()
        if path.is_file() and path.suffix.lower() in FACEFUSION_SOURCE_IMAGE_EXTENSIONS
    ]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    items = [_source_image_payload(path) for path in files[:200]]
    return {"success": True, "files": items, "items": items}


@router.get("/source-images/{image_id}")
async def get_facefusion_source_image(image_id: str):
    path = _source_image_path(image_id)
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return FileResponse(path, media_type=media_types.get(path.suffix.lower(), "application/octet-stream"))


@router.delete("/source-images/{image_id}")
async def delete_facefusion_source_image(image_id: str):
    path = _source_image_path(image_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return {"success": True}


@router.post("/reference-faces")
async def list_facefusion_reference_faces(payload: FaceFusionReferenceFacesRequest):
    input_path = Path(payload.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="目标文件不存在")

    settings_payload = dict(payload.settings or {})
    frame_number = max(0, int(payload.frame_number or 0))
    key_payload = {
        "input_path": str(input_path),
        "settings": {
            key: settings_payload.get(key)
            for key in (
                "execution_provider",
                "device_ids",
                "thread_count",
                "video_memory_strategy",
                "download_providers",
                "face_detector_model",
                "face_detector_size",
                "face_detector_score",
                "face_detector_angles",
                "face_detector_margin",
                "face_landmarker_model",
                "face_landmarker_score",
                "face_selector_order",
                "face_selector_gender",
                "face_selector_age_start",
                "face_selector_age_end",
                "face_selector_race",
                "reference_face_distance",
                "face_tracker_score",
                "log_level",
            )
        },
        "frame_number": frame_number,
    }
    reference_key = _stable_reference_faces_key(key_payload)
    root = _reference_face_root()
    output_dir = root / reference_key
    output_json = output_dir / "faces.json"
    if not output_json.exists():
        request_path = output_dir / f"{uuid4().hex}.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd, cwd, env = _build_reference_face_cli_args(str(input_path), settings_payload, frame_number)
        worker_payload = {
            "source_dir": cwd,
            "cli_args": cmd[1:],
            "frame_number": frame_number,
            "output_dir": str(output_dir),
            "output_json": str(output_json),
        }
        request_path.write_text(json.dumps(worker_payload, ensure_ascii=False), encoding="utf-8")
        try:
            result = subprocess.run(
                [cmd[0], str(PROJECT_ROOT / "backend" / "app" / "pipeline" / "facefusion" / "reference_faces_worker.py"), str(request_path)],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "参考人脸提取失败").strip()
                raise HTTPException(status_code=500, detail=detail[:2000])
        finally:
            with suppress(FileNotFoundError):
                request_path.unlink()

    data = json.loads(output_json.read_text(encoding="utf-8")) if output_json.exists() else {"faces": []}
    faces = []
    for face in data.get("faces") or []:
        position = int(face.get("position") or 0)
        faces.append({
            **face,
            "id": f"{reference_key}_{position}",
            "preview_url": f"/api/facefusion/reference-faces/{reference_key}_{position}",
        })
    return {
        "success": True,
        "frame_number": frame_number,
        "faces": faces,
        "generated_at": output_json.stat().st_mtime if output_json.exists() else time.time(),
    }


@router.get("/reference-faces/{face_id}")
async def get_facefusion_reference_face(face_id: str):
    return FileResponse(_reference_face_image_path(face_id), media_type="image/jpeg")


@router.post("/preview/metadata")
async def get_facefusion_preview_metadata(payload: FaceFusionPreviewMetadataRequest):
    input_path = Path(payload.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="目标文件不存在")

    capture = cv2.VideoCapture(str(input_path))
    try:
        if not capture.isOpened():
            return {
                "success": True,
                "frame_total": 0,
                "fps": None,
                "duration": None,
                "is_video": False,
            }
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        return {
            "success": True,
            "frame_total": max(0, frame_total),
            "fps": fps or None,
            "duration": (frame_total / fps) if frame_total and fps else None,
            "is_video": True,
        }
    finally:
        capture.release()


@router.post("/preview")
async def create_facefusion_preview(payload: FaceFusionPreviewRequest):
    input_path = Path(payload.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="目标文件不存在")
    try:
        result = generate_facefusion_preview(
            input_path=str(input_path),
            job_settings=payload.settings or {},
            frame_number=max(0, int(payload.frame_number or 0)),
            preview_mode=payload.preview_mode,
            preview_resolution=payload.preview_resolution,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"FaceFusion 预览失败: {exc}") from exc
    return {
        "success": True,
        "preview_id": result["preview_id"],
        "preview_url": f"/api/facefusion/preview/{result['preview_id']}",
        "cached": result["cached"],
        "generated_at": result["generated_at"],
    }


@router.get("/preview/{preview_id}")
async def get_facefusion_preview(preview_id: str):
    if not preview_id or not all(ch in "0123456789abcdef" for ch in preview_id) or len(preview_id) > 64:
        raise HTTPException(status_code=400, detail="非法预览 ID")
    path = _preview_root() / f"{preview_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="预览不存在")
    return FileResponse(path, media_type="image/png")
