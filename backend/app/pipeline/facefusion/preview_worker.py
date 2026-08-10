from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy


def _load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("Invalid preview request")
    return value


def main() -> int:
    payload = _load_payload(sys.argv[1])
    source_dir = payload.get("source_dir")
    if source_dir:
        os.chdir(source_dir)

    from facefusion import state_manager
    from facefusion.args import apply_args
    from facefusion.core import common_pre_check, processors_pre_check
    from facefusion.filesystem import is_image, is_video
    from facefusion.program import create_program
    from facefusion.uis.components import preview as preview_component
    from facefusion.vision import extract_vision_mask, merge_vision_mask, read_static_image, read_static_images, read_video_frame
    from facefusion.audio import create_empty_audio_frame

    cli_args = payload.get("cli_args") or []
    args = vars(create_program().parse_args(cli_args))
    apply_args(args, state_manager.init_item)

    if not common_pre_check() or not processors_pre_check():
        raise RuntimeError("FaceFusion preview pre-check failed")

    target_path = state_manager.get_item("target_path")
    source_paths = state_manager.get_item("source_paths") or []
    source_vision_frames = read_static_images(source_paths)
    source_audio_frame = create_empty_audio_frame()
    source_voice_frame = create_empty_audio_frame()
    preview_mode = payload.get("preview_mode") or "default"
    preview_resolution = payload.get("preview_resolution") or "768x768"
    frame_number = int(payload.get("frame_number") or 0)

    if is_image(target_path):
        reference_vision_frame = read_static_image(target_path)
        target_vision_frame = read_static_image(target_path, "rgba")
        target_vision_mask = extract_vision_mask(target_vision_frame)
        target_vision_frame = merge_vision_mask(target_vision_frame, target_vision_mask)
    elif is_video(target_path):
        reference_frame_number = int(state_manager.get_item("reference_frame_number") or 0)
        reference_vision_frame = read_video_frame(target_path, reference_frame_number)
        target_vision_frame = read_video_frame(target_path, frame_number)
        target_vision_mask = extract_vision_mask(target_vision_frame)
        target_vision_frame = merge_vision_mask(target_vision_frame, target_vision_mask)
    else:
        raise RuntimeError("Target path is not an image or video")

    if payload.get("skip_content_analysis", True):
        preview_component.analyse_frame = lambda _vision_frame: False

    preview_frame = preview_component.process_preview_frame(
        reference_vision_frame,
        source_vision_frames,
        source_audio_frame,
        source_voice_frame,
        target_vision_frame,
        preview_mode,
        preview_resolution,
    )
    if preview_frame is None or not numpy.any(preview_frame):
        raise RuntimeError("FaceFusion did not generate a preview frame")

    output_path = Path(payload["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), preview_frame):
        raise RuntimeError("Failed to write FaceFusion preview")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
