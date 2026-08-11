"""Whisper runtime inspection helpers, reconstructed from bytecode."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

FASTER_WHISPER_MODELS = [
    ("chickenrice-zh", "chickenrice0721--whisper-large-v2-translate-zh-v0.2-st-ct2"),
    ("large-v3", "Systran--faster-whisper-large-v3"),
]
TRANSFORMERS_MODELS = [("anime_whisper", "litagin/anime-whisper", "~3GB")]
OPTIONAL_MODULES = [("soundfile", "soundfile"), ("onnxruntime", "onnxruntime")]


def inspect_whisper_python_dependencies() -> tuple[dict[str, dict[str, Any]], bool, dict[str, Any]]:
    deps: dict[str, dict[str, Any]] = {}
    cuda_available = False
    cuda_info: dict[str, Any] = {}
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        cuda_info = {"available": cuda_available, "device_count": 0, "device_name": None, "version": torch.version.cuda}
        if cuda_available:
            try:
                cuda_info["device_count"] = torch.cuda.device_count()
                if cuda_info["device_count"] > 0:
                    cuda_info["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                pass
        deps["torch"] = {"installed": True, "version": torch.__version__, "cuda": cuda_available, "cuda_info": cuda_info, "installable": True}
    except ImportError:
        deps["torch"] = {"installed": False, "version": None, "cuda": False, "cuda_info": {}, "installable": True}
    for module_name, dep_key, installable in (("transformers", "transformers", False), ("faster_whisper", "faster_whisper", False), ("numpy", "numpy", False), ("librosa", "librosa", True)):
        try:
            module = __import__(module_name)
            deps[dep_key] = {"installed": True, "version": getattr(module, "__version__", None), "installable": installable}
        except ImportError:
            deps[dep_key] = {"installed": False, "version": None, "installable": installable}
    for module_name, dep_key in OPTIONAL_MODULES:
        try:
            module = __import__(module_name)
            deps[dep_key] = {"installed": True, "version": getattr(module, "__version__", None), "installable": False}
        except ImportError:
            deps[dep_key] = {"installed": False, "version": None, "installable": False}
    return deps, cuda_available, cuda_info


def resolve_whisper_cache_paths(whisper_model_dir: str) -> dict[str, Any]:
    default_hf_cache = str(Path.home() / ".cache" / "huggingface")
    return {"whisper_model_dir": whisper_model_dir, "default_hf_cache": default_hf_cache, "is_default_hf": whisper_model_dir == default_hf_cache, "hf_base": Path(whisper_model_dir), "default_hf_base": Path(default_hf_cache)}


def _transformers_exists(repo: str, base: Path, default_hf_cache: str) -> bool:
    if (base / f"models--{repo.replace('/', '--')}").exists():
        return True
    cache = base / ("hub" if str(base) == str(default_hf_cache) else "huggingface/hub")
    return (cache / f"models--{repo.replace('/', '--')}").exists()


def _faster_exists(model_id: str, base: Path) -> bool:
    return (base / "hub" / f"models--{model_id}").exists() or (base / f"models--{model_id}").exists()


def inspect_whisper_model_cache(*, whisper_model_dir: str, whisper_models: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cache_paths = resolve_whisper_cache_paths(whisper_model_dir)
    models_info: dict[str, dict[str, Any]] = {}
    for output_key, repo_id, size in TRANSFORMERS_MODELS:
        downloaded = _transformers_exists(repo_id, cache_paths["hf_base"], cache_paths["default_hf_cache"])
        if not downloaded and not cache_paths["is_default_hf"]:
            downloaded = _transformers_exists(repo_id, cache_paths["default_hf_base"], cache_paths["default_hf_cache"])
        models_info[output_key] = {"type": "transformers", "repo_id": repo_id, "downloaded": downloaded, "size": size}
    for model_name, model_id in FASTER_WHISPER_MODELS:
        downloaded = _faster_exists(model_id, cache_paths["hf_base"])
        if not downloaded and not cache_paths["is_default_hf"]:
            downloaded = _faster_exists(model_id, cache_paths["default_hf_base"])
        models_info[f"faster_{model_name}"] = {"type": "faster-whisper", "downloaded": downloaded, "size": whisper_models.get(model_name, {}).get("size", "Unknown")}
    vad_repo = "TransWithAI/Whisper-Vad-EncDec-ASMR-onnx"
    downloaded = _transformers_exists(vad_repo, cache_paths["hf_base"], cache_paths["default_hf_cache"])
    if not downloaded and not cache_paths["is_default_hf"]:
        downloaded = _transformers_exists(vad_repo, cache_paths["default_hf_base"], cache_paths["default_hf_cache"])
    models_info["whisper-vad-onnx"] = {"type": "onnx", "repo_id": vad_repo, "downloaded": downloaded, "size": whisper_models.get("whisper-vad-onnx", {}).get("size", "Unknown")}
    return models_info


def log_whisper_dependency_summary(log_mgr: Any, *, deps: dict[str, dict[str, Any]], cuda_available: bool, cuda_info: dict[str, Any]) -> None:
    missing_installable = [key for key, value in deps.items() if value.get("installable") and not value.get("installed")]
    if missing_installable:
        log_mgr.add_log("warning", f"[Whisper] 依赖检查完成 — 需安装: {', '.join(missing_installable)}")
        return
    all_installable_ok = all(value.get("installed") for value in deps.values() if value.get("installable"))
    if all_installable_ok:
        suffix = f" | CUDA 可用 ({cuda_info.get('device_name', 'GPU')})" if cuda_available else " | CUDA 不可用"
        log_mgr.add_log("success", "[Whisper] 依赖检查完成 — 所有运行时依赖已安装" + suffix)
        return
    log_mgr.add_log("success", "[Whisper] 依赖检查完成 — Docker 预装依赖已就绪")


def detect_install_requirements(torch_variant: str, torch_current_cuda: bool, import_module_fn: Callable[[str], Any] = __import__) -> tuple[bool, bool]:
    needs_torch = (torch_variant == "gpu") != torch_current_cuda
    try:
        import_module_fn("librosa")
        needs_librosa = False
    except ImportError:
        needs_librosa = True
    return needs_torch, needs_librosa
