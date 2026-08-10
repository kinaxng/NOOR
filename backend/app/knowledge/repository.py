from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import utcnow
from app.knowledge.models import (
    KnowledgeActionState,
    KnowledgeAnomaly,
    KnowledgeEdge,
    KnowledgeEntity,
    KnowledgeIndexRun,
    KnowledgeScore,
    stable_id,
)


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return await self.db.get(KnowledgeEntity, entity_id)

    async def upsert_entity(self, entity_type: str, key: str, label: str, **values: Any) -> KnowledgeEntity:
        entity_id = stable_id('entity', entity_type, key)
        entity = await self.db.get(KnowledgeEntity, entity_id)
        if entity is None:
            entity = KnowledgeEntity(id=entity_id, entity_type=entity_type, key=key, label=label, **values)
            self.db.add(entity)
        else:
            entity.label = label
            for name, value in values.items():
                setattr(entity, name, value)
        return entity

    async def upsert_edge(self, source_entity_id: str, target_entity_id: str, relation_type: str, source: str = 'knowledge-core', **values: Any) -> KnowledgeEdge:
        edge_id = stable_id('edge', source_entity_id, target_entity_id, relation_type, source)
        edge = await self.db.get(KnowledgeEdge, edge_id)
        if edge is None:
            edge = KnowledgeEdge(id=edge_id, source_entity_id=source_entity_id, target_entity_id=target_entity_id, relation_type=relation_type, source=source, **values)
            self.db.add(edge)
        else:
            for name, value in values.items():
                setattr(edge, name, value)
        return edge

    async def search(self, q: str, *, entity_type: str | None = None, filter_kind: str | None = None, limit: int = 30) -> list[KnowledgeEntity]:
        stmt = select(KnowledgeEntity)
        if entity_type:
            stmt = stmt.where(KnowledgeEntity.entity_type == entity_type)
        if q.strip():
            like = f'%{q.strip().lower()}%'
            stmt = stmt.where(or_(func.lower(KnowledgeEntity.label).like(like), func.lower(KnowledgeEntity.key).like(like)))
        return list((await self.db.execute(stmt.order_by(KnowledgeEntity.updated_at.desc()).limit(limit))).scalars())

    async def neighbors(self, entity_id: str, limit: int = 80) -> dict[str, list[Any]]:
        edge_stmt = select(KnowledgeEdge).where(or_(KnowledgeEdge.source_entity_id == entity_id, KnowledgeEdge.target_entity_id == entity_id)).limit(limit)
        edges = list((await self.db.execute(edge_stmt)).scalars())
        entity_ids = {edge.source_entity_id for edge in edges} | {edge.target_entity_id for edge in edges}
        entities = [] if not entity_ids else list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(entity_ids)))).scalars())
        return {'entities': entities, 'edges': edges}

    async def create_run(self, *, status: str, message: str, stats: dict[str, Any]) -> KnowledgeIndexRun:
        run = KnowledgeIndexRun(id=stable_id('run', utcnow().isoformat()), status=status, message=message, stats=stats)
        self.db.add(run)
        await self.db.commit()
        return run

    async def update_run(self, run: KnowledgeIndexRun, *, status: str | None = None, message: str | None = None, stats: dict[str, Any] | None = None) -> KnowledgeIndexRun:
        if status is not None:
            run.status = status
        if message is not None:
            run.message = message
        if stats is not None:
            run.stats = stats
        await self.db.commit()
        return run

    async def finish_run(self, run: KnowledgeIndexRun, status: str, message: str, stats: dict[str, Any]) -> KnowledgeIndexRun:
        run.status, run.message, run.stats, run.completed_at = status, message, stats, utcnow()
        await self.db.commit()
        return run

    async def latest_run(self) -> KnowledgeIndexRun | None:
        return (await self.db.execute(select(KnowledgeIndexRun).order_by(KnowledgeIndexRun.started_at.desc()).limit(1))).scalar_one_or_none()

    async def latest_active_run(self) -> KnowledgeIndexRun | None:
        return (await self.db.execute(select(KnowledgeIndexRun).where(KnowledgeIndexRun.status.in_(['queued', 'running'])).order_by(KnowledgeIndexRun.started_at.desc()).limit(1))).scalar_one_or_none()

    async def mark_action(self, entity_id: str, action_type: str, status: str = 'done', data: dict[str, Any] | None = None) -> KnowledgeActionState:
        action_id = stable_id('action', entity_id, action_type)
        action = await self.db.get(KnowledgeActionState, action_id)
        if action is None:
            action = KnowledgeActionState(id=action_id, entity_id=entity_id, action_type=action_type, status=status, data=data or {})
            self.db.add(action)
        else:
            action.status, action.data = status, data or {}
        await self.db.commit()
        return action

    async def stats(self) -> dict[str, Any]:
        async def count(model: Any) -> int:
            return int((await self.db.execute(select(func.count()).select_from(model))).scalar_one())
        return {'entities': await count(KnowledgeEntity), 'edges': await count(KnowledgeEdge), 'scores': await count(KnowledgeScore), 'anomalies': await count(KnowledgeAnomaly)}
