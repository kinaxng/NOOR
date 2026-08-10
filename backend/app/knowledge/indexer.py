from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.repository import KnowledgeRepository


async def rebuild_knowledge_index(db: AsyncSession, *, max_items: int | None = None, run_id: str | None = None) -> dict:
    """Finalize a rebuild run without fabricating external-library data.

    Media and plugin source adapters are restored separately; existing knowledge
    rows remain valid and this endpoint records an honest zero-source rebuild
    until those adapters are available.
    """
    repo = KnowledgeRepository(db)
    run = await repo.latest_run() if run_id else None
    stats = {'phase': 'completed', 'processed': 0, 'total': max_items or 0, 'reason': 'source adapters pending recovery'}
    if run:
        await repo.finish_run(run, 'completed', 'Knowledge rebuild completed with available sources', stats)
    return stats
