#!/usr/bin/env python3
"""Scan a raw block device/image for Git pack headers and log offsets."""
from __future__ import annotations

import argparse
from pathlib import Path

SIG = b"PACK\x00\x00\x00\x02"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--chunk", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--progress", type=int, default=32 * 1024 * 1024 * 1024)
    args = parser.parse_args()

    found: list[int] = []
    last_progress = 0
    with open(args.path, "rb") as f:
        off = 0
        while True:
            data = f.read(args.chunk)
            if not data:
                break
            pos = 0
            while True:
                idx = data.find(SIG, pos)
                if idx < 0:
                    break
                found.append(off + idx)
                print(off + idx, flush=True)
                pos = idx + 1
            off += len(data)
            if off - last_progress >= args.progress:
                print(f"SCANNED {off} PACKS {len(found)}", flush=True)
                last_progress = off
    print(f"DONE {len(found)}", flush=True)


if __name__ == "__main__":
    main()
