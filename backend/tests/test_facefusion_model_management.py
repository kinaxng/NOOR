from __future__ import annotations

import zlib
from pathlib import Path

from app.api import settings
from app.api import settings_status_helpers


def test_facefusion_model_inspection_validates_crc32(monkeypatch, tmp_path: Path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_path = model_dir / "sample.onnx"
    model_path.write_bytes(b"facefusion-model")
    checksum = format(zlib.crc32(model_path.read_bytes()), "08x")
    model_path.with_suffix(".hash").write_text(checksum, encoding="utf-8")

    monkeypatch.setattr(
        settings,
        "_facefusion_model_context",
        lambda: ("python", "/facefusion", {}, str(model_dir), "configured_symlink"),
    )

    result = settings._facefusion_model_status_payload()

    assert result["model_dir"] == str(model_dir)
    assert result["link_mode"] == "configured_symlink"
    assert result["onnx_count"] == 1
    assert result["valid_count"] == 1
    assert result["invalid_count"] == 0
    assert result["missing_hash_count"] == 0


def test_facefusion_model_inspection_reports_invalid_and_missing_hash(monkeypatch, tmp_path: Path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    invalid_path = model_dir / "invalid.onnx"
    invalid_path.write_bytes(b"invalid")
    invalid_path.with_suffix(".hash").write_text("00000000", encoding="utf-8")
    (model_dir / "missing.onnx").write_bytes(b"missing")

    monkeypatch.setattr(
        settings,
        "_facefusion_model_context",
        lambda: ("python", "/facefusion", {}, str(model_dir), "native_assets"),
    )

    result = settings._facefusion_model_status_payload()

    assert result["valid_count"] == 0
    assert result["invalid_count"] == 1
    assert result["missing_hash_count"] == 1
    assert result["invalid"][0]["name"] == "invalid.onnx"
    assert result["missing_hash"] == ["missing.onnx"]


def test_facefusion_model_download_status_is_persistent(monkeypatch, tmp_path: Path):
    status_path = tmp_path / "runtime" / "facefusion-model.json"
    monkeypatch.setattr(settings_status_helpers, "facefusion_model_status_path", lambda: status_path)

    settings_status_helpers.write_status_file(
        status_path,
        settings_status_helpers.build_status_payload(
            status="running",
            progress=42,
            message="downloading",
            scope="lite",
            output="line",
        ),
    )

    assert settings_status_helpers.read_facefusion_model_status_response() == {
        "status": "running",
        "progress": 42,
        "message": "downloading",
        "scope": "lite",
        "output": "line",
    }
