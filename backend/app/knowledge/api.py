from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.database import get_db
from app.knowledge.indexer import rebuild_knowledge_index
from app.knowledge.models import KnowledgeAnomaly, KnowledgeScore
from app.knowledge.repository import KnowledgeRepository

router = APIRouter(prefix='/api/knowledge', tags=['knowledge'])
_active_rebuild_task: asyncio.Task | None = None


async def _run_rebuild(run_id: str, max_items: int | None) -> None:
    async with database.async_session_maker() as db:
        await rebuild_knowledge_index(db, max_items=max_items, run_id=run_id)


def _entity(entity: Any) -> dict[str, Any]:
    return {'id': entity.id, 'type': entity.entity_type, 'key': entity.key, 'label': entity.label, 'summary': entity.summary, 'data': entity.data or {}, 'source': entity.source, 'confidence': entity.confidence, 'updated_at': entity.updated_at.isoformat() if entity.updated_at else None}


def _edge(edge: Any) -> dict[str, Any]:
    return {'id': edge.id, 'source_entity_id': edge.source_entity_id, 'target_entity_id': edge.target_entity_id, 'relation_type': edge.relation_type, 'source': edge.source, 'confidence': edge.confidence, 'data': edge.data or {}}


@router.post('/rebuild')
async def rebuild(max_items: int | None = Query(None, ge=1, le=5000), db: AsyncSession = Depends(get_db)):
    global _active_rebuild_task
    repo = KnowledgeRepository(db)
    active = await repo.latest_active_run()
    if _active_rebuild_task and not _active_rebuild_task.done():
        return {'ok': True, 'accepted': False, 'status': active.status if active else 'running', 'run_id': active.id if active else None}
    run = await repo.create_run(status='queued', message='Knowledge Core rebuild queued', stats={'phase': 'queued', 'percent': 0, 'processed': 0, 'total': max_items})
    _active_rebuild_task = asyncio.create_task(_run_rebuild(run.id, max_items))
    return {'ok': True, 'accepted': True, 'status': 'queued', 'run_id': run.id}


@router.get('/rebuild/status')
async def rebuild_status(db: AsyncSession = Depends(get_db)):
    run = await KnowledgeRepository(db).latest_run()
    return {'status': run.status if run else 'idle', 'run': None if not run else {'id': run.id, 'status': run.status, 'message': run.message, 'stats': run.stats or {}}}


@router.get('/search')
async def search(q: str = '', entity_type: str | None = None, limit: int = Query(30, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    items = await KnowledgeRepository(db).search(q, entity_type=entity_type, limit=limit)
    return {'items': [_entity(item) for item in items], 'total': len(items)}


@router.get('/entities/{entity_id}')
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    repo = KnowledgeRepository(db)
    entity = await repo.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail='knowledge entity not found')
    neighbors = await repo.neighbors(entity_id, limit=120)
    scores = (await db.execute(select(KnowledgeScore).where(KnowledgeScore.entity_id == entity_id))).scalars().all()
    anomalies = (await db.execute(select(KnowledgeAnomaly).where(KnowledgeAnomaly.entity_id == entity_id))).scalars().all()
    return {'entity': _entity(entity), 'neighbors': {'entities': [_entity(item) for item in neighbors['entities']], 'edges': [_edge(item) for item in neighbors['edges']]}, 'scores': [{'type': item.score_type, 'value': item.value, 'reason': item.reason, 'data': item.data or {}} for item in scores], 'anomalies': [{'type': item.anomaly_type, 'severity': item.severity, 'message': item.message, 'data': item.data or {}} for item in anomalies]}


@router.get('/entities/{entity_id}/neighbors')
@router.get('/graph')
async def neighbors(entity_id: str, limit: int = Query(80, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    data = await KnowledgeRepository(db).neighbors(entity_id, limit=limit)
    return {'entities': [_entity(item) for item in data['entities']], 'edges': [_edge(item) for item in data['edges']]}


@router.post('/actionables/mark')
async def mark_actionable(payload: dict = Body(default_factory=dict), db: AsyncSession = Depends(get_db)):
    entity_id = str(payload.get('entity_id') or '').strip()
    if not entity_id or not await KnowledgeRepository(db).get_entity(entity_id):
        raise HTTPException(status_code=404, detail='knowledge entity not found')
    action = await KnowledgeRepository(db).mark_action(entity_id, str(payload.get('action_type') or 'download_pushed'), str(payload.get('status') or 'done'), payload.get('data') or {})
    return {'ok': True, 'action': {'id': action.id, 'entity_id': action.entity_id, 'action_type': action.action_type, 'status': action.status, 'data': action.data or {}}}


@router.get('/stats')
async def stats(db: AsyncSession = Depends(get_db)):
    return await KnowledgeRepository(db).stats()
