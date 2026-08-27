"""Database engine, sessions, and lightweight schema compatibility migration.

Reconstructed from the preserved Python 3.13 bytecode.  The migration only
adds columns that are absent from legacy ``jobs`` tables.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings
from app.core.database_paths import prepare_sqlite_database


settings = get_settings()
database_url = prepare_sqlite_database(settings.database_url, noor_data_dir=settings.noor_data_dir)
engine = create_async_engine(database_url, echo=False)
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)
_sync_url = database_url.replace("+aiosqlite", "")
_sync_engine = create_engine(_sync_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_jobs_schema)


async def get_db():
    async with async_session_maker() as session:
        yield session


def _ensure_jobs_schema(sync_conn) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    columns = (
        {column["name"] for column in inspector.get_columns("jobs")}
        if "jobs" in inspector.get_table_names()
        else set()
    )
    alterations: list[str] = []
    if "phase_key" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN phase_key VARCHAR(64)")
    if "phase_label" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN phase_label VARCHAR(128)")
    if "phase_progress" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN phase_progress INTEGER")
    if "detail" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN detail TEXT")
    if "chain_id" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN chain_id VARCHAR(36)")
    if "depends_on_task_id" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN depends_on_task_id VARCHAR(36)")
    if "parent_task_id" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN parent_task_id VARCHAR(36)")
    if "result_metadata" not in columns:
        alterations.append("ALTER TABLE jobs ADD COLUMN result_metadata JSON")
    for statement in alterations:
        sync_conn.execute(text(statement))
