"""Subtitle browsing and acquisition API reconstructed from bytecode."""
from __future__ import annotations

import logging
import os
import re
import shutil
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.local_library import search_local_library
from app.core.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subtitles", tags=["subtitles"])
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".sbv", ".sup"}
SUBTITLE_MIME = {".srt": "text/plain", ".ass": "text/plain", ".ssa": "text/plain", ".vtt": "text/vtt", ".sub": "text/plain", ".sbv": "text/plain", ".sup": "application/octet-stream"}


class SubtitleFile(BaseModel):
    filename: str
    path: str
    size: int
    ext: str


class OnlineSubtitle(BaseModel):
    name: str
    url: str
    ext: str
    language: str
    source: str
    source_key: str = "remote"
    source_type: str = "remote"


class SubtitleListResponse(BaseModel):
    subtitles: list[SubtitleFile]
    video_path: str
    video_dir: str


class OnlineSubtitleResponse(BaseModel):
    results: list[OnlineSubtitle]
    video_name: str


class SubtitleContentResponse(BaseModel):
    content: str
    filename: str


class SubtitleDeleteResponse(BaseModel):
    success: bool
    deleted: str


def _get_httpx():
    return httpx


def map_emby_path_to_local(emby_path: str) -> str:
    settings = get_settings()
    if not settings.source_dir:
        return emby_path
    if emby_path.startswith("/data/media"):
        return emby_path.replace("/data/media", settings.source_dir, 1)
    return emby_path


def extract_video_code(video_path: str) -> Optional[str]:
    basename = os.path.basename(video_path)
    name = os.path.splitext(basename)[0]
    name = re.sub(r"[-_]?(破解|流出|中文|字幕|ch|chs|cht|cn|tw|z[ah]?[-_]?.*)", "", name, flags=re.IGNORECASE)
    match = re.match(r"([A-Z]+-\d+)", name.upper())
    return match.group(1) if match else name.upper()


@router.get("", response_model=SubtitleListResponse)
async def list_subtitles(video_path: str):
    if not video_path:
        raise HTTPException(status_code=400, detail="Video path is required")
    local_video_path = map_emby_path_to_local(video_path)
    video_dir = os.path.dirname(local_video_path)
    video_name = os.path.splitext(os.path.basename(local_video_path))[0]
    if not os.path.exists(video_dir):
        raise HTTPException(status_code=404, detail=f"Video directory not found: {video_dir}")
    subtitles = []
    try:
        for filename in os.listdir(video_dir):
            filepath = os.path.join(video_dir, filename)
            if not os.path.isfile(filepath):
                continue
            base_name, ext = os.path.splitext(filename)
            base_name, ext = base_name.lower(), ext.lower()
            if ext not in SUBTITLE_EXTS:
                continue
            video_lower = video_name.lower()
            if len(base_name) < 8 or not (base_name in video_lower or video_lower.startswith(base_name) or base_name.startswith(video_lower[:8])):
                continue
            subtitles.append(SubtitleFile(filename=filename, path=filepath, size=os.path.getsize(filepath), ext=ext))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    return SubtitleListResponse(subtitles=subtitles, video_path=video_path, video_dir=video_dir)


@router.get("/search", response_model=OnlineSubtitleResponse)
async def search_subtitles(video_path: str, local_only: bool = False):
    if not video_path:
        raise HTTPException(status_code=400, detail="Video path is required")
    video_code = extract_video_code(video_path)
    if not video_code:
        raise HTTPException(status_code=400, detail="Cannot extract video code from path")
    all_results = list(search_local_library(video_code, video_path))
    if not local_only:
        all_results.extend(await _search_xunlei(video_code))
    seen = {}
    for result in sorted(all_results, key=lambda item: item.get("score", 0), reverse=True):
        result_id = result.get("id", "")
        if result_id and result_id not in seen:
            seen[result_id] = result
    return OnlineSubtitleResponse(results=[OnlineSubtitle(name=item.get("filename", ""), url=item.get("url", ""), ext=item.get("ext", ".srt"), language=item.get("language", "unknown"), source=item.get("source", ""), source_key=item.get("source_key", "remote"), source_type=item.get("source_type", "remote")) for item in seen.values()], video_name=video_code)


async def _search_xunlei(video_code: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=float(30)) as client:
            response = await client.get("https://api-shoulei-ssl.xunlei.com/oracle/subtitle", params={"name": video_code})
            response.raise_for_status()
            data = response.json()
        results = []
        if data.get("code") == 0 and data.get("data"):
            for item in data["data"]:
                results.append({"id": f"xunlei:{item.get('name', '')}:{item.get('url', '')}", "filename": item.get("name", "unknown"), "ext": item.get("ext", ".srt"), "language": (item.get("languages", ["未知"])[0] if item.get("languages") else "未知"), "source": "迅雷", "source_key": "xunlei", "source_type": "remote_search", "url": item.get("url", ""), "score": 0.7})
        return results
    except Exception as exc:
        logger.warning("[subtitle:xunlei] Search failed for %s: %s", video_code, exc)
        return []


def read_subtitle_file(path: str) -> tuple[str, str]:
    filename = os.path.basename(path)
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as file:
                return file.read(), filename
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as file:
        return file.read().decode("utf-8", errors="replace"), filename


def _validate_subtitle_path(path: str) -> str:
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="Not a file")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUBTITLE_EXTS:
        raise HTTPException(status_code=400, detail="Not a subtitle file")
    return ext


@router.get("/file")
async def get_subtitle_file(path: str):
    ext = _validate_subtitle_path(path)
    return FileResponse(path=path, filename=os.path.basename(path), media_type=SUBTITLE_MIME.get(ext, "text/plain"))


@router.get("/content", response_model=SubtitleContentResponse)
async def get_subtitle_content(path: str):
    _validate_subtitle_path(path)
    try:
        content, filename = read_subtitle_file(path)
        return SubtitleContentResponse(content=content, filename=filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}")


@router.get("/fetch", response_model=SubtitleContentResponse)
async def fetch_online_subtitle(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    try:
        async with _get_httpx().AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        filename = os.path.basename(url.split("?")[0]) or "subtitle.srt"
        return SubtitleContentResponse(content=response.text, filename=filename)
    except _get_httpx().HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch subtitle: {exc}")


def is_local_subtitle_source(url: str, source: str | None = None, source_type: str | None = None, source_key: str | None = None) -> bool:
    if source_key == "local_library" or source_type == "local_library":
        return True
    if source_type is None and source == "本地字幕库":
        return True
    return source is None and os.path.exists(url)


def get_unique_subtitle_path(video_dir: str, video_name: str, ext: str) -> str:
    base_name = os.path.join(video_dir, video_name)
    if not ext.startswith("."):
        ext = "." + ext
    target_path = base_name + ext
    if not os.path.exists(target_path):
        return target_path
    for suffix in ("-a", "-b", "-c", "-d", "-e", "-f", "-g", "-h"):
        target_path = base_name + suffix + ext
        if not os.path.exists(target_path):
            return target_path
    for index in range(1, 100):
        target_path = f"{base_name}-{index}{ext}"
        if not os.path.exists(target_path):
            return target_path
    import time
    return f"{base_name}-{int(time.time())}{ext}"


@router.get("/download")
async def download_online_subtitle(url: str, video_path: str, source: str | None = None, source_type: str | None = None, source_key: str | None = None):
    if not url or not video_path:
        raise HTTPException(status_code=400, detail="URL and video path are required")
    local_video_path = map_emby_path_to_local(video_path)
    video_dir = os.path.dirname(local_video_path)
    video_name = os.path.splitext(os.path.basename(local_video_path))[0]
    clean_video_name = re.sub(r"[-_]?(破解|流出|中文|字幕|ch|chs|cht|cn|tw|z[ah]?[-_]?.*)", "", video_name, flags=re.IGNORECASE)
    if is_local_subtitle_source(url, source=source, source_type=source_type, source_key=source_key):
        local_sub_path = url if os.path.exists(url) else None
        if not local_sub_path:
            raise HTTPException(status_code=404, detail="Subtitle file not found")
        if not os.path.isfile(local_sub_path):
            raise HTTPException(status_code=400, detail="Not a file")
        ext = os.path.splitext(local_sub_path)[1].lower() or ".srt"
        save_path = get_unique_subtitle_path(video_dir, clean_video_name, ext)
        try:
            shutil.copy2(local_sub_path, save_path)
        except IOError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to copy subtitle: {exc}")
        return {"success": True, "filename": os.path.basename(save_path), "path": save_path, "size": os.path.getsize(save_path)}
    if not os.path.exists(video_dir):
        raise HTTPException(status_code=404, detail="Video directory not found")
    try:
        async with _get_httpx().AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
        ext_from_url = os.path.splitext(url.split("?")[0])[1].lower()
        ext = ext_from_url if ext_from_url in SUBTITLE_EXTS else ".srt"
        save_path = get_unique_subtitle_path(video_dir, clean_video_name, ext)
        with open(save_path, "wb") as file:
            file.write(content)
        return {"success": True, "filename": os.path.basename(save_path), "path": save_path, "size": len(content)}
    except _get_httpx().HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Download failed: {exc}")
    except IOError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save: {exc}")


@router.delete("")
async def delete_subtitle(path: str):
    _validate_subtitle_path(path)
    try:
        os.remove(path)
        return SubtitleDeleteResponse(success=True, deleted=path)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {exc}")
