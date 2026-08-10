from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.plugins.runtime import runtime

router = APIRouter(prefix='/api/plugins', tags=['plugins'])


class PluginConfigPayload(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class PluginEnabledPayload(BaseModel):
    enabled: bool


class PluginActionPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ResourceSearchPayload(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    limit_per_plugin: int = Field(24, ge=1, le=100)


@router.get('')
async def list_plugins():
    if not runtime._manifests:
        await runtime.reload_plugins()
    return {'items': runtime.list_plugins()}


@router.post('/reload')
async def reload_plugins():
    return {'items': await runtime.reload_plugins()}


@router.get('/background/tasks')
async def get_background_tasks():
    items = await runtime.get_background_tasks()
    return {'ok': True, 'items': items, 'total': len(items)}


@router.post('/resources/search')
async def search_resources(payload: ResourceSearchPayload):
    groups = await runtime.search_resources(payload.query, limit_per_plugin=payload.limit_per_plugin)
    return {'groups': groups}


@router.get('/{plugin_id}')
async def get_plugin(plugin_id: str):
    plugin = runtime.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail='Plugin not found')
    return plugin


@router.get('/{plugin_id}/config')
async def get_plugin_config(plugin_id: str):
    if not runtime.get_plugin(plugin_id):
        raise HTTPException(status_code=404, detail='Plugin not found')
    return {'config': runtime.get_config(plugin_id)}


@router.put('/{plugin_id}/config')
async def update_plugin_config(plugin_id: str, payload: PluginConfigPayload):
    try:
        return {'config': await runtime.update_config(plugin_id, payload.config)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Plugin not found') from exc


@router.put('/{plugin_id}/enabled')
async def set_plugin_enabled(plugin_id: str, payload: PluginEnabledPayload):
    try:
        return {'enabled': await runtime.set_enabled(plugin_id, payload.enabled)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Plugin not found') from exc


@router.post('/{plugin_id}/actions/{action}')
async def plugin_action(plugin_id: str, action: str, payload: PluginActionPayload):
    try:
        return await runtime.handle_action(plugin_id, action, payload.payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
