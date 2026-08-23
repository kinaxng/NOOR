from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.pipeline.lada.runner import LADA_PROGRESS_PHASE_ORDER, run_lada_restoration


@pytest.mark.asyncio
async def test_lada_runner_cancel_terminates_process_and_cleans_temp(tmp_path: Path):
    fake_cli = tmp_path / "fake_lada.py"
    pid_file = tmp_path / "fake.pid"
    fake_cli.write_text(
        """
import argparse
import os
import time

parser = argparse.ArgumentParser()
parser.add_argument('--input')
parser.add_argument('--output')
parser.add_argument('--device')
parser.add_argument('--mosaic-detection-model')
parser.add_argument('--mosaic-restoration-model')
parser.add_argument('--encoding-preset')
parser.add_argument('--max-clip-length')
parser.add_argument('--temporary-directory')
parser.add_argument('--fp16', action='store_true')
parser.add_argument('--no-fp16', action='store_true')
parser.add_argument('--detect-face-mosaics', action='store_true')
args = parser.parse_args()
open(r'%s', 'w').write(str(os.getpid()))
open(args.output + '.tmp.mp4', 'wb').write(b'x' * 1024)
print('Progress: 1%%', flush=True)
time.sleep(60)
""" % str(pid_file),
        encoding="utf-8",
    )

    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"x" * 2048)

    progress_queue: asyncio.Queue = asyncio.Queue()
    cancel_event = asyncio.Event()

    task = asyncio.create_task(
        run_lada_restoration(
            job_id="fake-job",
            input_path=str(input_path),
            output_path=str(output_path),
            job_settings={
                "lada_cli_path": f"python3 {fake_cli}",
                "device": "cpu",
                "fp16": False,
            },
            progress_queue=progress_queue,
            cancel_event=cancel_event,
        )
    )

    await asyncio.sleep(1.0)
    cancel_event.set()
    success = await asyncio.wait_for(task, timeout=25)

    assert success is False
    assert not output_path.exists()
    assert not Path(str(output_path) + ".tmp.mp4").exists()

    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

    events = []
    while not progress_queue.empty():
        events.append(await progress_queue.get())
    assert any("Cancellation requested" in e.get("line", "") for e in events)
    assert any("Process cancelled" in e.get("line", "") for e in events)


@pytest.mark.asyncio
async def test_lada_runner_emits_structured_phase_progress_on_success(tmp_path: Path):
    fake_cli = tmp_path / "fake_lada_success.py"
    fake_cli.write_text(
        """
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input')
parser.add_argument('--output')
parser.add_argument('--device')
parser.add_argument('--mosaic-detection-model')
parser.add_argument('--mosaic-restoration-model')
parser.add_argument('--encoding-preset')
parser.add_argument('--max-clip-length')
parser.add_argument('--temporary-directory')
parser.add_argument('--fp16', action='store_true')
parser.add_argument('--no-fp16', action='store_true')
parser.add_argument('--detect-face-mosaics', action='store_true')
args = parser.parse_args()
print('Detect mosaic regions...', flush=True)
print('Processing video... 95%', flush=True)
Path(args.output + '.tmp.mp4').write_bytes(b'x' * 4096)
time.sleep(2.3)
print('Progress: 100%', flush=True)
Path(args.output).write_bytes(b'done')
""",
        encoding="utf-8",
    )

    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"x" * 2048)

    progress_queue: asyncio.Queue = asyncio.Queue()
    success = await run_lada_restoration(
        job_id="success-job",
        input_path=str(input_path),
        output_path=str(output_path),
        job_settings={
            "lada_cli_path": f"python3 {fake_cli}",
            "device": "cpu",
            "fp16": False,
        },
        progress_queue=progress_queue,
    )

    assert success is True
    events = []
    while not progress_queue.empty():
        events.append(await progress_queue.get())

    progress_events = [e for e in events if e.get("type") == "progress"]
    phase_keys = [e.get("phase_key") for e in progress_events]

    assert "prepare" in phase_keys
    assert "detect" in phase_keys
    assert "restore" in phase_keys
    assert "encode" in phase_keys
    assert phase_keys[-1] == "finalize"
    assert progress_events[-1]["progress"] == 100
    assert progress_events[-1]["phase_progress"] == 100
    assert any(e.get("detail") == "输出文件整理完成" for e in progress_events)


def test_lada_progress_phase_order_declares_expected_pipeline_contract():
    assert LADA_PROGRESS_PHASE_ORDER == (
        "prepare",
        "detect",
        "restore",
        "encode",
        "finalize",
    )


@pytest.mark.asyncio
async def test_lada_runner_progress_ranges_follow_declared_contract(tmp_path: Path):
    fake_cli = tmp_path / "fake_lada_progress.py"
    fake_cli.write_text(
        """
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input')
parser.add_argument('--output')
parser.add_argument('--device')
parser.add_argument('--mosaic-detection-model')
parser.add_argument('--mosaic-restoration-model')
parser.add_argument('--encoding-preset')
parser.add_argument('--max-clip-length')
parser.add_argument('--temporary-directory')
parser.add_argument('--fp16', action='store_true')
parser.add_argument('--no-fp16', action='store_true')
parser.add_argument('--detect-face-mosaics', action='store_true')
args = parser.parse_args()
print('Detect mosaic regions...', flush=True)
print('Processing video... 95%', flush=True)
Path(args.output + '.tmp.mp4').write_bytes(b'x' * 4096)
time.sleep(4.5)
print('Progress: 100%', flush=True)
time.sleep(1.0)
Path(args.output).write_bytes(b'done')
""",
        encoding="utf-8",
    )

    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"x" * 2048)

    progress_queue: asyncio.Queue = asyncio.Queue()
    success = await run_lada_restoration(
        job_id="lada-range-job",
        input_path=str(input_path),
        output_path=str(output_path),
        job_settings={
            "lada_cli_path": f"python3 {fake_cli}",
            "device": "cpu",
            "fp16": False,
        },
        progress_queue=progress_queue,
    )

    assert success is True
    progress_events = []
    while not progress_queue.empty():
        item = await progress_queue.get()
        if item.get("type") == "progress":
            progress_events.append(item)

    prepare_event = progress_events[0]
    assert prepare_event["phase_key"] == "prepare"
    assert 0 <= prepare_event["progress"] <= 5

    detect_event = next(item for item in progress_events if item.get("phase_key") == "detect")
    assert 5 <= detect_event["progress"] <= 14

    restore_event = next(item for item in progress_events if item.get("phase_key") == "restore")
    assert 15 <= restore_event["progress"] <= 80

    encode_event = next(item for item in progress_events if item.get("phase_key") == "encode")
    assert 80 <= encode_event["progress"] <= 98

    finalize_event = progress_events[-1]
    assert finalize_event["phase_key"] == "finalize"
    assert finalize_event["progress"] == 100
