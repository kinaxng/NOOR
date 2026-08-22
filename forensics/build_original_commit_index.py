#!/usr/bin/env python3
"""Build an evidence index of NOOR commits recorded in a Codex rollout."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


COMMIT_RE = re.compile(r"^\[[^\]]*?\s([0-9a-f]{7,40})\]\s(.+)$", re.MULTILINE)
STAT_RE = re.compile(
    r"(?P<files>\d+) files? changed"
    r"(?:, (?P<insertions>\d+) insertions?\(\+\))?"
    r"(?:, (?P<deletions>\d+) deletions?\(-\))?"
)
WORKDIR_RE = re.compile(r'["\']workdir["\']\s*:\s*["\']([^"\']+)["\']')
ADD_RE = re.compile(r"\bgit add\s+(.+?)(?=\s*(?:&&|;|\n|\bgit commit\b))", re.DOTALL)


@dataclass
class CommitEvidence:
    timestamp: str
    commit: str
    subject: str
    workdir: str
    staged_paths: list[str]
    files_changed: int | None
    insertions: int | None
    deletions: int | None
    call_type: str
    call_id: str
    command: str


def flatten_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in value
        )
    if isinstance(value, dict):
        return str(value.get("text", value))
    return str(value or "")


def parse_standard_call(payload: dict[str, Any]) -> tuple[str, str]:
    try:
        arguments = json.loads(payload.get("arguments", "{}"))
    except json.JSONDecodeError:
        return "", ""
    return str(arguments.get("cmd", "")), str(arguments.get("workdir", ""))


def parse_custom_call(payload: dict[str, Any]) -> tuple[str, str]:
    raw = str(payload.get("input", ""))
    workdir_match = WORKDIR_RE.search(raw)
    workdir = workdir_match.group(1) if workdir_match else ""
    return raw, workdir


def staged_paths(command: str) -> list[str]:
    paths: list[str] = []
    for match in ADD_RE.finditer(command):
        value = match.group(1).replace("\\n", "\n").strip()
        try:
            tokens = shlex.split(value)
        except ValueError:
            tokens = value.split()
        for token in tokens:
            if token.startswith("-") or token in {".", "-A"}:
                continue
            if token not in paths:
                paths.append(token)
    return paths


def read_commits(rollout: Path, cutoff: str, repo: str) -> list[CommitEvidence]:
    calls: dict[str, tuple[str, str, str, str]] = {}
    commits: list[CommitEvidence] = []

    with rollout.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = str(event.get("timestamp", ""))
            if cutoff and timestamp >= cutoff:
                continue
            if event.get("type") != "response_item":
                continue

            payload = event.get("payload", {})
            payload_type = payload.get("type")
            if payload_type == "function_call" and payload.get("name") == "exec_command":
                command, workdir = parse_standard_call(payload)
                call_id = str(payload.get("call_id", ""))
                calls[call_id] = (timestamp, command, workdir, "function_call")
                continue
            if payload_type == "custom_tool_call" and payload.get("name") == "exec":
                command, workdir = parse_custom_call(payload)
                call_id = str(payload.get("call_id", ""))
                calls[call_id] = (timestamp, command, workdir, "custom_tool_call")
                continue
            if payload_type not in {"function_call_output", "custom_tool_call_output"}:
                continue

            call_id = str(payload.get("call_id", ""))
            call = calls.get(call_id)
            if not call:
                continue
            call_timestamp, command, workdir, call_type = call
            if workdir != repo or "git commit" not in command:
                continue

            output = flatten_output(payload.get("output", ""))
            matches = list(COMMIT_RE.finditer(output))
            if not matches:
                continue
            stat_match = STAT_RE.search(output)
            for match in matches:
                commits.append(
                    CommitEvidence(
                        timestamp=call_timestamp,
                        commit=match.group(1),
                        subject=match.group(2).strip(),
                        workdir=workdir,
                        staged_paths=staged_paths(command),
                        files_changed=int(stat_match.group("files")) if stat_match else None,
                        insertions=int(stat_match.group("insertions")) if stat_match and stat_match.group("insertions") else None,
                        deletions=int(stat_match.group("deletions")) if stat_match and stat_match.group("deletions") else None,
                        call_type=call_type,
                        call_id=call_id,
                        command=command,
                    )
                )

    unique: dict[str, CommitEvidence] = {}
    for commit in commits:
        unique[commit.commit] = commit
    return sorted(unique.values(), key=lambda item: item.timestamp)


def write_outputs(commits: list[CommitEvidence], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "original-commit-index.json"
    tsv_path = output_dir / "original-commit-index.tsv"
    summary_path = output_dir / "original-commit-index.md"

    json_path.write_text(
        json.dumps([asdict(commit) for commit in commits], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            ["timestamp", "commit", "subject", "files_changed", "insertions", "deletions", "staged_paths"]
        )
        for commit in commits:
            writer.writerow(
                [
                    commit.timestamp,
                    commit.commit,
                    commit.subject,
                    commit.files_changed if commit.files_changed is not None else "",
                    commit.insertions if commit.insertions is not None else "",
                    commit.deletions if commit.deletions is not None else "",
                    " ".join(commit.staged_paths),
                ]
            )

    by_month: dict[str, int] = {}
    for commit in commits:
        month = commit.timestamp[:7]
        by_month[month] = by_month.get(month, 0) + 1
    lines = [
        "# Original NOOR Commit Evidence",
        "",
        f"Recorded commits: **{len(commits)}**",
        "",
        "## Coverage",
        "",
    ]
    lines.extend(f"- `{month}`: {count}" for month, count in sorted(by_month.items()))
    lines.extend(["", "## Latest Commits", ""])
    lines.extend(
        f"- `{commit.timestamp}` `{commit.commit}` {commit.subject}"
        for commit in commits[-25:]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rollout", type=Path)
    parser.add_argument("--cutoff", default="2026-08-09T17:05:00Z")
    parser.add_argument("--repo", default="/home/kinax/noor")
    parser.add_argument("--output-dir", type=Path, default=Path("forensics"))
    args = parser.parse_args()
    commits = read_commits(args.rollout, args.cutoff, args.repo)
    write_outputs(commits, args.output_dir)
    print(f"indexed {len(commits)} original commits")


if __name__ == "__main__":
    main()
