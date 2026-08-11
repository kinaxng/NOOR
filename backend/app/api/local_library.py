"""Local subtitle-library index API reconstructed from bytecode."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.settings_helpers import read_env_file, set_env_values


router = APIRouter(prefix="/api/local-library", tags=["local-library"])
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".sbv", ".sup"}
_index_lock = threading.Lock()
LOCAL_LIBRARY_PATHS_ENV = "LOCAL_LIBRARY_PATHS"
LOCAL_LIBRARY_INDEX_ENABLED_ENV = "LOCAL_LIBRARY_INDEX_ENABLED"
LOCAL_LIBRARY_MATCH_FUZZY_ENV = "LOCAL_LIBRARY_MATCH_FUZZY"


class ConfigRequest(BaseModel):
    config: dict


def _env_backed_config(env_data: dict[str, str]) -> dict:
    raw_library_paths = env_data.get(LOCAL_LIBRARY_PATHS_ENV, "")
    if raw_library_paths.startswith("["):
        try:
            path_items = json.loads(raw_library_paths)
            if isinstance(path_items, list):
                raw_library_paths = "\n".join(str(item) for item in path_items if str(item).strip())
        except Exception:
            pass
    return {"library_paths": raw_library_paths, "index_enabled": env_data.get(LOCAL_LIBRARY_INDEX_ENABLED_ENV, "false").lower() == "true", "match_fuzzy": env_data.get(LOCAL_LIBRARY_MATCH_FUZZY_ENV, "false").lower() == "true"}


def _load_config() -> dict:
    return _env_backed_config(read_env_file())


def _save_config(config: dict) -> None:
    raw_paths = str(config.get("library_paths", "") or "")
    path_items = [line.strip() for line in raw_paths.splitlines() if line.strip()]
    set_env_values({LOCAL_LIBRARY_PATHS_ENV: json.dumps(path_items, ensure_ascii=False), LOCAL_LIBRARY_INDEX_ENABLED_ENV: "true" if bool(config.get("index_enabled", False)) else "false", LOCAL_LIBRARY_MATCH_FUZZY_ENV: "true" if bool(config.get("match_fuzzy", False)) else "false"})


def _index_db_path() -> Path:
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "subtitle_index.db"


def _get_library_paths(config: dict) -> list[str]:
    raw = config.get("library_paths", "")
    if not raw:
        return []
    return [item.strip() for item in raw.strip().split("\n") if item.strip() and os.path.isdir(item.strip())]


def _build_index(config: dict, force: bool = False) -> tuple[int, float]:
    start = time.time()
    paths = _get_library_paths(config)
    if not paths:
        return 0, 0.0
    db_path = _index_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subtitle_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_name TEXT NOT NULL,
            full_path TEXT UNIQUE NOT NULL,
            ext TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    if not force:
        cur.execute("SELECT COUNT(*) FROM subtitle_index")
        existing = cur.fetchone()[0]
        if existing > 0:
            conn.close()
            return existing, time.time() - start
    cur.execute("DELETE FROM subtitle_index")
    now, count = time.time(), 0
    for lib_path in paths:
        for root, _, files in os.walk(lib_path):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in SUBTITLE_EXTS:
                    continue
                base_name = os.path.splitext(filename)[0].lower()
                full_path = os.path.join(root, filename)
                try:
                    cur.execute("INSERT OR IGNORE INTO subtitle_index (base_name, full_path, ext, updated_at) VALUES (?, ?, ?, ?)", (base_name, full_path, ext, now))
                    count += 1
                except sqlite3.IntegrityError:
                    continue
    conn.commit()
    conn.close()
    return count, time.time() - start


def _index_stats(config: dict) -> dict:
    db_path = _index_db_path()
    if not os.path.exists(db_path):
        return {"exists": False, "count": 0, "indexed_count": 0, "index_updated_at": None}
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM subtitle_index")
        count = cur.fetchone()[0]
        cur.execute("SELECT MAX(updated_at) FROM subtitle_index")
        updated = cur.fetchone()[0]
        conn.close()
        return {"exists": True, "count": count, "indexed_count": count, "index_updated_at": updated}
    except Exception:
        conn.close()
        return {"exists": False, "count": 0, "indexed_count": 0, "index_updated_at": None}


def _match(subtitle_base: str, video_base: str, fuzzy: bool) -> bool:
    sub, vid = subtitle_base.lower(), video_base.lower()
    if sub == vid:
        return True
    if fuzzy:
        return sub in vid or (len(sub) >= 8 and vid.startswith(sub[:8]))
    return False


def _detect_language(filepath: str) -> str:
    name_lower = os.path.basename(filepath).lower()
    if re.search(r"[中港台澳]", name_lower):
        return "zh"
    if re.search(r"[日韩]", name_lower):
        return "ja"
    return "unknown"


def _result(filename: str, ext: str, full_path: str) -> dict:
    return {"id": f"local:{filename}:{full_path}", "filename": filename, "ext": ext, "language": _detect_language(full_path), "source": "本地字幕库", "source_key": "local_library", "source_type": "local_library", "url": full_path, "score": 1.0}


def search_local_library_with_config(video_code: str, config: dict, video_path: str = "") -> list[dict]:
    fuzzy, index_enabled = config.get("match_fuzzy", False), config.get("index_enabled", False)
    video_name_lower = video_code.lower()
    results: list[dict] = []
    lib_paths = _get_library_paths(config)
    if index_enabled and lib_paths:
        db_path = _index_db_path()
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT base_name, full_path, ext FROM subtitle_index WHERE base_name = ?", (video_name_lower,))
            rows = cur.fetchall()
            conn.close()
            for _, full_path, ext in rows:
                results.append(_result(os.path.basename(full_path), ext, full_path))
    elif lib_paths:
        for lib_path in lib_paths:
            if not os.path.isdir(lib_path):
                continue
            for root, _, files in os.walk(lib_path):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in SUBTITLE_EXTS:
                        continue
                    base = os.path.splitext(filename)[0].lower()
                    if _match(base, video_name_lower, fuzzy):
                        results.append(_result(filename, ext, os.path.join(root, filename)))
    return list({result["id"]: result for result in results}.values())


def search_local_library(video_code: str, video_path: str = "") -> list[dict]:
    return search_local_library_with_config(video_code, _load_config(), video_path=video_path)


@router.get("/config")
async def get_config():
    return {"config": _load_config()}


@router.post("/config")
async def save_config(body: ConfigRequest):
    _save_config(body.config)
    return {"ok": True}


@router.post("/index/rebuild")
async def rebuild_index():
    config = _load_config()
    with _index_lock:
        count, elapsed = _build_index(config, force=True)
    return {"indexed_files": count, "elapsed_seconds": round(elapsed, 2)}


@router.get("/index/status")
async def index_status():
    config = _load_config()
    stats = _index_stats(config)
    lib_paths = _get_library_paths(config)
    return {"index_exists": stats["exists"], "indexed_count": stats["indexed_count"], "index_updated_at": stats["index_updated_at"], "configured_paths": lib_paths, "index_enabled": config.get("index_enabled", False)}
