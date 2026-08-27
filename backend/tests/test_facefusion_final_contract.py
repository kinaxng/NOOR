from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import facefusion as facefusion_api
from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = ROOT / relative
    assert path.is_file(), f"missing source contract file: {path}"
    return path.read_text(encoding="utf-8")


def test_face_tracker_score_core_config_contract() -> None:
    assert "facefusion_face_tracker_score" in Settings.model_fields
    field = Settings.model_fields["facefusion_face_tracker_score"]
    assert field.default == 0.0


def test_face_tracker_score_settings_and_cli_contract() -> None:
    core = _read("backend/app/core/config.py")
    settings_api = _read("backend/app/api/settings.py")
    updates = _read("backend/app/api/settings_updates.py")
    facefusion_api_source = _read("backend/app/api/facefusion.py")
    runner = _read("backend/app/pipeline/facefusion/runner.py")
    types = _read("frontend/src/api/types.ts")
    settings_ui = _read("frontend/src/views/settings/FaceFusionSettings.vue")
    panel = _read("frontend/src/components/noor/FaceFusionPanel.vue")

    assert "facefusion_face_tracker_score: float = 0.0" in core
    assert "face_tracker_score: float = 0.0" in settings_api
    assert 'update_env_value_fn("FACEFUSION_FACE_TRACKER_SCORE", str(config.face_tracker_score))' in updates
    assert '"--face-tracker-score"' in facefusion_api_source
    assert '"face_tracker_score"' in facefusion_api_source
    assert 'cmd += ["--face-tracker-score"' in runner
    assert "face_tracker_score?: number" in types
    assert "faceTrackerScore" in settings_ui
    assert "face_tracker_score" in panel


def test_facefusion_source_library_panel_contract() -> None:
    panel = _read("frontend/src/components/noor/FaceFusionPanel.vue")

    assert "const selectedLibraryImageIds = ref<string[]>([])" not in panel
    assert "function addSelectedLibraryImages()" not in panel
    assert "function toggleLibraryImage(image: { id: string; name: string; path: string; preview_url: string })" in panel
    assert "点击图片即可加入或移除" in panel
    assert "isSourceSelected(image.path) ? '移除' : '使用'" in panel
    assert "sourceLibraryImages.value = sourceLibraryImages.value.filter(item => item.id !== image.id)" in panel
    assert "uploadedSourceImages.value = uploadedSourceImages.value.filter(item => item.path !== image.path)" in panel


def test_facefusion_source_image_library_api_roundtrip(monkeypatch, tmp_path: Path) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(facefusion_api, "_upload_root", lambda: upload_root)

    app = FastAPI()
    app.include_router(facefusion_api.router)
    client = TestClient(app)

    created = client.post(
        "/api/facefusion/source-images",
        files=[
            ("files", ("face-one.png", b"png-one", "image/png")),
            ("files", ("face-two.jpg", b"jpg-two", "image/jpeg")),
        ],
    )
    assert created.status_code == 200
    files = created.json()["files"]
    assert [item["name"] for item in files] == ["face-one.png", "face-two.jpg"]

    listed = client.get("/api/facefusion/source-images").json()["files"]
    assert {item["id"] for item in listed} == {item["id"] for item in files}

    deleted = client.delete(f"/api/facefusion/source-images/{files[0]['id']}")
    assert deleted.status_code == 200
    remaining = client.get("/api/facefusion/source-images").json()["files"]
    assert [item["id"] for item in remaining] == [files[1]["id"]]
