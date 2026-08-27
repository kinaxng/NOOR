from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.api.settings_lada_upgrade import github_mirror_url
from app.core.config import PROJECT_ROOT
from app.core.facefusion_paths import resolve_embedded_facefusion_source


FACEFUSION_UPSTREAM_REPO = "https://github.com/facefusion/facefusion.git"
FACEFUSION_UPSTREAM_MANIFEST = "NOOR_UPSTREAM.json"
FACEFUSION_SYNC_EXCLUDES = {
    ".git",
    ".github",
    ".assets",
    ".caches",
    ".claude",
    ".idea",
    ".jobs",
    ".venv",
    ".vscode",
    "__pycache__",
    "facefusion.ini",
    FACEFUSION_UPSTREAM_MANIFEST,
    "temp",
}


def facefusion_runtime_update_root(settings: Any) -> Path:
    cache_dir = Path(getattr(settings, "facefusion_cache_dir", "") or PROJECT_ROOT / "data" / "runtime" / "facefusion" / "cache")
    return cache_dir / "updater"


def get_facefusion_source_dir() -> Path:
    source = resolve_embedded_facefusion_source()
    if not source:
        raise RuntimeError("NOOR 内置 FaceFusion 源码不存在")
    return source.source_dir


def get_facefusion_version(source_dir: Path | None = None) -> str | None:
    source_dir = source_dir or get_facefusion_source_dir()
    metadata_path = source_dir / "facefusion" / "metadata.py"
    if not metadata_path.exists():
        return None
    namespace: dict[str, Any] = {}
    try:
        exec(metadata_path.read_text(encoding="utf-8"), namespace)
        metadata = namespace.get("METADATA") or {}
        version = metadata.get("version")
        return str(version) if version else None
    except Exception:
        return None


def get_facefusion_upstream_manifest(source_dir: Path | None = None) -> dict[str, Any]:
    source_dir = source_dir or get_facefusion_source_dir()
    manifest_path = source_dir / FACEFUSION_UPSTREAM_MANIFEST
    if not manifest_path.exists():
        return {}
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_facefusion_upstream_manifest(
    source_dir: Path,
    *,
    revision: str | None,
    version: str | None,
    updated_at: str | None,
) -> None:
    revision_value = revision or "unknown"
    manifest = {
        "repo": FACEFUSION_UPSTREAM_REPO,
        "revision": revision_value,
        "short_revision": revision_value[:12] if revision_value != "unknown" else "unknown",
        "version": version,
        "updated_at": updated_at,
    }
    (source_dir / FACEFUSION_UPSTREAM_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _git_stdout(cwd: Path, args: list[str], timeout: int = 15) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _package_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except Exception:
        return None


def get_facefusion_runtime_info() -> dict[str, Any]:
    onnxruntime_version = _package_version("onnxruntime") or _package_version("onnxruntime-gpu")
    providers: list[str] = []
    try:
        import onnxruntime

        onnxruntime_version = str(getattr(onnxruntime, "__version__", "") or onnxruntime_version or "") or None
        providers = list(onnxruntime.get_available_providers())
    except Exception:
        providers = []
    return {
        "versions": {
            "python": ".".join(str(part) for part in sys.version_info[:3]),
            "onnxruntime": onnxruntime_version,
            "onnx": _package_version("onnx"),
            "numpy": _package_version("numpy"),
            "opencv": _package_version("opencv-python") or _package_version("opencv-python-headless"),
            "scipy": _package_version("scipy"),
            "tqdm": _package_version("tqdm"),
            "gradio": _package_version("gradio"),
        },
        "execution_providers": providers,
        "python_executable": sys.executable,
    }


def get_facefusion_installation_info(settings: Any) -> dict[str, Any]:
    source_dir = get_facefusion_source_dir()
    is_docker = os.path.exists("/.dockerenv")
    runtime_info = get_facefusion_runtime_info()
    upstream_manifest = get_facefusion_upstream_manifest(source_dir)
    return {
        "version": get_facefusion_version(source_dir),
        "upstream_manifest": upstream_manifest,
        "upstream_revision": upstream_manifest.get("revision"),
        "upstream_short_revision": upstream_manifest.get("short_revision"),
        "upstream_updated_at": upstream_manifest.get("updated_at"),
        "runtime_versions": runtime_info["versions"],
        "execution_providers": runtime_info["execution_providers"],
        "python_executable": runtime_info["python_executable"],
        "source_mode": "embedded",
        "source_dir": str(source_dir),
        "is_docker": is_docker,
        "can_self_upgrade": not is_docker,
        "upgrade_strategy": "controlled-upstream-sync" if not is_docker else "docker-rebuild",
        "upgrade_hint": (
            "当前使用 NOOR 内置 FaceFusion，可从上游拉取源码、套用 NOOR 路径补丁并验证 CLI。"
            if not is_docker
            else "Docker 模式下不建议在容器内直接升级 FaceFusion。请更新镜像后重建容器。"
        ),
        "upstream_repo": FACEFUSION_UPSTREAM_REPO,
        "update_work_dir": str(facefusion_runtime_update_root(settings)),
    }


def _copy_source_tree(src: Path, dst: Path) -> None:
    for item in src.iterdir():
        if item.name in FACEFUSION_SYNC_EXCLUDES:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=True)
        else:
            shutil.copy2(item, target, follow_symlinks=False)


def _replace_source_from_clone(clone_dir: Path, source_dir: Path) -> None:
    preserved_names = {".assets", ".caches", ".jobs", "facefusion.ini", "temp"}
    preserved = {name: source_dir / name for name in preserved_names if (source_dir / name).exists() or (source_dir / name).is_symlink()}
    for item in source_dir.iterdir():
        if item.name in preserved:
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()
    _copy_source_tree(clone_dir, source_dir)


def _apply_noor_facefusion_patch(source_dir: Path) -> None:
    gitignore_path = source_dir / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    required_ignores = ["__pycache__", ".assets", ".claude", ".caches", ".idea", ".jobs", ".vscode", "temp"]
    lines = [line.rstrip("\n") for line in existing.splitlines()]
    for item in required_ignores:
        if item not in lines:
            lines.append(item)
    gitignore_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    execution_path = source_dir / "facefusion" / "execution.py"
    if not execution_path.exists():
        raise RuntimeError("FaceFusion execution.py 不存在，无法套用 NOOR 缓存补丁")
    text = execution_path.read_text(encoding="utf-8")
    if "ORT_TENSORRT_CACHE_PATH" not in text:
        old = "return os.path.join('.caches', onnxruntime.get_version_string())"
        new = "return os.getenv('ORT_TENSORRT_CACHE_PATH') or os.path.join('.caches', onnxruntime.get_version_string())"
        if old not in text:
            raise RuntimeError("FaceFusion TensorRT 缓存逻辑已变化，请手动检查 NOOR 补丁")
        execution_path.write_text(text.replace(old, new), encoding="utf-8")

    core_path = source_dir / "facefusion" / "core.py"
    if core_path.exists():
        text = core_path.read_text(encoding="utf-8")
        text, _ = re.subn(
            r"def common_pre_check\(\) -> bool:\n.*?(?=\n\ndef )",
            "def common_pre_check() -> bool:\n\treturn True\n",
            text,
            count=1,
            flags=re.DOTALL,
        )
        core_path.write_text(text, encoding="utf-8")

    content_path = source_dir / "facefusion" / "content_analyser.py"
    if content_path.exists():
        text = content_path.read_text(encoding="utf-8")
    else:
        text = ""
    if text and "NOOR_FACEFUSION_SKIP_CONTENT_ANALYSIS" not in text:
        text = text.replace("from functools import lru_cache\n", "from functools import lru_cache\nimport os\n", 1)
        text = text.replace(
            "STREAM_COUNTER = 0\n",
            "STREAM_COUNTER = 0\n\n\ndef skip_content_analysis() -> bool:\n\treturn os.getenv('NOOR_FACEFUSION_SKIP_CONTENT_ANALYSIS') == '1'\n",
            1,
        )
        replacements = {
            "def pre_check() -> bool:\n": "def pre_check() -> bool:\n\tif skip_content_analysis():\n\t\treturn True\n",
            "def analyse_stream(vision_frame : VisionFrame, video_fps : Fps) -> bool:\n\tglobal STREAM_COUNTER\n": "def analyse_stream(vision_frame : VisionFrame, video_fps : Fps) -> bool:\n\tglobal STREAM_COUNTER\n\tif skip_content_analysis():\n\t\treturn False\n",
            "def analyse_frame(vision_frame : VisionFrame) -> bool:\n": "def analyse_frame(vision_frame : VisionFrame) -> bool:\n\tif skip_content_analysis():\n\t\treturn False\n",
            "def analyse_image(image_path : str) -> bool:\n": "def analyse_image(image_path : str) -> bool:\n\tif skip_content_analysis():\n\t\treturn False\n",
            "def analyse_video(video_path : str, trim_frame_start : int, trim_frame_end : int) -> bool:\n": "def analyse_video(video_path : str, trim_frame_start : int, trim_frame_end : int) -> bool:\n\tif skip_content_analysis():\n\t\treturn False\n",
        }
        for old, new in replacements.items():
            if old not in text:
                raise RuntimeError("FaceFusion 内容分析结构已变化，请手动检查 NOOR 补丁")
            text = text.replace(old, new, 1)
        content_path.write_text(text, encoding="utf-8")


def _validate_facefusion_source(source_dir: Path, timeout: int = 45) -> None:
    if not (source_dir / "facefusion.py").exists() or not (source_dir / "facefusion").is_dir():
        raise RuntimeError("FaceFusion 源码目录不完整")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, "facefusion.py", "headless-run", "--help"],
        cwd=source_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error")[:3000]
        raise RuntimeError(f"FaceFusion CLI 验证失败: {detail}")


def _candidate_clone_urls(settings: Any) -> list[tuple[str, bool]]:
    candidates: list[tuple[str, bool]] = []
    mirror = (getattr(settings, "github_mirror", "") or "").strip().rstrip("/")
    if mirror:
        candidates.append((github_mirror_url(mirror, FACEFUSION_UPSTREAM_REPO), False))
    candidates.append((FACEFUSION_UPSTREAM_REPO, bool(getattr(settings, "http_proxy", ""))))
    candidates.append((FACEFUSION_UPSTREAM_REPO, False))

    deduped: list[tuple[str, bool]] = []
    seen: set[tuple[str, bool]] = set()
    for url, use_proxy in candidates:
        key = (url, use_proxy)
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def upgrade_facefusion_source(settings: Any, log_mgr: Any) -> dict[str, Any]:
    info = get_facefusion_installation_info(settings)
    if info["is_docker"]:
        raise HTTPException(status_code=409, detail=info["upgrade_hint"])

    source_dir = Path(info["source_dir"])
    before_version = get_facefusion_version(source_dir)
    work_root = facefusion_runtime_update_root(settings)
    clone_dir = work_root / "clone"
    backup_dir = work_root / "backup"
    work_root.mkdir(parents=True, exist_ok=True)
    for path in (clone_dir, backup_dir):
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()

    env_base = os.environ.copy()
    last_error = ""
    for clone_url, use_proxy in _candidate_clone_urls(settings):
        env = dict(env_base)
        if use_proxy and getattr(settings, "http_proxy", ""):
            env["HTTP_PROXY"] = settings.http_proxy
            env["HTTPS_PROXY"] = settings.http_proxy
            env["http_proxy"] = settings.http_proxy
            env["https_proxy"] = settings.http_proxy
        else:
            env.pop("HTTP_PROXY", None)
            env.pop("HTTPS_PROXY", None)
            env.pop("http_proxy", None)
            env.pop("https_proxy", None)
        env.setdefault("GIT_CONFIG_GLOBAL", os.devnull)
        log_mgr.add_log("info", f"[FaceFusion] 尝试拉取上游源码：{clone_url}")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(clone_dir)],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        if result.returncode == 0:
            break
        last_error = result.stderr or result.stdout
        log_mgr.add_log("warning", f"[FaceFusion] 拉取失败，尝试下一个源 — {last_error[:160]}")
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
    else:
        raise HTTPException(status_code=500, detail=f"FaceFusion 拉取失败: {last_error}")

    try:
        _validate_facefusion_source(clone_dir)
        upstream_revision = _git_stdout(clone_dir, ["rev-parse", "HEAD"])
        upstream_commit_time = _git_stdout(clone_dir, ["show", "-s", "--format=%cI", "HEAD"])
        shutil.copytree(source_dir, backup_dir, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", ".caches", ".jobs", "temp"))
        _replace_source_from_clone(clone_dir, source_dir)
        _apply_noor_facefusion_patch(source_dir)
        _validate_facefusion_source(source_dir)
        after_version = get_facefusion_version(source_dir)
        write_facefusion_upstream_manifest(
            source_dir,
            revision=upstream_revision,
            version=after_version,
            updated_at=upstream_commit_time,
        )
        log_mgr.add_log("success", f"[FaceFusion] 升级完成 — {before_version or '未知'} -> {after_version or '未知'}")
        return {
            "success": True,
            "before_version": before_version,
            "version": after_version,
            "upstream_revision": upstream_revision,
            "upstream_updated_at": upstream_commit_time,
            "source_dir": str(source_dir),
            "upstream_repo": FACEFUSION_UPSTREAM_REPO,
        }
    except Exception as exc:
        log_mgr.add_log("error", f"[FaceFusion] 升级失败，正在恢复旧源码 — {str(exc)[:180]}")
        if backup_dir.exists():
            for item in source_dir.iterdir():
                if item.name in {".assets", ".caches", ".jobs", "facefusion.ini", "temp"}:
                    continue
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            _copy_source_tree(backup_dir, source_dir)
            _apply_noor_facefusion_patch(source_dir)
        raise
    finally:
        if clone_dir.exists():
            shutil.rmtree(clone_dir)
