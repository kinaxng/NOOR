from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT


def sqlite_url_for_path(path: str | Path, *, async_driver: bool = True) -> str:
    driver = "sqlite+aiosqlite" if async_driver else "sqlite"
    return f"{driver}:///{Path(path)}"


def sqlite_db_path_from_url(database_url: str) -> Path | None:
    value = (database_url or "").strip()
    if not value:
        return None
    try:
        parsed = make_url(value)
    except Exception:
        return None
    if parsed.drivername not in {"sqlite", "sqlite+aiosqlite"}:
        return None
    raw_path = parsed.database or ""
    if raw_path in {"", ":memory:"}:
        return None
    return Path(raw_path)


def sqlite_database_score(path: Path) -> tuple[int, int, int]:
    if not path.exists() or not path.is_file():
        return (0, 0, 0)
    try:
        conn = sqlite3.connect(path)
        try:
            tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
            jobs = conn.execute("select count(*) from jobs").fetchone()[0] if "jobs" in tables else 0
            knowledge_entities = conn.execute("select count(*) from knowledge_entities").fetchone()[0] if "knowledge_entities" in tables else 0
            return (len(tables), int(jobs), int(knowledge_entities))
        finally:
            conn.close()
    except Exception:
        return (0, 0, 0)


def legacy_sqlite_candidates(project_root: Path = PROJECT_ROOT) -> list[Path]:
    return [project_root / "backend" / "noor.db", project_root / "noor.db"]


def prepare_sqlite_database(database_url: str, *, noor_data_dir: str | Path, project_root: Path = PROJECT_ROOT) -> str:
    target = sqlite_db_path_from_url(database_url)
    default_target = Path(noor_data_dir) / "noor.db"
    if target is None:
        return database_url
    if not target.is_absolute():
        target = (project_root / target).resolve()
    default_target = default_target.resolve()
    if target.resolve() != default_target:
        target.parent.mkdir(parents=True, exist_ok=True)
        return database_url
    candidates = [candidate for candidate in legacy_sqlite_candidates(project_root) if candidate.resolve() != target.resolve()]
    best_source = max(candidates, key=sqlite_database_score, default=None)
    target_score = sqlite_database_score(target)
    source_score = sqlite_database_score(best_source) if best_source else (0, 0, 0)
    target.parent.mkdir(parents=True, exist_ok=True)
    if best_source and best_source.exists() and source_score > target_score:
        if target.exists():
            target.replace(target.with_suffix(f".{int(time.time())}.bak"))
        shutil.copy2(best_source, target)
    return sqlite_url_for_path(target)
