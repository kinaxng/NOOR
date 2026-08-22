#!/usr/bin/env python3
"""Extract original Python/Vue symbols and routes recorded in a Codex rollout."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


PYTHON_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
ROUTE_RE = re.compile(r"^\s*@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)", re.MULTILINE)
VUE_FUNCTION_RE = re.compile(
    r"(?:^|\n)\s*(?:const|function)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:=\s*(?:async\s*)?\(|\()"
)


def text_value(value: Any) -> str:
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


def parse_arguments(payload: dict[str, Any]) -> tuple[str, str]:
    try:
        arguments = json.loads(str(payload.get("arguments") or "{}"))
    except json.JSONDecodeError:
        return "", ""
    return str(arguments.get("cmd") or ""), str(arguments.get("workdir") or "")


def matching_paths(text: str, targets: list[str]) -> list[str]:
    return [target for target in targets if target in text]


def patch_sections(patch: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^\*\*\* (?:Add|Update) File: (.+)$", patch, re.MULTILINE))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(patch)
        sections.append((match.group(1).strip(), patch[match.start():end]))
    return sections


def add_symbols(
    output: dict[str, dict[str, dict[str, str]]],
    path: str,
    text: str,
    timestamp: str,
    source: str,
) -> None:
    for name in PYTHON_DEF_RE.findall(text):
        output[path]["functions"][name] = {"timestamp": timestamp, "source": source}
    for method, route in ROUTE_RE.findall(text):
        key = f"{method.upper()} {route}"
        output[path]["routes"][key] = {"timestamp": timestamp, "source": source}
    if path.endswith(".vue"):
        for name in VUE_FUNCTION_RE.findall(text):
            output[path]["functions"][name] = {"timestamp": timestamp, "source": source}


def build_index(rollout: Path, targets: list[str], cutoff: str) -> dict[str, Any]:
    calls: dict[str, tuple[str, str, list[str]]] = {}
    symbols: dict[str, dict[str, dict[str, dict[str, str]]]] = defaultdict(
        lambda: {"functions": {}, "routes": {}}
    )

    with rollout.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = str(event.get("timestamp") or "")
            if cutoff and timestamp >= cutoff:
                continue
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload") or {}
            payload_type = payload.get("type")

            if payload_type == "function_call" and payload.get("name") == "exec_command":
                command, workdir = parse_arguments(payload)
                paths = matching_paths(command, targets)
                if paths:
                    calls[str(payload.get("call_id") or "")] = (timestamp, command, paths)
                continue

            if payload_type == "custom_tool_call" and payload.get("name") == "apply_patch":
                patch = str(payload.get("input") or "")
                for section_path, section in patch_sections(patch):
                    for path in targets:
                        if section_path.endswith(path):
                            add_symbols(symbols, path, section, timestamp, "patch")
                continue

            if payload_type != "function_call_output":
                continue
            call = calls.get(str(payload.get("call_id") or ""))
            if not call:
                continue
            call_timestamp, _command, paths = call
            output = text_value(payload.get("output"))
            if len(paths) == 1:
                add_symbols(symbols, paths[0], output, call_timestamp, "command_output")

    return {
        "cutoff": cutoff,
        "targets": {
            path: {
                "functions": sorted(value["functions"]),
                "routes": sorted(value["routes"]),
                "evidence": value,
            }
            for path, value in symbols.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rollout", type=Path)
    parser.add_argument("targets", nargs="+")
    parser.add_argument("--cutoff", default="2026-08-09T17:05:00Z")
    parser.add_argument("--output", type=Path, default=Path("forensics/original-symbol-index.json"))
    args = parser.parse_args()
    result = build_index(args.rollout, args.targets, args.cutoff)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, value in result["targets"].items():
        print(f"{path}: {len(value['functions'])} functions, {len(value['routes'])} routes")


if __name__ == "__main__":
    main()
