from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.plugins.runtime import runtime

router = APIRouter(prefix='/api/search', tags=['search'])


class GlobalSearchRequest(BaseModel):
    query: str = ''
    keyword: str = ''
    code: str = ''
    limit: int = Field(24, ge=1, le=100)


def _badge_tone(label: str) -> str:
    text = label.lower()
    if '字幕' in label or '中字' in label or '中文' in label:
        return 'success'
    if '破解' in label or '流出' in label or 'uncensored' in text:
        return 'danger'
    if 'free' in text or '免费' in label:
        return 'success'
    if 'pt' in text or 'm-team' in text or 'javdb' in text or 'avdb' in text:
        return 'info'
    return 'neutral'


def _resource_item_to_search_item(provider: str, provider_name: str, item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
    code = str(item.get('query_key') or metadata.get('video_code') or '').strip()
    title = str(item.get('title') or code or item.get('id') or '').strip()
    tags = [str(tag).strip() for tag in (item.get('tags') or []) if str(tag or '').strip()]
    badges = [{'label': provider_name, 'tone': 'info'}]
    badges.extend({'label': tag, 'tone': _badge_tone(tag)} for tag in tags[:4])
    if item.get('preferred_downloader'):
        badges.append({'label': str(item['preferred_downloader']), 'tone': 'neutral'})
    route_query = code or title
    return {
        'id': str(item.get('id') or f'{provider}:{title}'),
        'source': provider,
        'source_label': provider_name,
        'type': 'resource',
        'title': title,
        'subtitle': str(item.get('subtitle') or provider_name),
        'description': code,
        'image': item.get('cover_url') or item.get('image_url') or item.get('fanart_url'),
        'icon': 'search',
        'badges': badges,
        'action': {
            'type': 'route',
            'route': f'/search/resources?q={route_query}',
            'payload': {
                'provider': provider,
                'code': code,
                'source_url': item.get('source_url') or '',
            },
        },
    }


def _groups_to_scopes(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for group in groups:
        provider = str(group.get('provider') or '')
        provider_name = str(group.get('provider_name') or provider or '资源')
        if group.get('error'):
            errors.append(f'{provider_name}: {group["error"]}')
        for item in group.get('items') or []:
            if isinstance(item, dict):
                items.append(_resource_item_to_search_item(provider, provider_name, item))
    scope: dict[str, Any] = {
        'key': 'catalog',
        'label': '作品',
        'count': len(items),
        'items': items,
    }
    if errors and not items:
        scope['error'] = '；'.join(errors[:3])
    return [scope] if items or errors else []


@router.post('')
@router.post('/resources')
async def global_search(payload: GlobalSearchRequest) -> dict[str, Any]:
    keyword = payload.query.strip() or payload.keyword.strip() or payload.code.strip()
    result = await runtime.search_resources(
        {'keyword': keyword, 'q': keyword, 'code': payload.code.strip() or keyword, 'number': payload.code.strip() or keyword, 'limit': payload.limit},
        limit_per_plugin=payload.limit,
    )
    groups = result.get('groups') if isinstance(result, dict) else result
    return {'query': keyword, 'groups': groups, 'total': sum(len(group.get('items', [])) for group in groups)}


@router.get('')
async def global_search_get(q: str = '', limit: int = Query(5, ge=1, le=50)) -> dict[str, Any]:
    payload = GlobalSearchRequest(query=q, limit=limit)
    result = await global_search(payload)
    groups = result.get('groups') if isinstance(result.get('groups'), list) else []
    return {
        **result,
        'scopes': _groups_to_scopes(groups),
    }
