from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.system import SystemLogManager
from app.plugins.market import MarketError
from app.plugins.runtime import runtime
from app.core.runtime_cleanup import DEFAULT_MIN_AGE_HOURS, run_runtime_cleanup, runtime_cleanup_status

router = APIRouter(prefix='/api/plugins', tags=['plugins'])
NOISY_PLUGIN_ACTIONS = {
    'metrics',
    'overview',
    'status',
    'refresh-status',
    'refresh_status',
    'stats',
}
NOISY_PLUGIN_PATH_PARTS = (
    '/ws/overview',
    '/ws/metrics',
)


def _plugin_log(level: str, plugin_id: str, message: str, *, source: str | None = None) -> None:
    try:
        SystemLogManager.get_instance().add_log(level, message, source=source or f'plugin.{plugin_id}')
    except Exception:
        pass


def _payload_hint(payload: Any) -> str:
    if not isinstance(payload, dict):
        return type(payload).__name__
    keys = ', '.join(list(payload.keys())[:8])
    more = '' if len(payload) <= 8 else f', +{len(payload) - 8}'
    return f'keys=[{keys}{more}]'


def _request_hint(request: Request | None) -> str:
    if not request:
        return ''
    referer = str(request.headers.get('referer') or '')
    ua = str(request.headers.get('user-agent') or '')
    client = request.client.host if request.client else ''
    parts = []
    if client:
        parts.append(f'client={client}')
    if referer:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            ref = f"{parsed.path}{('?' + parsed.query) if parsed.query else ''}" or referer
        except Exception:
            ref = referer
        parts.append(f'referer={ref}')
    if ua:
        parts.append(f'ua={ua[:60]}')
    return ' '.join(parts)


def _is_noisy_plugin_action(action: str) -> bool:
    value = str(action or '').lower().strip()
    return value in NOISY_PLUGIN_ACTIONS or value.endswith('_status') or value.endswith('-status')


def _status_to_background_status(value: Any) -> str:
    status = str(value or 'idle').lower()
    if status in {'running', 'queued', 'pending'}:
        return 'running'
    if status in {'failed', 'error'}:
        return 'failed'
    return 'idle'


def _progress_value(value: Any) -> int:
    try:
        return max(0, min(int(value or 0), 100))
    except Exception:
        return 0


def _short_text(value: Any, limit: int = 180) -> str:
    text = str(value or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


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
    providers: list[str] = Field(default_factory=list)
    limit_per_plugin: int = Field(24, ge=1, le=100)
    requested_downloader_id: str = ''


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


async def _get_core_background_tasks() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    try:
        from app.api.settings_status_helpers import read_install_status_response, read_model_download_status_response

        download = read_model_download_status_response()
        download_status = _status_to_background_status(download.get('status'))
        download_progress = _progress_value(download.get('progress'))
        model = str(download.get('model') or '')
        items.append({
            'id': 'noor-core.whisper-model-download',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': 'Whisper 模型下载',
            'status': download_status,
            'enabled': True,
            'progress': download_progress if download_status == 'running' else (100 if str(download.get('status') or '') == 'completed' else 0),
            'summary': _short_text(download.get('message') or ('模型下载待命' if not model else f'{model} 下载状态')),
            'detail': _short_text(download.get('output') or download.get('message') or '', 320),
            'metrics': {
                '进度': download_progress,
            },
            'can_run': False,
        })

        install = read_install_status_response()
        install_status = _status_to_background_status(install.get('status'))
        install_progress = _progress_value(install.get('progress'))
        current_package = str(install.get('current_package') or '')
        items.append({
            'id': 'noor-core.whisper-runtime-install',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': 'Whisper 运行时依赖安装',
            'status': install_status,
            'enabled': True,
            'progress': install_progress if install_status == 'running' else (100 if str(install.get('status') or '') == 'completed' else 0),
            'summary': _short_text(install.get('message') or '运行时依赖安装待命'),
            'detail': _short_text(install.get('output') or '', 320),
            'metrics': {
                '进度': install_progress,
                '当前包': current_package,
            },
            'can_run': False,
        })
    except Exception as exc:
        items.append({
            'id': 'noor-core.whisper-background-status',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': 'Whisper 后台状态',
            'status': 'failed',
            'enabled': True,
            'summary': 'Whisper 后台状态读取失败',
            'detail': str(exc),
            'metrics': {},
            'can_run': False,
        })

    try:
        from app.core import database
        from app.knowledge.repository import KnowledgeRepository

        async with database.async_session_maker() as db:
            run = await KnowledgeRepository(db).latest_run()
        stats = run.stats if run and isinstance(run.stats, dict) else {}
        status = _status_to_background_status(run.status if run else 'idle')
        progress = _progress_value(stats.get('percent'))
        processed = int(stats.get('processed') or 0) if isinstance(stats, dict) else 0
        total = int(stats.get('total') or 0) if isinstance(stats, dict) else 0
        items.append({
            'id': 'noor-core.knowledge-rebuild',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': 'Knowledge Core 重建',
            'status': status,
            'enabled': True,
            'last_run_at': run.started_at.isoformat() if run and run.started_at else '',
            'last_started_at': run.started_at.isoformat() if run and run.started_at else '',
            'last_finished_at': run.completed_at.isoformat() if run and run.completed_at else '',
            'progress': progress if status == 'running' else (100 if run and run.status == 'completed' else progress),
            'summary': run.message if run else '知识库重建待命',
            'detail': str(stats.get('phase') or '') if isinstance(stats, dict) else '',
            'metrics': {
                '已处理': processed,
                '总数': total,
                '进度': progress,
            },
            'can_run': False,
        })
    except Exception as exc:
        items.append({
            'id': 'noor-core.knowledge-rebuild',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': 'Knowledge Core 重建',
            'status': 'failed',
            'enabled': True,
            'summary': 'Knowledge Core 状态读取失败',
            'detail': str(exc),
            'metrics': {},
            'can_run': False,
        })

    try:
        cleanup = runtime_cleanup_status()
        last_cleanup = cleanup.get('last_cleanup') or {}
        items.append({
            'id': 'noor-core.runtime-cleanup',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': '运行时临时文件清理',
            'status': _status_to_background_status(cleanup.get('status')),
            'enabled': True,
            'last_run_at': last_cleanup.get('finished_at') or last_cleanup.get('started_at') or '',
            'last_started_at': last_cleanup.get('started_at') or '',
            'last_finished_at': last_cleanup.get('finished_at') or '',
            'progress': 0,
            'summary': cleanup.get('summary') or '运行时清理待命',
            'detail': '清理 6 小时以前的 NOOR / Whisper / FaceFusion 临时目录，不删除模型和可复用推理缓存。',
            'metrics': {
                '候选': int(cleanup.get('candidate_count') or 0),
                '可清理': cleanup.get('summary', '').split(' · ')[0].replace('可清理 ', ''),
                '上次': last_cleanup.get('message') or '未运行',
            },
            'can_run': True,
            'run_action': {
                'plugin_id': 'noor-core',
                'action': 'runtime-cleanup',
                'payload': {'min_age_hours': 6},
            },
        })
    except Exception as exc:
        items.append({
            'id': 'noor-core.runtime-cleanup',
            'plugin_id': 'noor-core',
            'plugin_name': 'NOOR',
            'title': '运行时临时文件清理',
            'status': 'failed',
            'enabled': True,
            'summary': '运行时清理状态读取失败',
            'detail': str(exc),
            'metrics': {},
            'can_run': False,
        })

    return items


@router.get('')
async def list_plugins():
    if not runtime._manifests:
        await runtime.reload_plugins()
    return runtime.list_plugins()


@router.post('/reload')
async def reload_plugins():
    items = await runtime.reload_plugins()
    return {'ok': True, 'count': len(items)}


@router.get('/background/tasks')
async def get_background_tasks():
    items = await runtime.get_background_tasks()
    items.extend(await _get_core_background_tasks())
    return {'ok': True, 'items': items, 'total': len(items)}


@router.post('/resources/search')
async def search_resources(payload: ResourceSearchPayload):
    result = await runtime.search_resources(
        payload.query,
        provider_ids=payload.providers,
        limit_per_plugin=payload.limit_per_plugin,
        requested_downloader_id=payload.requested_downloader_id,
    )
    groups = result.get('groups') if isinstance(result, dict) else result
    items: list[dict[str, Any]] = []
    for group in groups or []:
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
    return {
        'groups': groups,
        'items': items,
        'downloaders': result.get('downloaders') if isinstance(result, dict) else [],
    }


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


@router.websocket('/{plugin_id}/ws/{action}')
async def plugin_action_ws(websocket: WebSocket, plugin_id: str, action: str):
    await websocket.accept()
    should_log = not _is_noisy_plugin_action(action)
    if should_log:
        _plugin_log('info', plugin_id, f'WebSocket 已连接 action={action}')
    try:
        interval = float(websocket.query_params.get('interval') or 5)
    except Exception:
        interval = 5.0
    interval = max(2.0, min(interval, 30.0))
    try:
        while True:
            try:
                data = await runtime.handle_action(plugin_id, action, {})
            except Exception as exc:
                data = {'ok': False, 'error': str(exc)}
            try:
                await websocket.send_json(data)
            except WebSocketDisconnect:
                if should_log:
                    _plugin_log('info', plugin_id, f'WebSocket 已断开 action={action}')
                return
            except Exception as exc:
                if should_log:
                    _plugin_log('warning', plugin_id, f'WebSocket 发送中断 action={action} error={exc}')
                return
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        if should_log:
            _plugin_log('info', plugin_id, f'WebSocket 已断开 action={action}')


@router.delete('/{plugin_id}/images/cache')
async def clear_plugin_image_cache(plugin_id: str):
    handler = runtime.get_handler(plugin_id)
    callback = getattr(handler, 'clear_image_cache', None) if handler is not None else None
    if not callable(callback):
        raise HTTPException(status_code=404, detail='Plugin image cache not supported')
    return callback()


@router.delete('/{plugin_id}')
async def uninstall_plugin(plugin_id: str):
    try:
        await runtime.uninstall_plugin(plugin_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'ok': True}


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
    return await _handle_plugin_action(plugin_id, 'test', PluginActionPayload())


async def _handle_plugin_action(
    plugin_id: str,
    action: str,
    body: PluginActionPayload,
    request: Request | None = None,
):
    start = time.perf_counter()
    should_log = not _is_noisy_plugin_action(action)
    origin = _request_hint(request)
    try:
        if plugin_id == 'noor-core' and action == 'runtime-cleanup':
            min_age_hours = int((body.payload or {}).get('min_age_hours') or 6)
            result = run_runtime_cleanup(min_age_hours=min_age_hours)
            if should_log:
                _plugin_log('info', plugin_id, f'action 完成 action={action} deleted={result.get("deleted_size")} count={result.get("deleted_count")} cost={(time.perf_counter() - start) * 1000:.0f}ms {origin}'.strip())
            return result
        if plugin_id not in runtime._manifests:
            raise LookupError(plugin_id)
        if not runtime.is_enabled(plugin_id):
            disabled_actions = {
                'resolve', 'candidates', 'stats', 'sync', 'overview',
                'device_info', 'tasks', 'about', 'device_config',
            }
            if action not in disabled_actions:
                raise ValueError('plugin disabled')
            result = {'ok': False, 'disabled': True, 'message': 'plugin disabled'}
            if action == 'candidates':
                result['items'] = []
            elif action in {'stats', 'sync'}:
                result['index'] = {}
            elif action == 'overview':
                result['defaults'] = {'target_folder': '', 'link_mode': 0, 'watch_dirs': []}
                result['jobs'] = []
                result['stats'] = {'total': 0, 'running': 0, 'finished': 0, 'failed': 0}
            elif action in {'device_info', 'tasks', 'about', 'device_config'}:
                result['info'] = {}
                result['tasks'] = []
                result['about'] = None
                result['config'] = None
            return result
        result = await runtime.handle_action(plugin_id, action, body.payload)
        if should_log:
            _plugin_log('info', plugin_id, f'action 完成 action={action} {_payload_hint(body.payload)} cost={(time.perf_counter() - start) * 1000:.0f}ms {origin}'.strip())
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/{plugin_id}/actions/{action}')
async def plugin_action(plugin_id: str, action: str, body: PluginActionPayload, request: Request):
    return await _handle_plugin_action(plugin_id, action, body, request)


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
