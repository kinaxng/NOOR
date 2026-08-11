from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path

from app.core.facefusion_paths import (
    build_facefusion_python_env,
    resolve_facefusion_model_dir,
    resolve_facefusion_python,
    resolve_facefusion_source,
)
from app.core.config import get_settings
from app.core.facefusion_defaults import facefusion_settings
from app.core.runtime_paths import ensure_directory
from app.tasks.job_phases import get_phase_label


def _progress_event(
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
        "phase_label": get_phase_label(phase_key, "FaceFusion 处理中"),
        "phase_progress": max(0, min(100, int(phase_progress))),
        "detail": detail,
    }


def _split_words(value: str | list[str] | None, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        items = [item.strip() for item in re.split(r"[\s,]+", value) if item.strip()]
        return items or fallback
    return fallback


def _build_env(*, facefusion_cache_dir: str, facefusion_temp_dir: str) -> dict[str, str]:
    env = os.environ.copy()
    env["NOOR_FACEFUSION_SKIP_CONTENT_ANALYSIS"] = "1"
    if facefusion_cache_dir:
        cache_root = Path(facefusion_cache_dir)
        xdg_cache_dir = cache_root / "xdg"
        tensorrt_cache_dir = cache_root / "onnxruntime" / "tensorrt"
        cuda_cache_dir = cache_root / "cuda"
        jobs_dir = cache_root / "jobs"
        for path in (xdg_cache_dir, tensorrt_cache_dir, cuda_cache_dir, jobs_dir):
            path.mkdir(parents=True, exist_ok=True)
        env["XDG_CACHE_HOME"] = str(xdg_cache_dir)
        env["ORT_TENSORRT_CACHE_PATH"] = str(tensorrt_cache_dir)
        env["CUDA_CACHE_PATH"] = str(cuda_cache_dir)
    if facefusion_temp_dir:
        env["TMPDIR"] = facefusion_temp_dir
    return env


_resolve_model_dir = resolve_facefusion_model_dir
FACEFUSION_TASK_TEMP_PARENT = "tasks"

FACEFUSION_ALLOWED_PROCESSORS = {
    "face_swapper",
    "face_enhancer",
    "frame_enhancer",
    "expression_restorer",
    "deep_swapper",
    "face_debugger",
}


FACEFUSION_PHASE_MAP = {
    "download": ("prepare", 1, 4),
    "analyze": ("analyze", 2, 5),
    "extract": ("analyze", 5, 20),
    "process": ("process", 20, 88),
    "merge": ("encode", 88, 94),
    "audio": ("encode", 94, 98),
    "finalize": ("finalize", 98, 100),
}


def _classify_output_line(line: str) -> str | None:
    lowered = line.lower()
    if any(token in line for token in ("下载中", "源验证", "哈希验证")) or "download" in lowered:
        return "download"
    if any(token in line for token in ("分析中",)) or "analys" in lowered or "detect" in lowered:
        return "analyze"
    if any(token in line for token in ("提取中", "正在提取帧", "提取帧")) or "extract" in lowered:
        return "extract"
    if any(token in line for token in ("处理中",)) or "processing" in lowered:
        return "process"
    if any(token in line for token in ("合并中", "合并视频")) or "merging" in lowered:
        return "merge"
    if any(token in line for token in ("恢复音频", "替换音频", "跳过音频")) or "audio" in lowered:
        return "audio"
    if any(token in line for token in ("最终化", "清理临时", "处理成功")) or "finaliz" in lowered:
        return "finalize"
    return None


def _overall_for_phase(stage: str, pct: int) -> tuple[int, str, int]:
    phase_key, start, end = FACEFUSION_PHASE_MAP[stage]
    phase_progress = max(0, min(100, int(pct)))
    overall = start + round((end - start) * phase_progress / 100)
    return max(0, min(100, overall)), phase_key, phase_progress


def _execution_providers(job_settings: dict) -> list[str]:
    settings = facefusion_settings(get_settings())
    return _split_words(job_settings.get("execution_provider", settings.facefusion_execution_provider), [])


def _system_memory_limit(job_settings: dict) -> int:
    settings = facefusion_settings(get_settings())
    return int(job_settings.get("system_memory_limit", settings.facefusion_system_memory_limit) or 0)


def _safe_job_id(job_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(job_id or ""))
    return safe.strip("_")[:96] or "facefusion"


def _task_temp_dir(base_temp_dir: str, job_id: str) -> Path:
    return Path(base_temp_dir) / FACEFUSION_TASK_TEMP_PARENT / _safe_job_id(job_id)


def _prepare_task_runtime_settings(job_id: str, job_settings: dict) -> tuple[dict, Path]:
    settings = get_settings()
    runtime_settings = dict(job_settings or {})
    base_temp_dir = ensure_directory(runtime_settings.get("facefusion_temp_dir", settings.facefusion_temp_dir) or "")
    task_temp_dir = _task_temp_dir(base_temp_dir, job_id)
    task_temp_dir.mkdir(parents=True, exist_ok=True)
    runtime_settings["facefusion_temp_dir"] = str(task_temp_dir)
    runtime_settings["facefusion_jobs_dir"] = str(task_temp_dir / "jobs")
    return runtime_settings, task_temp_dir


def _release_process_memory() -> None:
    gc.collect()
    torch_module = sys.modules.get("torch")
    if torch_module is None:
        return
    cuda = getattr(torch_module, "cuda", None)
    if cuda is None:
        return
    with suppress(Exception):
        if cuda.is_available():
            cuda.empty_cache()
    with suppress(Exception):
        if cuda.is_available() and hasattr(cuda, "ipc_collect"):
            cuda.ipc_collect()


def _cleanup_task_runtime(task_temp_dir: Path | None) -> None:
    if task_temp_dir is None:
        return
    with suppress(Exception):
        if task_temp_dir.exists():
            shutil.rmtree(task_temp_dir)
    with suppress(Exception):
        parent = task_temp_dir.parent
        if parent.name == FACEFUSION_TASK_TEMP_PARENT and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def _build_command(input_path: str, output_path: str, job_settings: dict) -> tuple[list[str], str, dict[str, str], str, str, str, str]:
    settings = facefusion_settings(get_settings())
    configured_dir = job_settings.get("facefusion_dir")
    if configured_dir is None:
        configured_dir = settings.facefusion_dir
    source = resolve_facefusion_source(configured_dir)

    source_paths = job_settings.get("source_paths") or job_settings.get("source_path") or []
    if isinstance(source_paths, str):
        source_paths = [source_paths]
    source_paths = [str(path).strip() for path in source_paths if str(path).strip()]
    if not source_paths:
        raise RuntimeError("FaceFusion 需要至少一个源脸图片路径")

    python_path = resolve_facefusion_python(
        source.source_dir,
        job_settings.get("facefusion_python_path") or settings.facefusion_python_path,
    )
    facefusion_cache_dir = ensure_directory(job_settings.get("facefusion_cache_dir", settings.facefusion_cache_dir) or "")
    facefusion_temp_dir = ensure_directory(job_settings.get("facefusion_temp_dir", settings.facefusion_temp_dir) or "")
    configured_model_dir = (
        job_settings.get("facefusion_model_dir")
        or getattr(settings, "facefusion_model_dir", "")
    )
    model_dir, model_dir_mode = _resolve_model_dir(source.source_dir, configured_model_dir)
    cmd = [python_path, str(source.facefusion_py), "headless-run"]
    cmd += ["-s", *source_paths]
    cmd += ["-t", input_path]
    cmd += ["-o", output_path]
    cmd += ["--temp-path", facefusion_temp_dir]
    jobs_dir = job_settings.get("facefusion_jobs_dir")
    if jobs_dir:
        cmd += ["--jobs-path", ensure_directory(jobs_dir)]
    elif facefusion_cache_dir:
        cmd += ["--jobs-path", str(Path(facefusion_cache_dir) / "jobs")]

    processors = _split_words(
        job_settings.get("processors"),
        _split_words(settings.facefusion_processors, []),
    )
    processors = [processor for processor in processors if processor in FACEFUSION_ALLOWED_PROCESSORS]
    if not processors:
        processors = ["face_swapper"]
    if processors:
        cmd += ["--processors", *processors]
    if "face_swapper" in processors:
        cmd += ["--face-swapper-model", str(job_settings.get("face_swapper_model", settings.facefusion_face_swapper_model))]
        cmd += ["--face-swapper-pixel-boost", str(job_settings.get("face_swapper_pixel_boost", settings.facefusion_face_swapper_pixel_boost))]
        cmd += ["--face-swapper-weight", str(job_settings.get("face_swapper_weight", settings.facefusion_face_swapper_weight))]
    if "face_enhancer" in processors:
        cmd += ["--face-enhancer-model", str(job_settings.get("face_enhancer_model", settings.facefusion_face_enhancer_model))]
        cmd += ["--face-enhancer-blend", str(job_settings.get("face_enhancer_blend", settings.facefusion_face_enhancer_blend))]
        cmd += ["--face-enhancer-weight", str(job_settings.get("face_enhancer_weight", settings.facefusion_face_enhancer_weight))]
    if "frame_enhancer" in processors:
        cmd += ["--frame-enhancer-model", str(job_settings.get("frame_enhancer_model", settings.facefusion_frame_enhancer_model))]
        cmd += ["--frame-enhancer-blend", str(job_settings.get("frame_enhancer_blend", settings.facefusion_frame_enhancer_blend))]
    if "expression_restorer" in processors:
        cmd += ["--expression-restorer-model", str(job_settings.get("expression_restorer_model", "live_portrait"))]
        cmd += ["--expression-restorer-factor", str(job_settings.get("expression_restorer_factor", 80))]
        expression_areas = _split_words(job_settings.get("expression_restorer_areas", "upper-face lower-face"), ["upper-face", "lower-face"])
        if expression_areas:
            cmd += ["--expression-restorer-areas", *expression_areas]
    if "deep_swapper" in processors:
        cmd += ["--deep-swapper-model", str(job_settings.get("deep_swapper_model", "iperov/elon_musk_224"))]
        cmd += ["--deep-swapper-morph", str(job_settings.get("deep_swapper_morph", 100))]
    if "face_debugger" in processors:
        debugger_items = _split_words(job_settings.get("face_debugger_items", "face-landmark-5/68 face-mask"), ["face-landmark-5/68", "face-mask"])
        if debugger_items:
            cmd += ["--face-debugger-items", *debugger_items]

    providers = _execution_providers(job_settings)
    if providers:
        cmd += ["--execution-providers", *providers]
    device_ids = _split_words(job_settings.get("device_ids", settings.facefusion_device_ids), ["0"])
    if device_ids:
        cmd += ["--execution-device-ids", *device_ids]
    cmd += ["--execution-thread-count", str(job_settings.get("thread_count", settings.facefusion_thread_count))]
    cmd += ["--video-memory-strategy", str(job_settings.get("video_memory_strategy", settings.facefusion_video_memory_strategy))]
    system_memory_limit = _system_memory_limit(job_settings)
    if system_memory_limit > 0 and "tensorrt" not in {provider.lower() for provider in providers}:
        cmd += ["--system-memory-limit", str(system_memory_limit)]
    download_providers = _split_words(job_settings.get("download_providers", settings.facefusion_download_providers), [])
    if download_providers:
        cmd += ["--download-providers", *download_providers]

    cmd += ["--face-detector-model", str(job_settings.get("face_detector_model", settings.facefusion_face_detector_model))]
    cmd += ["--face-detector-size", str(job_settings.get("face_detector_size", settings.facefusion_face_detector_size))]
    cmd += ["--face-detector-score", str(job_settings.get("face_detector_score", settings.facefusion_face_detector_score))]
    detector_angles = _split_words(job_settings.get("face_detector_angles", settings.facefusion_face_detector_angles), ["0"])
    if detector_angles:
        cmd += ["--face-detector-angles", *detector_angles]
    detector_margin = _split_words(job_settings.get("face_detector_margin", settings.facefusion_face_detector_margin), [])
    if detector_margin:
        cmd += ["--face-detector-margin", *detector_margin]
    cmd += ["--face-landmarker-model", str(job_settings.get("face_landmarker_model", settings.facefusion_face_landmarker_model))]
    cmd += ["--face-landmarker-score", str(job_settings.get("face_landmarker_score", settings.facefusion_face_landmarker_score))]
    cmd += ["--face-selector-mode", str(job_settings.get("face_selector_mode", settings.facefusion_face_selector_mode))]
    selector_order = job_settings.get("face_selector_order", settings.facefusion_face_selector_order)
    if selector_order:
        cmd += ["--face-selector-order", str(selector_order)]
    gender = job_settings.get("face_selector_gender", settings.facefusion_face_selector_gender)
    if gender:
        cmd += ["--face-selector-gender", str(gender)]
    age_start = job_settings.get("face_selector_age_start", settings.facefusion_face_selector_age_start)
    if age_start not in (None, ""):
        cmd += ["--face-selector-age-start", str(age_start)]
    age_end = job_settings.get("face_selector_age_end", settings.facefusion_face_selector_age_end)
    if age_end not in (None, ""):
        cmd += ["--face-selector-age-end", str(age_end)]
    race = job_settings.get("face_selector_race", settings.facefusion_face_selector_race)
    if race:
        cmd += ["--face-selector-race", str(race)]
    cmd += ["--reference-frame-number", str(job_settings.get("reference_frame_number", settings.facefusion_reference_frame_number))]
    cmd += ["--reference-face-position", str(job_settings.get("reference_face_position", settings.facefusion_reference_face_position))]
    cmd += ["--reference-face-distance", str(job_settings.get("reference_face_distance", settings.facefusion_reference_face_distance))]

    mask_types = _split_words(job_settings.get("face_mask_types", settings.facefusion_face_mask_types), ["box"])
    if mask_types:
        cmd += ["--face-mask-types", *mask_types]
    mask_areas = _split_words(job_settings.get("face_mask_areas", settings.facefusion_face_mask_areas), [])
    if mask_areas:
        cmd += ["--face-mask-areas", *mask_areas]
    mask_regions = _split_words(job_settings.get("face_mask_regions", settings.facefusion_face_mask_regions), [])
    if mask_regions:
        cmd += ["--face-mask-regions", *mask_regions]
    cmd += ["--face-mask-blur", str(job_settings.get("face_mask_blur", settings.facefusion_face_mask_blur))]
    mask_padding = _split_words(job_settings.get("face_mask_padding", settings.facefusion_face_mask_padding), [])
    if mask_padding:
        cmd += ["--face-mask-padding", *mask_padding]
    cmd += ["--face-occluder-model", str(job_settings.get("face_occluder_model", settings.facefusion_face_occluder_model))]
    cmd += ["--face-parser-model", str(job_settings.get("face_parser_model", settings.facefusion_face_parser_model))]

    cmd += ["--output-video-encoder", str(job_settings.get("output_video_encoder", settings.facefusion_output_video_encoder))]
    cmd += ["--output-video-preset", str(job_settings.get("output_video_preset", settings.facefusion_output_video_preset))]
    cmd += ["--output-video-quality", str(job_settings.get("output_video_quality", settings.facefusion_output_video_quality))]
    output_video_scale = job_settings.get("output_video_scale", settings.facefusion_output_video_scale)
    if output_video_scale:
        cmd += ["--output-video-scale", str(output_video_scale)]
    output_video_fps = job_settings.get("output_video_fps", settings.facefusion_output_video_fps)
    if output_video_fps:
        cmd += ["--output-video-fps", str(output_video_fps)]
    cmd += ["--output-audio-encoder", str(job_settings.get("output_audio_encoder", settings.facefusion_output_audio_encoder))]
    cmd += ["--output-audio-quality", str(job_settings.get("output_audio_quality", settings.facefusion_output_audio_quality))]
    cmd += ["--output-audio-volume", str(job_settings.get("output_audio_volume", settings.facefusion_output_audio_volume))]
    cmd += ["--output-image-quality", str(job_settings.get("output_image_quality", settings.facefusion_output_image_quality))]
    output_image_scale = job_settings.get("output_image_scale", settings.facefusion_output_image_scale)
    if output_image_scale:
        cmd += ["--output-image-scale", str(output_image_scale)]
    cmd += ["--temp-frame-format", str(job_settings.get("temp_frame_format", settings.facefusion_temp_frame_format))]
    cmd += ["--log-level", str(job_settings.get("log_level", settings.facefusion_log_level))]

    env = build_facefusion_python_env(source.source_dir, _build_env(
        facefusion_cache_dir=facefusion_cache_dir,
        facefusion_temp_dir=facefusion_temp_dir,
    ))
    return cmd, str(source.source_dir), env, model_dir, model_dir_mode, facefusion_cache_dir, source.mode


def _returncode_detail(returncode: int) -> str:
    if returncode == 3:
        return "FaceFusion 返回码 3：目标内容分析命中并中止。NOOR 任务应跳过内容分析，请检查嵌入版补丁是否生效。"
    if returncode < 0:
        return f"FaceFusion 被信号 {-returncode} 终止"
    return f"FaceFusion 返回码 {returncode}"


async def run_facefusion_restoration(
    job_id: str,
    input_path: str,
    output_path: str,
    job_settings: dict,
    progress_queue: asyncio.Queue,
    cancel_event: asyncio.Event | None = None,
) -> bool:
    runtime_settings, task_temp_dir = _prepare_task_runtime_settings(job_id, job_settings)
    proc_holder: dict[str, subprocess.Popen | None] = {"proc": None}
    proc_lock = threading.Lock()
    terminate_requested = threading.Event()

    def push(item: dict) -> None:
        try:
            progress_queue.put_nowait(item)
        except Exception:
            pass

    def terminate_process_tree(proc: subprocess.Popen | None) -> None:
        if proc is None or proc.poll() is not None:
            return
        terminate_requested.set()
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
        except ProcessLookupError:
            return
        except Exception:
            with suppress(Exception):
                proc.terminate()

    def kill_process_tree(proc: subprocess.Popen | None) -> None:
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
            with suppress(Exception):
                proc.kill()

    try:
        cmd, cwd, env, model_dir, model_dir_mode, facefusion_cache_dir, source_mode = _build_command(input_path, output_path, runtime_settings)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        await progress_queue.put(_progress_event(
            progress=1,
            phase_key="prepare",
            phase_progress=10,
            detail="初始化 FaceFusion CLI",
        ))
        await progress_queue.put({"type": "log", "line": f"Starting command: {' '.join(cmd)}"})
        await progress_queue.put({"type": "log", "line": f"FaceFusion source mode: {source_mode}"})
        await progress_queue.put({"type": "log", "line": f"FaceFusion model directory: {model_dir} ({model_dir_mode})"})
        await progress_queue.put({"type": "log", "line": f"FaceFusion working directory: {cwd}"})
        await progress_queue.put({"type": "log", "line": f"FaceFusion runtime cache directory: {facefusion_cache_dir}"})
        await progress_queue.put({"type": "log", "line": f"FaceFusion task temp directory: {task_temp_dir}"})
        if _system_memory_limit(runtime_settings) > 0 and "tensorrt" in {provider.lower() for provider in _execution_providers(runtime_settings)}:
            await progress_queue.put({
                "type": "log",
                "line": "FaceFusion system memory limit ignored for TensorRT to avoid ONNXRuntime/TensorRT RLIMIT_DATA crashes.",
            })

        result = {"returncode": None, "cancelled": False}
        progress_state = {"overall": 1, "stage": ""}
        state_lock = threading.Lock()

        def publish(progress: int, phase_key: str, phase_progress: int, detail: str | None = None, stage: str | None = None) -> None:
            progress = max(0, min(100, int(progress)))
            with state_lock:
                current_stage = str(progress_state.get("stage") or "")
                if stage and current_stage != stage:
                    progress_state["stage"] = stage
                elif progress < int(progress_state["overall"]):
                    return
                progress_state["overall"] = progress
            push(_progress_event(
                progress=progress,
                phase_key=phase_key,
                phase_progress=phase_progress,
                detail=detail,
            ))

        def run_in_thread() -> None:
            creation_kwargs = {"start_new_session": True} if os.name == "posix" else {}
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                **creation_kwargs,
            )
            with proc_lock:
                proc_holder["proc"] = proc
            if terminate_requested.is_set():
                terminate_process_tree(proc)
            if proc.stdout:
                for raw_line in proc.stdout:
                    if terminate_requested.is_set():
                        terminate_process_tree(proc)
                        break
                    line = raw_line.rstrip()
                    if not line:
                        continue
                    push({"type": "log", "line": line})
                    stage = _classify_output_line(line)
                    match = re.search(r"(\d{1,3})%", line)
                    if stage and match:
                        pct = max(0, min(100, int(match.group(1))))
                        overall, phase_key, phase_progress = _overall_for_phase(stage, pct)
                        publish(overall, phase_key, phase_progress, line, stage=stage)
                    elif stage:
                        overall, phase_key, phase_progress = _overall_for_phase(stage, 0)
                        publish(overall, phase_key, phase_progress, line, stage=stage)
            if proc.stdout:
                proc.stdout.close()
            try:
                proc.wait(timeout=10 if terminate_requested.is_set() else None)
            except subprocess.TimeoutExpired:
                kill_process_tree(proc)
                proc.wait()
            result["returncode"] = proc.returncode

        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="facefusion-")
        future = loop.run_in_executor(executor, run_in_thread)
        cancel_wait_task = None

        try:
            if cancel_event is None:
                await future
            else:
                cancel_wait_task = asyncio.create_task(cancel_event.wait())
                done, _ = await asyncio.wait({future, cancel_wait_task}, return_when=asyncio.FIRST_COMPLETED)
                if cancel_wait_task in done and cancel_event.is_set() and not future.done():
                    await progress_queue.put({"type": "log", "line": "Cancellation requested; terminating FaceFusion..."})
                    result["cancelled"] = True
                    terminate_requested.set()
                    with proc_lock:
                        proc = proc_holder.get("proc")
                    terminate_process_tree(proc)
                    try:
                        await asyncio.wait_for(asyncio.shield(future), timeout=15)
                    except asyncio.TimeoutError:
                        await progress_queue.put({"type": "log", "line": "FaceFusion did not exit after SIGTERM; killing..."})
                        with proc_lock:
                            proc = proc_holder.get("proc")
                        kill_process_tree(proc)
                        await future
                else:
                    await future
        except asyncio.CancelledError:
            result["cancelled"] = True
            terminate_requested.set()
            with proc_lock:
                proc = proc_holder.get("proc")
            terminate_process_tree(proc)
            raise
        finally:
            if cancel_wait_task is not None:
                cancel_wait_task.cancel()
            executor.shutdown(wait=False)

        returncode = result["returncode"] if result["returncode"] is not None else -1
        if result.get("cancelled") or (cancel_event is not None and cancel_event.is_set()):
            await progress_queue.put(_progress_event(
                progress=max(0, min(99, int(progress_state.get("overall", 0)))),
                phase_key="finalize",
                phase_progress=100,
                detail="任务已取消，正在清理临时文件",
            ))
            for path in (output_path,):
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
            return False

        await progress_queue.put(_progress_event(
            progress=100 if returncode == 0 else 99,
            phase_key="finalize",
            phase_progress=100,
            detail="输出文件整理完成" if returncode == 0 else "处理失败，正在结束任务",
        ))
        await progress_queue.put({"type": "log", "line": f"Process finished with return code: {returncode}"})
        if returncode != 0:
            await progress_queue.put({"type": "log", "line": _returncode_detail(returncode)})
        return returncode == 0
    finally:
        with proc_lock:
            proc = proc_holder.get("proc")
        terminate_process_tree(proc)
        kill_process_tree(proc)
        _cleanup_task_runtime(task_temp_dir)
        _release_process_memory()
        push({"type": "log", "line": "FaceFusion runtime cache cleaned and memory release requested."})
