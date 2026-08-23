from __future__ import annotations

import pytest

from app.pipeline.facefusion.preview import (
    PREVIEW_MODES,
    PREVIEW_RESOLUTIONS,
    _is_cuda_oom_error,
    _preview_cache_dir,
    _stable_preview_key,
    generate_facefusion_preview,
)


def test_preview_key_is_stable_and_sensitive_to_payload():
    payload = {"input_path": "/tmp/video.mp4", "settings": {"execution_provider": "cuda"}, "frame_number": 12}

    first = _stable_preview_key(payload)
    second = _stable_preview_key(payload)
    changed = _stable_preview_key({**payload, "frame_number": 13})

    assert first == second
    assert first != changed
    assert len(first) == 32


def test_preview_cache_dir_uses_configured_runtime_cache(tmp_path):
    assert _preview_cache_dir(str(tmp_path)) == tmp_path / "previews"


def test_cuda_oom_detection_matches_common_worker_outputs():
    assert _is_cuda_oom_error("CUDA out of memory")
    assert _is_cuda_oom_error("RuntimeError: CUDA failure 2")
    assert not _is_cuda_oom_error("codec error")


def test_preview_rejects_unknown_modes_and_resolutions():
    with pytest.raises(RuntimeError, match="预览模式"):
        generate_facefusion_preview(
            input_path="/tmp/video.mp4",
            job_settings={},
            frame_number=0,
            preview_mode="unknown",
            preview_resolution="768x768",
        )

    with pytest.raises(RuntimeError, match="预览分辨率"):
        generate_facefusion_preview(
            input_path="/tmp/video.mp4",
            job_settings={},
            frame_number=0,
            preview_mode="default",
            preview_resolution="999x999",
        )

    assert "default" in PREVIEW_MODES
    assert "768x768" in PREVIEW_RESOLUTIONS
