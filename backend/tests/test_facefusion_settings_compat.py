from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings
from app.core import config as core_config


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(settings.router)
    return app


def test_facefusion_runtime_settings_compat_route(monkeypatch, tmp_path):
    monkeypatch.setenv("NOOR_DATA_DIR", str(tmp_path))
    core_config.clear_settings_cache()
    try:
        response = TestClient(_app()).put("/api/settings/facefusion", json={
            "dir": "/tmp/facefusion",
            "python_path": "/tmp/facefusion/.venv/bin/python",
        })
        assert response.status_code == 200
        assert response.json()["success"] is True

        settings_response = TestClient(_app()).get("/api/settings")
        assert settings_response.status_code == 200
        assert settings_response.json()["facefusion"]["dir"] == "/tmp/facefusion"
    finally:
        core_config.clear_settings_cache()


def test_facefusion_defaults_settings_compat_route(monkeypatch, tmp_path):
    monkeypatch.setenv("NOOR_DATA_DIR", str(tmp_path))
    core_config.clear_settings_cache()
    try:
        response = TestClient(_app()).put("/api/settings/facefusion/defaults", json={
            "execution_provider": "tensorrt",
            "processors": "face_swapper face_enhancer",
            "badge_always_visible": True,
        })
        assert response.status_code == 200

        client = TestClient(_app())
        prefs = client.get("/api/settings/facefusion/preferences").json()
        assert prefs["badge_always_visible"] is True
        payload = client.get("/api/settings").json()
        assert payload["facefusion_defaults"]["execution_provider"] == "tensorrt"
        assert payload["facefusion_defaults"]["processors"] == "face_swapper face_enhancer"
    finally:
        core_config.clear_settings_cache()
