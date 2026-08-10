from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.plugins.runtime import runtime

router = APIRouter(prefix='/api/search', tags=['search'])


class GlobalSearchRequest(BaseModel):
    query: str = ''
    keyword: str = ''
    code: str = ''
    limit: int = Field(24, ge=1, le=100)


@router.post('')
@router.post('/resources')
async def global_search(payload: GlobalSearchRequest) -> dict[str, Any]:
    keyword = payload.query.strip() or payload.keyword.strip() or payload.code.strip()
    groups = await runtime.search_resources(
        {'keyword': keyword, 'q': keyword, 'code': payload.code.strip() or keyword, 'number': payload.code.strip() or keyword, 'limit': payload.limit},
        limit_per_plugin=payload.limit,
    )
    return {'query': keyword, 'groups': groups, 'total': sum(len(group.get('items', [])) for group in groups)}
