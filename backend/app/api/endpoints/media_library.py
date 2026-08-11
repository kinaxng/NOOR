"""Media Library API - direct Emby/Jellyfin adapter.

Reconstructed from preserved Python 3.13 bytecode and split recovery helpers.
"""
from __future__ import annotations
import mimetypes, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.api.endpoints.media_library_helpers import ADAPTER_NOT_ACTIVATED as _ADAPTER_NOT_ACTIVATED, VIDEO_EXTS, config_path as _config_path, headers as _headers, load_config as _load_config, map_path as _map_path, parse_item as _parse_item, parse_tags as _parse_tags, save_config as _save_config, server_url as _server_url
from app.api.endpoints.media_library_item_detail import get_item_impl, get_main_nfo_impl, get_siblings_impl
from app.api.endpoints.media_library_hardlinks import build_hardlink_groups_impl, enrich_hardlink_groups_impl, extract_code_from_path_impl, fetch_emby_item_info_impl, hardlink_groups_path_impl, load_hardlink_groups_impl, save_hardlink_groups_impl, scan_inodes_impl, scan_single_group_impl
from app.api.endpoints.media_library_listing import deduplicate_items as _deduplicate_items, item_matches_query as _item_matches_query, apply_filter_and_paginate as _apply_filter_and_paginate
from app.api.endpoints.media_library_deletion import allowed_scan_roots as _allowed_scan_roots, assert_safe_path as _assert_safe_path, collect_chain_delete_targets as _collect_chain_delete_targets, execute_delete_targets as _execute_delete_targets, preview_delete_targets as _preview_delete_targets, remove_file_and_sibling_nfo as _remove_file_and_sibling_nfo
from app.api.endpoints.media_library_streaming import parse_range_header as _parse_range_header, iter_file_range as _iter_file_range

router=APIRouter(prefix='/api/media-library',tags=['media-library'])
_CACHE_TTL=86400
_items_cache:dict[str,tuple[list[dict],float]]={}

class HardlinkDeleteRequest(BaseModel):
 file_path:str; remove_nfo:bool=True; dry_run:bool=False
class SourceChainDeleteRequest(BaseModel):
 source_path:str; hardlink_paths:list[str]=[]; code:str|None=None; dry_run:bool=False
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
  async with httpx.AsyncClient(timeout=10.0) as client:
   resp=await client.get(f'{_server_url(config)}/emby/System/Info',headers=_headers(config.get('api_key','')))
   if resp.status_code==401:return False,'API Key 无效或已过期'
   resp.raise_for_status();return True,f"已连接至 {resp.json().get('ServerName','Emby/Jellyfin')}"
 except httpx.HTTPStatusError as e:
  return (False,'API Key 无效或已过期') if e.response.status_code==401 else (False,f'连接失败: HTTP {e.response.status_code}')
 except Exception as e:return False,f'连接失败: {e}'

async def _list_libraries(config:dict)->list[dict]:
 async with httpx.AsyncClient(timeout=30.0) as client:
  resp=await client.get(f'{_server_url(config)}/emby/Library/MediaFolders',headers=_headers(config.get('api_key','')));resp.raise_for_status();data=resp.json()
 result=[]
 for item in data.get('Items',[]):
  typ=item.get('Type');collection=item.get('CollectionType')
  if typ not in ('movies','tvshows') and collection not in ('movies','tvshows'):continue
  tag=(item.get('ImageTags') or {}).get('Primary');poster=f"{_server_url(config)}/emby/Items/{item['Id']}/Images/Primary?tag={tag}" if tag else None
  result.append({'id':item['Id'],'name':item['Name'],'type':collection or typ or 'unknown','poster_url':poster})
 return result

async def _list_items(config:dict,library_id:str,limit:int=50,offset:int=0,filter:Optional[str]=None,q:Optional[str]=None,force_refresh:bool=False)->tuple[list[dict],int]:
 async with httpx.AsyncClient(timeout=60.0) as client:
  resp=await client.get(f'{_server_url(config)}/emby/Items',headers=_headers(config.get('api_key','')),params={'ParentId':library_id,'IncludeItemTypes':'Movie','Recursive':'true','Fields':'MediaSources,Path,DateCreated,Studios,ImageTags','Limit':limit,'StartIndex':offset,'SortBy':'DateCreated','SortOrder':'Descending'});resp.raise_for_status();data=resp.json()
 items=_deduplicate_items([_parse_item(i,config) for i in data.get('Items',[])])
 return _apply_filter_and_paginate(items,filter,q,0,len(items))

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

@router.get('')
async def get_status():
 config=_load_config()
 if not config.get('server_url') or not config.get('api_key'):return MediaLibraryStatus(available=False,current=None,message=_ADAPTER_NOT_ACTIVATED)
 return MediaLibraryStatus(available=True,current=MediaAdapterMeta(id='emby',name='Emby / Jellyfin',version='1.0.0',description='连接 Emby 或 Jellyfin 媒体服务器',author='NOOR'),message=None)
@router.get('/config')
async def get_config():return {'config':_load_config()}
@router.post('/config')
async def save_config(config:dict):
 existing=_load_config();existing.update(config);_save_config(existing);_items_cache.clear();return {'ok':True}
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
 config=_load_config();_,roots=_allowed_scan_roots(config);path=Path(req.file_path).resolve();_assert_safe_path(path,roots,'硬链接文件')
 if not path.exists():raise HTTPException(404,'文件不存在')
 if req.dry_run:return {'dry_run':True,'planned_files':[str(path)]+([str(path.with_suffix('.nfo'))] if req.remove_nfo and path.with_suffix('.nfo').exists() else [])}
 return {'deleted_files':_remove_file_and_sibling_nfo(path,remove_nfo=req.remove_nfo)}
@router.post('/hardlinks/delete-source-chain')
async def delete_source_chain(req:SourceChainDeleteRequest):
 config=_load_config();sources,hardlinks=_allowed_scan_roots(config);source=Path(req.source_path).resolve();_assert_safe_path(source,sources,'源文件');paths=[Path(x).resolve() for x in req.hardlink_paths]
 for path in paths:_assert_safe_path(path,hardlinks,'硬链接文件')
 dirs,files=_collect_chain_delete_targets(source,paths,code=req.code,source_roots=sources,hardlink_roots=hardlinks)
 return {'dry_run':True,**_preview_delete_targets(dirs,files)} if req.dry_run else _execute_delete_targets(dirs,files)
@router.post('/hardlinks/delete-group')
async def delete_hardlink_group(req:GroupDeleteRequest):
 config=_load_config();sources,hardlinks=_allowed_scan_roots(config);dirs=set();files=set()
 for entry in req.entries:
  source=Path(entry.source_path).resolve() if entry.source_path else None
  if source:_assert_safe_path(source,sources,'源文件')
  paths=[Path(x).resolve() for x in entry.hardlink_paths]
  for path in paths:_assert_safe_path(path,hardlinks,'硬链接文件')
  d,f=_collect_chain_delete_targets(source,paths,code=req.code,source_roots=sources,hardlink_roots=hardlinks);dirs.update(d);files.update(f)
 return {'dry_run':True,**_preview_delete_targets(dirs,files)} if req.dry_run else _execute_delete_targets(dirs,files)
