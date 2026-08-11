from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, get_settings
from app.core.runtime_paths import data_path


DEFAULT_MIN_AGE_HOURS = 6
MAX_CLEANUP_ITEMS = 256
TMP_ROOT = Path("/tmp")


_last_cleanup: dict[str, Any] = {
    "status": "idle",
    "message": "",
    "started_at": "",
    "finished_at": "",
    "deleted_bytes": 0,
    "deleted_count": 0,
}


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    label: str
    size: int
    mtime: float


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _status_path() -> Path:
    path = data_path("runtime", "runtime_cleanup_status.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_last_cleanup() -> dict[str, Any]:
    import json

    try:
        path = _status_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**_last_cleanup, **data}
    except Exception:
        pass
    return dict(_last_cleanup)


def _write_last_cleanup(status: dict[str, Any]) -> None:
    import json

    global _last_cleanup
    _last_cleanup = {**_last_cleanup, **status}
    try:
        _status_path().write_text(json.dumps(_last_cleanup, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _safe_size(path: Path) -> int:
    try:
        if path.is_file() or path.is_symlink():
            return path.stat().st_size
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file() or item.is_symlink():
                    total += item.stat().st_size
            except OSError:
                continue
        return total
    except OSError:
        return 0


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0


def _is_old_enough(path: Path, cutoff: float) -> bool:
    return _safe_mtime(path) <= cutoff


def _append_existing(candidates: list[CleanupCandidate], path: Path, label: str, cutoff: float) -> None:
    if not path.exists() or not _is_old_enough(path, cutoff):
        return
    candidates.append(CleanupCandidate(path=path, label=label, size=_safe_size(path), mtime=_safe_mtime(path)))


def _append_children(candidates: list[CleanupCandidate], root: Path, label: str, cutoff: float) -> None:
    if not root.exists() or not root.is_dir():
        return
    try:
        children = sorted(root.iterdir(), key=lambda item: _safe_mtime(item))
    except OSError:
        return
    for child in children:
        if _is_old_enough(child, cutoff):
            candidates.append(CleanupCandidate(path=child, label=label, size=_safe_size(child), mtime=_safe_mtime(child)))
        if len(candidates) >= MAX_CLEANUP_ITEMS:
            return


def collect_runtime_cleanup_candidates(min_age_hours: int = DEFAULT_MIN_AGE_HOURS) -> list[CleanupCandidate]:
    settings = get_settings()
    cutoff = time.time() - max(0, int(min_age_hours or 0)) * 3600
    candidates: list[CleanupCandidate] = []

    # NOOR-owned runtime temp roots.
    _append_children(candidates, Path(settings.facefusion_temp_dir) / "tasks", "FaceFusion 任务临时目录", cutoff)
    _append_children(candidates, Path(settings.whisper_temp_dir) / "whisper_jav", "Whisper JAV 临时目录", cutoff)
    _append_children(candidates, Path(settings.whisper_temp_dir) / "segments", "Whisper 分段临时目录", cutoff)
    _append_children(candidates, Path(settings.lada_temp_dir) / "tasks", "LADA 任务临时目录", cutoff)

    # Historical NOOR temp locations before runtime-root consolidation.
    for pattern, label in (
        ("noor-*", "NOOR /tmp 临时目录"),
        ("whisper_jav", "旧 Whisper JAV 临时目录"),
        ("qwen3-asr-*", "NOOR ASR 实验临时目录"),
    ):
        for path in TMP_ROOT.glob(pattern):
            _append_existing(candidates, path, label, cutoff)
            if len(candidates) >= MAX_CLEANUP_ITEMS:
                break

    smoke_dir = PROJECT_ROOT / "data" / "runtime" / "facefusion" / "smoke"
    _append_existing(candidates, smoke_dir, "FaceFusion smoke 测试文件", cutoff)

    deduped: dict[Path, CleanupCandidate] = {}
    for candidate in candidates:
        deduped[candidate.path.resolve(strict=False)] = candidate
    return sorted(deduped.values(), key=lambda item: item.size, reverse=True)[:MAX_CLEANUP_ITEMS]


def runtime_cleanup_status(min_age_hours: int = DEFAULT_MIN_AGE_HOURS) -> dict[str, Any]:
    candidates = collect_runtime_cleanup_candidates(min_age_hours=min_age_hours)
    total_size = sum(item.size for item in candidates)
    last_cleanup = _read_last_cleanup()
    return {
        "status": last_cleanup.get("status") or "idle",
        "summary": f"可清理 {format_bytes(total_size)} · {len(candidates)} 项",
        "reclaimable_bytes": total_size,
        "candidate_count": len(candidates),
        "min_age_hours": min_age_hours,
        "last_cleanup": last_cleanup,
        "top_candidates": [
            {
                "path": str(item.path),
                "label": item.label,
                "size": item.size,
                "size_text": format_bytes(item.size),
                "mtime": item.mtime,
            }
            for item in candidates[:8]
        ],
    }


def run_runtime_cleanup(min_age_hours: int = DEFAULT_MIN_AGE_HOURS) -> dict[str, Any]:
    started_at = _now_iso()
    _write_last_cleanup({
        "status": "running",
        "message": "运行时清理中",
        "started_at": started_at,
        "finished_at": "",
    })
    candidates = collect_runtime_cleanup_candidates(min_age_hours=min_age_hours)
    deleted_bytes = 0
    deleted_count = 0
    errors: list[str] = []
    for candidate in candidates:
        try:
            if candidate.path.is_dir() and not candidate.path.is_symlink():
                shutil.rmtree(candidate.path)
            else:
                candidate.path.unlink(missing_ok=True)
            deleted_bytes += candidate.size
            deleted_count += 1
        except Exception as exc:
            errors.append(f"{candidate.path}: {exc}")

    _write_last_cleanup({
        "status": "failed" if errors else "completed",
        "message": f"已清理 {format_bytes(deleted_bytes)} · {deleted_count} 项" if not errors else f"部分清理失败 · {len(errors)} 项",
        "started_at": started_at,
        "finished_at": _now_iso(),
        "deleted_bytes": deleted_bytes,
        "deleted_count": deleted_count,
        "errors": errors[:8],
    })
    return {
        "ok": not errors,
        "deleted_bytes": deleted_bytes,
        "deleted_size": format_bytes(deleted_bytes),
        "deleted_count": deleted_count,
        "errors": errors[:8],
        "status": runtime_cleanup_status(min_age_hours=min_age_hours),
    }


def format_bytes(value: int) -> str:
    size = float(max(0, int(value or 0)))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"
