from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT


def _pool_path() -> Path:
    return PROJECT_ROOT / 'data' / 'av_recommend' / 'candidate_pool.json'


def _pool() -> dict[str, Any]:
    try:
        data = json.loads(_pool_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _items() -> list[dict[str, Any]]:
    values = _pool().get('items', {})
    return [item for item in values.values() if isinstance(item, dict)] if isinstance(values, dict) else []


def _sort_key(item: dict[str, Any]) -> tuple:
    return (str(item.get('last_seen_at') or ''), str(item.get('first_seen_at') or ''), str(item.get('release_date') or ''))


def _result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': item.get('id'), 'code': item.get('code') or item.get('number'), 'number': item.get('number'),
        'title': item.get('display_title') or item.get('title'), 'origin_title': item.get('origin_title'),
        'cover_url': item.get('cover_url'), 'thumb_url': item.get('thumb_url'), 'release_date': item.get('release_date'),
        'duration': item.get('duration'), 'score': item.get('score'), 'ranking': item.get('ranking'),
        'has_cnsub': item.get('has_cnsub'), 'is_cracked': item.get('is_cracked'),
        'in_library': bool((item.get('library') or {}).get('in_library')), 'actors': item.get('actors') or [],
        'categories': item.get('categories') or [], 'source_tags': item.get('source_tags') or [],
        'is_today_increment': bool(item.get('is_today_increment')), 'detail': item.get('detail') or {},
    }


async def search_resources(query: dict[str, Any], _config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    needle = str(query.get('keyword') or query.get('q') or query.get('code') or '').strip().lower()
    limit = max(1, min(int(query.get('limit') or 24), 100))
    items = _items()
    if needle:
        items = [item for item in items if needle in ' '.join([str(item.get('code') or ''), str(item.get('number') or ''), str(item.get('title') or ''), str(item.get('origin_title') or '')]).lower()]
    return [_result(item) for item in sorted(items, key=_sort_key, reverse=True)[:limit]]


async def handle_action(action: str, payload: dict[str, Any], _config: dict[str, Any] | None = None) -> dict[str, Any]:
    if action in {'list', 'recommendations', 'get_recommendations'}:
        return {'items': await search_resources(payload, _config), 'pool': _pool().get('last_full_scan') or {}}
    if action in {'detail', 'get_detail'}:
        code = str(payload.get('code') or payload.get('number') or '').lower()
        item = next((item for item in _items() if str(item.get('code') or item.get('number') or '').lower() == code), None)
        return {'item': _result(item)} if item else {'item': None}
    raise LookupError(action)


def background_tasks(_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    pool = _pool()
    background = pool.get('background') or {}
    scan = pool.get('last_full_scan') or {}
    return [{
        'id': 'av-recommend.full-candidate-pool', 'title': '完整候选池扫描',
        'status': 'running' if background.get('running') else ('failed' if background.get('last_error') else 'idle'),
        'last_run_at': scan.get('at'), 'last_finished_at': background.get('finished_at'),
        'summary': f"扫描 {scan.get('scanned', 0)}，新增 {scan.get('added', 0)}，更新 {scan.get('updated', 0)}",
        'detail': background.get('last_error') or '', 'metrics': scan,
    }]
