#!/usr/bin/env python3
"""Generate a file-level NOOR restore gap report from the original commit index.

The report is intentionally conservative: it does not claim byte-for-byte
restoration. It records which original paths were touched most often, whether
they exist in the restored tree, and which ones have already been verified or
are intentionally different.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "forensics" / "original-commit-index.json"
OUTPUT = ROOT / "forensics" / "version-gap-audit.md"

VERIFIED = {
    "backend/app/plugins/runtime.py",
    "backend/app/api/settings_facefusion_upgrade.py",
    "backend/app/api/endpoints/media_library_helpers.py",
    "backend/tests/test_facefusion_upgrade.py",
    "plugins/qbittorrent/plugin.json",
    "plugins/av-recommend",
    "plugins/subscription-core/frontend/page.js",
    "plugins/xunlei-remote/backend.py",
    "plugins/xunlei-remote/frontend/page.js",
    "plugins/xunlei-remote/plugin.json",
    "frontend/src/components/noor/FaceFusionPanel.vue",
    "frontend/src/components/noor/LadaPanel.vue",
    "frontend/src/views/ActorDetailView.vue",
    "frontend/src/views/ActorManagementView.vue",
    "frontend/src/views/Home.vue",
    "frontend/src/views/PluginManager.vue",
    "frontend/src/views/ResourceSearch.vue",
    "frontend/src/views/settings/FaceFusionSettings.vue",
    "frontend/src/views/settings/StorageSettings.vue",
    "frontend/src/views/settings/SystemSettings.vue",
    "frontend/src/components/noor/MediaCard.vue",
    "frontend/src/components/noor/SubtitlePanel.vue",
    "frontend/src/i18n/en.ts",
    "frontend/src/i18n/zh.ts",
}

INTENTIONAL = {
    "backend/app/api/endpoints/media_library.py",
    "backend/app/pipeline/whisper/decoupled/anime_qwen3_chain.py",
    "backend/app/pipeline/whisper/decoupled/qwen3.py",
    "backend/app/pipeline/whisper/enhancer.py",
    "backend/app/pipeline/whisper/preprocess.py",
    "backend/tests/test_whisper_preprocess.py",
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "DOCKER.md",
    "docker-compose.yml",
    "README.md",
    "docs/DEV_DOCKER_ALIGNMENT.md",
}

ORIGIN_PREFIXES = ("backend/", "frontend/", "plugins/", "forensics/")


def git_last_subject(path: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%h %s", "--", path],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or "-"
    except subprocess.CalledProcessError:
        return "-"


def main() -> None:
    commits = json.loads(INDEX.read_text())
    touched: dict[str, list[dict]] = defaultdict(list)
    for commit in commits:
        for path in commit.get("staged_paths") or []:
            touched[path].append(
                {
                    "timestamp": commit.get("timestamp", ""),
                    "commit": str(commit.get("commit", ""))[:10],
                    "subject": commit.get("subject", ""),
                }
            )

    rows = []
    for path, entries in touched.items():
        if not path.startswith(ORIGIN_PREFIXES):
            continue
        last = max(entries, key=lambda item: item["timestamp"])
        exists = (ROOT / path).exists()
        if path in VERIFIED:
            state = "verified"
        elif path in INTENTIONAL or not exists:
            state = "intentional" if path in INTENTIONAL else "missing"
        else:
            state = "pending"
        rows.append(
            {
                "path": path,
                "count": len(entries),
                "last": last,
                "exists": exists,
                "state": state,
                "current": git_last_subject(path) if exists else "-",
            }
        )

    rank = {"missing": 0, "pending": 1, "intentional": 2, "verified": 3}
    rows.sort(key=lambda item: (rank[item["state"]], -item["count"], item["path"]))

    lines = [
        "# NOOR 文件级恢复差距清单",
        "",
        "更新时间：2026-08-23",
        "",
        "本清单由 `forensics/version_gap_audit.py` 从 `forensics/original-commit-index.json` 生成。",
        "它用于追踪原版历史中改过的路径在恢复树里的状态，不能替代行为/路由/字节级验证。",
        "",
        "## 状态说明",
        "",
        "- `verified`：已按原版会话/运行契约核对。",
        "- `pending`：文件存在，但尚未完成最终原版逐版本核对。",
        "- `missing`：原版历史中出现，但当前恢复树没有对应路径。",
        "- `intentional`：按用户后续要求或恢复策略有意不复原/改为不同实现。",
        "",
        "## 清单",
        "",
        "| 路径 | 原版提交数 | 状态 | 原版最后提交 | 当前最后提交 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{}` | {} | {} | {} | {} |".format(
                row["path"],
                row["count"],
                row["state"],
                f"{row['last']['commit']} {row['last']['subject']}",
                row["current"],
            )
        )
    lines.append("")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    summary = {
        state: sum(1 for row in rows if row["state"] == state)
        for state in ("verified", "pending", "missing", "intentional")
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
