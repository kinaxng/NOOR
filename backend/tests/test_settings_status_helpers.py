from __future__ import annotations

from app.api import settings_status_helpers
from app.api.settings_status_helpers import build_status_payload


def test_build_status_payload_adds_timestamp_and_extra_fields():
    payload = build_status_payload(
        status="running",
        progress=50,
        message="Working",
        output="chunk",
        model="large-v3",
    )

    assert payload["status"] == "running"
    assert payload["progress"] == 50
    assert payload["message"] == "Working"
    assert payload["output"] == "chunk"
    assert payload["model"] == "large-v3"
    assert "updated_at" in payload


def test_status_files_use_runtime_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_status_helpers, "data_path", lambda *parts: tmp_path.joinpath(*parts))

    payload = build_status_payload(status="running", progress=10, message="Installing")
    status_path = settings_status_helpers.install_status_path()
    settings_status_helpers.write_status_file(status_path, payload)

    assert status_path == tmp_path / "runtime" / "status" / "install_status.json"
    assert settings_status_helpers.read_status_file(status_path)["message"] == "Installing"
