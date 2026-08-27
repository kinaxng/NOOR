"""Bounded two-pane filesystem browser for configured media roots."""
from __future__ import annotations

import grp
import os
import pwd
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def browser_roots(config: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    sources: list[Path] = []
    hardlinks: list[Path] = []
    for group in config.get("scan_groups", []) or []:
        source = str(group.get("source_dir") or "").strip()
        hardlink = str(group.get("hardlink_dir") or "").strip()
        if source:
            sources.append(Path(source).expanduser().resolve())
        if hardlink:
            hardlinks.append(Path(hardlink).expanduser().resolve())
    return _unique_paths(sources), _unique_paths(hardlinks)


def _unique_paths(paths: list[Path]) -> list[Path]:
    return list(dict.fromkeys(paths))


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _is_corridor(path: Path, roots: list[Path]) -> bool:
    return any(_inside(path, root) or _inside(root, path) for root in roots)


def resolve_browser_path(raw_path: str | None, roots: list[Path], default: Path) -> Path:
    if not roots:
        raise HTTPException(status_code=400, detail="尚未配置媒体扫描目录")
    candidate = Path(raw_path).expanduser().resolve() if raw_path else default
    if not _is_corridor(candidate, roots):
        raise HTTPException(status_code=403, detail=f"路径不在媒体文件浏览范围内: {candidate}")
    if not candidate.is_dir():
        raise HTTPException(status_code=404, detail=f"目录不存在: {candidate}")
    return candidate


def assert_operable(path: Path, roots: list[Path], *, must_exist: bool = True) -> Path:
    resolved = path.expanduser().resolve()
    if not any(_inside(resolved, root) for root in roots):
        raise HTTPException(status_code=403, detail=f"只能操作已配置媒体目录内的文件: {resolved}")
    if must_exist and not resolved.exists():
        raise HTTPException(status_code=404, detail=f"文件或目录不存在: {resolved}")
    if resolved in roots:
        raise HTTPException(status_code=400, detail=f"禁止操作媒体根目录: {resolved}")
    return resolved


def _owner_name(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _group_name(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def _entry_payload(path: Path) -> dict[str, Any]:
    item_stat = path.lstat()
    is_link = path.is_symlink()
    is_dir = path.is_dir()
    return {
        "name": path.name or str(path),
        "path": str(path),
        "is_dir": is_dir,
        "is_symlink": is_link,
        "size": 0 if is_dir else item_stat.st_size,
        "modified_at": datetime.fromtimestamp(item_stat.st_mtime, timezone.utc).isoformat(),
        "mode": stat.filemode(item_stat.st_mode),
        "owner": _owner_name(item_stat.st_uid),
        "group": _group_name(item_stat.st_gid),
        "readable": os.access(path, os.R_OK),
        "writable": os.access(path, os.W_OK),
        "executable": os.access(path, os.X_OK),
        "inode": item_stat.st_ino,
        "link_count": item_stat.st_nlink,
        "extension": "" if is_dir else path.suffix.lower(),
    }


def browse_directory(path: Path, roots: list[Path]) -> dict[str, Any]:
    try:
        entries = []
        for child in path.iterdir():
            if not _is_corridor(child.resolve(), roots):
                continue
            try:
                entries.append(_entry_payload(child))
            except (FileNotFoundError, PermissionError, OSError):
                continue
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"没有权限读取目录: {path}") from exc
    entries.sort(key=lambda item: (not item["is_dir"], item["name"].casefold()))
    parent = path.parent if path.parent != path and _is_corridor(path.parent, roots) else None
    current = _entry_payload(path)
    return {
        "path": str(path),
        "parent": str(parent) if parent else None,
        "entries": entries,
        "permissions": {key: current[key] for key in ("mode", "owner", "group", "readable", "writable", "executable")},
    }


def transfer_entries(action: str, sources: list[Path], target_dir: Path, roots: list[Path]) -> list[str]:
    target_dir = target_dir.expanduser().resolve()
    if not any(_inside(target_dir, root) for root in roots) or not target_dir.is_dir():
        raise HTTPException(status_code=403, detail="目标目录不在允许的媒体目录内")
    if action not in {"copy", "move"}:
        raise HTTPException(status_code=400, detail="不支持的传输操作")
    resolved_sources = [assert_operable(raw_source, roots) for raw_source in sources]
    destinations = [target_dir / source.name for source in resolved_sources]
    if len(set(destinations)) != len(destinations):
        raise HTTPException(status_code=409, detail="选中项包含同名文件，无法放入同一目标目录")
    for source, destination in zip(resolved_sources, destinations, strict=True):
        if destination.exists():
            raise HTTPException(status_code=409, detail=f"目标已存在: {destination}")
        if source.is_dir() and _inside(destination, source):
            raise HTTPException(status_code=400, detail="不能把目录复制或移动到其自身内部")
    results = []
    for source, destination in zip(resolved_sources, destinations, strict=True):
        if action == "move":
            shutil.move(str(source), str(destination))
        elif source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)
        results.append(str(destination))
    return results


def rename_entry(source: Path, new_name: str, roots: list[Path]) -> str:
    source = assert_operable(source, roots)
    name = new_name.strip()
    if not name or name in {".", ".."} or Path(name).name != name or "\x00" in name:
        raise HTTPException(status_code=400, detail="文件名无效")
    destination = source.with_name(name)
    assert_operable(destination, roots, must_exist=False)
    if destination.exists():
        raise HTTPException(status_code=409, detail=f"目标已存在: {destination}")
    source.rename(destination)
    return str(destination)


def create_directory(parent: Path, name: str, roots: list[Path]) -> str:
    parent = parent.expanduser().resolve()
    if not any(_inside(parent, root) for root in roots):
        raise HTTPException(status_code=403, detail="只能在已配置媒体目录内新建文件夹")
    clean_name = name.strip()
    if not clean_name or clean_name in {".", ".."} or Path(clean_name).name != clean_name:
        raise HTTPException(status_code=400, detail="文件夹名称无效")
    destination = parent / clean_name
    if destination.exists():
        raise HTTPException(status_code=409, detail=f"目标已存在: {destination}")
    destination.mkdir()
    return str(destination)


def delete_entries(paths: list[Path], roots: list[Path]) -> list[str]:
    resolved = [assert_operable(path, roots) for path in paths]
    for path in resolved:
        if any(path != other and _inside(path, other) for other in resolved):
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    return [str(path) for path in resolved]
