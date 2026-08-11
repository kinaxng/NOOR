from __future__ import annotations

from pathlib import Path

from app.api.settings_facefusion_upgrade import (
    _apply_noor_facefusion_patch,
    _replace_source_from_clone,
    get_facefusion_version,
)


def test_facefusion_upgrade_patch_routes_tensorrt_cache_to_env(tmp_path):
    source_dir = tmp_path / "source"
    execution_path = source_dir / "facefusion" / "execution.py"
    execution_path.parent.mkdir(parents=True)
    execution_path.write_text(
        "import os\nimport onnxruntime\n\n"
        "def resolve_cache_path() -> str:\n"
        "\treturn os.path.join('.caches', onnxruntime.get_version_string())\n",
        encoding="utf-8",
    )

    _apply_noor_facefusion_patch(source_dir)

    patched = execution_path.read_text(encoding="utf-8")
    assert "ORT_TENSORRT_CACHE_PATH" in patched
    assert (source_dir / ".gitignore").read_text(encoding="utf-8").splitlines() == [
        "__pycache__",
        ".assets",
        ".claude",
        ".caches",
        ".idea",
        ".jobs",
        ".vscode",
        "temp",
    ]


def test_facefusion_upgrade_replace_preserves_runtime_model_link(tmp_path):
    clone_dir = tmp_path / "clone"
    source_dir = tmp_path / "source"
    model_dir = tmp_path / "models"
    clone_pkg = clone_dir / "facefusion"
    source_pkg = source_dir / "facefusion"
    clone_pkg.mkdir(parents=True)
    source_pkg.mkdir(parents=True)
    model_dir.mkdir()
    (clone_dir / "facefusion.py").write_text("print('new')", encoding="utf-8")
    (clone_dir / "facefusion.ini").write_text("upstream", encoding="utf-8")
    (clone_pkg / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("old", encoding="utf-8")
    (source_dir / "facefusion.ini").write_text("noor", encoding="utf-8")
    (source_dir / ".assets").mkdir()
    (source_dir / ".assets" / "models").symlink_to(model_dir, target_is_directory=True)

    _replace_source_from_clone(clone_dir, source_dir)

    assert not (source_dir / "old.py").exists()
    assert (source_dir / "facefusion.py").read_text(encoding="utf-8") == "print('new')"
    assert (source_dir / "facefusion.ini").read_text(encoding="utf-8") == "noor"
    assert (source_dir / ".assets" / "models").is_symlink()
    assert (source_dir / ".assets" / "models").resolve() == model_dir.resolve()


def test_get_facefusion_version_reads_metadata(tmp_path):
    metadata_path = tmp_path / "facefusion" / "metadata.py"
    metadata_path.parent.mkdir()
    metadata_path.write_text("METADATA = {'version': '9.9.9'}\n", encoding="utf-8")

    assert get_facefusion_version(Path(tmp_path)) == "9.9.9"
