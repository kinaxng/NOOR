#!/usr/bin/env python3
"""Extract Vite source-map sourcesContent from a raw image."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re


MARKER = b"//# sourceMappingURL=data:application/json;base64,"


def read_source_map(raw_path: str, offset: int) -> dict | None:
    with open(raw_path, "rb") as raw:
        raw.seek(offset + len(MARKER))
        payload = raw.read(3_000_000)
    match = re.match(rb"[A-Za-z0-9+/=]+", payload)
    if not match:
        return None
    encoded = match.group(0)
    encoded += b"=" * ((4 - len(encoded) % 4) % 4)
    try:
        return json.loads(base64.b64decode(encoded))
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw")
    parser.add_argument("offsets")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    output = pathlib.Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    offsets = [
        int(line.split(":", 1)[0])
        for line in pathlib.Path(args.offsets).read_text().splitlines()
        if line.strip() and ":" in line
    ]
    print(f"offsets {len(offsets)}", flush=True)
    for offset in offsets:
        try:
            source_map = read_source_map(args.raw, offset)
            if not source_map:
                print(f"FAIL {offset} parse", flush=True)
                continue
            sources = source_map.get("sources", [])
            contents = source_map.get("sourcesContent", [])
            if not sources or not contents:
                print(f"SKIP {offset} no contents", flush=True)
                continue
            candidates = [
                (source, content)
                for source, content in zip(sources, contents)
                if content
                and (
                    "noor" in source.lower()
                    or source.endswith(".vue")
                    or source.endswith(".ts")
                    or source.endswith(".js")
                )
            ]
            if not candidates:
                print(f"SKIP {offset} not noor", flush=True)
                continue
            digest = hashlib.sha1(str(offset).encode()).hexdigest()[:12]

            for source, content in candidates:
                name = pathlib.Path(source).name
                safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
                target = output / f"{digest}-{safe_name}"
                target.write_text(content, encoding="utf-8")
                print(f"SAVED {offset} {source} {len(content)} {target}", flush=True)
        except Exception as exc:
            print(f"FAIL {offset} {exc!r}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
