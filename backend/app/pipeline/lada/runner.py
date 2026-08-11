import asyncio
import concurrent.futures
import os
import re
import signal
import subprocess
import threading

from app.core.config import get_settings
from app.tasks.job_phases import get_phase_label


default_settings = get_settings()

LADA_PROGRESS_PHASE_ORDER = (
    "prepare",
    "detect",
    "restore",
    "encode",
    "finalize",
)


def _build_lada_env(lada_model_dir: str) -> dict:
    """Build environment dict with LADA_MODEL_WEIGHTS_DIR set."""
    env = os.environ.copy()
    if lada_model_dir:
        env["LADA_MODEL_WEIGHTS_DIR"] = lada_model_dir
    return env


def _lada_progress_event(
    *,
    progress: int,
    phase_key: str,
    phase_progress: int,
    detail: str | None = None,
) -> dict:
    return {
        "type": "progress",
        "progress": max(0, min(100, int(progress))),
        "phase_key": phase_key,
        "phase_label": get_phase_label(phase_key, "LADA 处理中"),
        "phase_progress": max(0, min(100, int(phase_progress))),
        "detail": detail,
    }


def _restore_overall(progress: int) -> int:
    return min(80, max(15, 15 + round(progress * 0.65)))


def _encode_overall(progress: int) -> int:
    return min(98, max(80, 80 + round(progress * 0.18)))


async def run_lada_restoration(
    job_id: str,
    input_path: str,
    output_path: str,
    job_settings: dict,
    progress_queue: asyncio.Queue,
    cancel_event: asyncio.Event | None = None,
) -> bool:
    """Run lada-cli restoration using a dedicated thread pool executor."""
    settings = get_settings()
    lada_model_dir = job_settings.get("lada_model_dir", settings.lada_model_dir) or ""

    lada_cli_path = job_settings.get("lada_cli_path", settings.lada_cli_path).strip()
    if " " in lada_cli_path:
        parts = lada_cli_path.split()
        cmd = [parts[0], "-u"] + parts[1:]
    else:
        unbuffered_path = re.sub(r"/lada-cli$", "/lada-cli-unbuffered", lada_cli_path)
        cmd = [unbuffered_path] if os.path.exists(unbuffered_path) else [lada_cli_path]

    cmd.extend([
        "--input", input_path,
        "--output", output_path,
        "--device", job_settings.get("device", settings.lada_device or "cuda:0"),
        "--mosaic-detection-model", job_settings.get(
            "detection_model", settings.lada_detection_model or "v4-fast"
        ),
        "--mosaic-restoration-model", job_settings.get(
            "restoration_model", settings.lada_restoration_model or "basicvsrpp-v1.2"
        ),
        "--encoding-preset", job_settings.get(
            "encoding_preset", settings.lada_encoding_preset or "hevc-nvidia-gpu-hq"
        ),
        "--max-clip-length", str(
            job_settings.get("max_clip_length", settings.lada_max_clip_length or 180)
        ),
    ])

    lada_fp16 = job_settings.get("fp16", settings.lada_fp16)
    cmd.append("--fp16" if lada_fp16 else "--no-fp16")
    if job_settings.get("detect_face_mosaics", settings.lada_detect_face_mosaics):
        cmd.append("--detect-face-mosaics")

    await progress_queue.put(_lada_progress_event(
        progress=1,
        phase_key="prepare",
        phase_progress=10,
        detail="初始化 LADA 运行环境",
    ))
    await progress_queue.put({"type": "log", "line": f"Starting command: {' '.join(cmd)}"})
    await progress_queue.put(_lada_progress_event(
        progress=5,
        phase_key="detect",
        phase_progress=0,
        detail="启动 LADA CLI，准备检测视频中的马赛克区域",
    ))

    env = _build_lada_env(lada_model_dir)
    result = {"returncode": None, "lines": [], "cancelled": False}
    proc_holder: dict[str, subprocess.Popen | None] = {"proc": None}
    proc_lock = threading.Lock()
    terminate_requested = threading.Event()
    progress_state = {
        "overall": 5,
        "phase_key": "detect",
        "restore_progress": 0,
        "encode_progress": 0,
    }
    state_lock = threading.Lock()

    def push_progress(event: dict):
        try:
            progress_queue.put_nowait(event)
        except Exception:
            pass

    def publish_progress(
        *,
        progress: int,
        phase_key: str,
        phase_progress: int,
        detail: str | None = None,
        allow_equal: bool = False,
    ):
        progress = max(0, min(100, int(progress)))
        phase_progress = max(0, min(100, int(phase_progress)))
        with state_lock:
            current_overall = int(progress_state["overall"])
            if progress < current_overall or (progress == current_overall and not allow_equal):
                return
            if progress == current_overall and phase_key == progress_state.get("phase_key"):
                previous = int(progress_state.get(f"{phase_key}_progress", 0))
                if phase_progress <= previous and not allow_equal:
                    return
            progress_state["overall"] = progress
            progress_state["phase_key"] = phase_key
            progress_state[f"{phase_key}_progress"] = phase_progress
        push_progress(_lada_progress_event(
            progress=progress,
            phase_key=phase_key,
            phase_progress=phase_progress,
            detail=detail,
        ))

    def _terminate_process_tree(proc: subprocess.Popen | None):
        if proc is None or proc.poll() is not None:
            return
        result["cancelled"] = True
        terminate_requested.set()
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        except ProcessLookupError:
            return
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass

    def _kill_process_tree(proc: subprocess.Popen | None):
        if proc is None or proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            return
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def run_in_thread():
        creation_kwargs = {"start_new_session": True} if os.name == "posix" else {}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            **creation_kwargs,
        )
        with proc_lock:
            proc_holder["proc"] = proc
        if terminate_requested.is_set():
            _terminate_process_tree(proc)
        for raw_line in iter(proc.stdout.readline, b""):
            if terminate_requested.is_set():
                _terminate_process_tree(proc)
                break
            line = raw_line.decode("utf-8", errors="replace")
            stripped = line.strip()
            result["lines"].append(line)

            lowered = stripped.lower()
            if any(token in lowered for token in ("detect", "scan", "mosaic")):
                publish_progress(
                    progress=8,
                    phase_key="detect",
                    phase_progress=35,
                    detail=stripped or "检测马赛克区域",
                )

            match = re.search(r"[Pp]rocessing video.*?(\d+)%", line)
            if not match:
                match = re.search(r"[Pp]rogress:\s*(\d+)%", line)
            if match:
                percent = int(match.group(1))
                publish_progress(
                    progress=_restore_overall(percent),
                    phase_key="restore",
                    phase_progress=percent,
                    detail=stripped or f"修复进度 {percent}%",
                )
        if proc.stdout:
            proc.stdout.close()
        try:
            proc.wait(timeout=10 if terminate_requested.is_set() else None)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            proc.wait()
        result["returncode"] = proc.returncode

    input_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
    estimated_output_size = input_size * 1.3
    temp_path = output_path + ".tmp.mp4"

    async def monitor_output_size():
        last_phase_progress = -1
        while True:
            await asyncio.sleep(2)
            if cancel_event is not None and cancel_event.is_set():
                return
            with state_lock:
                restore_progress = int(progress_state.get("restore_progress", 0))
            if restore_progress < 90:
                continue
            target = temp_path if os.path.exists(temp_path) else output_path
            if not os.path.exists(target):
                continue
            try:
                current_size = os.path.getsize(target)
                if estimated_output_size > 0:
                    percent = min(int(current_size / estimated_output_size * 100), 99)
                    if percent != last_phase_progress:
                        last_phase_progress = percent
                        publish_progress(
                            progress=_encode_overall(percent),
                            phase_key="encode",
                            phase_progress=percent,
                            detail=f"编码输出文件 {percent}%",
                        )
            except Exception:
                pass

    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="lada-")
    future = loop.run_in_executor(executor, run_in_thread)
    monitor_task = asyncio.create_task(monitor_output_size())
    cancel_wait_task = None
    try:
        if cancel_event is None:
            await future
        else:
            cancel_wait_task = asyncio.create_task(cancel_event.wait())
            done, pending = await asyncio.wait(
                {future, cancel_wait_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_wait_task in done and cancel_event.is_set() and not future.done():
                await progress_queue.put({
                    "type": "log",
                    "line": "Cancellation requested; terminating lada-cli...",
                })
                result["cancelled"] = True
                terminate_requested.set()
                with proc_lock:
                    proc = proc_holder.get("proc")
                _terminate_process_tree(proc)
                try:
                    await asyncio.wait_for(asyncio.shield(future), timeout=15)
                except asyncio.TimeoutError:
                    await progress_queue.put({
                        "type": "log",
                        "line": "lada-cli did not exit after SIGTERM; killing...",
                    })
                    with proc_lock:
                        proc = proc_holder.get("proc")
                    _kill_process_tree(proc)
                    await future
            else:
                await future
    except asyncio.CancelledError:
        result["cancelled"] = True
        terminate_requested.set()
        with proc_lock:
            proc = proc_holder.get("proc")
        _terminate_process_tree(proc)
        raise
    finally:
        if cancel_wait_task is not None:
            cancel_wait_task.cancel()

    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    executor.shutdown(wait=False)

    for line in result["lines"]:
        await progress_queue.put({"type": "log", "line": line})

    returncode = result["returncode"] if result["returncode"] is not None else -1
    if result.get("cancelled") or (cancel_event is not None and cancel_event.is_set()):
        await progress_queue.put(_lada_progress_event(
            progress=max(0, min(99, int(progress_state.get("overall", 0)))),
            phase_key="finalize",
            phase_progress=100,
            detail="任务已取消，正在清理临时文件",
        ))
        await progress_queue.put({
            "type": "log",
            "line": f"Process cancelled with return code: {returncode}",
        })
        for path in (output_path + ".tmp.mp4", output_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        return False

    await progress_queue.put(_lada_progress_event(
        progress=99 if returncode != 0 else 100,
        phase_key="finalize",
        phase_progress=100,
        detail="输出文件整理完成" if returncode == 0 else "处理失败，正在结束任务",
    ))
    await progress_queue.put({
        "type": "log",
        "line": f"Process finished with return code: {returncode}",
    })
    return returncode == 0
