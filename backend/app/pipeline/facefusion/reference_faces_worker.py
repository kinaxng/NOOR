from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2


def _load_payload(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("Invalid reference faces request")
    return value


def main() -> int:
    payload = _load_payload(sys.argv[1])
    source_dir = payload.get("source_dir")
    if source_dir:
        os.chdir(source_dir)

    from facefusion import state_manager
    from facefusion.args import apply_args
    from facefusion.core import common_pre_check
    from facefusion.face_creator import get_many_faces
    from facefusion.face_selector import sort_and_filter_faces
    from facefusion.filesystem import is_image, is_video
    from facefusion.program import create_program
    from facefusion.vision import fit_cover_frame, read_static_image, read_video_frame

    cli_args = payload.get("cli_args") or []
    args = vars(create_program().parse_args(cli_args))
    apply_args(args, state_manager.init_item)

    if not common_pre_check():
        raise RuntimeError("FaceFusion reference face pre-check failed")

    target_path = state_manager.get_item("target_path")
    frame_number = int(payload.get("frame_number") or 0)
    if is_image(target_path):
        target_vision_frame = read_static_image(target_path)
    elif is_video(target_path):
        target_vision_frame = read_video_frame(target_path, frame_number)
    else:
        raise RuntimeError("Target path is not an image or video")

    if target_vision_frame is None:
        raise RuntimeError("Failed to read reference frame")

    faces = sort_and_filter_faces([], get_many_faces([target_vision_frame]))
    output_dir = Path(payload["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, face in enumerate(faces):
        start_x, start_y, end_x, end_y = map(int, face.bounding_box)
        padding_x = int((end_x - start_x) * 0.25)
        padding_y = int((end_y - start_y) * 0.25)
        start_x = max(0, start_x - padding_x)
        start_y = max(0, start_y - padding_y)
        end_x = min(target_vision_frame.shape[1], max(0, end_x + padding_x))
        end_y = min(target_vision_frame.shape[0], max(0, end_y + padding_y))
        crop_vision_frame = target_vision_frame[start_y:end_y, start_x:end_x]
        if crop_vision_frame is None or crop_vision_frame.size == 0:
            continue
        crop_vision_frame = fit_cover_frame(crop_vision_frame, (128, 128))
        output_path = output_dir / f"{index}.jpg"
        if not cv2.imwrite(str(output_path), crop_vision_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92]):
            continue
        score_set = getattr(face, "score_set", {}) or {}
        results.append({
            "position": index,
            "path": str(output_path),
            "bounding_box": [start_x, start_y, end_x, end_y],
            "detector_score": float(score_set.get("detector") or 0),
            "gender": getattr(face, "gender", None),
            "age": getattr(face, "age", None),
            "race": getattr(face, "race", None),
        })

    output_json = Path(payload["output_json"])
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"faces": results}, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
