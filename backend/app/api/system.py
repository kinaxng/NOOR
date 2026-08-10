from __future__ import annotations

from collections import deque
from datetime import datetime
import logging
import os
import platform
import threading
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix='/api', tags=['system'])


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


@router.get('/system/info')
async def get_system_info():
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'pid': os.getpid(),
    }
