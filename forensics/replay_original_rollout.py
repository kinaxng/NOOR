#!/usr/bin/env python3
"""Replay the original NOOR patch history from the pre-takeover backup."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROLLOUT = Path(
    "/home/kinax/.codex/sessions/2026/06/08/"
    "rollout-2026-06-08T16-08-55-019ea647-0e81-7d81-9b62-558364a36e3f.jsonl"
)
ORIGINAL_PREFIX = "/home/kinax/noor/"
ORIGINAL_CUTOFF = "2026-08-09T16:52:00Z"
PATCH_HEADER_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class PatchEvent:
    timestamp: str
    source: str
    call_id: str
    patch: str


def normalize_path(path: str) -> str:
    clean = path.strip()
    if clean.startswith(ORIGINAL_PREFIX):
        return clean.removeprefix(ORIGINAL_PREFIX)
    return clean.lstrip("./")


def contains_original_file(patch: str) -> bool:
    return any(
        normalize_path(match.group(2)).startswith("")
        and match.group(2).startswith(ORIGINAL_PREFIX)
        for match in PATCH_HEADER_RE.finditer(patch)
    )


def rewrite_patch_paths(patch: str) -> str:
    return re.sub(
        r"^(\*\*\* (?:Add|Update|Delete) File: )/home/kinax/noor/",
        r"\1",
        patch,
        flags=re.MULTILINE,
    )


def parse_exec_patches(input_text: str) -> list[str]:
    patches: list[str] = []
    for match in re.finditer(r'const patch = "(.*?)";', input_text, re.S):
        try:
            patch = json.loads('"' + match.group(1) + '"')
        except json.JSONDecodeError:
            continue
        if "*** Begin Patch" in patch and contains_original_file(patch):
            patches.append(patch)
    return patches


def output_succeeded(output_text: str) -> bool:
    try:
        payload = json.loads(output_text)
        metadata = payload.get("metadata") or {}
        if metadata.get("exit_code") == 0:
            return True
        return "Success" in str(payload.get("output") or "")
    except json.JSONDecodeError:
        return "Success" in output_text or "Exit code: 0" in output_text


def load_events(rollouts: list[Path], cutoff: str) -> list[PatchEvent]:
    outputs: dict[str, str] = {}
    apply_ends: list[dict[str, Any]] = []
    events: list[PatchEvent] = []

    for rollout in rollouts:
        with rollout.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload") or {}
                if event.get("type") == "event_msg" and payload.get("type") == "patch_apply_end":
                    apply_ends.append({"ts": str(event.get("timestamp") or ""), **payload})
                    continue
                if payload.get("type") == "custom_tool_call_output":
                    outputs[str(payload.get("call_id") or "")] = str(payload.get("output") or "")
                    continue
                if payload.get("type") != "custom_tool_call":
                    continue
                name = payload.get("name")
                timestamp = str(event.get("timestamp") or "")
                if timestamp >= cutoff:
                    continue
                input_text = str(payload.get("input") or "")
                patches: list[str] = []
                if name == "apply_patch":
                    if "*** Begin Patch" in input_text and contains_original_file(input_text):
                        patches = [input_text]
                elif name == "exec":
                    patches = parse_exec_patches(input_text)
                for patch in patches:
                    events.append(
                        PatchEvent(
                            timestamp=timestamp,
                            source=str(name),
                            call_id=str(payload.get("call_id") or ""),
                            patch=patch,
                        )
                    )

    successful: list[PatchEvent] = []
    for event in events:
        if event.source == "exec":
            near = [
                payload
                for payload in apply_ends
                if payload.get("success") is True
                and payload.get("ts", "") >= event.timestamp
            ]
            if near:
                successful.append(event)
            continue
        output_text = outputs.get(event.call_id, "")
        if output_text and output_succeeded(output_text):
            successful.append(event)
    return sorted(successful, key=lambda item: item.timestamp)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("worktree", type=Path)
    parser.add_argument("--rollout", type=Path, action="append", default=[ROLLOUT])
    parser.add_argument("--cutoff", default=ORIGINAL_CUTOFF)
    parser.add_argument(
        "--apply-patch",
        type=Path,
        default=Path("/home/kinax/.codex/tmp/arg0/codex-arg0bfVUZD/apply_patch"),
    )
    parser.add_argument("--max-events", type=int, default=0)
    args = parser.parse_args()

    worktree = args.worktree.resolve()
    if not worktree.exists():
        raise SystemExit(f"worktree does not exist: {worktree}")
    events = load_events(args.rollout, args.cutoff)
    if args.max_events:
        events = events[: args.max_events]
    print(f"replaying {len(events)} successful original patches into {worktree}", flush=True)

    log_path = worktree.parent / "replay-log.jsonl"
    failed = 0
    with log_path.open("w", encoding="utf-8") as log:
        for index, event in enumerate(events, start=1):
            result = subprocess.run(
                [str(args.apply_patch)],
                input=rewrite_patch_paths(event.patch),
                text=True,
                cwd=worktree,
                capture_output=True,
                check=False,
            )
            row = {
                "index": index,
                "timestamp": event.timestamp,
                "source": event.source,
                "call_id": event.call_id,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            if result.returncode != 0:
                failed += 1
                print(
                    f"FAILED index={index} ts={event.timestamp} "
                    f"src={event.source} call={event.call_id}\n"
                    f"{result.stdout}\n{result.stderr}",
                    flush=True,
                )
                if failed >= 3:
                    break
    print(f"done failed={failed} log={log_path}", flush=True)


if __name__ == "__main__":
    main()
