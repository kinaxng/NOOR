from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.plugins.runtime import runtime
from app.core.runtime_cleanup import DEFAULT_MIN_AGE_HOURS, run_runtime_cleanup, runtime_cleanup_status

router = APIRouter(prefix='/api/plugins', tags=['plugins'])


class PluginConfigPayload(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class PluginEnabledPayload(BaseModel):
    enabled: bool


class PluginActionPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class PluginDownloadPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ResourceSearchPayload(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    limit_per_plugin: int = Field(24, ge=1, le=100)


class FeedPushPayload(BaseModel):
    item: dict[str, Any] = Field(default_factory=dict)


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
    cleanup = runtime_cleanup_status(min_age_hours=DEFAULT_MIN_AGE_HOURS)
    last = cleanup.get('last_cleanup') or {}
    items.insert(0, {
        'plugin_id': 'noor-core',
        'plugin_name': 'NOOR 核心',
        'id': 'noor-core.runtime-cleanup',
        'title': '运行时资源清理',
        'status': last.get('status') if last.get('status') in {'running', 'failed'} else 'idle',
        'last_run_at': last.get('started_at') or None,
        'last_finished_at': last.get('finished_at') or None,
        'summary': cleanup.get('summary', ''),
        'detail': last.get('message') or '按需清理过期的 NOOR 任务临时目录',
        'metrics': {
            'reclaimable_bytes': cleanup.get('reclaimable_bytes', 0),
            'candidate_count': cleanup.get('candidate_count', 0),
            'min_age_hours': DEFAULT_MIN_AGE_HOURS,
        },
    })
    return {'ok': True, 'items': items, 'total': len(items)}


@router.post('/noor-core/actions/runtime-cleanup')
async def run_core_runtime_cleanup(payload: PluginActionPayload):
    min_age_hours = payload.payload.get('min_age_hours', DEFAULT_MIN_AGE_HOURS)
    try:
        min_age_hours = max(0, min(168, int(min_age_hours)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail='min_age_hours 必须为整数') from exc
    return run_runtime_cleanup(min_age_hours=min_age_hours)


@router.post('/resources/search')
async def search_resources(payload: ResourceSearchPayload):
    groups = await runtime.search_resources(payload.query, limit_per_plugin=payload.limit_per_plugin)
    return {'groups': groups}


@router.get('/dashboard/widgets')
async def get_dashboard_widgets(plugin_ids: str = ''):
    ids = [item.strip() for item in plugin_ids.split(',') if item.strip()]
    return await runtime.get_dashboard_widgets(ids or None)


@router.get('/{plugin_id}/rss/items')
async def get_plugin_rss_items(plugin_id: str, limit: int = 30, refresh: bool = False):
    try:
        return await runtime.get_rss_items(plugin_id, limit=limit, force_refresh=refresh)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/{plugin_id}/rss/push')
async def push_plugin_rss_item(plugin_id: str, payload: FeedPushPayload):
    try:
        return await runtime.push_rss_download(plugin_id, payload.item)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete('/{plugin_id}/images/cache')
async def clear_plugin_image_cache(plugin_id: str):
    handler = runtime._handlers.get(plugin_id)
    callback = getattr(handler, 'clear_image_cache', None) if handler is not None else None
    if not callable(callback):
        raise HTTPException(status_code=404, detail='Plugin image cache not supported')
    return callback()


@router.post('/{plugin_id}/downloads')
async def submit_plugin_download(plugin_id: str, payload: PluginDownloadPayload):
    try:
        return await runtime.submit_download(plugin_id, payload.payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/{plugin_id}')
async def get_plugin(plugin_id: str):
    plugin = runtime.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail='Plugin not found')
    return plugin


@router.get('/{plugin_id}/config')
async def get_plugin_config(plugin_id: str):
    plugin = runtime.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail='Plugin not found')
    return {'plugin': plugin, 'config': runtime.get_config(plugin_id)}


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/{plugin_id}/assets/{asset_path:path}')
async def get_plugin_asset(plugin_id: str, asset_path: str):
    manifest = runtime._manifests.get(plugin_id)
    if not manifest:
        raise HTTPException(status_code=404, detail='Plugin not found')
    frontend_dir = runtime.plugin_root.joinpath(plugin_id, 'frontend').resolve()
    asset = frontend_dir.joinpath(asset_path).resolve()
    try:
        asset.relative_to(frontend_dir)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='Plugin asset not found') from exc
    if not asset.is_file():
        raise HTTPException(status_code=404, detail='Plugin asset not found')
    return FileResponse(asset)


@router.get('/{plugin_id}/images/{image_id}')
async def get_plugin_cached_image(plugin_id: str, image_id: str):
    """Serve an image that a plugin explicitly cached under its runtime data."""
    handler = runtime._handlers.get(plugin_id)
    resolver = getattr(handler, 'get_cached_image', None) if handler is not None else None
    if not callable(resolver):
        raise HTTPException(status_code=404, detail='Plugin image provider not found')
    try:
        result = resolver(image_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail='Cached image not found') from exc
    if not result:
        raise HTTPException(status_code=404, detail='Cached image not found')
    path, content_type = result
    return FileResponse(path, media_type=content_type, filename=path.name)
