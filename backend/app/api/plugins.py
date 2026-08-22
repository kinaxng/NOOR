from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.plugins.market import MarketError
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


class ResourceResolvePayload(BaseModel):
    provider_id: str = ''
    provider: str = ''
    item: dict[str, Any] = Field(default_factory=dict)


class FeedPushPayload(BaseModel):
    item: dict[str, Any] = Field(default_factory=dict)


class MarketInstallPayload(BaseModel):
    repo_url: str = ''
    plugin_id: str = ''


class MarketRepoPayload(BaseModel):
    repo_url: str = ''
    url: str = ''


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
    items: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        provider = str(group.get('provider') or '')
        provider_name = str(group.get('provider_name') or provider or '')
        for item in group.get('items') or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row.setdefault('provider', provider)
            row.setdefault('provider_label', provider_name)
            items.append(row)
    return {'groups': groups, 'items': items}


@router.post('/resources/resolve-download')
async def resolve_resource_download(payload: ResourceResolvePayload):
    provider_id = str(payload.provider_id or payload.provider or payload.item.get('provider') or '').strip()
    if not provider_id:
        raise HTTPException(status_code=400, detail='缺少资源来源')
    try:
        return await runtime.resolve_resource_download(provider_id, payload.item)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/market/repos')
async def list_market_repos():
    return runtime.list_market_repos()


@router.post('/market/repos')
async def add_market_repo(payload: MarketRepoPayload):
    try:
        return runtime.add_market_repo(payload.repo_url or payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete('/market/repos')
async def remove_market_repo(payload: MarketRepoPayload):
    return runtime.remove_market_repo(payload.repo_url or payload.url)


@router.get('/market/items')
async def list_market_plugins():
    return await runtime.list_market_items()


@router.post('/market/install')
async def install_market_plugin(payload: MarketInstallPayload):
    try:
        return await runtime.install_market_plugin(payload.repo_url, payload.plugin_id)
    except (MarketError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.post('/{plugin_id}/enable')
async def enable_plugin(plugin_id: str):
    try:
        return {'enabled': await runtime.set_enabled(plugin_id, True)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Plugin not found') from exc


@router.post('/{plugin_id}/disable')
async def disable_plugin(plugin_id: str):
    try:
        return {'enabled': await runtime.set_enabled(plugin_id, False)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Plugin not found') from exc


@router.post('/{plugin_id}/test')
async def test_plugin(plugin_id: str):
    return await plugin_action(plugin_id, 'test', PluginActionPayload())


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
    # Frontend modules live under frontend/, while manifests may reference
    # plugin-owned icons (for example icons/service.svg) as well.
    plugin_dir = runtime.plugin_root.joinpath(plugin_id).resolve()
    candidates = [
        plugin_dir.joinpath('frontend', asset_path).resolve(),
        plugin_dir.joinpath(asset_path).resolve(),
    ]
    asset = next((candidate for candidate in candidates if candidate.is_file()), None)
    if asset is None:
        raise HTTPException(status_code=404, detail='Plugin asset not found')
    try:
        asset.relative_to(plugin_dir)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail='Plugin asset not found') from exc
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
