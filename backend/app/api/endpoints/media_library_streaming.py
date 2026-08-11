"""HTTP range parsing and streaming helpers for local media previews.

Reconstructed from the preserved media-library router bytecode.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException


STREAM_CHUNK_SIZE = 1024 * 1024


def parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None
    match = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
    if not match:
        raise HTTPException(status_code=416, detail="无效的 Range 请求")
    start_raw, end_raw = match.groups()
    if not start_raw and not end_raw:
        raise HTTPException(status_code=416, detail="无效的 Range 请求")
    if start_raw:
        start = int(start_raw)
        end = int(end_raw) if end_raw else file_size - 1
    else:
        length = int(end_raw)
        if length <= 0:
            raise HTTPException(status_code=416, detail="无效的 Range 请求")
        start = max(file_size - length, 0)
        end = file_size - 1
    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Range 超出文件范围")
    end = min(end, file_size - 1)
    return start, end


def iter_file_range(target: Path, start: int, end: int, *, chunk_size: int = STREAM_CHUNK_SIZE) -> Iterator[bytes]:
    with target.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
