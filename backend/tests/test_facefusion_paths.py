from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.core import facefusion_paths
from app.core import facefusion_defaults
from app.core.facefusion_defaults import facefusion_settings_payload


def _make_source(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "facefusion.py").write_text("", encoding="utf-8")
    (path / "facefusion").mkdir()
    return path


def test_facefusion_default_dir_uses_embedded_source():
    payload = facefusion_settings_payload(SimpleNamespace())

    assert payload["facefusion_dir"] == ""


def test_facefusion_legacy_saved_dir_is_normalized(monkeypatch, tmp_path):
    settings_path = tmp_path / "facefusion_settings.json"
    settings_path.write_text(
        '{"facefusion_dir": "/volume1/facefusion/facefusion"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(facefusion_defaults, "_settings_path", lambda: settings_path)

    payload = facefusion_settings_payload(SimpleNamespace())

    assert payload["facefusion_dir"] == ""


def test_legacy_external_path_normalizes_to_embedded_when_available(monkeypatch, tmp_path):
    source_dir = _make_source(tmp_path / "embedded")
    monkeypatch.setattr(
        facefusion_paths,
        "resolve_embedded_facefusion_source",
        lambda: facefusion_paths.FaceFusionSource(source_dir, source_dir / "facefusion.py", "embedded"),
    )

    resolved = facefusion_paths.resolve_facefusion_source(facefusion_paths.LEGACY_EXTERNAL_FACEFUSION_DIR)

    assert resolved.mode == "embedded"
    assert resolved.source_dir == source_dir


def test_non_legacy_external_facefusion_dir_still_overrides(tmp_path):
    source_dir = _make_source(tmp_path / "external")

    resolved = facefusion_paths.resolve_facefusion_source(str(source_dir))

    assert resolved.mode == "external"
    assert resolved.source_dir == source_dir
