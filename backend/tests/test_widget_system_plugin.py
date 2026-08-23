from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_widget_system():
    spec = importlib.util.spec_from_file_location(
        "widget_system_backend",
        ROOT / "plugins" / "widget-system" / "backend.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_metrics_payload_uses_short_lived_cache(monkeypatch):
    module = _load_widget_system()
    module._metrics_cache = {"at": 0.0, "value": None}
    cpu_calls = 0
    gpu_calls = 0

    def fake_cpu(*args, **kwargs):
        nonlocal cpu_calls
        cpu_calls += 1
        return 12.0

    def fake_gpu():
        nonlocal gpu_calls
        gpu_calls += 1
        return {
            "available": False,
            "gpu_util": 0,
            "mem_used": 0,
            "mem_total": 0,
            "temp": 0,
            "power": 0,
        }

    monkeypatch.setattr(module.psutil, "cpu_percent", fake_cpu)
    monkeypatch.setattr(module, "_read_gpu_info", fake_gpu)

    first = module.build_metrics_payload()
