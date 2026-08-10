from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT


_pool_lock = asyncio.Lock()
_scheduler_task: asyncio.Task[None] | None = None
_scheduler_stop: asyncio.Event | None = None


def _pool_path() -> Path:
    return PROJECT_ROOT / 'data' / 'av_recommend' / 'candidate_pool.json'


def _feedback_path() -> Path:
    return PROJECT_ROOT / 'data' / 'av_recommend' / 'feedback.json'


def _subscription_path() -> Path:
    return PROJECT_ROOT / 'data' / 'subscription_core' / 'subscriptions.json'


def _pool() -> dict[str, Any]:
    try:
        data = json.loads(_pool_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_pool(pool: dict[str, Any]) -> None:
    path = _pool_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pool['updated_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def _pool_scan_due(pool: dict[str, Any], interval_minutes: int = 360) -> bool:
    previous = (pool.get('last_full_scan') or {}).get('at')
    try:
        value = dt.datetime.fromisoformat(str(previous).replace('Z', '+00:00'))
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - value.astimezone(dt.timezone.utc)).total_seconds() >= interval_minutes * 60
    except (TypeError, ValueError):
        return True


def _merge_candidate(existing: dict[str, Any] | None, item: dict[str, Any], source: str, label: str) -> dict[str, Any]:
    current = dict(existing or {})
    if not current:
        current.update(item)
        current['first_seen_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    else:
        for key, value in item.items():
            if value not in (None, '', [], {}) and (not current.get(key) or key in {'magnets_count', 'has_cnsub', 'is_cracked'}):
                current[key] = max(int(current.get(key) or 0), int(value or 0)) if key == 'magnets_count' else bool(current.get(key) or value) if key in {'has_cnsub', 'is_cracked'} else value
    tags = current.get('source_tags') if isinstance(current.get('source_tags'), list) else []
    if not any(isinstance(tag, dict) and tag.get('id') == source for tag in tags):
        tags.append({'id': source, 'label': label, 'date': dt.date.today().isoformat()})
    current['source_tags'] = tags[:16]
    current['last_seen_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    current['is_today_increment'] = bool(current.get('first_seen_at', '').startswith(dt.date.today().isoformat()))
    return current


async def _scan_candidate_pool(config: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    from app.plugins.runtime import runtime

    if not runtime.is_enabled('javdb'):
        return {'ok': False, 'message': 'JavDB 插件未启用'}
    async with _pool_lock:
        pool = _pool()
        background = pool.get('background') if isinstance(pool.get('background'), dict) else {}
        if background.get('running') and not force:
            return {'ok': True, 'skipped': True, 'reason': 'running', 'pool': _candidate_pool_stats(pool)}
        pool['background'] = {**background, 'running': True, 'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'last_error': ''}
        _save_pool(pool)

    pages = max(1, min(int(config.get('full_scan_pages') or 5), 30))
    requests: list[tuple[str, str, dict[str, Any]]] = [
        ('latest', '最新更新', {'page': 1, 'limit': 48, 'type': 'all', 'filter_by': 'magnets', 'sort_by': 'update'}),
        ('rankings', '日榜', {'page': 1, 'limit': 24, 'period': 'daily', 'type': 0}),
        ('rankings', '周榜', {'page': 1, 'limit': 24, 'period': 'weekly', 'type': 0}),
        ('rankings', '月榜', {'page': 1, 'limit': 24, 'period': 'monthly', 'type': 0}),
        ('recommend', 'JavDB 推荐', {'page': 1, 'limit': 24}),
    ]
    requests.extend(('videos', f'完整库 P{page}', {'page': page, 'limit': 80, 'sort': 'update', 'order': 'desc'}) for page in range(1, pages + 1))
    scanned = added = updated = 0
    warnings: list[str] = []
    try:
        for action, label, payload in requests:
            try:
                response = await runtime.handle_action('javdb', action, payload)
            except Exception as exc:
                warnings.append(f'{label}: {exc}')
                continue
            values = response.get('items') if isinstance(response, dict) else []
            async with _pool_lock:
                pool = _pool()
                items = pool.get('items') if isinstance(pool.get('items'), dict) else {}
                for value in values or []:
                    if not isinstance(value, dict):
                        continue
                    code = _norm_code(value)
                    if not code:
                        continue
                    existed = code in items
                    items[code] = _merge_candidate(items.get(code), value, f'{action}:{label}', label)
                    scanned += 1
                    added += 0 if existed else 1
                    updated += 1 if existed else 0
                pool['items'] = items
                _save_pool(pool)
        async with _pool_lock:
            pool = _pool()
            pool['last_full_scan'] = {'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'pages': pages, 'scanned': scanned, 'added': added, 'updated': updated, 'warnings': warnings[:8]}
            pool['background'] = {**(pool.get('background') or {}), 'running': False, 'finished_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'last_error': ''}
            _save_pool(pool)
            return {'ok': True, 'scanned': scanned, 'added': added, 'updated': updated, 'warnings': warnings, 'pool': _candidate_pool_stats(pool)}
    except Exception as exc:
        async with _pool_lock:
            pool = _pool()
            pool['background'] = {**(pool.get('background') or {}), 'running': False, 'failed_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'last_error': str(exc)}
            _save_pool(pool)
        raise


async def _scheduler_loop() -> None:
    global _scheduler_stop
    _scheduler_stop = asyncio.Event()
    while not _scheduler_stop.is_set():
        try:
            from app.plugins.runtime import runtime
            config = runtime.get_config('av-recommend')
            if _pool_scan_due(_pool(), max(30, min(int(config.get('scan_interval_minutes') or 360), 1440))):
                await _scan_candidate_pool(config)
            minutes = max(30, min(int(config.get('scan_interval_minutes') or 360), 1440))
        except asyncio.CancelledError:
            raise
        except Exception:
            minutes = 30
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(_scheduler_stop.wait(), timeout=minutes * 60)


async def start_background(_config: dict[str, Any] | None = None) -> None:
    global _scheduler_task
    if not _scheduler_task or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())


async def stop_background() -> None:
    global _scheduler_task, _scheduler_stop
    if _scheduler_stop:
        _scheduler_stop.set()
    if _scheduler_task:
        _scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scheduler_task
    _scheduler_task = None
    _scheduler_stop = None


def _candidate_pool_stats(pool: dict[str, Any]) -> dict[str, Any]:
    items = pool.get('items') if isinstance(pool.get('items'), dict) else {}
    return {
        'total': len(items),
        'today_increment': sum(bool(item.get('is_today_increment')) for item in items.values() if isinstance(item, dict)),
        'last_full_scan': pool.get('last_full_scan') or {},
        'background': pool.get('background') or {},
    }


def _items() -> list[dict[str, Any]]:
    values = _pool().get('items', {})
    return [item for item in values.values() if isinstance(item, dict)] if isinstance(values, dict) else []


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def _feedback() -> dict[str, set[str]]:
    data = _read_json(_feedback_path(), {})

    def codes(key: str) -> set[str]:
        entries = data.get(key) or []
        return {
            str(entry.get('code') if isinstance(entry, dict) else entry or '').strip().upper().replace('_', '-')
            for entry in entries
            if str(entry.get('code') if isinstance(entry, dict) else entry or '').strip()
        }

    return {'liked': codes('liked'), 'disliked': codes('disliked'), 'ignored': codes('ignored')}


def _save_feedback(kind: str, code: str, payload: dict[str, Any]) -> None:
    path = _feedback_path()
    data = _read_json(path, {'version': 1, 'liked': [], 'disliked': [], 'ignored': []})
    key = {'like': 'liked', 'dislike': 'disliked', 'ignore': 'ignored'}[kind]
    entries = data.get(key) if isinstance(data.get(key), list) else []
    normalized = code.upper().replace('_', '-')
    entries = [entry for entry in entries if str(entry.get('code') if isinstance(entry, dict) else entry or '').upper().replace('_', '-') != normalized]
    entries.insert(0, {'code': code, 'reason': str(payload.get('reason') or ''), 'actors': payload.get('actors') or [], 'categories': payload.get('categories') or []})
    data[key] = entries
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _subscription_codes() -> set[str]:
    data = _read_json(_subscription_path(), {})
    values = data.get('subscriptions') if isinstance(data.get('subscriptions'), list) else []
    return {
        str(item.get('code') or item.get('number') or '').strip().upper().replace('_', '-')
        for item in values if isinstance(item, dict) and str(item.get('code') or item.get('number') or '').strip()
    }


def _norm_code(item: dict[str, Any]) -> str:
    return str(item.get('code') or item.get('number') or '').strip().upper().replace('_', '-')


def _score(item: dict[str, Any], feedback: dict[str, set[str]]) -> float:
    code = _norm_code(item)
    score = float(item.get('score') or 0) * 3
    score += min(10, int(item.get('magnets_count') or 0) * 2)
    score += 8 if item.get('has_cnsub') else 0
    score += 7 if item.get('is_cracked') else 0
    score += 5 if item.get('is_today_increment') else 0
    score += 4 * min(3, len(item.get('source_tags') or []))
    score += 20 if code in feedback['liked'] else 0
    return round(score, 1)


def _sort_key(item: dict[str, Any], feedback: dict[str, set[str]]) -> tuple:
    return (_score(item, feedback), str(item.get('last_seen_at') or ''), str(item.get('release_date') or ''))


def _result(item: dict[str, Any], feedback: dict[str, set[str]], subscribed: set[str]) -> dict[str, Any]:
    code = _norm_code(item)
    return {
        'id': item.get('id'), 'code': item.get('code') or item.get('number'), 'number': item.get('number'),
        'title': item.get('display_title') or item.get('title'), 'origin_title': item.get('origin_title'),
        'cover_url': item.get('cover_url'), 'thumb_url': item.get('thumb_url'), 'release_date': item.get('release_date'),
        'duration': item.get('duration'), 'score': item.get('score'), 'ranking': item.get('ranking'),
        'has_cnsub': item.get('has_cnsub'), 'is_cracked': item.get('is_cracked'),
        'in_library': bool((item.get('library') or {}).get('in_library')), 'subscribed': code in subscribed, 'actors': item.get('actors') or [],
        'categories': item.get('categories') or [], 'source_tags': item.get('source_tags') or [],
        'is_today_increment': bool(item.get('is_today_increment')), 'detail': item.get('detail') or {},
        'recommendation_score': _score(item, feedback),
    }


async def search_resources(query: dict[str, Any], _config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    needle = str(query.get('keyword') or query.get('q') or query.get('code') or '').strip().lower()
    limit = max(1, min(int(query.get('limit') or 24), 100))
    feedback, subscribed = _feedback(), _subscription_codes()
    items = _items()
    if needle:
        items = [item for item in items if needle in ' '.join([str(item.get('code') or ''), str(item.get('number') or ''), str(item.get('title') or ''), str(item.get('origin_title') or '')]).lower()]
    return [_result(item, feedback, subscribed) for item in sorted(items, key=lambda item: _sort_key(item, feedback), reverse=True)[:limit]]


async def handle_action(action: str, payload: dict[str, Any], _config: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    config = _config or {}
    feedback, subscribed = _feedback(), _subscription_codes()
    if action in {'list', 'recommendations', 'get_recommendations'}:
        mode = str(payload.get('source_mode') or payload.get('mode') or 'latest').lower()
        include_existing = bool(payload.get('include_existing'))
        items = _items()
        if mode == 'latest':
            items = [item for item in items if any((tag.get('id') or '').startswith(('latest:', 'rankings:')) for tag in item.get('source_tags') or [] if isinstance(tag, dict))]
        items = [item for item in items if _norm_code(item) not in feedback['ignored'] | feedback['disliked']]
        if not include_existing:
            items = [item for item in items if not (item.get('library') or {}).get('in_library') and _norm_code(item) not in subscribed]
        limit = max(1, min(int(payload.get('limit') or 48), 100))
        result = [_result(item, feedback, subscribed) for item in sorted(items, key=lambda item: _sort_key(item, feedback), reverse=True)[:limit]]
        pool = _pool()
        return {'ok': True, 'items': result, 'total': len(items), 'source_mode': mode, 'source_label': '完整推荐' if mode == 'full' else '最新推荐', 'pool': _candidate_pool_stats(pool), 'stats': {'candidates': len(items), 'today_increment': sum(bool(item.get('is_today_increment')) for item in items), 'in_library': sum(bool((item.get('library') or {}).get('in_library')) for item in _items()), 'subscribed': len(subscribed)}}
    if action in {'detail', 'get_detail'}:
        code = str(payload.get('code') or payload.get('number') or '').lower()
        item = next((item for item in _items() if str(item.get('code') or item.get('number') or '').lower() == code), None)
        return {'item': _result(item, feedback, subscribed)} if item else {'item': None}
    if action == 'feedback':
        kind = str(payload.get('kind') or 'ignore').lower()
        code = str(payload.get('code') or '').strip()
        if kind not in {'like', 'dislike', 'ignore'} or not code:
            raise ValueError('反馈需要有效的 kind 与番号')
        _save_feedback(kind, code, payload)
        return {'ok': True, 'kind': kind, 'code': code}
    if action == 'reset_feedback':
        _feedback_path().unlink(missing_ok=True)
        return {'ok': True}
    if action == 'scan_candidate_pool':
        return await _scan_candidate_pool(config, force=bool(payload.get('force')))
    if action == 'candidate_pool':
        return {'ok': True, 'pool': _candidate_pool_stats(_pool())}
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
