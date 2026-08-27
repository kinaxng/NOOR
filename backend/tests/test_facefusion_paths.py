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


def test_facefusion_legacy_percentage_weights_are_normalized(monkeypatch, tmp_path):
    settings_path = tmp_path / "facefusion_settings.json"
    settings_path.write_text(
        '{"facefusion_face_swapper_weight": 100, "facefusion_face_enhancer_weight": 75}',
        encoding="utf-8",
    )
    monkeypatch.setattr(facefusion_defaults, "_settings_path", lambda: settings_path)
    payload = facefusion_defaults.facefusion_settings_payload(SimpleNamespace())
    assert payload["facefusion_face_swapper_weight"] == 1.0
    assert payload["facefusion_face_enhancer_weight"] == 0.75


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


def test_configured_model_dir_overrides_nonempty_native_assets(tmp_path):
    source_dir = _make_source(tmp_path / "embedded")
    native_model_dir = source_dir / ".assets" / "models"
    native_model_dir.mkdir(parents=True)
    stale_model = native_model_dir / "stale.onnx"
    stale_model.write_bytes(b"stale")
    configured_model_dir = tmp_path / "models"

    resolved, mode = facefusion_paths.resolve_facefusion_model_dir(
        source_dir,
        str(configured_model_dir),
    )

    assert resolved == str(configured_model_dir)
    assert mode == "configured_override"
    assert stale_model.read_bytes() == b"stale"
    assert not native_model_dir.is_symlink()


def test_facefusion_python_env_exposes_configured_model_dir(monkeypatch, tmp_path):
    source_dir = tmp_path / "source"
    model_dir = tmp_path / "models"

    nvidia_lib = tmp_path / "nvidia" / "cuda_runtime" / "lib"
    nvidia_lib.mkdir(parents=True)
    monkeypatch.setattr(facefusion_paths, "_nvidia_library_dirs", lambda: [nvidia_lib])
    env = facefusion_paths.build_facefusion_python_env(
        source_dir,
        {"PYTHONPATH": "/existing", "LD_LIBRARY_PATH": "/system/cuda"},
        model_dir=str(model_dir),
    )

    assert env["FACEFUSION_MODEL_DIR"] == str(model_dir)
    assert env["PYTHONPATH"].split(":") == [str(source_dir), "/existing"]
    assert env["LD_LIBRARY_PATH"].split(":") == [str(nvidia_lib), "/system/cuda"]
