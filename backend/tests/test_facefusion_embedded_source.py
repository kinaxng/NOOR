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
