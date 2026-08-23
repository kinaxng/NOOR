#!/usr/bin/env python3
"""Extract unique unified-diff evidence from the original NOOR rollout.

The rollout contains many full ``git diff`` outputs inside tool-call responses.
This script archives each unique diff section under
``forensics/recovered-sources/session-diffs/`` and records an index. With
``--check-current`` it also runs ``git apply --reverse --check`` against the
current tree, which is a strong signal that the current file already contains
the change described by that diff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROLLOUT = ROOT / "/home/kinax/.codex/sessions/2026/06/08/rollout-2026-06-08T16-08-55-019ea647-0e81-7d81-9b62-558364a36e3f.jsonl"
DEFAULT_OUTPUT = ROOT / "forensics" / "recovered-sources" / "session-diffs"
ORIGIN_PREFIXES = ("backend/", "frontend/", "plugins/", "docs/", "forensics/")
ORIGIN_FILES = {"README.md", "DOCKER.md", ".dockerignore", ".env.example"}
DIFF_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)


def section_path(section: str) -> str | None:
    m = DIFF_RE.search(section)
    if not m:
        return None
    path = m.group(1)
    if not path.startswith(ORIGIN_PREFIXES) and path not in ORIGIN_FILES:
        return None
    return path


def collect_sections(rollout: Path, cutoff: str) -> list[dict]:
    sections: list[dict] = []
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
            if payload.get("type") not in ("function_call_output", "custom_tool_call_output"):
                continue
            output = str(payload.get("output") or "")
            if "diff --git a/" not in output:
                continue
            for part in re.split(r"(?m)^(?=diff --git a/)", output):
                path = section_path(part)
                if not path:
                    continue
                sections.append(
                    {
                        "timestamp": timestamp,
                        "path": path,
                        "content": part,
                    }
                )
    return sections


def safe_name(path: str) -> str:
    return path.replace("/", "__")


def reverse_check(workdir: Path, diff_file: Path) -> dict:
    result = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(diff_file)],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "error": result.stderr.strip()[:500],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollout", type=Path, default=DEFAULT_ROLLOUT)
    parser.add_argument("--cutoff", default="2026-08-10T00:00:00Z")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-current", action="store_true")
    args = parser.parse_args()

    sections = collect_sections(args.rollout, args.cutoff)
    seen: set[str] = set()
    unique: list[dict] = []
    by_path: Counter[str] = Counter()
    for section in sections:
        sha = hashlib.sha256(section["content"].encode("utf-8")).hexdigest()
        if sha in seen:
            continue
        seen.add(sha)
        by_path[section["path"]] += 1
        unique.append({**section, "sha256": sha})

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for item in unique:
        name = f"{item['sha256'][:12]}-{safe_name(item['path'])}.diff"
        diff_file = output_dir / name
        diff_file.write_text(item["content"], encoding="utf-8")
        entry = {
            "sha256": item["sha256"],
            "path": item["path"],
            "first_timestamp": item["timestamp"],
            "bytes": len(item["content"].encode("utf-8")),
            "diff_file": f"session-diffs/{name}",
        }
        if args.check_current:
            entry["reverse_check"] = reverse_check(ROOT, diff_file)
        manifest.append(entry)

    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "rollout": str(args.rollout),
                "cutoff": args.cutoff,
                "total_sections": len(sections),
                "unique_sections": len(unique),
                "paths": len(by_path),
                "entries": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"sections={len(sections)} unique={len(unique)} paths={len(by_path)} output={output_dir}")


if __name__ == "__main__":
    main()
