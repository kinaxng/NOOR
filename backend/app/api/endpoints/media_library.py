"""Media Library API - direct Emby/Jellyfin adapter.

Reconstructed from preserved Python 3.13 bytecode and split recovery helpers.
"""
from __future__ import annotations
import mimetypes, os, secrets, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.api.endpoints.media_library_helpers import ADAPTER_NOT_ACTIVATED as _ADAPTER_NOT_ACTIVATED, VIDEO_EXTS, config_path as _config_path, env_source_dir, headers as _headers, load_config as _load_config, local_media_root, map_path as _map_path, parse_item as _parse_item, parse_tags as _parse_tags, save_config as _save_config, server_url as _server_url
from app.api.endpoints.media_library_item_detail import get_item_impl, get_main_nfo_impl, get_siblings_impl, resolve_playback_stream_url_impl
from app.api.endpoints.media_library_hardlinks import build_hardlink_groups_impl, enrich_hardlink_groups_impl, extract_code_from_path_impl as _extract_code_from_path, fetch_emby_item_info_impl as _fetch_emby_item_info, hardlink_groups_path_impl, load_hardlink_groups_impl, save_hardlink_groups_impl, scan_inodes_impl, scan_single_group_impl
from app.api.endpoints.media_library_listing import apply_filter_and_paginate as _apply_filter_and_paginate, deduplicate_items as _deduplicate_items, item_matches_query as _item_matches_query, item_variant_penalty as _item_variant_penalty, merge_group_metadata as _merge_group_metadata, pick_group_representative as _pick_group_representative
from app.api.endpoints.media_library_deletion import allowed_scan_roots as _allowed_scan_roots, assert_safe_path as _assert_safe_path, collect_chain_delete_targets as _collect_chain_delete_targets, delete_plan_from_hardlink_entry as _delete_plan_from_hardlink_entry, delete_plan_from_inode_chain as _delete_plan_from_inode_chain, directory_matches_target_videos as _directory_matches_target_videos, execute_delete_targets as _execute_delete_targets, find_inode_chain_for_path as _find_inode_chain_for_path, is_under_roots as _is_under_roots, normalize_code_token as _normalize_code_token, parent_is_code_bucket as _parent_is_code_bucket, path_matches_hardlink_entry as _path_matches_hardlink_entry, preview_delete_targets as _preview_delete_targets, remove_file_and_sibling_nfo as _remove_file_and_sibling_nfo
from app.api.endpoints.media_library_streaming import parse_range_header as _parse_range_header, iter_file_range as _iter_file_range
from app.api.system import SystemLogManager, _webhook_source, _webhook_summary

router=APIRouter(prefix='/api/media-library',tags=['media-library'])
_CACHE_TTL=86400
_items_cache:dict[str,tuple[list[dict],float]]={}
_sync_version=0
_last_invalidated_at:float|None=None
_last_webhook_at:float|None=None
MDC_NG_ACTOR_MAPPING_RELATIVE_PATH = Path("data") / "data" / "mapping_actor.xml"


# Public names from the pre-split media_library module.
config_path = _config_path
headers = _headers
load_config = _load_config
server_url = _server_url
map_path = _map_path
parse_tags = _parse_tags
parse_item = _parse_item

def _iso_from_ts(value:float|None)->str|None:
 return datetime.fromtimestamp(value,timezone.utc).isoformat() if value is not None else None

def _sync_state_payload()->dict:
 return {'version':_sync_version,'last_invalidated_at':_iso_from_ts(_last_invalidated_at),'last_webhook_at':_iso_from_ts(_last_webhook_at),'cache_keys':sorted(_items_cache.keys())}

def _bump_sync_state(*,webhook:bool=False)->dict:
 global _sync_version,_last_invalidated_at,_last_webhook_at
 _items_cache.clear();now=time.time();_sync_version+=1;_last_invalidated_at=now
 if webhook:_last_webhook_at=now
 return _sync_state_payload()

def _ensure_webhook_token(config:dict)->dict:
 if str(config.get('webhook_token') or '').strip():return config
 next_config=dict(config);next_config['webhook_token']=secrets.token_urlsafe(24);_save_config(next_config);return _load_config()


async def _media_item_delete_plan(item_id: str, config: dict) -> tuple[str, set[Path], set[Path]]:
    try:
        item = await _get_item(config, item_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取媒体项目失败: {exc}") from exc
    if not item:
        raise HTTPException(status_code=404, detail=f"未找到媒体项目: {item_id}")
    file_path = str(item.get("file_path") or "").strip()
    if not file_path:
        raise HTTPException(status_code=400, detail="媒体项目没有可删除的文件路径")
    source_roots, hardlink_roots = _allowed_scan_roots(config)
    if not source_roots and not hardlink_roots:
        raise HTTPException(status_code=400, detail="未配置扫描组路径，无法执行删除")
    target = Path(file_path).resolve()
    _assert_safe_path(target, source_roots + hardlink_roots, label="媒体文件路径")
    groups = _enrich_hardlink_groups(_load_hardlink_groups()).get("groups") or []
    for group in groups:
        for entry in group.get("entries") or []:
            if not _path_matches_hardlink_entry(target, entry):
                continue
            delete_dirs, delete_files = _delete_plan_from_hardlink_entry(
                entry,
                code=group.get("code") or _extract_code_from_path(str(target)),
                source_roots=source_roots,
                hardlink_roots=hardlink_roots,
            )
            return str(group.get("code") or item.get("name") or target.name), delete_dirs, delete_files
    delete_dirs, delete_files = _delete_plan_from_inode_chain(
        target,
        code=_extract_code_from_path(str(target)),
        source_roots=source_roots,
        hardlink_roots=hardlink_roots,
    )
    return str(item.get("name") or target.name), delete_dirs, delete_files

class HardlinkDeleteRequest(BaseModel):
 file_path:str; remove_nfo:bool=True; dry_run:bool=False
class SourceChainDeleteRequest(BaseModel):
 source_path:str; hardlink_paths:list[str]=[]; code:str|None=None; dry_run:bool=False
class ItemChainDeleteRequest(BaseModel):
 item_id:str; dry_run:bool=False
class HardlinkEntryDeletePayload(BaseModel):
 source_path:str|None=None; hardlink_paths:list[str]=[]
class GroupDeleteRequest(BaseModel):
 code:str; entries:list[HardlinkEntryDeletePayload]; dry_run:bool=False
class MediaAdapterMeta(BaseModel):
 id:str;name:str;version:str;description:str;author:str
class MediaLibraryStatus(BaseModel):
 available:bool;current:MediaAdapterMeta|None;message:str|None

async def _test_connection(config:dict)->tuple[bool,str]:
 try:
  async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
   resp=await client.get(f'{_server_url(config)}/emby/System/Info',headers=_headers(config.get('api_key','')))
   if resp.status_code==401:return False,'API Key 无效或已过期'
   resp.raise_for_status();return True,f"已连接至 {resp.json().get('ServerName','Emby/Jellyfin')}"
 except httpx.HTTPStatusError as e:
  return (False,'API Key 无效或已过期') if e.response.status_code==401 else (False,f'连接失败: HTTP {e.response.status_code}')
 except Exception as e:return False,f'连接失败: {e}'

async def _list_libraries(config:dict)->list[dict]:
 async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
  resp=await client.get(f'{_server_url(config)}/emby/Library/MediaFolders',headers=_headers(config.get('api_key','')));resp.raise_for_status();data=resp.json()
 result=[]
 for item in data.get('Items',[]):
  typ=item.get('Type');collection=item.get('CollectionType')
  if typ not in ('movies','tvshows') and collection not in ('movies','tvshows'):continue
  tag=(item.get('ImageTags') or {}).get('Primary');poster=f"{_server_url(config)}/emby/Items/{item['Id']}/Images/Primary?tag={tag}" if tag else None
  result.append({'id':item['Id'],'name':item['Name'],'type':collection or typ or 'unknown','poster_url':poster})
 return result

async def _list_items(config:dict,library_id:str,limit:int=50,offset:int=0,filter:Optional[str]=None,q:Optional[str]=None,force_refresh:bool=False)->tuple[list[dict],int]:
 async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
  resp=await client.get(f'{_server_url(config)}/emby/Items',headers=_headers(config.get('api_key','')),params={'ParentId':library_id,'IncludeItemTypes':'Movie','Recursive':'true','Fields':'MediaSources,Path,DateCreated,Studios,ImageTags','Limit':limit,'StartIndex':offset,'SortBy':'DateCreated','SortOrder':'Descending'});resp.raise_for_status();data=resp.json()
 items=_deduplicate_items([_parse_item(i,config) for i in data.get('Items',[])])
 payload=_apply_filter_and_paginate(items,filter,q,0,len(items))
 return payload['items'],payload['total']

async def _get_siblings(config,parent_id,current_id):return await get_siblings_impl(config,parent_id,current_id,httpx_module=httpx,server_url_fn=_server_url,headers_fn=_headers,map_path_fn=_map_path)
def _get_main_nfo(file_path):return get_main_nfo_impl(file_path)
async def _get_item(config,item_id):return await get_item_impl(config,item_id,httpx_module=httpx,server_url_fn=_server_url,headers_fn=_headers,map_path_fn=_map_path,parse_tags_fn=_parse_tags,get_siblings_fn=_get_siblings,get_main_nfo_fn=_get_main_nfo)
def _hardlink_groups_path():return hardlink_groups_path_impl(_config_path)
def _hardlink_groups_last_scanned_at():
 try:return datetime.fromtimestamp(_hardlink_groups_path().stat().st_mtime,timezone.utc).isoformat()
 except OSError:return None
def _scan_inodes(d):return scan_inodes_impl(d)
def _scan_single_group(s,h):return scan_single_group_impl(s,h,scan_inodes_fn=_scan_inodes)
async def _build_hardlink_groups():return await build_hardlink_groups_impl(_load_config(),scan_single_group_fn=_scan_single_group,extract_code_from_path_fn=extract_code_from_path_impl)
def _save_hardlink_groups(g):save_hardlink_groups_impl(g,hardlink_groups_path_fn=_hardlink_groups_path)
def _load_hardlink_groups():return load_hardlink_groups_impl(hardlink_groups_path_fn=_hardlink_groups_path)
def _enrich_hardlink_groups(g):return enrich_hardlink_groups_impl(g)

def _configured(config):
 if not config.get('server_url') or not config.get('api_key'):raise HTTPException(503,_ADAPTER_NOT_ACTIVATED)


def _item_matches_filter(item: dict, filter_str: str) -> bool:
    tags = item.get("tags", {})
    if not tags:
        return False
    if filter_str == "cracked" and tags.get("is_cracked"):
        return True
    if filter_str == "chinese" and tags.get("has_chinese"):
        return True
    if filter_str == "leaked" and tags.get("release_type_key") == "leaked":
        return True
    if filter_str == "uncensored" and tags.get("release_type_key") == "uncensored":
        return True
    return False


def _paginate_filter(all_items: list, filter_str: str | None, q: str | None, offset: int, limit: int):
    filtered = [item for item in all_items if _item_matches_filter(item, filter_str)] if filter_str else list(all_items)
    filtered = [item for item in filtered if _item_matches_query(item, q)] if q else filtered
    total = len(filtered)
    return {"items": filtered[offset:offset + limit], "total": total}

@router.get('')
async def get_status():
 config=_load_config()
 if not config.get('server_url') or not config.get('api_key'):return MediaLibraryStatus(available=False,current=None,message=_ADAPTER_NOT_ACTIVATED)
 return MediaLibraryStatus(available=True,current=MediaAdapterMeta(id='emby',name='Emby / Jellyfin',version='1.0.0',description='连接 Emby 或 Jellyfin 媒体服务器',author='NOOR'),message=None)
@router.get('/config')
async def get_config():return {'config':_ensure_webhook_token(_load_config())}
@router.post('/config')
async def save_config(config:dict):
 existing=_load_config();existing.update(config);_save_config(existing);return {'ok':True,'sync_state':_bump_sync_state()}
@router.get('/sync-state')
async def get_sync_state():return _sync_state_payload()
@router.post('/cache/invalidate')
async def invalidate_cache():
 state=_bump_sync_state();SystemLogManager.get_instance().add_log('info','[MediaLibrary] 媒体库缓存已手动刷新',source='media_library');return {'ok':True,'sync_state':state}
@router.post('/webhook/emby')
async def emby_webhook(request:Request,token:str|None=None):
 config=_ensure_webhook_token(_load_config());expected=str(config.get('webhook_token') or '').strip();provided=str(token or request.headers.get('X-NOOR-Webhook-Token') or '').strip()
 if not expected or not secrets.compare_digest(provided,expected):raise HTTPException(403,'Invalid webhook token')
 body=await request.body()
 if len(body)>1024*1024:raise HTTPException(413,'Webhook 请求超过 1 MB')
 payload=None
 if body:
  try:
   import json
   payload=json.loads(body)
  except Exception:payload=None
 state=_bump_sync_state(webhook=True);source=_webhook_source(request);summary=_webhook_summary(payload)
 SystemLogManager.get_instance().add_log('info',f'[MediaLibrary] 收到 Emby Webhook，已刷新媒体库缓存 · {summary}',source=f'Emby · {source}',event_type=(payload.get('Event') if isinstance(payload,dict) else None))
 return {'ok':True,'source':source,'summary':summary,'sync_state':state}
@router.post('/test')
async def test_connection(config:dict|None=None):
 cfg=config if config is not None else _load_config()
 if not cfg:return {'ok':False,'message':_ADAPTER_NOT_ACTIVATED,'libraries':[]}
 ok,msg=await _test_connection(cfg)
 try:libs=await _list_libraries(cfg)
 except Exception:libs=[]
 return {'ok':ok,'message':msg,'libraries':libs}
@router.get('/libraries')
async def get_libraries():
 config=_load_config();_configured(config)
 try:return {'libraries':await _list_libraries(config)}
 except Exception:return {'libraries':[]}
@router.get('/items')
async def get_items(library_id:str|None=None,limit:int=50,offset:int=0,filter:str|None=None,q:str|None=None,force_refresh:bool=Query(False)):
 config=_load_config();_configured(config);now=time.time()
 try:
  if not library_id:
   enabled=[x.strip() for x in config.get('enabled_library_ids','').split(',') if x.strip()]
   ids=enabled or [x['id'] for x in await _list_libraries(config)];all_items=[]
   for lid in ids:
    key='all_'+lid;cached=_items_cache.get(key)
    if cached and not force_refresh and now-cached[1]<_CACHE_TTL:items=cached[0]
    else:items,_=await _list_items(config,lid,2000,0,force_refresh=force_refresh);_items_cache[key]=(items,now)
    all_items.extend(items)
   all_items.sort(key=lambda x:x.get('date_created') or '',reverse=True);return _apply_filter_and_paginate(all_items,filter,q,offset,limit)
  cached=_items_cache.get(library_id)
  if cached and not force_refresh and now-cached[1]<_CACHE_TTL:return _apply_filter_and_paginate(cached[0],filter,q,offset,limit)
  all_items,_=await _list_items(config,library_id,2000,0,force_refresh=force_refresh);_items_cache[library_id]=(all_items,now);return _apply_filter_and_paginate(all_items,filter,q,offset,limit)
 except Exception as e:raise HTTPException(502,f'获取媒体失败: {e}')
@router.get('/item/{item_id}')
async def get_item(item_id:str):
 config=_load_config();_configured(config)
 try:
  item=await _get_item(config,item_id)
  if not item:raise HTTPException(404,f'未找到媒体项目: {item_id}')
  return item
 except HTTPException:raise
 except Exception as e:raise HTTPException(502,f'获取详情失败: {e}')
@router.get('/hardlinks/groups')
async def get_hardlink_groups():return {**_enrich_hardlink_groups(_load_hardlink_groups()),'last_scanned_at':_hardlink_groups_last_scanned_at()}
@router.get('/stream/{item_id}')
async def stream_emby_item(request:Request,item_id:str,media_source_id:str|None=Query(default=None),container:str|None=Query(default=None)):
 config=_load_config();server_url=_server_url(config);api_key=config.get('api_key','')
 if not server_url or not api_key:raise HTTPException(400,'Emby 未配置，无法播放')
 playback=await resolve_playback_stream_url_impl(config,item_id,media_source_id=media_source_id,container=container,httpx_module=httpx,server_url_fn=_server_url,headers_fn=_headers)
 upstream_url=playback.get('url')
 if not upstream_url:raise HTTPException(502,'未能解析 Emby 播放地址')
 upstream_headers={}
 if request.headers.get('range'):upstream_headers['Range']=request.headers['range']
 client=httpx.AsyncClient(timeout=None,trust_env=False)
 try:
  upstream_request=client.build_request('GET',upstream_url,headers=upstream_headers)
  upstream_response=await client.send(upstream_request,stream=True)
 except Exception as exc:
  await client.aclose();raise HTTPException(502,f'Emby 播放流打开失败: {exc}') from exc
 if upstream_response.status_code>=400:
  try:detail=await upstream_response.aread()
  finally:await upstream_response.aclose();await client.aclose()
  message=detail.decode('utf-8',errors='ignore') if detail else ''
  raise HTTPException(upstream_response.status_code,message or f"Emby 播放失败 ({playback.get('play_method') or 'unknown'})")
 response_headers={}
 for header_name in ('content-type','content-length','accept-ranges','content-range','cache-control','etag','last-modified'):
  value=upstream_response.headers.get(header_name)
  if value:response_headers[header_name]=value
 if playback.get('play_method'):response_headers['x-noor-play-method']=str(playback['play_method'])
 if playback.get('play_session_id'):response_headers['x-noor-play-session-id']=str(playback['play_session_id'])
 async def _iter_upstream():
  try:
   async for chunk in upstream_response.aiter_bytes():
    if chunk:yield chunk
  finally:await upstream_response.aclose();await client.aclose()
 return StreamingResponse(_iter_upstream(),status_code=upstream_response.status_code,headers=response_headers,media_type=upstream_response.headers.get('content-type') or 'application/octet-stream')
@router.post('/hardlinks/scan')
async def scan_hardlinks():
 config=_load_config()
 if not config.get('scan_groups'):raise HTTPException(400,'未配置扫描组')
 groups=await _build_hardlink_groups();_save_hardlink_groups(groups);return {**_enrich_hardlink_groups(groups),'last_scanned_at':_hardlink_groups_last_scanned_at()}
@router.get('/hardlinks/preview-file')
async def preview_hardlink_file(request:Request,path:str=Query(...)):
 config=_load_config();source_roots,hardlink_roots=_allowed_scan_roots(config);target=Path(_map_path(path,config)).resolve();_assert_safe_path(target,source_roots+hardlink_roots,'预览文件')
 if not target.is_file():raise HTTPException(404,'文件不存在')
 if target.suffix.lower() not in VIDEO_EXTS:raise HTTPException(400,'仅支持视频文件预览')
 size=target.stat().st_size;parsed=_parse_range_header(request.headers.get('range'),size);media_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
 if not parsed:return StreamingResponse(_iter_file_range(target,0,size-1),media_type=media_type,headers={'Accept-Ranges':'bytes','Content-Length':str(size)})
 start,end=parsed;return StreamingResponse(_iter_file_range(target,start,end),status_code=206,media_type=media_type,headers={'Accept-Ranges':'bytes','Content-Range':f'bytes {start}-{end}/{size}','Content-Length':str(end-start+1)})
@router.post('/hardlinks/delete-hardlink')
async def delete_hardlink_file(req:HardlinkDeleteRequest):
 config=_load_config();sources,hardlinks=_allowed_scan_roots(config);path=Path(req.file_path).resolve();_assert_safe_path(path,sources+hardlinks,'硬链接文件')
 if not path.exists():raise HTTPException(404,'文件不存在')
 if req.dry_run:return {'ok':True,'dry_run':True,'planned_files':[str(path)]+([str(path.with_suffix('.nfo'))] if req.remove_nfo and path.with_suffix('.nfo').exists() else [])}
 result={'ok':True,'deleted_files':_remove_file_and_sibling_nfo(path,remove_nfo=req.remove_nfo)}
 if not result['deleted_files']:raise HTTPException(400,'未删除任何文件')
 return result
@router.post('/hardlinks/delete-source-chain')
async def delete_source_chain(req:SourceChainDeleteRequest):
 config=_load_config();sources,hardlinks=_allowed_scan_roots(config);source=Path(req.source_path).resolve();_assert_safe_path(source,sources+hardlinks,'主文件路径');paths=[Path(x).resolve() for x in req.hardlink_paths]
 for path in paths:_assert_safe_path(path,sources+hardlinks,'硬链接路径')
 dirs,files=_collect_chain_delete_targets(source,paths,code=req.code,source_roots=sources,hardlink_roots=hardlinks)
 result={'ok':True,'dry_run':True,**_preview_delete_targets(dirs,files)} if req.dry_run else {'ok':True,**_execute_delete_targets(dirs,files)}
 return result
@router.post('/items/delete-chain')
async def delete_item_chain(req:ItemChainDeleteRequest):
 config=_load_config();_configured(config)
 code,delete_dirs,delete_files=await _media_item_delete_plan(req.item_id,config)
 if req.dry_run:return {'ok':True,'dry_run':True,'code':code,**_preview_delete_targets(delete_dirs,delete_files)}
 result={'ok':True,'code':code,**_execute_delete_targets(delete_dirs,delete_files)}
 result['sync_state']=_bump_sync_state()
 return result
@router.post('/hardlinks/delete-group')
async def delete_hardlink_group(req:GroupDeleteRequest):
 config=_load_config();sources,hardlinks=_allowed_scan_roots(config);dirs=set();files=set()
 for entry in req.entries:
  source=Path(entry.source_path).resolve() if entry.source_path else None
  if source:_assert_safe_path(source,sources+hardlinks,'主文件路径')
  paths=[Path(x).resolve() for x in entry.hardlink_paths]
  for path in paths:_assert_safe_path(path,sources+hardlinks,'硬链接路径')
  d,f=_collect_chain_delete_targets(source,paths,code=req.code,source_roots=sources,hardlink_roots=hardlinks);dirs.update(d);files.update(f)
 result={'ok':True,'dry_run':True,**_preview_delete_targets(dirs,files)} if req.dry_run else {'ok':True,**_execute_delete_targets(dirs,files)}
 return result

# Compatibility re-exports for code written against the pre-split media_library API.
def sort_key(item: dict) -> tuple:
    path = item.get("file_path") or ""
    name = item.get("name") or item.get("label") or ""
    return (bool(path), -len(os.path.basename(path)) if path else 0, name.lower())


async def delete_media_item_chain(req):
    return await delete_item_chain(req)


async def get_duplicate_actors(limit: int = 2000):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_duplicates(limit=limit)


async def get_actor_profile(actor_id: str, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.get_actor(actor_id, lang=lang)


async def update_actor_profile(actor_id: str, req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.update_actor(actor_id, req, lang=lang)


async def diagnose_actor_delete(actor_id: str):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_delete_diagnostics(actor_id)


async def delete_actor_profile(actor_id: str):
    from app.api.endpoints import actors as actor_api
    return await actor_api.delete_actor(actor_id)


async def get_actor_mapping_status():
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_mapping_status()


async def get_actor_mapping_matches(limit: int = 5000, only_candidates: bool = False, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_mapping_matches(limit=limit, only_candidates=only_candidates, lang=lang)


async def get_actor_tmdb_backfill_progress(progress_key: str):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_tmdb_backfill_progress(progress_key)


async def get_actor_name_sync_progress(progress_key: str):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_name_sync_progress(progress_key)


async def get_actor_mapping_merge_plan(mapping_id: str, target_name: str | None = None, target_actor_id: str | None = None, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.actor_mapping_merge_plan(mapping_id=mapping_id, target_name=target_name, target_actor_id=target_actor_id, lang=lang)


async def execute_actor_mapping_merge_batch(req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.execute_actor_mapping_batch(req, lang=lang)


async def upload_actor_mapping(file):
    from app.api.endpoints import actors as actor_api
    return await actor_api.upload_actor_mapping(file)


async def get_latest_actor_mapping_upload():
    from app.api.endpoints import actors as actor_api
    return await actor_api.get_latest_actor_mapping_upload()


async def sync_online_actor_mapping():
    from app.api.endpoints import actors as actor_api
    return await actor_api.sync_online_actor_mapping()


async def import_latest_actor_mapping():
    from app.api.endpoints import actors as actor_api
    return await actor_api.import_latest_actor_mapping()


async def get_actors(limit: int = 60, offset: int = 0, q: str | None = None, sort_by: str = "SortName", sort_order: str = "Ascending", lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.get_actors(limit=limit, offset=offset, q=q, sort_by=sort_by, sort_order=sort_order, lang=lang)


async def get_actor_movies(actor_id: str, limit: int = 120, offset: int = 0):
    from app.api.endpoints import actors as actor_api
    return await actor_api.get_actor_movies(actor_id=actor_id, limit=limit, offset=offset)


async def upload_actor_avatar(actor_id: str, file, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.upload_actor_avatar(actor_id=actor_id, file=file, lang=lang)


async def set_actor_avatar_from_url(actor_id: str, req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.set_actor_avatar_from_url(actor_id=actor_id, req=req, lang=lang)


async def preview_actor_tmdb_metadata(actor_id: str, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.preview_actor_tmdb_metadata(actor_id=actor_id, lang=lang)


async def apply_actor_tmdb_metadata(actor_id: str, req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.apply_actor_tmdb_metadata(actor_id=actor_id, req=req, lang=lang)


async def sync_mdc_ng_actor_mapping():
    from app.api.endpoints import actors as actor_api
    return await actor_api.sync_mdc_ng_actor_mapping()


async def clear_actor_mapping():
    from app.api.endpoints import actors as actor_api
    return await actor_api.clear_actor_mapping()


async def preview_actor_tmdb_backfill(limit: int = 5000, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.preview_actor_tmdb_backfill(lang=lang)


async def apply_actor_tmdb_backfill(req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.apply_actor_tmdb_backfill(req=req, lang=lang)


async def preview_actor_name_sync(lang: str | None = None, limit: int = 5000):
    from app.api.endpoints import actors as actor_api
    return await actor_api.preview_actor_name_sync(lang=lang)


async def apply_actor_name_sync(req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.apply_actor_name_sync(req=req, lang=lang)


async def execute_actor_mapping_merge(req, lang: str | None = None):
    from app.api.endpoints import actors as actor_api
    return await actor_api.execute_actor_mapping_merge(req=req, lang=lang)


MediaItemDeleteRequest = ItemChainDeleteRequest

_ACTOR_COMPAT_EXPORTS = {
    "ActorAvatarUrlRequest",
    "ActorMappingMergeBatchRequest",
    "ActorMappingMergeRequest",
    "ActorNameSyncRequest",
    "ActorProfileUpdateRequest",
    "ActorTmdbApplyRequest",
    "ActorTmdbBackfillRequest",
}

_ACTOR_COMPAT_ALIASES = {
    "_actor_mapping_name_index": "_mapping_index",
    "_actor_mapping_store_path": "_mapping_store_path",
    "_actor_mapping_sync_state_path": "_mapping_sync_state_path",
    "_actor_profile_overrides_path": "_profile_overrides_path",
    "_apply_actor_profile_override": "_apply_profile_override",
    "_build_actor_mapping_merge_plan": "_merge_plan",
    "_configured_mdc_ng_actor_mapping_path": "_mapping_path",
    "_configured_mdc_ng_root_path": "_configured_mapping_root",
    "_execute_actor_mapping_merge": "_execute_merge",
    "_get_actor_profile": "_actor_profile",
    "_load_actor_mapping_records": "_mapping_records",
    "_load_actor_profile_overrides": "_load_profile_overrides",
    "_localized_mapping_name": "_mapping_display_name",
    "_parse_actor_mapping_xml": "_parse_mapping_xml",
    "_preview_actor_name_sync": "_name_sync_candidates",
    "_preview_actor_tmdb_backfill": "_tmdb_backfill_candidates",
    "_save_actor_mapping_records": "_save_mapping_records",
    "_save_actor_profile_overrides": "_save_profile_overrides",
    "_sync_actor_mapping_from_mdc_ng": "_sync_mapping_from_mdc_ng",
}


def __getattr__(name: str):
    if name in _ACTOR_COMPAT_EXPORTS:
        from app.api.endpoints import actors as actor_api
        return getattr(actor_api, name)
    alias = _ACTOR_COMPAT_ALIASES.get(name)
    if alias:
        from app.api.endpoints import actors as actor_api
        return getattr(actor_api, alias)
    from app.api.endpoints import actors as actor_api
    if hasattr(actor_api, name):
        return getattr(actor_api, name)
    from app.api.endpoints import media_library_helpers as helper_api
    if hasattr(helper_api, name):
        return getattr(helper_api, name)
    from app.api.endpoints import media_library_actor_compat as compat_api
    if hasattr(compat_api, name):
        return getattr(compat_api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
