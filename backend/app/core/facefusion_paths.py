from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.core.config import PROJECT_ROOT
from app.core.runtime_paths import ensure_directory


LEGACY_EXTERNAL_FACEFUSION_DIR = "/volume1/facefusion/facefusion"


@dataclass(frozen=True)
class FaceFusionSource:
    source_dir: Path
    facefusion_py: Path
    mode: str


def _is_facefusion_source(path: Path) -> bool:
    return (path / "facefusion.py").is_file() and (path / "facefusion").is_dir()


def embedded_facefusion_source_candidates() -> list[Path]:
    return [
        PROJECT_ROOT / "backend" / "app" / "pipeline" / "facefusion" / "source",
        PROJECT_ROOT / "app" / "pipeline" / "facefusion" / "source",
        PROJECT_ROOT / "facefusion",
    ]


def resolve_embedded_facefusion_source() -> FaceFusionSource | None:
    for candidate in embedded_facefusion_source_candidates():
        if _is_facefusion_source(candidate):
            return FaceFusionSource(candidate, candidate / "facefusion.py", "embedded")
    return None


def normalize_configured_facefusion_dir(value: str | None) -> str:
    configured = (value or "").strip()
    # The historical host install path was used before FaceFusion was embedded
    # into NOOR.  Once the embedded source exists, treat that legacy value as
    # "use the built-in source" so old settings do not keep routing jobs to the
    # host project by accident.
    if configured == LEGACY_EXTERNAL_FACEFUSION_DIR and resolve_embedded_facefusion_source() is not None:
        return ""
    return configured


def resolve_facefusion_source(configured_dir: str | None = None) -> FaceFusionSource:
    configured = normalize_configured_facefusion_dir(configured_dir)
    if configured:
        source_dir = Path(configured).expanduser()
        if not _is_facefusion_source(source_dir):
            raise RuntimeError(f"FaceFusion CLI 不存在或目录不完整: {source_dir}")
        return FaceFusionSource(source_dir, source_dir / "facefusion.py", "external")

    embedded = resolve_embedded_facefusion_source()
    if embedded:
        return embedded
    raise RuntimeError("NOOR 内置 FaceFusion 源码不存在，请检查 backend/app/pipeline/facefusion/source")


def resolve_facefusion_python(source_dir: Path, configured_python: str) -> str:
    configured = (configured_python or "").strip()
    if configured:
        return configured
    for rel in (".venv/bin/python", "venv/bin/python"):
        candidate = source_dir / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_facefusion_python_env(
    source_dir: Path,
    base_env: dict[str, str] | None = None,
    model_dir: str | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    existing = env.get("PYTHONPATH", "")
    entries = [str(source_dir)]
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    nvidia_library_dirs = _nvidia_library_dirs()
    existing_libraries = env.get("LD_LIBRARY_PATH", "")
    library_entries = [str(path) for path in nvidia_library_dirs]
    if existing_libraries:
        library_entries.append(existing_libraries)
    if library_entries:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(library_entries)
    if model_dir:
        env["FACEFUSION_MODEL_DIR"] = str(Path(model_dir).expanduser())
    return env


def _nvidia_library_dirs() -> list[Path]:
    """Expose pip-installed CUDA runtime libraries to ONNX Runtime children."""
    directories: list[Path] = []
    for entry in sys.path:
        root = Path(entry) / "nvidia"
        if not root.is_dir():
            continue
        for package_dir in root.iterdir():
            library_dir = package_dir / "lib"
            if library_dir.is_dir() and library_dir not in directories:
                directories.append(library_dir)
    return directories


def resolve_facefusion_model_dir(source_dir: Path | str, configured_model_dir: str | None) -> tuple[str, str]:
    native_model_dir = Path(source_dir) / ".assets" / "models"
    configured = (configured_model_dir or "").strip()
    if not configured:
        return str(native_model_dir), "native_assets"

    configured_path = Path(ensure_directory(configured))
    if native_model_dir.exists() or native_model_dir.is_symlink():
        try:
            if native_model_dir.resolve() == configured_path.resolve():
                return str(configured_path), "configured_symlink"
        except FileNotFoundError:
            pass

    if native_model_dir.is_symlink():
        native_model_dir.unlink()
        native_model_dir.symlink_to(configured_path, target_is_directory=True)
        return str(configured_path), "configured_symlink"

    if not native_model_dir.exists():
        native_model_dir.parent.mkdir(parents=True, exist_ok=True)
        native_model_dir.symlink_to(configured_path, target_is_directory=True)
        return str(configured_path), "configured_symlink"

    if native_model_dir.is_dir() and not any(native_model_dir.iterdir()):
        native_model_dir.rmdir()
        native_model_dir.symlink_to(configured_path, target_is_directory=True)
        return str(configured_path), "configured_symlink"

    # Embedded FaceFusion resolves model assets through FACEFUSION_MODEL_DIR.
    # Keep any legacy files untouched, but never let them override NOOR's
    # configured model storage.
    return str(configured_path), "configured_override"


def inspect_facefusion_model_dir(source_dir: Path | str, configured_model_dir: str | None) -> tuple[str, str]:
    native_model_dir = Path(source_dir) / ".assets" / "models"
    configured = (configured_model_dir or "").strip()
    if not configured:
        return str(native_model_dir), "native_assets"

    configured_path = Path(configured)
    if native_model_dir.is_symlink():
        try:
            if native_model_dir.resolve() == configured_path.resolve():
                return str(configured_path), "configured_symlink"
        except FileNotFoundError:
            return str(configured_path), "configured_missing"
        return str(configured_path), "configured_symlink_mismatch"

    if native_model_dir.exists():
        if native_model_dir.is_dir() and not any(native_model_dir.iterdir()):
            return str(configured_path), "configured_pending_symlink"
        return str(configured_path), "configured_override"

    return str(configured_path), "configured_pending_symlink"
