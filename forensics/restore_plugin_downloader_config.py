#!/usr/bin/env python3
"""Restore downloader runtime config from preserved original evidence snapshots.

This script keeps credentials out of the script itself by reading the original
read snapshots under forensics/recovered-sources/original-read-snapshots. It is
meant for local recovery only; data/plugins_config.json and plugins_state.json
are ignored by Git on purpose.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "data" / "plugins_config.json"
STATE_FILE = ROOT / "data" / "plugins_state.json"
QB_SNAPSHOT = ROOT / "forensics/recovered-sources/original-read-snapshots/2026-06-24T1845_f5013144_data__plugins_config.json_64-74.txt"
XUNLEI_SNAPSHOT = ROOT / "forensics/recovered-sources/original-read-snapshots/2026-07-25T1732_446fd55d_data__plugins_config.json_96-132.txt"


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot_value(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\\\]|\\\\.)*)"', text)
    return match.group(1) if match else ""


def main() -> None:
    config = read_json(CONFIG_FILE)
    state = read_json(STATE_FILE)

    qb = config.setdefault("qbittorrent", {})
    if QB_SNAPSHOT.exists():
        qb.update({
            "base_url": snapshot_value(QB_SNAPSHOT, "base_url"),
            "username": snapshot_value(QB_SNAPSHOT, "username"),
            "password": snapshot_value(QB_SNAPSHOT, "password"),
            "api_key": snapshot_value(QB_SNAPSHOT, "api_key"),
            "category": snapshot_value(QB_SNAPSHOT, "category") or "默认",
            "savepath": snapshot_value(QB_SNAPSHOT, "savepath") or "/downloads",
            "noor_tag": qb.get("noor_tag") or "noor",
            "show_noor_only": bool(qb.get("show_noor_only")),
            "min_file_size_mb": int(qb.get("min_file_size_mb") or 0),
        })

    subscription = config.setdefault("subscription-core", {})
    subscription["default_savepath"] = "/volume1/data/downloads/av/"

    xunlei = config.setdefault("xunlei-remote", {})
    if XUNLEI_SNAPSHOT.exists():
        xunlei["base_url"] = snapshot_value(XUNLEI_SNAPSHOT, "base_url") or xunlei.get("base_url", "")
        xunlei["savepath"] = snapshot_value(XUNLEI_SNAPSHOT, "savepath") or xunlei.get("savepath", "")
        xunlei["insecure_skip_verify"] = True
        xunlei["timeout"] = 30

    state.setdefault("qbittorrent", {})["enabled"] = True

    write_json(CONFIG_FILE, config)
    write_json(STATE_FILE, state)
    print(f"restored qbittorrent={bool(qb.get('base_url'))} subscription_savepath={subscription['default_savepath']} xunlei_base_url={bool(xunlei.get('base_url'))}")


if __name__ == "__main__":
    main()
