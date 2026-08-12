from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import utcnow
from app.knowledge.models import (
    KnowledgeActionState,
    KnowledgeAnomaly,
    KnowledgeEdge,
    KnowledgeEntity,
    KnowledgeIndexRun,
    KnowledgeScore,
    KnowledgeSource,
    stable_id,
)


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return await self.db.get(KnowledgeEntity, entity_id)

    async def clear(self) -> None:
        for model in (KnowledgeActionState, KnowledgeAnomaly, KnowledgeScore, KnowledgeEdge, KnowledgeEntity, KnowledgeSource):
            await self.db.execute(delete(model))
        await self.db.commit()

    async def upsert_source(self, source_id: str, name: str, source_type: str, *, data: dict[str, Any] | None = None) -> KnowledgeSource:
        source = await self.db.get(KnowledgeSource, source_id)
        if source is None:
            source = KnowledgeSource(id=source_id, name=name, source_type=source_type, data=data or {})
            self.db.add(source)
        else:
            source.name = name
            source.source_type = source_type
            source.data = data or {}
        return source

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

    async def upsert_edge(self, source_entity_id: str, relation_type: str, target_entity_id: str, source: str = 'knowledge-core', **values: Any) -> KnowledgeEdge:
        edge_id = stable_id('edge', source_entity_id, target_entity_id, relation_type, source)
        edge = await self.db.get(KnowledgeEdge, edge_id)
        if edge is None:
            edge = KnowledgeEdge(id=edge_id, source_entity_id=source_entity_id, target_entity_id=target_entity_id, relation_type=relation_type, source=source, **values)
            self.db.add(edge)
        else:
            for name, value in values.items():
                setattr(edge, name, value)
        return edge

    async def upsert_score(self, entity_id: str, score_type: str, value: int, *, reason: str | None = None, data: dict[str, Any] | None = None) -> KnowledgeScore:
        score_id = stable_id('score', entity_id, score_type)
        score = await self.db.get(KnowledgeScore, score_id)
        if score is None:
            score = KnowledgeScore(id=score_id, entity_id=entity_id, score_type=score_type, value=value, reason=reason, data=data or {})
            self.db.add(score)
        else:
            score.value = value
            score.reason = reason
            score.data = data or {}
        return score

    async def upsert_anomaly(self, entity_id: str, anomaly_type: str, message: str, *, severity: str = 'info', source: str = 'knowledge-core', data: dict[str, Any] | None = None) -> KnowledgeAnomaly:
        anomaly_id = stable_id('anomaly', entity_id, anomaly_type, source)
        anomaly = await self.db.get(KnowledgeAnomaly, anomaly_id)
        if anomaly is None:
            anomaly = KnowledgeAnomaly(id=anomaly_id, entity_id=entity_id, anomaly_type=anomaly_type, severity=severity, message=message, source=source, data=data or {})
            self.db.add(anomaly)
        else:
            anomaly.severity = severity
            anomaly.message = message
            anomaly.data = data or {}
        return anomaly

    async def search(self, q: str, *, entity_type: str | None = None, filter_kind: str | None = None, limit: int = 30) -> list[KnowledgeEntity]:
        stmt = select(KnowledgeEntity)
        if entity_type:
            stmt = stmt.where(KnowledgeEntity.entity_type == entity_type)
        if q.strip():
            like = f'%{q.strip().lower()}%'
            stmt = stmt.where(or_(func.lower(KnowledgeEntity.label).like(like), func.lower(KnowledgeEntity.key).like(like)))
        if filter_kind in {'missing_subtitle', 'missing_subtitle_with_candidate', 'has_anomaly'}:
            anomaly_query = select(KnowledgeAnomaly.entity_id).where(KnowledgeAnomaly.anomaly_type == 'missing_subtitle')
            if filter_kind == 'has_anomaly':
                anomaly_query = select(KnowledgeAnomaly.entity_id)
            stmt = stmt.where(KnowledgeEntity.id.in_(anomaly_query))
        if filter_kind == 'missing_subtitle_with_candidate':
            candidate_query = select(KnowledgeEdge.source_entity_id).where(KnowledgeEdge.relation_type == 'HAS_TORRENT_CANDIDATE')
            stmt = stmt.where(KnowledgeEntity.id.in_(candidate_query))
        if filter_kind == 'has_torrent_candidate':
            candidate_query = select(KnowledgeEdge.source_entity_id).where(KnowledgeEdge.relation_type == 'HAS_TORRENT_CANDIDATE')
            stmt = stmt.where(KnowledgeEntity.id.in_(candidate_query))
        return list((await self.db.execute(stmt.order_by(KnowledgeEntity.updated_at.desc()).limit(limit))).scalars())

    async def neighbors(self, entity_id: str, limit: int = 80) -> dict[str, list[Any]]:
        edge_stmt = select(KnowledgeEdge).where(or_(KnowledgeEdge.source_entity_id == entity_id, KnowledgeEdge.target_entity_id == entity_id)).limit(limit)
        edges = list((await self.db.execute(edge_stmt)).scalars())
        entity_ids = {edge.source_entity_id for edge in edges} | {edge.target_entity_id for edge in edges}
        entities = [] if not entity_ids else list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(entity_ids)))).scalars())
        return {'entities': entities, 'edges': edges}

    async def explore(self, *, entity_id: str | None = None, query: str = '', depth: int = 1, limit: int = 80) -> dict[str, Any]:
        """Return a bounded graph around an entity, resolving a text query when needed."""
        center = await self.get_entity(entity_id) if entity_id else None
        if center is None and query.strip():
            matches = await self.search(query, limit=1)
            center = matches[0] if matches else None
        if center is None:
            return {'center': None, 'entities': [], 'edges': []}

        depth = max(1, min(int(depth or 1), 2))
        limit = max(1, min(int(limit or 80), 240))
        seen = {center.id}
        frontier = {center.id}
        collected: dict[str, KnowledgeEdge] = {}
        for _ in range(depth):
            if not frontier or len(seen) >= limit:
                break
            rows = await self.db.execute(
                select(KnowledgeEdge)
                .where(or_(KnowledgeEdge.source_entity_id.in_(frontier), KnowledgeEdge.target_entity_id.in_(frontier)))
                .limit(limit * 4)
            )
            next_frontier: set[str] = set()
            for edge in rows.scalars().all():
                collected[edge.id] = edge
                other = edge.target_entity_id if edge.source_entity_id in frontier else edge.source_entity_id
                if other not in seen and len(seen) < limit:
                    seen.add(other)
                    next_frontier.add(other)
            frontier = next_frontier
        entities = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(seen)))).scalars())
        return {'center': center, 'entities': entities, 'edges': list(collected.values())}

    async def clusters(self, limit: int = 12) -> list[dict[str, Any]]:
        """Build the work clusters used by the AV graph dashboard."""
        relations = ('HAS_ACTOR', 'HAS_STUDIO', 'HAS_CODE', 'IN_SERIES', 'HAS_TAG', 'HAS_GENRE', 'HAS_LABEL')
        media = aliased(KnowledgeEntity)
        target = aliased(KnowledgeEntity)
        rows = await self.db.execute(
            select(KnowledgeEdge, target)
            .join(media, media.id == KnowledgeEdge.source_entity_id)
            .join(target, target.id == KnowledgeEdge.target_entity_id)
            .where(KnowledgeEdge.relation_type.in_(relations), media.entity_type == 'media_item')
        )
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        for edge, target_entity in rows.all():
            key = (edge.relation_type, target_entity.id)
            group = groups.setdefault(key, {'relation_type': edge.relation_type, 'target': target_entity, 'media_ids': set()})
            group['media_ids'].add(edge.source_entity_id)
        ranked = sorted(groups.values(), key=lambda item: len(item['media_ids']), reverse=True)[:max(1, min(limit, 50))]
        all_media_ids = {media_id for group in ranked for media_id in group['media_ids']}
        media_rows = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(all_media_ids)))).scalars()) if all_media_ids else []
        media_by_id = {item.id: item for item in media_rows}
        subtitle_edges = await self.db.execute(select(KnowledgeEdge).where(KnowledgeEdge.relation_type == 'HAS_SUBTITLE', KnowledgeEdge.source_entity_id.in_(all_media_ids))) if all_media_ids else None
        subtitled = {edge.source_entity_id for edge in subtitle_edges.scalars().all()} if subtitle_edges else set()
        result = []
        for group in ranked:
            members = [media_by_id[item] for item in group['media_ids'] if item in media_by_id]
            result.append({
                'relation_type': group['relation_type'],
                'target': group['target'],
                'media_count': len(members),
                'missing_subtitle_count': sum(item.id not in subtitled for item in members),
                'media': members[:40],
            })
        return result

    async def actionables(self, kind: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return actionable media/resource pairs, excluding already handled items."""
        limit = max(1, min(int(limit or 20), 100))
        anomaly_rows = await self.db.execute(select(KnowledgeAnomaly).where(KnowledgeAnomaly.anomaly_type.in_(['missing_subtitle', 'multi_version'])))
        anomaly_by_media: dict[str, set[str]] = defaultdict(set)
        for anomaly in anomaly_rows.scalars().all():
            anomaly_by_media[anomaly.entity_id].add(anomaly.anomaly_type)
        candidate_rows = await self.db.execute(select(KnowledgeEdge).where(KnowledgeEdge.relation_type == 'HAS_TORRENT_CANDIDATE'))
        candidates = list(candidate_rows.scalars().all())
        if kind == 'missing_subtitle_with_candidate':
            candidates = [edge for edge in candidates if 'missing_subtitle' in anomaly_by_media.get(edge.source_entity_id, set())]
        elif kind == 'multi_version_missing_subtitle':
            candidates = [edge for edge in candidates if {'missing_subtitle', 'multi_version'} <= anomaly_by_media.get(edge.source_entity_id, set())]
        elif kind == 'high_quality_candidates':
            candidates.sort(key=lambda edge: edge.confidence or 0, reverse=True)
        states = await self.db.execute(select(KnowledgeActionState).where(KnowledgeActionState.status.in_(['done', 'hidden'])))
        handled = {item.entity_id for item in states.scalars().all()}
        candidates = [edge for edge in candidates if edge.source_entity_id not in handled][:limit]
        ids = {edge.source_entity_id for edge in candidates} | {edge.target_entity_id for edge in candidates}
        entities = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(ids)))).scalars()) if ids else []
        by_id = {item.id: item for item in entities}
        return [{'media': by_id.get(edge.source_entity_id), 'torrent': by_id.get(edge.target_entity_id), 'edge': edge} for edge in candidates if by_id.get(edge.source_entity_id) and by_id.get(edge.target_entity_id)]

    async def action_states(self, statuses: set[str], limit: int = 20) -> list[dict[str, Any]]:
        rows = await self.db.execute(select(KnowledgeActionState).where(KnowledgeActionState.status.in_(statuses)).order_by(KnowledgeActionState.updated_at.desc()).limit(max(1, min(limit, 100))))
        actions = list(rows.scalars().all())
        entities = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_({item.entity_id for item in actions})))).scalars()) if actions else []
        by_id = {item.id: item for item in entities}
        return [{'entity': by_id.get(item.entity_id), 'action': item} for item in actions if by_id.get(item.entity_id)]

    async def insights(self, entity_id: str) -> dict[str, Any]:
        entity = await self.get_entity(entity_id)
        if entity is None:
            return {}
        incident = await self.db.execute(select(KnowledgeEdge).where(or_(KnowledgeEdge.source_entity_id == entity_id, KnowledgeEdge.target_entity_id == entity_id)))
        edges = list(incident.scalars().all())
        related_ids = {edge.target_entity_id if edge.source_entity_id == entity_id else edge.source_entity_id for edge in edges}
        related = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(related_ids)))).scalars()) if related_ids else []
        by_id = {item.id: item for item in related}
        result: dict[str, Any] = {
            'resource': {'quality': None, 'subtitle_count': 0, 'version_count': 0},
            'similar_media': [], 'shared_groups': [], 'cluster_members': [],
            'recommendations': [], 'warnings': [],
        }
        scores = list((await self.db.execute(select(KnowledgeScore).where(KnowledgeScore.entity_id == entity_id))).scalars().all())
        quality = next((score.value for score in scores if score.score_type == 'library_quality'), None)
        if entity.entity_type == 'media_item':
            subtitle_ids = {item.id for item in related if item.entity_type == 'subtitle'}
            version_ids = {item.id for item in related if item.entity_type == 'file_version'}
            result['resource'] = {'quality': quality, 'subtitle_count': len(subtitle_ids), 'version_count': len(version_ids)}
            targets = [item for item in related if item.entity_type not in {'subtitle', 'file_version', 'torrent'}]
            target_ids = {item.id for item in targets}
            if target_ids:
                peer_edges = await self.db.execute(select(KnowledgeEdge).where(KnowledgeEdge.relation_type.in_(['HAS_ACTOR', 'HAS_STUDIO', 'HAS_CODE', 'IN_SERIES', 'HAS_GENRE', 'HAS_TAG', 'HAS_LABEL']), KnowledgeEdge.target_entity_id.in_(target_ids)))
                peer_edges = list(peer_edges.scalars().all())
                peer_counts: dict[str, int] = defaultdict(int)
                peer_reasons: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for edge in peer_edges:
                    if edge.source_entity_id == entity_id:
                        continue
                    peer_counts[edge.source_entity_id] += 1
                    target_entity = by_id.get(edge.target_entity_id)
                    if target_entity:
                        peer_reasons[edge.source_entity_id].append({'relation_type': edge.relation_type, 'label': target_entity.label})
                peer_ids = [item for item, _ in sorted(peer_counts.items(), key=lambda value: value[1], reverse=True)[:12]]
                peer_entities = list((await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(peer_ids), KnowledgeEntity.entity_type == 'media_item')))).scalars() if peer_ids else []
                result['similar_media'] = [{'entity': item, 'score': peer_counts.get(item.id, 0), 'reasons': peer_reasons.get(item.id, [])[:5]} for item in peer_entities]
                for target_entity in targets[:8]:
                    members = await self._media_for_target(target_entity.id, limit=40)
                    if len(members) > 1:
                        result['shared_groups'].append({'relation_type': next((edge.relation_type for edge in edges if edge.target_entity_id == target_entity.id), ''), 'target': target_entity, 'media': members, 'missing_subtitle_count': await self._missing_subtitle_count(members)})
        else:
            members = [item for item in related if item.entity_type == 'media_item']
            if members:
                result['cluster_members'] = await self._media_members(members)
                result['resource']['quality'] = quality
        anomalies = list((await self.db.execute(select(KnowledgeAnomaly).where(KnowledgeAnomaly.entity_id == entity_id))).scalars().all())
        for anomaly in anomalies:
            result['warnings'].append(anomaly.message)
        if entity.entity_type == 'media_item' and result['resource']['subtitle_count'] == 0:
            result['recommendations'].append('可以优先寻找可用字幕或带字幕的版本。')
        return result

    async def _media_for_target(self, target_id: str, limit: int = 40) -> list[KnowledgeEntity]:
        source_edges = await self.db.execute(select(KnowledgeEdge.source_entity_id).where(KnowledgeEdge.target_entity_id == target_id, KnowledgeEdge.relation_type != 'HAS_TORRENT_CANDIDATE').limit(limit))
        ids = list(dict.fromkeys(source_edges.scalars().all()))
        if not ids:
            return []
        result = await self.db.execute(select(KnowledgeEntity).where(KnowledgeEntity.id.in_(ids), KnowledgeEntity.entity_type == 'media_item'))
        return list(result.scalars())

    async def _missing_subtitle_count(self, members: list[KnowledgeEntity]) -> int:
        if not members:
            return 0
        rows = await self.db.execute(select(KnowledgeEdge.source_entity_id).where(KnowledgeEdge.relation_type == 'HAS_SUBTITLE', KnowledgeEdge.source_entity_id.in_([item.id for item in members])))
        return sum(item.id not in set(rows.scalars().all()) for item in members)

    async def _media_members(self, members: list[KnowledgeEntity]) -> list[dict[str, Any]]:
        ids = [item.id for item in members]
        rows = await self.db.execute(select(KnowledgeEdge.source_entity_id).where(KnowledgeEdge.relation_type == 'HAS_SUBTITLE', KnowledgeEdge.source_entity_id.in_(ids)))
        subtitled = set(rows.scalars().all())
        return [{'entity': item, 'missing_subtitle': item.id not in subtitled, 'subtitle_count': 1 if item.id in subtitled else 0, 'quality': None} for item in members]

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
        entity_rows = await self.db.execute(select(KnowledgeEntity.entity_type, func.count(KnowledgeEntity.id)).group_by(KnowledgeEntity.entity_type))
        edge_rows = await self.db.execute(select(KnowledgeEdge.relation_type, func.count(KnowledgeEdge.id)).group_by(KnowledgeEdge.relation_type))
        score_count = int((await self.db.execute(select(func.count()).select_from(KnowledgeScore))).scalar_one())
        anomaly_count = int((await self.db.execute(select(func.count()).select_from(KnowledgeAnomaly))).scalar_one())
        return {
            'entities': {key: int(value) for key, value in entity_rows.all()},
            'edges': {key: int(value) for key, value in edge_rows.all()},
            'scores': score_count,
            'anomalies': anomaly_count,
        }
