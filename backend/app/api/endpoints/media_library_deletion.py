"""Safe hardlink/source deletion helpers for the media-library router.

Reconstructed from the preserved media-library router bytecode.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastapi import HTTPException

from app.api.endpoints.media_library_helpers import VIDEO_EXTS


def allowed_scan_roots(config: dict) -> tuple[list[Path], list[Path]]:
    source_roots, hardlink_roots = [], []
    for group in config.get("scan_groups", []) or []:
        source_dir, hardlink_dir = group.get("source_dir"), group.get("hardlink_dir")
        if source_dir:
            source_roots.append(Path(source_dir).resolve())
        if hardlink_dir:
            hardlink_roots.append(Path(hardlink_dir).resolve())
    return source_roots, hardlink_roots


def is_under_roots(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def assert_safe_path(path: Path, roots: list[Path], label: str) -> None:
    if not roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")
    if not is_under_roots(path, roots):
        raise HTTPException(status_code=400, detail=f"{label} 不在允许的扫描路径内: {path}")


def remove_file_and_sibling_nfo(path: Path, *, remove_nfo: bool = True) -> list[str]:
    deleted = []
    if path.is_file():
        path.unlink()
        deleted.append(str(path))
    if remove_nfo:
        sibling_nfo = path.with_suffix(".nfo")
        if sibling_nfo.is_file():
            sibling_nfo.unlink()
            deleted.append(str(sibling_nfo))
    return deleted


def normalize_code_token(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def directory_matches_target_videos(dir_path: Path, target_files: set[Path]) -> bool:
    if not dir_path.is_dir() or not target_files:
        return False
    target_in_dir = {path.resolve() for path in target_files if path.parent == dir_path}
    if not target_in_dir:
        return False
    try:
        video_files = set()
        for child in dir_path.iterdir():
            if child.is_dir():
                return False
            if child.suffix.lower() in VIDEO_EXTS:
                video_files.add(child.resolve())
        return bool(video_files) and video_files == target_in_dir
    except OSError:
        return False


def parent_is_code_bucket(file_path: Path, code: str | None) -> bool:
    if not code:
        return False
    code_token = normalize_code_token(code)
    if not code_token:
        return False
    parent_token = normalize_code_token(file_path.parent.name)
    return bool(parent_token and code_token in parent_token)


def collect_chain_delete_targets(
    source_path: Path | None,
    hardlink_paths: list[Path],
    code: str | None,
    source_roots: list[Path],
    hardlink_roots: list[Path],
) -> tuple[set[Path], set[Path]]:
    delete_dirs: set[Path] = set()
    delete_files: set[Path] = set()
    protected_roots = set(source_roots + hardlink_roots)
    if source_path:
        if parent_is_code_bucket(source_path, code) and directory_matches_target_videos(source_path.parent, {source_path}):
            if source_path.parent in protected_roots:
                raise HTTPException(status_code=400, detail=f"禁止删除扫描根目录: {source_path.parent}")
            delete_dirs.add(source_path.parent)
        else:
            delete_files.add(source_path)
    hardlink_targets = set(hardlink_paths)
    for hardlink_path in hardlink_paths:
        if parent_is_code_bucket(hardlink_path, code) and directory_matches_target_videos(hardlink_path.parent, hardlink_targets):
            if hardlink_path.parent in protected_roots:
                raise HTTPException(status_code=400, detail=f"禁止删除扫描根目录: {hardlink_path.parent}")
            delete_dirs.add(hardlink_path.parent)
        else:
            delete_files.add(hardlink_path)
    for target_dir in list(delete_dirs):
        delete_files = {path for path in delete_files if target_dir not in path.parents}
    return delete_dirs, delete_files


def execute_delete_targets(delete_dirs: set[Path], delete_files: set[Path]) -> dict[str, list[str]]:
    deleted_dirs: list[str] = []
    missing_dirs: list[str] = []
    deleted_files: list[str] = []
    missing_files: list[str] = []
    errors: list[str] = []
    for target_dir in sorted(delete_dirs, key=lambda path: len(path.parts), reverse=True):
        if not target_dir.exists():
            missing_dirs.append(str(target_dir))
            continue
        try:
            shutil.rmtree(target_dir)
            deleted_dirs.append(str(target_dir))
        except Exception as exc:
            errors.append(f"{target_dir}: {exc}")
    for target_file in sorted(delete_files):
        if not target_file.exists():
            missing_files.append(str(target_file))
            continue
        try:
            deleted_files.extend(remove_file_and_sibling_nfo(target_file, remove_nfo=True))
        except Exception as exc:
            errors.append(f"{target_file}: {exc}")
    if errors:
        raise HTTPException(status_code=500, detail=f"部分删除失败: {'; '.join(errors)}")
    if not deleted_dirs and not deleted_files and not missing_dirs and not missing_files:
        raise HTTPException(status_code=404, detail="目标不存在")
    return {"deleted_dirs": deleted_dirs, "missing_dirs": missing_dirs, "deleted_files": deleted_files, "missing_files": missing_files}


def preview_delete_targets(delete_dirs: set[Path], delete_files: set[Path]) -> dict[str, list[str]]:
    planned_dirs = sorted(str(path) for path in delete_dirs)
    planned_files = []
    for file_path in sorted(delete_files):
        planned_files.append(str(file_path))
        nfo_path = file_path.with_suffix(".nfo")
        if nfo_path.exists():
            planned_files.append(str(nfo_path))
    return {"planned_dirs": planned_dirs, "planned_files": planned_files}
