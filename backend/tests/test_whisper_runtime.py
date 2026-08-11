import subprocess

import pytest

from app.pipeline.whisper.runtime import raise_if_cancelled, run_cancellable_subprocess
from app.pipeline.whisper.types import WhisperCancellationRequested


def test_raise_if_cancelled_accepts_missing_callback():
    raise_if_cancelled(None)


def test_raise_if_cancelled_raises_pipeline_exception():
    with pytest.raises(WhisperCancellationRequested):
        raise_if_cancelled(lambda: True)


def test_cancellable_subprocess_returns_completed_process():
    result = run_cancellable_subprocess(
        ["/bin/sh", "-c", "printf ready"],
        cancel_callback=lambda: False,
    )
    assert isinstance(result, subprocess.CompletedProcess)
    assert result.stdout == "ready"
