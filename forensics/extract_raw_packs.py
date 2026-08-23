#!/usr/bin/env python3
"""Extract valid Git packs from a raw disk scan and match NOOR commits."""

from __future__ import annotations

import argparse
import os
import pathlib
import signal
import struct
import subprocess
import zlib


def read_varint(f) -> bytes:
    header = b""
    while True:
        byte = f.read(1)
        if not byte:
            raise EOFError("varint header eof")
        header += byte
        if not (byte[0] & 0x80):
            return header


def pack_meta(f, offset: int) -> tuple[int, int, int] | None:
    f.seek(offset)
    head = f.read(12)
    if head[:4] != b"PACK":
        return None
    version, count = struct.unpack(">II", head[4:12])
    if version not in (2, 3) or count <= 0 or count > 5_000_000:
        return None
    header = read_varint(f)
    obj_type = (header[0] >> 4) & 7
    if obj_type not in (1, 2, 3, 4, 6, 7):
        return None
    return version, count, obj_type


def pack_length(f, offset: int) -> int:
    f.seek(offset)
    head = f.read(12)
    _, count = struct.unpack(">II", head[4:12])
    for obj in range(count):
        header = read_varint(f)
        first = header[0]
        obj_type = (first >> 4) & 7
        size = first & 15
        shift = 4
        for byte in header[1:]:
            size |= (byte & 0x7F) << shift
            shift += 7
        if obj_type == 6:
            while True:
                byte = f.read(1)
                if not byte:
                    raise EOFError("delta offset eof")
                if not (byte[0] & 0x80):
                    break
        elif obj_type == 7:
            if len(f.read(20)) != 20:
                raise EOFError("base sha eof")
        start = f.tell()
        decompressor = zlib.decompressobj()
        output = b""
        consumed = 0
        read_bytes = 0
        while len(output) < size or not decompressor.eof:
            chunk = f.read(1 << 20)
            if not chunk:
                raise EOFError(f"zlib eof obj {obj} size {size} got {len(output)}")
            read_bytes += len(chunk)
            if read_bytes > 64 * 1024 * 1024:
                raise ValueError(f"object {obj} compressed data exceeds 64MiB")
            output += decompressor.decompress(chunk)
            if decompressor.unused_data:
                consumed = len(chunk) - len(decompressor.unused_data)
                break
            consumed = len(chunk)
        f.seek(start + consumed)
    if len(f.read(20)) != 20:
        raise EOFError("trailer eof")
    return f.tell() - offset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", help="raw device or image")
    parser.add_argument("scan_log", help="pack offset log")
    parser.add_argument("output_dir")
    parser.add_argument("--original-hashes", default="/tmp/original-commit-hashes.txt")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    original_prefixes = []
    for line in pathlib.Path(args.original_hashes).read_text().splitlines():
        if line.strip():
            original_prefixes.append(line.split("\t")[0])

    offsets = sorted(
        {
            int(line)
            for line in pathlib.Path(args.scan_log).read_text().splitlines()
            if line.strip().isdigit()
        }
    )
    print(f"offsets {len(offsets)}", flush=True)
    with open(args.raw, "rb") as raw_file:
        for offset in offsets:
            pack_path = output_dir / f"pack-{offset}.pack"
            if pack_path.exists() and pack_path.with_suffix(".idx").exists():
                print(f"SKIP {offset}", flush=True)
                continue
            signal.alarm(120)
            try:
                meta = pack_meta(raw_file, offset)
                if meta is None:
                    print(f"FALSE {offset}", flush=True)
                    continue
                length = pack_length(raw_file, offset)
                raw_file.seek(offset)
                with pack_path.open("wb") as out:
                    remaining = length
                    while remaining:
                        buf = raw_file.read(min(1 << 20, remaining))
                        if not buf:
                            raise EOFError("extract eof")
                        out.write(buf)
                        remaining -= len(buf)
                result = subprocess.run(
                    ["git", "index-pack", str(pack_path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    print(f"INDEXFAIL {offset} {length} {result.stderr.strip()[:300]}", flush=True)
                    continue
                verify = subprocess.run(
                    ["git", "verify-pack", "-v", str(pack_path) + ".idx"],
                    capture_output=True,
                    text=True,
                ).stdout
                commits = [
                    parts[0]
                    for parts in (line.split() for line in verify.splitlines())
                    if len(parts) >= 3 and parts[2] == "commit"
                ]
                matches = [
                    commit
                    for commit in commits
                    if any(commit.startswith(prefix) for prefix in original_prefixes)
                ]
                print(
                    f"INDEXED {offset} meta {meta} length {length} "
                    f"commits {len(commits)} matches {','.join(matches)}",
                    flush=True,
                )
            except Exception as exc:
                print(f"FAIL {offset} {exc!r}", flush=True)
            finally:
                signal.alarm(0)
    print("EXTRACT_DONE", flush=True)


if __name__ == "__main__":
    main()
