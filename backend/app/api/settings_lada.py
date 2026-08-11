"""LADA settings inspection helpers.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable


LADA_ENCODING_PRESETS = [
    {"id": "hevc-nvidia-gpu-hq", "name": "HEVC (H.265) - High Quality", "desc": "Nvidia GPU, High Quality, Medium File Size"},
    {"id": "hevc-nvidia-gpu-balanced", "name": "HEVC (H.265) - Balanced", "desc": "Nvidia GPU, Excellent Quality, Smaller File Size"},
    {"id": "hevc-nvidia-gpu-uhq", "name": "HEVC (H.265) - Ultra HQ", "desc": "Nvidia GPU, Indistinguishable Quality, Large File Size"},
    {"id": "h264-nvidia-gpu-fast", "name": "H.264 - Fast", "desc": "Nvidia GPU, Fast, Medium File Size"},
    {"id": "h264-cpu-fast", "name": "H.264 - CPU Fast", "desc": "x264 software encoder, Fast, Medium File Size"},
    {"id": "h264-cpu-uhq", "name": "H.264 - CPU Ultra HQ", "desc": "x264 software encoder, Indistinguishable Quality, Slow, Very Large File Size"},
    {"id": "av1-cpu-uhq", "name": "AV1 - CPU Ultra HQ", "desc": "SVT-AV1 software encoder, Indistinguishable Quality, Smaller File Size"},
]


def get_lada_info_impl(
    *, settings: Any, project_root: Path, install_info: dict,
    lada_cli_base_cmd_fn: Callable[[], list[str]], python_executable_fn: Callable[[], str],
    format_size_fn: Callable[[int], str],
) -> dict:
    devices = []
    try:
        result = subprocess.run(lada_cli_base_cmd_fn() + ["--list-devices"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[2:]:
                line = line.strip()
                if not line or line.startswith("-") or line.startswith("Device"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    devices.append({"id": parts[0], "name": " ".join(parts[1:]).strip()})
    except Exception:
        devices = [{"id": "cpu", "name": "CPU"}, {"id": "cuda:0", "name": "CUDA GPU"}]

    configured_dir = settings.lada_model_dir
    if configured_dir:
        model_weights_dir = configured_dir if os.path.isabs(configured_dir) else str(project_root / configured_dir)
    else:
        model_weights_dir = str(project_root / "app" / "pipeline" / "lada" / "model_weights")
    lada_model_script = """
import json
import lada as lada_pkg

detection = lada_pkg.ModelFiles._WELL_KNOWN_DETECTION_MODELS
restoration = lada_pkg.ModelFiles._WELL_KNOWN_RESTORATION_MODELS
result = {
    'detection': [(m.name, m.description or '', m.path) for m in detection],
    'restoration': [(m.name, m.description or '', m.path) for m in restoration],
}
print(json.dumps(result))
"""
    try:
        env = {**os.environ, "LADA_MODEL_WEIGHTS_DIR": model_weights_dir}
        cp = subprocess.run([python_executable_fn(), "-c", lada_model_script], capture_output=True, text=True, timeout=10, env=env)
        if cp.returncode == 0:
            import json
            lada_result = json.loads(cp.stdout)
            all_detection_raw = lada_result["detection"]
            all_restoration_raw = lada_result["restoration"]
        else:
            all_detection_raw, all_restoration_raw = [], []
    except Exception:
        all_detection_raw, all_restoration_raw = [], []

    downloaded_files = {}
    if os.path.isdir(model_weights_dir):
        for root, _, files in os.walk(model_weights_dir):
            for filename in files:
                if filename.endswith((".license", ".txt")) or filename.startswith("."):
                    continue
                downloaded_files[filename] = os.path.getsize(os.path.join(root, filename))
    detection_model_info = {
        "v2": ("v2（经典版）", "LADA 早期检测模型，算法成熟，兼容性好。精度中等，适用于对旧模型有特殊需求的场景。性能对比：★★☆"),
        "v3": ("v3（稳定版）", "v3 系列首个版本，检测稳定性良好。相比 v2 有明显提升，是早期用户常用的版本。性能对比：★★☆"),
        "v3.1-fast": ("v3.1 快速版", "v3.1 的速度优化版本，在保持较好精度的同时提升推理速度。适合批量处理场景。性能对比：★★★"),
        "v3.1-accurate": ("v3.1 精准版", "v3.1 的精度优化版本，检测准确率更高，适合对质量要求更严格的场景。性能对比：★★★☆"),
        "v4-fast": ("v4 极速版", "最新第四代检测模型的速度优先版本。推理速度最快，适合高吞吐量场景，精度损失极小。性能对比：★★★★"),
        "v4-accurate": ("v4 精准版 ⭐推荐", "最新第四代检测模型的精度优先版本。比极速版稍慢，但检测准确率最高，适合对质量要求极高的场景。性能对比：★★★★★"),
    }
    restoration_model_info = {
        "basicvsrpp-v1.0": ("BasicVSR++ v1.0", "基于 BasicVSR++ 架构的早期版本，画质提升稳定。模型较小，处理速度快，但细节恢复能力有限。性能对比：★★★"),
        "basicvsrpp-v1.1": ("BasicVSR++ v1.1", "v1.0 的改进版本，在细节恢复和运动补偿上有优化。文件体积增大，输出质量更好。性能对比：★★★☆"),
        "basicvsrpp-v1.2": ("BasicVSR++ v1.2 ⭐推荐", "LADA 最新推荐版本。基于 BasicVSR++ 深度增强，色彩和细节恢复效果最好，综合体验最优。性能对比：★★★★★"),
        "deepmosaics": ("DeepMosaics（备选）", "来自已停止维护的 DeepMosaics 项目。使用与 BasicVSR++ 不同的 GAN/自编码器架构，风格略有差异。可作为效果对比备选。性能对比：★★★★（风格差异，非优劣）"),
    }
    def build_models(raw_models, descriptions):
        models = []
        for name, desc, path in raw_models:
            filename = os.path.basename(path)
            file_size = downloaded_files.get(filename, 0)
            downloaded = file_size > 1000
            display_name, desc_zh = descriptions.get(name, (name, desc or ""))
            models.append({"id": name, "name": display_name, "size": format_size_fn(file_size) if downloaded else "Not downloaded", "description": desc or display_name, "description_zh": desc_zh, "downloaded": downloaded, "filename": filename})
        return models
    return {
        "model_weights_dir": model_weights_dir,
        "devices": devices,
        "encoding_presets": LADA_ENCODING_PRESETS,
        "detection_models": build_models(all_detection_raw, detection_model_info),
        "restoration_models": build_models(all_restoration_raw, restoration_model_info),
        "install_mode": install_info["install_mode"],
        "can_self_upgrade": install_info["can_self_upgrade"],
        "upgrade_strategy": install_info["upgrade_strategy"],
        "upgrade_hint": install_info["upgrade_hint"],
    }
