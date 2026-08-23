#!/usr/bin/env python3
"""Replay one file's apply_patch history from original Codex rollouts."""

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
    source: str
    call_id: str
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


def parse_call_input(payload: dict[str, Any]) -> str:
    for key in ("input", "arguments"):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return str(parsed.get("input") or parsed.get("patch") or value)
            except json.JSONDecodeError:
                pass
            return value
        if isinstance(value, dict):
            return str(value.get("input") or value.get("patch") or value)
    return ""


def parse_exec_patches(input_text: str) -> list[str]:
    patches: list[str] = []
    for match in re.finditer(r'const patch = "(.*?)";', input_text, re.S):
        try:
            patch = json.loads('"' + match.group(1) + '"')
        except json.JSONDecodeError:
            continue
        if "*** Begin Patch" in patch:
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


def load_events(
    rollouts: list[Path],
    target: str,
    cutoff: str,
    after: str = "",
) -> list[PatchEvent]:
    pending: list[PatchEvent] = []
    outputs: dict[str, str] = {}
    apply_ends: list[dict[str, Any]] = []
    for rollout in rollouts:
        with rollout.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = str(event.get("timestamp") or "")
                if cutoff and timestamp >= cutoff:
                    continue
                if after and timestamp <= after:
                    continue
                payload = event.get("payload") or {}
                payload_type = payload.get("type")
                if event.get("type") == "event_msg" and payload_type == "patch_apply_end":
                    apply_ends.append({"ts": timestamp, **payload})
                    continue
                if payload_type in ("function_call_output", "custom_tool_call_output"):
                    outputs[str(payload.get("call_id") or "")] = str(payload.get("output") or "")
                    continue
                if payload_type not in ("function_call", "custom_tool_call"):
                    continue
                name = payload.get("name")
                call_id = str(payload.get("call_id") or payload.get("id") or "")
                input_text = parse_call_input(payload)
                if name == "apply_patch":
                    file_patch = extract_file_patch(input_text, target)
                    if file_patch:
                        pending.append(
                            PatchEvent(
                                timestamp=timestamp,
                                source="apply_patch",
                                call_id=call_id,
                                patch=file_patch,
                            )
                        )
                    continue
                if name == "exec":
                    for patch in parse_exec_patches(input_text):
                        file_patch = extract_file_patch(patch, target)
                        if file_patch:
                            pending.append(
                                PatchEvent(
                                    timestamp=timestamp,
                                    source="exec",
                                    call_id=call_id,
                                    patch=file_patch,
                                )
                            )
    successful: list[PatchEvent] = []
    for event in pending:
        if event.source == "exec":
            if any(
                payload.get("success") is True
                and payload.get("ts", "") >= event.timestamp
                for payload in apply_ends
            ):
                successful.append(event)
            continue
        output_text = outputs.get(event.call_id, "")
        if output_text and output_succeeded(output_text):
            successful.append(event)
    return sorted(successful, key=lambda item: item.timestamp)


def replay(
    events: list[PatchEvent],
    target: str,
    output_dir: Path,
    apply_patch: Path,
    seed: Path | None = None,
) -> Path:
    worktree = output_dir / "worktree"
    if worktree.exists():
        shutil.rmtree(worktree)
    worktree.mkdir(parents=True)
    if seed is not None:
        destination = worktree / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, destination)
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
    parser.add_argument("rollouts", type=Path, nargs="+")
    parser.add_argument("target")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--cutoff", default="2026-08-09T16:52:00Z")
    parser.add_argument("--after", default="")
    parser.add_argument("--seed", type=Path)
    parser.add_argument(
        "--apply-patch",
        type=Path,
        default=Path("/home/kinax/.codex/tmp/arg0/codex-arg0bfVUZD/apply_patch"),
    )
    args = parser.parse_args()

    target = normalize_path(args.target)
    events = load_events(args.rollouts, target, args.cutoff, args.after)
    if not events and args.seed is None:
        raise SystemExit(f"no patch events found for {target}")
    result_path = replay(events, target, args.output_dir, args.apply_patch, args.seed)
    print(f"events={len(events)} result={result_path}")


if __name__ == "__main__":
    main()
