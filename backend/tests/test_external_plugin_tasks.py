from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.plugins.external_tasks import (
    EXTERNAL_JOB_TYPE,
    external_task_metadata,
    is_external_task_cancelable,
    is_external_task_job,
)
from app.plugins.runtime import PluginRuntime
from app.tasks.job_phases import get_job_type_phase_defaults, get_terminal_detail


ROOT = Path(__file__).resolve().parents[2]
MDC_BACKEND = ROOT / "plugins" / "mdc-ng-manual" / "backend.py"
spec = importlib.util.spec_from_file_location("test_external_mdc_backend", MDC_BACKEND)
mdc_manual = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mdc_manual)


def test_external_task_metadata_is_self_describing():
    metadata = external_task_metadata(
        "mdc-ng-manual",
        provider_label="MDC-NG",
        external_id=17,
        can_cancel=False,
        data={"source_paths": ["/data/a"]},
    )

    assert metadata["external_provider"] == "mdc-ng-manual"
    assert metadata["external_task"] == {
        "provider_id": "mdc-ng-manual",
        "provider_label": "MDC-NG",
        "external_id": "17",
        "can_cancel": False,
        "data": {"source_paths": ["/data/a"]},
    }


def test_external_task_detection_does_not_capture_internal_jobs():
    internal = {"job_type": "whisper", "result_metadata": {}}
    external = {"job_type": EXTERNAL_JOB_TYPE, "result_metadata": {}}
    contributed = {
        "job_type": "legacy",
        "result_metadata": external_task_metadata("provider", can_cancel=True),
    }

    assert not is_external_task_job(internal)
    assert is_external_task_cancelable(internal)
    assert is_external_task_job(external)
    assert not is_external_task_cancelable(external)
    assert is_external_task_job(contributed)
    assert is_external_task_cancelable(contributed)


def test_external_task_phase_contract_is_restored():
    assert get_job_type_phase_defaults(EXTERNAL_JOB_TYPE) == {
        "phase_key": "output",
        "phase_label": "外部任务",
    }
    assert get_terminal_detail(EXTERNAL_JOB_TYPE, "completed") == "外部任务完成"


@pytest.mark.asyncio
async def test_runtime_syncs_only_enabled_external_task_providers():
    calls: list[tuple[dict, str | None]] = []

    async def sync_external_tasks(config: dict, *, job_id: str | None = None):
        calls.append((config, job_id))
        return {"updated": 2}

    runtime = PluginRuntime()
    runtime._manifests = {
        "provider": {"capabilities": ["external_task_provider"]},
        "ordinary": {"capabilities": ["resource_search"]},
    }
    runtime._handlers = {
        "provider": SimpleNamespace(sync_external_tasks=sync_external_tasks),
        "ordinary": SimpleNamespace(sync_external_tasks=sync_external_tasks),
    }
    runtime.is_enabled = lambda plugin_id: True
    runtime.get_config = lambda plugin_id: {"plugin_id": plugin_id}

    result = await runtime.sync_external_tasks(job_id="job-1")

    assert result == {"checked": 1, "updated": 2, "errors": []}
    assert calls == [({"plugin_id": "provider"}, "job-1")]


def test_mdc_path_mapping_prefers_longest_explicit_prefix():
    config = {
        "local_source_prefix": "/downloads",
        "mdc_source_prefix": "/data/downloads",
        "source_path_mappings": "/downloads/av => /data/special-av",
    }

    assert mdc_manual._map_source_path(config, "/downloads/av/AAA-001") == "/data/special-av/AAA-001"
    assert mdc_manual._map_source_path(config, "/downloads/other/file") == "/data/downloads/other/file"
    assert mdc_manual._map_source_path(config, "/unmapped/file") == "/unmapped/file"


@pytest.mark.asyncio
async def test_plugin_background_tasks_default_to_enabled():
    runtime = PluginRuntime()
    runtime._manifests = {"demo": {"name": "Demo Plugin"}}
    runtime._handlers = {
        "demo": SimpleNamespace(background_tasks=lambda config: [
            {"id": "demo.task", "title": "Demo Task", "status": "idle"},
        ]),
    }
    runtime.is_enabled = lambda plugin_id: True
    runtime.get_config = lambda plugin_id: {}

    result = await runtime.get_background_tasks()

    assert result == [{
        "id": "demo.task",
        "plugin_id": "demo",
        "plugin_name": "Demo Plugin",
        "title": "Demo Task",
        "status": "idle",
        "enabled": True,
    }]
