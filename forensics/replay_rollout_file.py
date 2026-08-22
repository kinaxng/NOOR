#!/usr/bin/env python3
"""Replay one file's apply_patch history from a Codex rollout."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PATCH_HEADER_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$", re.MULTILINE)
ORIGINAL_REPO_PREFIX = "/home/kinax/noor/"


@dataclass(frozen=True)
class PatchEvent:
    timestamp: str
    patch: str


def normalize_path(path: str) -> str:
    clean = path.strip()
    if clean.startswith(ORIGINAL_REPO_PREFIX):
        return clean.removeprefix(ORIGINAL_REPO_PREFIX)
    return clean.lstrip("./")


def extract_file_patch(patch: str, target: str) -> str | None:
    matches = list(PATCH_HEADER_RE.finditer(patch))
    sections: list[str] = []
    for index, match in enumerate(matches):
        if normalize_path(match.group(2)) != target:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(patch)
        section = patch[match.start():end]
        section = re.sub(
            r"^(\*\*\* (?:Add|Update|Delete) File: ).+$",
            rf"\1{target}",
            section,
            count=1,
            flags=re.MULTILINE,
        )
        section = section.removesuffix("*** End Patch\n").removesuffix("*** End Patch")
        sections.append(section.rstrip())
    if not sections:
        return None
    return "*** Begin Patch\n" + "\n".join(sections) + "\n*** End Patch\n"


def load_events(rollout: Path, target: str, cutoff: str) -> list[PatchEvent]:
    pending: list[tuple[str, PatchEvent]] = []
    successful_calls: set[str] = set()
    with rollout.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = str(event.get("timestamp") or "")
            if cutoff and timestamp >= cutoff:
                continue
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload") or {}
            payload_type = payload.get("type")
            if payload_type == "custom_tool_call_output":
                output = str(payload.get("output") or "")
                if "Exit code: 0" in output or "Success. Updated" in output:
                    successful_calls.add(str(payload.get("call_id") or ""))
                continue
            if payload_type != "custom_tool_call" or payload.get("name") != "apply_patch":
                continue
            file_patch = extract_file_patch(str(payload.get("input") or ""), target)
            if file_patch:
                pending.append(
                    (
                        str(payload.get("call_id") or ""),
                        PatchEvent(timestamp=timestamp, patch=file_patch),
                    )
                )
    return [event for call_id, event in pending if call_id in successful_calls]


def replay(events: list[PatchEvent], target: str, output_dir: Path, apply_patch: Path) -> Path:
    worktree = output_dir / "worktree"
    if worktree.exists():
        shutil.rmtree(worktree)
    worktree.mkdir(parents=True)
    log_rows: list[dict[str, Any]] = []

    for index, event in enumerate(events, start=1):
        result = subprocess.run(
            [str(apply_patch)],
            input=event.patch,
            text=True,
            cwd=worktree,
            capture_output=True,
            check=False,
        )
        log_rows.append(
            {
                "index": index,
                "timestamp": event.timestamp,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"patch {index} at {event.timestamp} failed:\n{result.stdout}{result.stderr}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "replay-log.json").write_text(
        json.dumps(log_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result_path = worktree / target
    if not result_path.is_file():
        raise FileNotFoundError(f"replay did not produce {target}")
    return result_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rollout", type=Path)
    parser.add_argument("target")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--cutoff", default="2026-08-09T17:05:00Z")
    parser.add_argument(
        "--apply-patch",
        type=Path,
        default=Path("/home/kinax/.codex/tmp/arg0/codex-arg0tFnK6x/apply_patch"),
    )
    args = parser.parse_args()

    target = normalize_path(args.target)
    events = load_events(args.rollout, target, args.cutoff)
    if not events:
        raise SystemExit(f"no patch events found for {target}")
    result_path = replay(events, target, args.output_dir, args.apply_patch)
    print(f"events={len(events)} result={result_path}")


if __name__ == "__main__":
    main()
