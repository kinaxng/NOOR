#!/usr/bin/env python3
"""Extract full-file read snapshots from original NOOR Codex sessions.

The project was modified through Codex in several sessions before deletion. Both
old ``function_call`` events and newer ``custom_tool_call`` events contain
``exec_command`` reads such as ``sed -n '1,260p' path``. This script archives
those exact outputs so they can be used as pre-patch seeds during file replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ORIGINAL_PREFIX = "/home/kinax/noor/"
SED_RE = re.compile(r"sed -n '(\d+),(\d+)\s*p'\s+(\S+)")
OUTPUT_RE = re.compile(r"^Output:\s*\n", re.MULTILINE)


def parse_call_args(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("input", "arguments"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {"cmd": value}
            except json.JSONDecodeError:
                return {"cmd": value}
    return {}


def output_text(raw: Any) -> str:
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("output") or ""))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    elif isinstance(raw, dict):
        text = str(raw.get("output") or raw.get("text") or raw.get("content") or "")
    else:
        text = str(raw or "")
    match = OUTPUT_RE.search(text)
    if match:
        text = text[match.end():]
    return text


def normalize_path(raw_path: str, workdir: str) -> str | None:
    path = raw_path.strip().strip("'\"")
    if path.startswith(ORIGINAL_PREFIX):
        return path.removeprefix(ORIGINAL_PREFIX)
    candidate = Path(path)
    if candidate.is_absolute():
        return None
    if workdir and workdir.startswith(ORIGINAL_PREFIX):
        return (Path(workdir) / candidate).resolve().as_posix().removeprefix(ORIGINAL_PREFIX)
    return None


def collect_snapshots(rollout: Path, cutoff: str) -> list[dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    outputs: dict[str, str] = {}
    snapshots: list[dict[str, Any]] = []

    with rollout.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = str(event.get("timestamp") or "")
            if timestamp >= cutoff:
                continue
            payload = event.get("payload") or {}
            payload_type = payload.get("type")
            if payload_type in ("function_call", "custom_tool_call"):
                name = payload.get("name")
                if name not in ("exec_command", "exec"):
                    continue
                args = parse_call_args(payload)
                cmd = str(args.get("cmd") or "")
                match = SED_RE.search(cmd)
                if not match:
                    continue
                call_id = str(payload.get("call_id") or payload.get("id") or "")
                path = normalize_path(match.group(3), str(args.get("workdir") or ""))
                if not path:
                    continue
                calls[call_id] = {
                    "timestamp": timestamp,
                    "path": path,
                    "start": int(match.group(1)),
                    "end": int(match.group(2)),
                    "cmd": cmd,
                    "call_id": call_id,
                }
            elif payload_type in ("function_call_output", "custom_tool_call_output"):
                call_id = str(payload.get("call_id") or "")
                outputs[call_id] = output_text(payload.get("output"))

    for call_id, call in calls.items():
        if call_id not in outputs:
            continue
        content = outputs[call_id]
        if not content:
            continue
        lines = content.splitlines()
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        snapshots.append(
            {
                "call": call_id,
                "ts": call["timestamp"],
                "path": call["path"],
                "range": [call["start"], call["end"]],
                "lines": len(lines),
                "sha256": sha,
                "file": "",
                "content": content,
            }
        )
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rollouts", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cutoff", default="2026-08-09T16:52:00Z")
    args = parser.parse_args()

    all_snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rollout in args.rollouts:
        for snapshot in collect_snapshots(rollout, args.cutoff):
            key = (
                snapshot["ts"],
                snapshot["path"],
                snapshot["range"][0],
                snapshot["range"][1],
                snapshot["sha256"],
            )
            if key in seen:
                continue
            seen.add(key)
            all_snapshots.append(snapshot)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for index, snapshot in enumerate(all_snapshots):
        path_part = snapshot["path"].replace("/", "__")
        name = (
            f"{snapshot['ts'][:13].replace('-', '').replace(':', '')}_"
            f"{snapshot['sha256'][:8]}_{path_part}_"
            f"{snapshot['range'][0]}-{snapshot['range'][1]}.txt"
        )
        target = output_dir / name
        target.write_text(snapshot["content"], encoding="utf-8")
        entry = {key: value for key, value in snapshot.items() if key != "content"}
        manifest.append({**entry, "file": name})

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"snapshots={len(all_snapshots)} output={output_dir}")


if __name__ == "__main__":
    main()
