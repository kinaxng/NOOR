from __future__ import annotations

from pathlib import Path

from app.api.settings_facefusion_upgrade import (
    _apply_noor_facefusion_patch,
    _replace_source_from_clone,
    get_facefusion_upstream_manifest,
    get_facefusion_runtime_info,
    get_facefusion_version,
    write_facefusion_upstream_manifest,
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


def test_facefusion_upgrade_patch_skips_content_analysis(tmp_path):
    source_dir = tmp_path / "source"
    package_dir = source_dir / "facefusion"
    package_dir.mkdir(parents=True)
    (package_dir / "execution.py").write_text(
        "import os\nimport onnxruntime\n\n"
        "def resolve_cache_path() -> str:\n"
        "\treturn os.path.join('.caches', onnxruntime.get_version_string())\n",
        encoding="utf-8",
    )
    (package_dir / "content_analyser.py").write_text(
        "from functools import lru_cache\n"
        "from facefusion.types import Fps, VisionFrame\n"
        "from facefusion.vision import detect_video_fps, read_image\n\n"
        "STREAM_COUNTER = 0\n\n\n"
        "def pre_check() -> bool:\n"
        "\treturn conditional_download_hashes({}) and conditional_download_sources({})\n\n\n"
        "def analyse_stream(vision_frame : VisionFrame, video_fps : Fps) -> bool:\n"
        "\tglobal STREAM_COUNTER\n\n"
        "\tSTREAM_COUNTER = STREAM_COUNTER + 1\n"
        "\tif STREAM_COUNTER % int(video_fps) == 0:\n"
        "\t\treturn analyse_frame(vision_frame)\n"
        "\treturn False\n\n\n"
        "def analyse_frame(vision_frame : VisionFrame) -> bool:\n"
        "\treturn detect_nsfw(vision_frame)\n\n\n"
        "@lru_cache()\n"
        "def analyse_image(image_path : str) -> bool:\n"
        "\tvision_frame = read_image(image_path)\n"
        "\treturn analyse_frame(vision_frame)\n\n\n"
        "@lru_cache()\n"
        "def analyse_video(video_path : str, trim_frame_start : int, trim_frame_end : int) -> bool:\n"
        "\tvideo_fps = detect_video_fps(video_path)\n"
        "\treturn bool(rate > 10.0)\n",
        encoding="utf-8",
    )

    _apply_noor_facefusion_patch(source_dir)

    patched = (package_dir / "content_analyser.py").read_text(encoding="utf-8")
    assert "NOOR_FACEFUSION_SKIP_CONTENT_ANALYSIS" in patched
    assert "if skip_content_analysis():\n\t\treturn True" in patched
    assert patched.count("if skip_content_analysis():\n\t\treturn False") >= 2


def test_facefusion_upgrade_patch_preserves_existing_content_patch(tmp_path):
    source_dir = tmp_path / "source"
    package_dir = source_dir / "facefusion"
    package_dir.mkdir(parents=True)
    (package_dir / "execution.py").write_text(
        "import os\nimport onnxruntime\n\n"
        "def resolve_cache_path() -> str:\n"
        "\treturn os.getenv('ORT_TENSORRT_CACHE_PATH') or os.path.join('.caches', onnxruntime.get_version_string())\n",
        encoding="utf-8",
    )
    original = (
        "from functools import lru_cache\n"
        "import os\n"
        "from facefusion.vision import detect_video_fps, read_image\n\n"
        "STREAM_COUNTER = 0\n\n\n"
        "def skip_content_analysis() -> bool:\n"
        "\treturn os.getenv('NOOR_FACEFUSION_SKIP_CONTENT_ANALYSIS') == '1'\n\n\n"
        "def pre_check() -> bool:\n"
        "\tif skip_content_analysis():\n"
        "\t\treturn True\n"
        "\treturn conditional_download_hashes({}) and conditional_download_sources({})\n\n\n"
        "def analyse_frame(vision_frame) -> bool:\n"
        "\tif skip_content_analysis():\n"
        "\t\treturn False\n"
        "\treturn detect_nsfw(vision_frame)\n"
    )
    (package_dir / "content_analyser.py").write_text(original, encoding="utf-8")

    _apply_noor_facefusion_patch(source_dir)

    assert (package_dir / "content_analyser.py").read_text(encoding="utf-8") == original


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


def test_get_facefusion_runtime_info_includes_core_versions():
    info = get_facefusion_runtime_info()

    assert info["versions"]["python"]
    assert info["versions"]["onnxruntime"]
    assert info["versions"]["numpy"]
    assert isinstance(info["execution_providers"], list)
    assert info["python_executable"]


def test_facefusion_upstream_manifest_round_trip(tmp_path):
    write_facefusion_upstream_manifest(
        tmp_path,
        revision="1234567890abcdef",
        version="4.0.0",
        updated_at="2026-06-30T12:00:00+08:00",
    )

    manifest = get_facefusion_upstream_manifest(tmp_path)
    assert manifest["repo"] == "https://github.com/facefusion/facefusion.git"
    assert manifest["revision"] == "1234567890abcdef"
    assert manifest["short_revision"] == "1234567890ab"
    assert manifest["version"] == "4.0.0"
    assert manifest["updated_at"] == "2026-06-30T12:00:00+08:00"
