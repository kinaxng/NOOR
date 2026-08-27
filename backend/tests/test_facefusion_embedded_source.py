from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_embedded_facefusion_uses_noor_tensorrt_cache(monkeypatch, tmp_path):
    source_dir = Path(__file__).resolve().parents[1] / "app/pipeline/facefusion/source"
    monkeypatch.syspath_prepend(source_dir)
    monkeypatch.setenv("ORT_TENSORRT_CACHE_PATH", str(tmp_path / "trt-cache"))
    sys.modules.pop("facefusion.execution", None)

    execution = importlib.import_module("facefusion.execution")

    assert execution.resolve_cache_path() == str(tmp_path / "trt-cache")


def test_embedded_facefusion_uses_noor_model_dir(monkeypatch, tmp_path):
    source_dir = Path(__file__).resolve().parents[1] / "app/pipeline/facefusion/source"
    model_dir = tmp_path / "models"
    monkeypatch.syspath_prepend(str(source_dir))
    monkeypatch.setenv("FACEFUSION_MODEL_DIR", str(model_dir))
    sys.modules.pop("facefusion.filesystem", None)

    filesystem = importlib.import_module("facefusion.filesystem")

    assert filesystem.resolve_relative_path("../.assets/models/inswapper_128.onnx") == str(
        model_dir / "inswapper_128.onnx"
    )
    assert filesystem.resolve_relative_path("../.assets/examples/source.jpg") == str(
        source_dir / ".assets/examples/source.jpg"
    )
