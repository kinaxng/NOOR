from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import plugins, runtime_cleanup


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_cleanup.router)
    app.include_router(plugins.router)
    return app


def test_runtime_cleanup_status_endpoint(monkeypatch):
    expected = {
        'status': 'idle',
        'summary': '可清理 0 B · 0 项',
        'reclaimable_bytes': 0,
        'candidate_count': 0,
        'min_age_hours': 12,
        'last_cleanup': {},
        'top_candidates': [],
    }
    monkeypatch.setattr('app.api.runtime_cleanup.runtime_cleanup_status', lambda min_age_hours: {**expected, 'min_age_hours': min_age_hours})
    response = TestClient(_app()).get('/api/runtime-cleanup/status?min_age_hours=12')
    assert response.status_code == 200
    assert response.json()['min_age_hours'] == 12


def test_background_tasks_exposes_core_cleanup(monkeypatch):
    async def empty_background_tasks():
        return []

    monkeypatch.setattr(plugins.runtime, 'get_background_tasks', empty_background_tasks)
    monkeypatch.setattr(plugins, 'runtime_cleanup_status', lambda min_age_hours: {
        'summary': '可清理 1 KB · 1 项',
        'candidate_count': 1,
        'reclaimable_bytes': 1024,
        'last_cleanup': {'status': 'completed', 'started_at': 's', 'finished_at': 'f', 'message': '完成'},
    })
    response = TestClient(_app()).get('/api/plugins/background/tasks')
    assert response.status_code == 200
    item = response.json()['items'][0]
    assert item['id'] == 'noor-core.runtime-cleanup'
    assert item['status'] == 'idle'
    assert item['metrics']['candidate_count'] == 1


def test_core_cleanup_action_forwards_age(monkeypatch):
    calls = []

    def fake_run(*, min_age_hours):
        calls.append(min_age_hours)
        return {'ok': True, 'min_age_hours': min_age_hours}

    monkeypatch.setattr(plugins, 'run_runtime_cleanup', fake_run)
    response = TestClient(_app()).post(
        '/api/plugins/noor-core/actions/runtime-cleanup',
        json={'payload': {'min_age_hours': 18}},
    )
    assert response.status_code == 200
    assert calls == [18]
