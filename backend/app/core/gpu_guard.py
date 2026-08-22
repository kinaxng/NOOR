from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass
class GpuProcess:
    pid: int
    used_mb: int
    name: str
    command: str


@dataclass
class GpuSnapshot:
    index: int
    total_mb: int
    used_mb: int
    free_mb: int
    processes: list[GpuProcess]


def _run_nvidia_smi(args: list[str]) -> str:
    result = subprocess.run(
        ["nvidia-smi", *args],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "nvidia-smi failed").strip()
        raise RuntimeError(detail)
    return result.stdout


def _read_cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            raw = handle.read()
        return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except Exception:
        return ""


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def read_gpu_snapshot(device_index: int = 0) -> GpuSnapshot:
    gpu_lines = _run_nvidia_smi([
        f"--id={device_index}",
        "--query-gpu=index,memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]).strip().splitlines()
    if not gpu_lines:
        raise RuntimeError(f"未找到 GPU {device_index}")
    gpu_parts = [part.strip() for part in gpu_lines[0].split(",")]
    if len(gpu_parts) < 4:
        raise RuntimeError("nvidia-smi GPU 输出格式异常")

    processes: list[GpuProcess] = []
    process_output = _run_nvidia_smi([
        f"--id={device_index}",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits",
    ]).strip()
    for line in process_output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        pid = _parse_int(parts[0], -1)
        if pid <= 0:
            continue
        processes.append(GpuProcess(
            pid=pid,
            name=parts[1],
            used_mb=_parse_int(parts[2]),
            command=_read_cmdline(pid),
        ))

    return GpuSnapshot(
        index=_parse_int(gpu_parts[0], device_index),
        total_mb=_parse_int(gpu_parts[1]),
        used_mb=_parse_int(gpu_parts[2]),
        free_mb=_parse_int(gpu_parts[3]),
        processes=processes,
    )


def _is_noor_process(process: GpuProcess) -> bool:
    if process.pid in {os.getpid(), os.getppid()}:
        return False
    command = f"{process.name} {process.command}"
    markers = (
        "/home/kinax/noor/",
        "/home/kinax/noor-restored/",
        "/home/kinax/.venvs/noor-backend/",
        "backend/app/pipeline/lada",
        "backend/app/pipeline/facefusion",
        "app.pipeline.whisper",
    )
    return any(marker in command for marker in markers)


def _is_gpu_service_process(process: GpuProcess) -> bool:
    if process.pid in {os.getpid(), os.getppid()}:
        return False
    command = f"{process.name} {process.command}".lower()
    markers = (
        "llama-server",
        "ollama runner",
        "/ollama",
        "text-generation-launcher",
        "text-generation-server",
        "vllm",
        "lmdeploy",
        "sglang",
    )
    return any(marker in command for marker in markers)


def _format_processes(processes: list[GpuProcess]) -> str:
    if not processes:
        return "无 GPU 计算进程"
    items = []
    for process in sorted(processes, key=lambda item: item.used_mb, reverse=True):
        command = process.command or process.name
        if len(command) > 160:
            command = command[:157] + "..."
        items.append(f"PID {process.pid} · {process.used_mb} MiB · {command}")
    return "；".join(items)


def _terminate_processes(processes: list[GpuProcess], grace_seconds: int) -> list[int]:
    killed: list[int] = []
    for process in processes:
        try:
            os.kill(process.pid, signal.SIGTERM)
            killed.append(process.pid)
        except ProcessLookupError:
            killed.append(process.pid)
        except Exception:
            pass

    deadline = time.time() + max(1, grace_seconds)
    while time.time() < deadline:
        if all(not os.path.exists(f"/proc/{process.pid}") for process in processes):
            return killed
        time.sleep(0.25)

    for process in processes:
        if not os.path.exists(f"/proc/{process.pid}"):
            continue
        try:
            os.kill(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            pass
    return killed


def ensure_gpu_memory(
    *,
    task_name: str,
    required_free_mb: int,
    device_index: int = 0,
    cleanup_policy: str = "services",
    grace_seconds: int = 8,
) -> list[str]:
    if required_free_mb <= 0:
        return []

    logs: list[str] = []
    snapshot = read_gpu_snapshot(device_index)
    logs.append(
        f"GPU Guard: {task_name} 需要空闲 {required_free_mb} MiB；"
        f"GPU {snapshot.index} 当前空闲 {snapshot.free_mb}/{snapshot.total_mb} MiB"
    )
    if snapshot.free_mb >= required_free_mb:
        return logs

    policy = (cleanup_policy or "services").strip().lower()
    candidates: list[GpuProcess] = []
    if policy == "noor":
        candidates = [process for process in snapshot.processes if _is_noor_process(process)]
    elif policy in {"services", "managed", "managed-services"}:
        candidates = [
            process for process in snapshot.processes
            if _is_noor_process(process) or _is_gpu_service_process(process)
        ]
    elif policy == "aggressive":
        candidates = [
            process for process in snapshot.processes
            if process.pid not in {os.getpid(), os.getppid()}
        ]

    if candidates:
        logs.append(f"GPU Guard: 显存不足，准备清理进程：{_format_processes(candidates)}")
        killed = _terminate_processes(candidates, grace_seconds)
        if killed:
            logs.append(f"GPU Guard: 已请求释放 GPU 进程 PID：{', '.join(str(pid) for pid in killed)}")
        time.sleep(1.0)
        snapshot = read_gpu_snapshot(device_index)
        logs.append(f"GPU Guard: 清理后空闲 {snapshot.free_mb}/{snapshot.total_mb} MiB")

    if snapshot.free_mb < required_free_mb:
        raise RuntimeError(
            f"GPU 显存不足：{task_name} 需要空闲 {required_free_mb} MiB，"
            f"当前仅 {snapshot.free_mb} MiB。当前占用：{_format_processes(snapshot.processes)}"
        )
    return logs
