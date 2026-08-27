from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.api import settings_whisper_runtime as runtime
from app.api.settings_whisper_runtime import (
    detect_install_requirements,
    detect_onnxruntime_gpu_requirement,
    inspect_whisper_model_cache,
    log_whisper_dependency_summary,
)


class DummyLogManager:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []

    def add_log(self, level: str, message: str) -> None:
        self.entries.append((level, message))


def test_detect_install_requirements_respects_torch_variant_and_librosa_presence():
    def fake_import(name: str):
        if name == "librosa":
            return object()
        raise AssertionError(name)

    needs_torch, needs_librosa = detect_install_requirements("gpu", True, fake_import)
    assert needs_torch is False
    assert needs_librosa is False


def test_detect_install_requirements_marks_missing_librosa():
    def fake_import(name: str):
        raise ImportError(name)

    needs_torch, needs_librosa = detect_install_requirements("cpu", True, fake_import)
    assert needs_torch is True
    assert needs_librosa is True


def test_detect_onnxruntime_gpu_requirement_when_cuda_provider_missing():
    fake_ort = SimpleNamespace(get_available_providers=lambda: ["CPUExecutionProvider"])

    def fake_import(name: str):
        if name == "onnxruntime":
            return fake_ort
        raise AssertionError(name)

    assert detect_onnxruntime_gpu_requirement("gpu", True, fake_import) is True


def test_detect_onnxruntime_gpu_requirement_when_cuda_provider_present():
    fake_ort = SimpleNamespace(get_available_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])

    def fake_import(name: str):
        if name == "onnxruntime":
            return fake_ort
        raise AssertionError(name)

    assert detect_onnxruntime_gpu_requirement("gpu", True, fake_import) is False


def test_inspect_whisper_model_cache_checks_custom_and_default_locations(tmp_path: Path, monkeypatch):
    custom_dir = tmp_path / "custom-cache"
    custom_dir.mkdir()
    default_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: default_home)

    anime_dir = default_home / ".cache" / "huggingface" / "hub" / "models--litagin--anime-whisper"
    faster_dir = custom_dir / "hub" / "models--Systran--faster-whisper-large-v3"
    anime_dir.mkdir(parents=True)
    faster_dir.mkdir(parents=True)
    (anime_dir / "model.safetensors").write_bytes(b"model")
    (faster_dir / "model.bin").write_bytes(b"model")

    models = inspect_whisper_model_cache(
        whisper_model_dir=str(custom_dir),
        whisper_models={"large-v3": {"size": "~3GB"}},
    )

    assert models["anime_whisper"]["downloaded"] is True
    assert models["faster_large-v3"]["downloaded"] is True
    assert models["faster_large-v3"]["size"] == "~3GB"


def test_inspect_whisper_model_cache_detects_onnx_vad_without_reazon(tmp_path: Path):
    repo_path = tmp_path / "models--TransWithAI--Whisper-Vad-EncDec-ASMR-onnx"
    repo_path.mkdir(parents=True)
    (repo_path / "model.onnx").write_bytes(b"x")

    payload = runtime.inspect_whisper_model_cache(
        whisper_model_dir=str(tmp_path),
        whisper_models={"whisper-vad-onnx": {"size": "~250MB"}},
    )

    assert payload["whisper_vad_onnx"]["downloaded"] is True
    assert payload["whisper_vad_onnx"]["type"] == "onnx-vad"
    assert "reazon_nemo" not in payload


def test_log_whisper_dependency_summary_logs_missing_installable_packages():
    log_mgr = DummyLogManager()
    log_whisper_dependency_summary(
        log_mgr,
        deps={
            "torch": {"installable": True, "installed": True},
            "librosa": {"installable": True, "installed": False},
        },
        cuda_available=False,
        cuda_info={},
    )

    assert log_mgr.entries == [("warning", "[Whisper] 依赖检查完成 — 需安装: librosa")]


def test_log_whisper_dependency_summary_logs_cuda_success():
    log_mgr = DummyLogManager()
    log_whisper_dependency_summary(
        log_mgr,
        deps={"torch": {"installable": True, "installed": True}},
        cuda_available=True,
        cuda_info={"device_name": "RTX"},
    )

    assert log_mgr.entries == [("success", "[Whisper] 依赖检查完成 — 所有运行时依赖已安装 | CUDA 可用 (RTX)")]


def test_log_whisper_dependency_summary_warns_external_modules():
    log_mgr = DummyLogManager()
    log_whisper_dependency_summary(
        log_mgr,
        deps={
            "torch": {"installable": True, "installed": True, "in_noor_env": False, "source": "user_site"},
            "librosa": {"installable": True, "installed": True, "in_noor_env": True, "source": "noor_venv"},
        },
        cuda_available=True,
        cuda_info={"device_name": "RTX"},
    )

    assert log_mgr.entries == [("warning", "[Whisper] 依赖检查完成 — 有模块来自 NOOR 环境外: torch")]


def test_log_whisper_dependency_summary_warns_onnxruntime_without_cuda_provider():
    log_mgr = DummyLogManager()
    log_whisper_dependency_summary(
        log_mgr,
        deps={
            "torch": {"installable": True, "installed": True, "in_noor_env": True},
            "onnxruntime": {"installable": True, "installed": True, "in_noor_env": True, "cuda": False},
        },
        cuda_available=True,
        cuda_info={"device_name": "RTX"},
    )

    assert log_mgr.entries == [("warning", "[Whisper] 依赖检查完成 — ONNX Runtime 未启用 CUDAExecutionProvider")]
