#!/usr/bin/env python3
"""Extract original NOOR frontend sources embedded in cached Vite source maps."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SOURCE_MAP_RE = re.compile(
    rb"sourceMappingURL=data:application/json(?:;charset=[^;,]+)?;base64,([A-Za-z0-9+/=]+)"
)
NOOR_SOURCE_PREFIXES = (
    "/home/kinax/noor/frontend/",
    "/home/kinax/noor/frontend_rewrite/",
)


@dataclass(frozen=True)
class Candidate:
    source_path: str
    cache_file: str
    cache_mtime: float
    content_sha256: str
    content_size: int
    line_count: int
    complete_vue: bool
    output_file: str


def source_path_for(source_map: dict[str, Any], source: str) -> str:
    file_name = str(source_map.get("file") or "")
    for prefix in NOOR_SOURCE_PREFIXES:
        if file_name.startswith(prefix):
            return file_name.removeprefix(prefix)
    source = str(source or "").replace("\\", "/")
    marker = "frontend/"
    if marker in source:
        return source.split(marker, 1)[1]
    return source.lstrip("./")


def safe_candidate_name(cache_file: Path, index: int, source_path: str) -> str:
    suffix = Path(source_path).suffix or ".txt"
    return f"{cache_file.stem}-{index}{suffix}"


def decode_source_map(encoded: bytes) -> dict[str, Any] | None:
    # Chrome's disk cache can append a few metadata bytes immediately after
    # the inline source map. Trim only the tail until a complete JSON map is
    # recovered instead of rejecting the otherwise intact source payload.
    for trim in range(65):
        candidate = encoded[:-trim] if trim else encoded
        if not candidate:
            break
        try:
            decoded = base64.b64decode(candidate, validate=True)
            source_map = json.loads(decoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(source_map, dict):
            return source_map
    return None


def belongs_to_noor(source_map: dict[str, Any]) -> bool:
    file_name = str(source_map.get("file") or "").replace("\\", "/")
    sources = [str(source).replace("\\", "/") for source in source_map.get("sources") or []]
    return any(file_name.startswith(prefix) for prefix in NOOR_SOURCE_PREFIXES) or any(
        source.startswith(prefix)
        for source in sources
        for prefix in NOOR_SOURCE_PREFIXES
    )


def extract(cache_dir: Path, output_dir: Path) -> list[Candidate]:
    candidates_dir = output_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Candidate] = []

    for cache_file in sorted(cache_dir.glob("*_0")):
        try:
            payload = cache_file.read_bytes()
        except OSError:
            continue
        match = SOURCE_MAP_RE.search(payload)
        if not match:
            continue
        source_map = decode_source_map(match.group(1))
        if source_map is None or not belongs_to_noor(source_map):
            continue
        sources = source_map.get("sources") or []
        contents = source_map.get("sourcesContent") or []
        if not isinstance(sources, list) or not isinstance(contents, list):
            continue
        for index, (source, content) in enumerate(zip(sources, contents)):
            if not isinstance(content, str) or not content.strip():
                continue
            source_path = source_path_for(source_map, str(source))
            if not source_path.startswith("src/"):
                continue
            encoded = content.encode("utf-8")
            candidate_name = safe_candidate_name(cache_file, index, source_path)
            candidate_path = candidates_dir / candidate_name
            candidate_path.write_bytes(encoded)
            candidates.append(
                Candidate(
                    source_path=source_path,
                    cache_file=str(cache_file),
                    cache_mtime=cache_file.stat().st_mtime,
                    content_sha256=hashlib.sha256(encoded).hexdigest(),
                    content_size=len(encoded),
                    line_count=content.count("\n") + 1,
                    complete_vue=(
                        source_path.endswith(".vue")
                        and "<script" in content
                        and "<template" in content
                        and "<style" in content
                    ),
                    output_file=str(candidate_path),
                )
            )
    return candidates


def choose_latest(candidates: list[Candidate]) -> dict[str, Candidate]:
    selected: dict[str, Candidate] = {}
    for candidate in candidates:
        current = selected.get(candidate.source_path)
        rank = (candidate.complete_vue, candidate.cache_mtime, candidate.content_size)
        if current is None:
            selected[candidate.source_path] = candidate
            continue
        current_rank = (current.complete_vue, current.cache_mtime, current.content_size)
        if rank > current_rank:
            selected[candidate.source_path] = candidate
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    candidates = extract(args.cache_dir, args.output_dir)
    selected = choose_latest(candidates)
    latest_dir = args.output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    selected_rows = []
    for source_path, candidate in sorted(selected.items()):
        destination = latest_dir / source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(candidate.output_file).read_bytes())
        selected_rows.append({**asdict(candidate), "latest_file": str(destination)})

    manifest = {
        "cache_dir": str(args.cache_dir),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "candidates": [asdict(candidate) for candidate in candidates],
        "selected": selected_rows,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"candidates={len(candidates)} selected={len(selected)}")


if __name__ == "__main__":
    main()
