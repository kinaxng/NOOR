from __future__ import annotations

import sqlite3

from app.core.database_paths import prepare_sqlite_database, sqlite_database_score, sqlite_db_path_from_url


def _make_db(path, *, jobs: int = 0, knowledge_entities: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("create table jobs (id text)")
        for index in range(jobs):
            conn.execute("insert into jobs (id) values (?)", (f"job-{index}",))
        if knowledge_entities:
            conn.execute("create table knowledge_entities (id text)")
            for index in range(knowledge_entities):
                conn.execute("insert into knowledge_entities (id) values (?)", (f"entity-{index}",))
        conn.commit()
    finally:
        conn.close()


def test_sqlite_db_path_from_url_handles_relative_and_absolute_paths():
    assert sqlite_db_path_from_url("sqlite+aiosqlite:///./noor.db").as_posix() == "noor.db"
    assert sqlite_db_path_from_url("sqlite+aiosqlite:////tmp/noor.db").as_posix() == "/tmp/noor.db"
    assert sqlite_db_path_from_url("postgresql+asyncpg://db/noor") is None


def test_prepare_sqlite_database_copies_stronger_legacy_database(tmp_path):
    target = tmp_path / "data" / "noor.db"
    legacy = tmp_path / "backend" / "noor.db"
    _make_db(target, jobs=1)
    _make_db(legacy, jobs=10, knowledge_entities=3)

    url = prepare_sqlite_database(
        f"sqlite+aiosqlite:///{target}",
        noor_data_dir=tmp_path / "data",
        project_root=tmp_path,
    )

    assert url == f"sqlite+aiosqlite:///{target}"
    assert sqlite_database_score(target) == (2, 10, 3)
    assert list((tmp_path / "data").glob("noor.*.bak"))


def test_prepare_sqlite_database_keeps_explicit_non_default_database(tmp_path):
    explicit = tmp_path / "custom" / "noor.db"
    legacy = tmp_path / "backend" / "noor.db"
    _make_db(legacy, jobs=10, knowledge_entities=3)

    prepare_sqlite_database(
        f"sqlite+aiosqlite:///{explicit}",
        noor_data_dir=tmp_path / "data",
        project_root=tmp_path,
    )

    assert not explicit.exists()
