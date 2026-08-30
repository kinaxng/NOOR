from __future__ import annotations

from app.core.database import _configure_sqlite_connection


def test_sqlite_connections_enable_concurrent_runtime_pragmas() -> None:
    statements: list[str] = []

    class Cursor:
        def execute(self, statement: str) -> None:
            statements.append(statement)

        def close(self) -> None:
            statements.append("CLOSE")

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

    _configure_sqlite_connection(Connection())

    assert statements == [
        "PRAGMA busy_timeout=15000",
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA foreign_keys=ON",
        "CLOSE",
    ]
