"""Whisper task API reconstructed from preserved Python 3.13 bytecode."""
from __future__ import annotations

import os
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.system import SystemLogManager
from app.core.config import get_settings
from app.pipeline.whisper.strategy import apply_whisper_strategy, normalize_whisper_strategy
from app.tasks.manager import job_manager


router = APIRouter(prefix="/api/whisper", tags=["whisper"])


class WhisperRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    video_path: str
    strategy: Optional[str] = None
    preset: Optional[str] = None
    model: str = "anime-whisper"
    pipeline_mode: str = "ensemble"
    merge_strategy: str = "smart_merge"
    language: str = "ja"
    sensitivity: str = "balanced"
    vad_method: Optional[str] = "semantic"
    audio_preprocess_mode: Optional[str] = "none"
    audio_preprocess_model: Optional[str] = "vocal_balanced"
    speech_enhancer: Optional[str] = "none"
    pass1_pipeline: Optional[str] = None
    pass2_pipeline: Optional[str] = None
    custom_config: Optional[dict] = None
    timestamp_mode: Optional[str] = "aligner_interpolation"
    aligner_backend: Optional[str] = "qwen3"
    framer_backend: Optional[str] = "vad-grouped"
    translate_to: Optional[str] = None
    translate_base_url: Optional[str] = "https://api.openai.com/v1"
    translate_api_key: Optional[str] = ""
    translate_model: Optional[str] = "llama3.2"
    translate_style: Optional[str] = "adult_explicit"


class TranslateSrtRequest(BaseModel):
    srt_path: str
    target_lang: str = "zh"
    model: str = "gpt-4o-mini"
    style: str = "adult_explicit"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""


class WhisperResponse(BaseModel):
    task_id: str
    status: str
    message: str
    chain_id: Optional[str] = None
    followup_task_id: Optional[str] = None
    followup_job_type: Optional[str] = None


def map_emby_path_to_local(emby_path: str) -> str:
    settings = get_settings()
    if not settings.source_dir:
        return emby_path
    if emby_path.startswith("/data/media"):
        return emby_path.replace("/data/media", settings.source_dir, 1)
    return emby_path


def clean_video_name(name: str) -> str:
    name = re.sub(r"[-_]?(破解|流出|中文|字幕|ch|chs|cht|cn|tw|z[ah]?[-_]?.*)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.(mp4|mkv|avi|mov|wmv|flv|m4v)$", "", name, flags=re.IGNORECASE)
    return name.strip()


def build_expected_ja_srt_path(local_video_path: str) -> str:
    video_dir = os.path.dirname(local_video_path)
    clean_name = clean_video_name(os.path.basename(local_video_path))
    return os.path.join(video_dir, f"{clean_name}.ja.srt")


def resolve_whisper_strategy(request: WhisperRequest) -> str:
    explicit_strategy = request.strategy or request.preset
    if explicit_strategy:
        return normalize_whisper_strategy(explicit_strategy)
    common = (
        request.merge_strategy == "smart_merge" and request.language == "ja"
        and request.sensitivity == "balanced" and (request.vad_method or "semantic") == "semantic"
        and (request.audio_preprocess_mode or "none") == "none"
        and (request.speech_enhancer or "none") == "none" and not request.custom_config
    )
    recommended_shape = common and request.model == "anime-whisper" and request.pipeline_mode == "ensemble" and (request.pass1_pipeline or "anime") == "anime" and (request.pass2_pipeline or "qwen") == "qwen"
    baseline_shape = common and request.model == "large-v3" and request.pipeline_mode == "qwen" and (request.pass1_pipeline or "qwen") == "qwen" and not (request.pass2_pipeline or "")
    reazon_shape = common and request.model == "reazonspeech-nemo-v2" and request.pipeline_mode == "reazon" and (request.pass1_pipeline or "reazon") == "reazon" and not (request.pass2_pipeline or "")
    if recommended_shape:
        return "recommended"
    if baseline_shape:
        return "baseline"
    if reazon_shape:
        return "reazon_nemo"
    return "advanced"


@router.post("/tasks", response_model=WhisperResponse)
async def create_whisper_task(request: WhisperRequest):
    from app.api.settings import _assert_custom_pipeline_supported
    from app.core.models import JobCreate, JobSettings

    local_video_path = map_emby_path_to_local(request.video_path)
    if not os.path.exists(local_video_path):
        raise HTTPException(status_code=404, detail=f"Video not found: {local_video_path}")
    resolved_strategy = resolve_whisper_strategy(request)
    requested_translate_to = (request.translate_to or "").strip() or None
    whisper_config = {
        "strategy": resolved_strategy, "model": request.model, "pipeline_mode": request.pipeline_mode,
        "merge_strategy": request.merge_strategy, "language": request.language, "sensitivity": request.sensitivity,
        "vad_method": request.vad_method, "audio_preprocess_mode": request.audio_preprocess_mode,
        "audio_preprocess_model": request.audio_preprocess_model, "speech_enhancer": request.speech_enhancer,
        "pass1_pipeline": request.pass1_pipeline, "pass2_pipeline": request.pass2_pipeline,
        "custom_config": request.custom_config, "translate_to": None,
        "translate_base_url": request.translate_base_url, "translate_api_key": request.translate_api_key,
        "translate_model": request.translate_model, "translate_style": request.translate_style,
        "timestamp_mode": request.timestamp_mode, "aligner_backend": request.aligner_backend,
        "framer_backend": request.framer_backend,
    }
    whisper_config = apply_whisper_strategy(whisper_config, resolved_strategy)
    _assert_custom_pipeline_supported(whisper_config.get("pipeline_mode"), whisper_config.get("pass1_pipeline"), whisper_config.get("pass2_pipeline"))
    video_name = os.path.splitext(os.path.basename(local_video_path))[0]
    chain_id = str(os.urandom(16).hex())
    job_data = JobCreate(emby_item_id=f"whisper_{os.path.basename(local_video_path)}", emby_item_name=f"[Whisper] {video_name}", input_path=local_video_path, settings=JobSettings(**whisper_config), chain_id=chain_id)
    result = await job_manager.enqueue_whisper(job_data)
    translate_job_response = None
    if requested_translate_to:
        translate_job_data = JobCreate(
            emby_item_id=f"translate_{os.path.basename(local_video_path)}", emby_item_name=f"[翻译] {video_name}",
            input_path=build_expected_ja_srt_path(local_video_path),
            settings=JobSettings(srt_path=build_expected_ja_srt_path(local_video_path), target_lang=requested_translate_to, translate_model=request.translate_model, translate_base_url=request.translate_base_url, translate_api_key=request.translate_api_key or "", translate_style=request.translate_style),
            chain_id=chain_id, depends_on_task_id=result.id, parent_task_id=result.id,
        )
        translate_job_response = await job_manager.create_job(translate_job_data, job_type="translate-srt", status="blocked", enqueue_now=False)
    return WhisperResponse(task_id=result.id, status=result.status, message="Whisper 转写任务已创建，翻译任务将自动衔接" if requested_translate_to else "Whisper 转写任务已创建", chain_id=chain_id, followup_task_id=translate_job_response.id if translate_job_response else None, followup_job_type="translate-srt" if translate_job_response else None)


@router.get("/tasks/{task_id}")
async def get_whisper_task(task_id: str):
    job = await job_manager.get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")
    if job.job_type not in frozenset({"whisper", "whisper_transcribe"}):
        raise HTTPException(status_code=400, detail="Task is not a Whisper job")
    log_lines = await job_manager.get_logs(task_id)
    return {"task_id": job.id, "status": job.status, "progress": job.progress, "log_lines": log_lines[-50:], "error": job.error_message, "result_metadata": job.result_metadata, "recommended_diagnostics": (job.result_metadata or {}).get("recommended_diagnostics")}


@router.post("/tasks/{task_id}/run")
async def run_whisper_task(task_id: str):
    job = await job_manager.get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")
    if job.job_type not in frozenset({"whisper", "whisper_transcribe"}):
        raise HTTPException(status_code=400, detail="Task is not a Whisper job")
    return {"task_id": task_id, "status": job.status}


@router.post("/translate/test")
async def test_translate_connection(base_url: str = "https://api.openai.com/v1", api_key: str = "", model: str = "gpt-4o-mini"):
    from app.pipeline.whisper.translator import check_translator_health
    log_mgr = SystemLogManager.get_instance()
    log_mgr.add_log("info", f"[Whisper] 正在测试翻译服务连接 ({model} @ {base_url})...")
    result = check_translator_health(base_url=base_url, api_key=api_key or None, model=model)
    if result.get("available"):
        log_mgr.add_log("success", f"[Whisper] 翻译服务可用 — 可用模型: {', '.join(result.get('models', [])[:3]) or '未知'}")
    else:
        log_mgr.add_log("error", f"[Whisper] 翻译服务不可用 — {result.get('message', '未知错误')}")
    return result


@router.post("/translate/srt")
async def translate_srt(req: TranslateSrtRequest):
    from app.core.models import JobCreate, JobSettings
    if not os.path.exists(req.srt_path):
        raise HTTPException(status_code=404, detail=f"SRT file not found: {req.srt_path}")
    filename = os.path.splitext(os.path.basename(req.srt_path))[0]
    job_data = JobCreate(emby_item_id="translate-srt", emby_item_name=f"[翻译] {filename}", input_path=req.srt_path, settings=JobSettings(srt_path=req.srt_path, target_lang=req.target_lang, translate_model=req.model, translate_base_url=req.base_url, translate_api_key=req.api_key or "", translate_style=req.style))
    result = await job_manager.enqueue_translate_srt(job_data)
    return {"task_id": result.id, "status": result.status, "message": "翻译任务已创建"}


@router.get("/translate/preview")
async def translate_preview(srt_path: str):
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail=f"SRT file not found: {srt_path}")
    with open(srt_path, "r", encoding="utf-8") as file:
        srt_content = file.read()
    return {"content": srt_content}


async def init_whisper_db():
    return None
