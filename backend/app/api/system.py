from __future__ import annotations

from collections import deque
from datetime import datetime
import logging
import os
import platform
import threading
from typing import Any
from pathlib import Path

import json

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.runtime_paths import data_path

router = APIRouter(prefix='/api', tags=['system'])


def _ui_settings_path() -> Path:
    return data_path('ui_settings.json')


def _ui_settings() -> dict[str, Any]:
    try:
        value = json.loads(_ui_settings_path().read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_ui_settings(value: dict[str, Any]) -> None:
    path = _ui_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class SystemLogManager:
    _instance: 'SystemLogManager | None' = None
    _instance_lock = threading.Lock()

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._cursor = 0

    @classmethod
    def get_instance(cls) -> 'SystemLogManager':
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def add_log(self, level: str, message: str, source: str = 'NOOR', **extra: Any) -> dict[str, Any]:
        with self._lock:
            self._cursor += 1
            item: dict[str, Any] = {
                'id': self._cursor,
                'timestamp': datetime.now().astimezone().isoformat(),
                'level': str(level).lower(),
                'message': str(message),
                'source': source,
            }
            item.update({key: value for key, value in extra.items() if value is not None})
            self._entries.append(item)
            return item

    def get_logs(self, *, tail: int = 200, cursor: int | None = None) -> dict[str, Any]:
        with self._lock:
            entries = list(self._entries)
            if cursor is not None:
                entries = [entry for entry in entries if int(entry['id']) > cursor]
            else:
                entries = entries[-max(1, min(int(tail), 1000)):]
            return {'logs': entries, 'cursor': self._cursor}


@router.get('/logs')
async def get_logs(tail: int = Query(200, ge=1, le=1000), cursor: int | None = None):
    return SystemLogManager.get_instance().get_logs(tail=tail, cursor=cursor)


@router.get('/ui-settings')
async def get_ui_settings():
    value = _ui_settings()
    return {'cover_blur': bool(value.get('cover_blur', False))}


@router.put('/ui-settings')
async def update_ui_settings(payload: dict[str, Any]):
    if 'cover_blur' in payload and not isinstance(payload['cover_blur'], bool):
        raise HTTPException(status_code=422, detail='cover_blur 必须为布尔值')
    value = _ui_settings()
    if 'cover_blur' in payload:
        value['cover_blur'] = payload['cover_blur']
    _save_ui_settings(value)
    return {'cover_blur': bool(value.get('cover_blur', False))}


def _webhook_source(request: Request) -> str:
    forwarded = str(request.headers.get('x-forwarded-for') or '').strip()
    if forwarded:
        return forwarded.split(',', 1)[0].strip() or 'unknown'
    return request.client.host if request.client else 'unknown'


def _webhook_summary(payload: object) -> str:
    if not isinstance(payload, dict):
        return '收到测试或非 JSON 通知'
    event = str(
        payload.get('Event')
        or payload.get('EventName')
        or payload.get('NotificationType')
        or payload.get('Type')
        or '通知'
    ).strip()
    item = payload.get('Item') if isinstance(payload.get('Item'), dict) else {}
    name = str(
        payload.get('Name')
        or payload.get('ItemName')
        or item.get('Name')
        or ''
    ).strip()
    return f'{event}{": " + name if name else ""}'


@router.post('/webhooks/emby')
async def receive_emby_webhook(request: Request):
    """Accept Emby notification webhooks and retain a concise audit log.

    The recovery media adapter reads Emby live, so a webhook does not need to
    mutate a local media cache.  Recording the event gives the user a reliable
    connection test and preserves the real sender address for diagnostics.
    """
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise HTTPException(status_code=413, detail='Webhook 请求超过 1 MB')
    payload: object = None
    if body:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
    source = _webhook_source(request)
    summary = _webhook_summary(payload)
    SystemLogManager.get_instance().add_log(
        'info',
        f'已接收 Emby Webhook：{summary}',
        source=f'Emby · {source}',
        event_type=(payload.get('Event') if isinstance(payload, dict) else None),
    )
    return {'ok': True, 'message': 'Webhook 已接收', 'source': source, 'summary': summary}


@router.get('/system/info')
async def get_system_info():
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'pid': os.getpid(),
    }
