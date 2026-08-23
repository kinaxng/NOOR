"""Whisper runtime inspection helpers, reconstructed from bytecode."""
from __future__ import annotations

import site
import sys
import sysconfig
from pathlib import Path
from typing import Any, Callable

from app.api.settings_whisper_models import resolve_model_cache_candidates


FASTER_WHISPER_MODELS = [
    ("chickenrice-zh", "chickenrice0721--whisper-large-v2-translate-zh-v0.2-st-ct2"),
    ("large-v3", "Systran--faster-whisper-large-v3"),
]

TRANSFORMERS_MODELS = [
    ("anime_whisper", "litagin/anime-whisper", "~3GB"),
]

ONNX_VAD_MODELS = [
    ("whisper_vad_onnx", "TransWithAI/Whisper-Vad-EncDec-ASMR-onnx", "~250MB"),
]

OPTIONAL_MODULES = [
    ("soundfile", "soundfile", False),
    ("onnxruntime", "onnxruntime", True),
]


def _runtime_paths() -> dict[str, str]:
    purelib = sysconfig.get_paths().get("purelib") or ""
    usersite = site.getusersitepackages() if hasattr(site, "getusersitepackages") else ""
    return {
        "executable": sys.executable,
        "venv_site": str(Path(purelib).resolve()) if purelib else "",
        "user_site": str(Path(usersite).resolve()) if usersite else "",
    }


def _classify_module_source(module: Any) -> dict[str, Any]:
    path = getattr(module, "__file__", None) or ""
    resolved = str(Path(path).resolve()) if path else ""
    runtime = _runtime_paths()
    venv_site = runtime["venv_site"]
    user_site = runtime["user_site"]

    source = "unknown"
    in_noor_env = False
    if resolved and venv_site and resolved.startswith(venv_site):
        source = "noor_venv"
        in_noor_env = True
    elif resolved and user_site and resolved.startswith(user_site):
        source = "user_site"
    elif resolved and ("/dist-packages/" in resolved or "/site-packages/" in resolved):
        source = "system_site"
    elif resolved:
        source = "stdlib_or_local"
        in_noor_env = True

    return {
        "path": resolved or None,
        "source": source,
        "in_noor_env": in_noor_env,
    }


def _module_dependency_payload(module: Any, *, installable: bool) -> dict[str, Any]:
    payload = {
        "installed": True,
        "version": getattr(module, "__version__", None),
        "installable": installable,
    }
    payload.update(_classify_module_source(module))
    return payload


def inspect_whisper_python_dependencies() -> tuple[dict[str, dict[str, Any]], bool, dict[str, Any]]:
    deps: dict[str, dict[str, Any]] = {}
    cuda_available = False
    cuda_info: dict[str, Any] = {}
    runtime_paths = _runtime_paths()

    try:
        import torch

        cuda_available = torch.cuda.is_available()
        cuda_info = {
            "available": cuda_available,
            "device_count": 0,
            "device_name": None,
            "version": torch.version.cuda,
        }
        if cuda_available:
            try:
                cuda_info["device_count"] = torch.cuda.device_count()
                if cuda_info["device_count"] > 0:
                    cuda_info["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                pass
        deps["torch"] = {
            **_module_dependency_payload(torch, installable=True),
            "cuda": cuda_available,
            "cuda_info": cuda_info,
        }
    except ImportError:
        deps["torch"] = {"installed": False, "version": None, "cuda": False, "cuda_info": {}, "installable": True}

    for module_name, dep_key, installable in [
        ("transformers", "transformers", False),
        ("faster_whisper", "faster_whisper", False),
        ("numpy", "numpy", False),
        ("librosa", "librosa", True),
    ]:
        try:
            module = __import__(module_name)
            deps[dep_key] = _module_dependency_payload(module, installable=installable)
        except ImportError:
            deps[dep_key] = {"installed": False, "version": None, "installable": installable}

    for module_name, dep_key, installable in OPTIONAL_MODULES:
        try:
            module = __import__(module_name)
            deps[dep_key] = _module_dependency_payload(module, installable=installable)
            if dep_key == "onnxruntime":
                providers = module.get_available_providers()
                deps[dep_key]["providers"] = providers
                deps[dep_key]["device"] = module.get_device()
                deps[dep_key]["cuda"] = "CUDAExecutionProvider" in providers
        except ImportError:
            deps[dep_key] = {"installed": False, "version": None, "installable": installable}

    deps["_runtime"] = {
        "installed": True,
        "version": None,
        "installable": False,
        "path": runtime_paths["executable"],
        "source": "runtime",
        "in_noor_env": True,
        "venv_site": runtime_paths["venv_site"],
        "user_site": runtime_paths["user_site"],
        "uses_user_site": any(
            value.get("source") == "user_site"
            for key, value in deps.items()
            if not key.startswith("_")
        ),
        "uses_system_site": any(
            value.get("source") == "system_site"
            for key, value in deps.items()
            if not key.startswith("_")
        ),
    }

    return deps, cuda_available, cuda_info


def resolve_whisper_cache_paths(whisper_model_dir: str) -> dict[str, Any]:
    default_hf_cache = str(Path.home() / ".cache" / "huggingface")
    return {
        "whisper_model_dir": whisper_model_dir,
        "default_hf_cache": default_hf_cache,
        "is_default_hf": whisper_model_dir == default_hf_cache,
        "hf_base": Path(whisper_model_dir),
        "default_hf_base": Path(default_hf_cache),
    }


def _transformers_exists(repo: str, base: Path) -> bool:
    return any(path.exists() and any(path.iterdir()) for path in resolve_model_cache_candidates(str(base), repo))


def _faster_exists(model_id: str, base: Path) -> bool:
    return any(
        path.exists() and any(path.iterdir())
        for path in (
            base / "hub" / f"models--{model_id}",
            base / f"models--{model_id}",
            base / "huggingface" / "hub" / f"models--{model_id}",
        )
    )


def inspect_whisper_model_cache(*, whisper_model_dir: str, whisper_models: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cache_paths = resolve_whisper_cache_paths(whisper_model_dir)
    models_info: dict[str, dict[str, Any]] = {}

    for output_key, repo_id, size in TRANSFORMERS_MODELS:
        downloaded = _transformers_exists(repo_id, cache_paths["hf_base"])
        if not downloaded and not cache_paths["is_default_hf"]:
            downloaded = _transformers_exists(repo_id, cache_paths["default_hf_base"])
        models_info[output_key] = {
            "type": "transformers",
            "repo_id": repo_id,
            "downloaded": downloaded,
            "size": size,
        }

    for output_key, repo_id, size in ONNX_VAD_MODELS:
        downloaded = _transformers_exists(repo_id, cache_paths["hf_base"])
        if not downloaded and not cache_paths["is_default_hf"]:
            downloaded = _transformers_exists(repo_id, cache_paths["default_hf_base"])
        models_info[output_key] = {
            "type": "onnx-vad",
            "repo_id": repo_id,
            "downloaded": downloaded,
            "size": size,
        }

    for model_name, model_id in FASTER_WHISPER_MODELS:
        downloaded = _faster_exists(model_id, cache_paths["hf_base"])
        if not downloaded and not cache_paths["is_default_hf"]:
            downloaded = _faster_exists(model_id, cache_paths["default_hf_base"])
        models_info[f"faster_{model_name}"] = {
            "type": "faster-whisper",
            "downloaded": downloaded,
            "size": whisper_models.get(model_name, {}).get("size", "Unknown"),
        }

    return models_info


def log_whisper_dependency_summary(log_mgr: Any, *, deps: dict[str, dict[str, Any]], cuda_available: bool, cuda_info: dict[str, Any]) -> None:
    external_modules = [
        key for key, value in deps.items()
        if value.get("installed") and not value.get("in_noor_env", True)
    ]
    if external_modules:
        log_mgr.add_log("warning", f"[Whisper] 依赖检查完成 — 有模块来自 NOOR 环境外: {', '.join(external_modules)}")
        return
    onnx_without_cuda = any(
        value.get("installed") and value.get("cuda") is False
        for value in deps.values()
    )
    if onnx_without_cuda:
        log_mgr.add_log("warning", "[Whisper] 依赖检查完成 — ONNX Runtime 未启用 CUDAExecutionProvider")
        return
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


def detect_onnxruntime_gpu_requirement(
    torch_variant: str,
    torch_current_cuda: bool,
    import_module_fn: Callable[[str], Any] = __import__,
) -> bool:
    if torch_variant != "gpu":
        return False
    try:
        onnxruntime = import_module_fn("onnxruntime")
        providers = onnxruntime.get_available_providers()
        return "CUDAExecutionProvider" not in providers
    except Exception:
        return True
