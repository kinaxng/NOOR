"""Legacy actor helper compatibility backed by the current split implementation."""
from __future__ import annotations

import base64
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request

from app.api.endpoints import actors as actor_api
from app.api.endpoints import media_library as media
from app.core.runtime_paths import data_path


def _provider_id(provider_ids: dict, *keys: str) -> str | None:
    if not isinstance(provider_ids, dict):
        return None
    wanted = {key.lower() for key in keys}
    for key, value in provider_ids.items():
        if str(key).lower() in wanted and str(value or "").strip():
            return str(value).strip()
    return None


def _tmdb_credentials(config: dict) -> tuple[str, str]:
    api_key = str(config.get("tmdb_api_key") or os.environ.get("TMDB_API_KEY") or "").strip()
    api_token = str(config.get("tmdb_api_token") or os.environ.get("TMDB_API_TOKEN") or "").strip()
    return api_key, api_token


def _tmdb_request_params(config: dict, params: dict | None = None) -> dict:
    api_key, api_token = _tmdb_credentials(config)
    if not api_key and not api_token:
        raise HTTPException(status_code=400, detail="TMDB API Key 未配置，请在系统设置中填写 TMDB API Key")
    next_params = dict(params or {})
    if api_key and not api_token:
        next_params["api_key"] = api_key
    return next_params


def _tmdb_headers(config: dict) -> dict:
    _api_key, api_token = _tmdb_credentials(config)
    headers = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    return headers


def _tmdb_lang_candidates(lang: str | None) -> list[str]:
    normalized = str(lang or "").replace("_", "-")
    out: list[str] = []
    if normalized:
        out.append(normalized)
    if normalized.lower().startswith("zh"):
        out.extend(["zh-CN", "zh-TW", "ja-JP", "en-US"])
    elif normalized.lower().startswith("ja"):
        out.extend(["ja-JP", "zh-CN", "en-US"])
    else:
        out.extend(["en-US", "ja-JP", "zh-CN"])
    seen: set[str] = set()
    return [item for item in out if item and not (item in seen or seen.add(item))]


def _tmdb_profile_url(profile_path: str | None) -> str:
    path = str(profile_path or "").strip()
    return f"https://image.tmdb.org/t/p/original{path}" if path else ""


async def _tmdb_get_json(client: httpx.AsyncClient, config: dict, path: str, *, params: dict | None = None) -> dict:
    response = await client.get(
        f"https://api.themoviedb.org/3{path}",
        headers=_tmdb_headers(config),
        params=_tmdb_request_params(config, params),
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _tmdb_pick_biography(person: dict, lang: str | None = None) -> str:
    biography = str(person.get("biography") or "").strip()
    if biography:
        return biography
    translations = (
        (person.get("translations") or {}).get("translations")
        or (person.get("translations") or {}).get("data")
        or []
    )
    if not isinstance(translations, list):
        return ""
    by_lang: dict[str, str] = {}
    for item in translations:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        bio = str(data.get("biography") or "").strip()
        if not bio:
            continue
        iso = str(item.get("iso_639_1") or "").lower()
        country = str(item.get("iso_3166_1") or "").upper()
        by_lang[f"{iso}-{country}"] = bio
        by_lang.setdefault(iso, bio)
    for candidate in _tmdb_lang_candidates(lang):
        key = candidate.lower()
        if key in by_lang:
            return by_lang[key]
        short = key.split("-", 1)[0]
        if short in by_lang:
            return by_lang[short]
    return ""


def _merge_external_urls(*items: dict | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip()
            if not clean_key or not clean_value:
                continue
            if clean_key not in merged:
                merged[clean_key] = clean_value
                continue
            if merged[clean_key] == clean_value:
                continue
            suffix = 2
            while f"{clean_key}_{suffix}" in merged:
                suffix += 1
            merged[f"{clean_key}_{suffix}"] = clean_value
    return merged


def _actor_metadata_diff(current: dict, proposal: dict) -> list[dict]:
    fields = [
        ("name", "名称"),
        ("sort_name", "排序名"),
        ("overview", "简介"),
        ("birthday", "出生日期"),
        ("deathday", "去世日期"),
        ("place_of_birth", "出生地"),
        ("gender", "性别"),
        ("known_for_department", "领域"),
        ("homepage", "主页"),
        ("tmdb_id", "TMDB"),
        ("imdb_id", "IMDB"),
        ("image_url", "头像"),
    ]
    diffs = []
    for key, label in fields:
        old = str(current.get(key) or "").strip()
        new = str(proposal.get(key) or "").strip()
        if old != new and new:
            diffs.append({"field": key, "label": label, "current": old, "proposed": new})
    return diffs


def _localized_mapping_name(record: dict | None, fallback: str, lang: str | None = None) -> str:
    return actor_api._mapping_display_name(record, lang) if record else fallback


def _normalize_actor_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).translate(str.maketrans({"菫": "堇"}))
    return re.sub(r"[\s\u3000・·._\-]+", "", normalized).lower()


def _split_mapping_keywords(value: str | None) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,，、;；|/]+", raw)
    out: list[str] = []
    for part in parts:
        name = part.strip()
        if name and name not in out:
            out.append(name)
    return out


def _normalize_mapping_record(attrs: dict[str, str]) -> dict:
    zh_cn = str(attrs.get("zh_cn") or "").strip()
    zh_tw = str(attrs.get("zh_tw") or "").strip()
    jp = str(attrs.get("jp") or "").strip()
    keyword_names = _split_mapping_keywords(attrs.get("keyword"))
    names: list[str] = []
    for name in [jp, zh_cn, zh_tw, *keyword_names]:
        if name and name not in names:
            names.append(name)
    tmdb_id = str(attrs.get("tmdb_id") or "").strip()
    key_source = tmdb_id or jp or zh_cn or zh_tw or (names[0] if names else "")
    return {
        "id": tmdb_id or _normalize_actor_key(key_source),
        "jp": jp,
        "zh_cn": zh_cn,
        "zh_tw": zh_tw,
        "aliases": [name for name in names if name not in {jp, zh_cn, zh_tw}],
        "names": names,
        "tmdb_id": tmdb_id,
        "verified": str(attrs.get("verified") or "").strip() in {"1", "true", "True", "yes"},
    }


def _actor_mapping_primary_names(record: dict) -> set[str]:
    return {
        str(name or "")
        for name in (record.get("jp"), record.get("zh_cn"), record.get("zh_tw"))
        if str(name or "").strip()
    }


def _actor_mapping_tmdb_index(records: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for record in records:
        tmdb_id = str(record.get("tmdb_id") or "").strip()
        if tmdb_id and tmdb_id not in index:
            index[tmdb_id] = record
    return index


def _mapping_match_record(match: dict | None) -> dict | None:
    if not match:
        return None
    return match.get("record") if isinstance(match.get("record"), dict) else match


def _should_reject_actor_mapping_match(actor: dict, record: dict, match: dict | None) -> bool:
    if not match or match.get("source") != "alias":
        return False
    if record.get("verified"):
        return False
    actor_tmdb = str(actor.get("tmdb_id") or "").strip()
    mapping_tmdb = str(record.get("tmdb_id") or "").strip()
    return not (actor_tmdb and mapping_tmdb and actor_tmdb == mapping_tmdb)


def _actor_mapping_warning_reason(actor: dict, record: dict, match: dict | None, ignored_ghost_ids: set[str]) -> str | None:
    actor_id = str(actor.get("id") or "").strip()
    if actor_id in ignored_ghost_ids:
        return "ignored_person"
    if _should_reject_actor_mapping_match(actor, record, match):
        return "tmdb_conflict_alias"
    return None


def _actor_merge_score(actor: dict, mapping_tmdb_id: str) -> tuple[int, int, int, int, str]:
    tmdb_id = str(actor.get("tmdb_id") or "")
    return (
        int(actor.get("related_movie_count") or 0),
        1 if mapping_tmdb_id and tmdb_id == mapping_tmdb_id else 0,
        1 if actor.get("image_url") else 0,
        1 if actor.get("overview") else 0,
        str(actor.get("name") or ""),
    )


def _actor_emby_aliases(actor: dict) -> set[str]:
    aliases: set[str] = set()
    provider_ids = actor.get("provider_ids") if isinstance(actor.get("provider_ids"), dict) else {}
    for value in provider_ids.values():
        text = str(value or "").strip()
        if not text:
            continue
        if "?" in text:
            alias = text.rsplit("?", 1)[-1].strip()
            if alias:
                aliases.add(alias)
    overview = str(actor.get("overview") or "")
    for alias in re.findall(r"[（(]([^()（）]{2,40})[）)]", overview):
        alias = alias.strip()
        if alias:
            aliases.add(alias)
    aliases.discard(str(actor.get("name") or "").strip())
    return aliases


def _person_image_url(config: dict, person: dict) -> str | None:
    person_id = person.get("Id")
    if not person_id:
        return None
    tag = person.get("PrimaryImageTag") or (person.get("ImageTags") or {}).get("Primary")
    if not tag:
        return None
    return f"{media._server_url(config)}/emby/Items/{person_id}/Images/Primary?tag={tag}"


def _external_urls_from_provider_ids(provider_ids: dict) -> dict[str, str]:
    urls: dict[str, str] = {}
    tmdb_id = _provider_id(provider_ids, "Tmdb", "TMDB", "tmdb")
    imdb_id = _provider_id(provider_ids, "Imdb", "IMDB", "imdb")
    twitter_id = _provider_id(provider_ids, "Twitter", "twitter", "X", "x")
    instagram_id = _provider_id(provider_ids, "Instagram", "instagram")
    tiktok_id = _provider_id(provider_ids, "TikTok", "Tiktok", "tiktok")
    youtube_id = _provider_id(provider_ids, "YouTube", "Youtube", "youtube")
    wikidata_id = _provider_id(provider_ids, "Wikidata", "wikidata")
    facebook_id = _provider_id(provider_ids, "Facebook", "facebook")
    homepage = _provider_id(provider_ids, "Homepage", "homepage", "OfficialSite", "Official Website")
    if tmdb_id:
        urls["tmdb"] = f"https://www.themoviedb.org/person/{quote(tmdb_id, safe='')}"
    if imdb_id:
        urls["imdb"] = f"https://www.imdb.com/name/{quote(imdb_id, safe='')}/"
    if twitter_id:
        urls["x"] = f"https://x.com/{quote(str(twitter_id).lstrip('@'), safe='')}"
    if instagram_id:
        urls["instagram"] = f"https://www.instagram.com/{quote(str(instagram_id).lstrip('@'), safe='')}/"
    if tiktok_id:
        urls["tiktok"] = f"https://www.tiktok.com/@{quote(str(tiktok_id).lstrip('@'), safe='')}"
    if youtube_id:
        urls["youtube"] = f"https://www.youtube.com/{quote(youtube_id, safe='')}"
    if wikidata_id:
        urls["wikidata"] = f"https://www.wikidata.org/wiki/{quote(wikidata_id, safe='')}"
    if facebook_id:
        urls["facebook"] = f"https://www.facebook.com/{quote(facebook_id, safe='')}"
    if homepage:
        urls["homepage"] = homepage if str(homepage).startswith(("http://", "https://")) else f"https://{homepage}"
    return urls


def _parse_person(config: dict, person: dict) -> dict:
    provider_ids = person.get("ProviderIds") if isinstance(person.get("ProviderIds"), dict) else {}
    item_counts = person.get("ItemCounts") if isinstance(person.get("ItemCounts"), dict) else {}
    movie_count = person.get("MovieCount") or item_counts.get("Movie") or item_counts.get("Movies")
    production_locations = person.get("ProductionLocations")
    return {
        "id": person.get("Id"),
        "server_id": person.get("ServerId") or "",
        "name": person.get("Name") or "Unknown",
        "sort_name": person.get("SortName") or person.get("Name") or "",
        "overview": person.get("Overview") or "",
        "image_url": _person_image_url(config, person),
        "provider_ids": provider_ids,
        "tmdb_id": _provider_id(provider_ids, "Tmdb", "TMDB", "tmdb"),
        "imdb_id": _provider_id(provider_ids, "Imdb", "IMDB", "imdb"),
        "movie_count": movie_count,
        "premiere_date": person.get("PremiereDate"),
        "birthday": person.get("PremiereDate"),
        "deathday": person.get("EndDate"),
        "place_of_birth": (
            ", ".join(str(item) for item in production_locations if str(item).strip())
            if isinstance(production_locations, list)
            else person.get("PlaceOfBirth") or person.get("BirthPlace") or ""
        ),
        "gender": person.get("Gender") or "",
        "known_for_department": person.get("KnownForDepartment") or "",
        "popularity": person.get("Popularity"),
        "homepage": person.get("Homepage") or "",
        "external_urls": _external_urls_from_provider_ids(provider_ids),
        "date_created": person.get("DateCreated"),
    }


def _actor_identity_names(actor: dict, record: dict | None, *, lang: str | None = None) -> dict:
    override = actor.get("identity_names") if isinstance(actor.get("identity_names"), dict) else {}
    aliases = override.get("aliases") if isinstance(override.get("aliases"), list) else None
    names = {
        "emby_name": actor.get("name") or "",
        "emby_sort_name": actor.get("sort_name") or actor.get("name") or "",
        "jp": override.get("jp") or (record.get("jp") if record else "") or "",
        "zh_cn": override.get("zh_cn") or (record.get("zh_cn") if record else "") or "",
        "zh_tw": override.get("zh_tw") or (record.get("zh_tw") if record else "") or "",
        "aliases": aliases if aliases is not None else ((record.get("aliases") or []) if record else []),
        "source": "noor" if override else ("mapping" if record else "emby"),
    }
    fallback = str(actor.get("display_name") or actor.get("name") or "")
    names["selected_lang"] = lang or ""
    names["selected_name"] = _localized_mapping_name(
        {"jp": names["jp"], "zh_cn": names["zh_cn"], "zh_tw": names["zh_tw"]},
        fallback,
        lang,
    )
    return names


def _enrich_actor_display_names(actors: list[dict], *, lang: str | None = None) -> list[dict]:
    config = media._load_config()
    records = actor_api._mapping_records(config)
    if not records:
        return [{**actor, "display_name": actor.get("name") or ""} for actor in actors]
    index = actor_api._mapping_index(config)
    out: list[dict] = []
    for actor in actors:
        name = str(actor.get("name") or "")
        match = index.get(_normalize_actor_key(name)) or index.get(_normalize_actor_key(actor.get("sort_name")))
        record = _mapping_match_record(match)
        if record and _should_reject_actor_mapping_match(actor, record, match):
            record = None
        identity_names = _actor_identity_names(actor, record, lang=lang)
        out.append({
            **actor,
            "display_name": identity_names.get("selected_name") or _localized_mapping_name(record, name, lang),
            "mapping_id": record.get("id") if record else None,
            "mapping_tmdb_id": record.get("tmdb_id") if record else None,
            "identity_names": identity_names,
        })
    return out


def _legacy_actor_mapping_online_state_path() -> Path:
    return data_path() / "media_actor_mapping_online_state.json"


def _load_actor_mapping_sync_state() -> dict:
    path = actor_api._mapping_sync_state_path()
    if not path.is_file() and _legacy_actor_mapping_online_state_path().is_file():
        path = _legacy_actor_mapping_online_state_path()
    if not path.is_file():
        return {}
    payload = actor_api._load_json(path, {})
    return payload if isinstance(payload, dict) else {}


def _save_actor_mapping_sync_state(payload: dict) -> None:
    actor_api._save_json(actor_api._mapping_sync_state_path(), payload)


def _load_actor_mapping_status() -> dict:
    path = actor_api._mapping_store_path()
    if not path.is_file():
        return {"imported": False}
    payload = actor_api._load_json(path, {})
    if not isinstance(payload, dict):
        return {"imported": False, "error": "映射表文件无法读取"}
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    return {
        "imported": True,
        "path": str(path),
        "source_path": payload.get("source_path"),
        "updated_at": payload.get("updated_at"),
        "stats": payload.get("stats") or {"total": len(records)},
    }


def _validate_actor_mapping_xml_path(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"MDC-NG 演员映射表不存在: {path}")
    if path.suffix.lower() != ".xml":
        raise ValueError("MDC-NG 演员映射表必须是 XML 文件")
    if path.stat().st_size <= 0:
        raise ValueError("MDC-NG 演员映射表为空")


def _request_source_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


async def _emby_get_json(client: httpx.AsyncClient, config: dict, path: str, *, params: dict | None = None) -> dict:
    response = await client.get(
        f"{media._server_url(config)}/emby{path}",
        headers=media._headers(str(config.get("api_key") or "")),
        params=params or {},
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def _emby_related_movies_for_actor(client: httpx.AsyncClient, config: dict, actor_id: str, *, limit: int = 5000) -> list[dict]:
    user_id = str(config.get("user_id") or "").strip()
    path = f"/Users/{quote(user_id, safe='')}/Items" if user_id else "/Items"
    data = await _emby_get_json(
        client,
        config,
        path,
        params={
            "PersonIds": actor_id,
            "Recursive": "true",
            "IncludeItemTypes": "Movie",
            "Limit": max(1, min(limit, 5000)),
            "Fields": "Path,People,ProviderIds,ImageTags,DateCreated",
        },
    )
    return [item for item in data.get("Items", []) if isinstance(item, dict)]


def _emby_item_diagnostic_brief(item: dict) -> dict:
    provider_ids = item.get("ProviderIds") if isinstance(item.get("ProviderIds"), dict) else {}
    people = item.get("People") if isinstance(item.get("People"), list) else []
    return {
        "id": item.get("Id") or "",
        "name": item.get("Name") or "",
        "type": item.get("Type") or "",
        "path": item.get("Path") or "",
        "can_delete": item.get("CanDelete"),
        "sort_name": item.get("SortName") or "",
        "date_created": item.get("DateCreated") or "",
        "provider_ids": provider_ids,
        "people_count": len(people),
    }


async def _emby_items_for_person(
    client: httpx.AsyncClient,
    config: dict,
    actor_id: str,
    *,
    item_type: str | None = None,
    limit: int = 20,
) -> dict:
    user_id = str(config.get("user_id") or "").strip()
    path = f"/Users/{quote(user_id, safe='')}/Items" if user_id else "/Items"
    params = {
        "PersonIds": actor_id,
        "Recursive": "true",
        "Limit": max(1, min(limit, 100)),
        "Fields": "Path,People,ProviderIds,ImageTags,DateCreated,SortName",
    }
    if item_type:
        params["IncludeItemTypes"] = item_type
    data = await _emby_get_json(client, config, path, params=params)
    items = [item for item in data.get("Items", []) if isinstance(item, dict)]
    return {
        "total": int(data.get("TotalRecordCount") or len(items) or 0),
        "items": [_emby_item_diagnostic_brief(item) for item in items],
    }


async def _emby_optional_item(client: httpx.AsyncClient, config: dict, item_id: str) -> dict | None:
    safe_id = quote(str(item_id), safe="")
    paths = [f"/Items/{safe_id}"]
    user_id = str(config.get("user_id") or "").strip()
    if user_id:
        paths.append(f"/Users/{quote(user_id, safe='')}/Items/{safe_id}")
    for path in paths:
        response = await client.get(
            f"{media._server_url(config)}/emby{path}",
            headers=media._headers(str(config.get("api_key") or "")),
            params={"Fields": "Path,ProviderIds,CanDelete,DateCreated,SortName,Overview,People"},
        )
        if response.status_code == 404:
            continue
        response.raise_for_status()
        return response.json()
    return None


async def _media_server_info(config: dict, client: httpx.AsyncClient | None = None) -> dict:
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0, trust_env=False)
        close_client = True
    try:
        data = await _emby_get_json(client, config, "/System/Info")
        product = str(data.get("ProductName") or data.get("ServerName") or "Emby / Jellyfin")
        lowered = product.lower()
        kind = "jellyfin" if "jellyfin" in lowered else "emby"
        return {
            "kind": kind,
            "name": "Jellyfin" if kind == "jellyfin" else "Emby",
            "server_name": data.get("ServerName") or "",
            "version": data.get("Version") or "",
        }
    except Exception:
        return {"kind": "emby", "name": "Emby / Jellyfin", "server_name": "", "version": ""}
    finally:
        if close_client:
            await client.aclose()


def _actor_web_url(config: dict, actor_id: str | None, server_id: str | None = None) -> str | None:
    if not actor_id:
        return None
    url = f"{media._server_url(config)}/web/index.html#!/item?id={quote(str(actor_id), safe='')}"
    if server_id:
        url += f"&serverId={quote(str(server_id), safe='')}"
    return url


def _save_actor_avatar_override_url(actor_id: str, image_url: str) -> None:
    image_url = str(image_url or "").strip()
    if not image_url:
        return
    overrides = actor_api._load_profile_overrides()
    current_override = dict(overrides.get(str(actor_id)) or {})
    current_override["image_url"] = image_url
    current_override["updated_at"] = datetime.now(timezone.utc).isoformat()
    overrides[str(actor_id)] = current_override
    actor_api._save_profile_overrides(overrides)


async def _set_actor_avatar_bytes(
    config: dict,
    actor_id: str,
    content: bytes,
    *,
    content_type: str = "image/jpeg",
    lang: str | None = None,
) -> dict:
    if not content:
        raise HTTPException(status_code=400, detail="头像文件为空")
    safe_id = quote(str(actor_id), safe="")
    body = base64.b64encode(content)
    async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
        headers = {**media._headers(str(config.get("api_key") or "")), "Content-Type": content_type or "image/jpeg"}
        response = await client.post(f"{media._server_url(config)}/emby/Items/{safe_id}/Images/Primary", headers=headers, content=body)
        if response.status_code in {404, 405}:
            response = await client.put(f"{media._server_url(config)}/emby/Items/{safe_id}/Images/Primary", headers=headers, content=body)
        response.raise_for_status()
    _save_actor_avatar_override_url(actor_id, f"{media._server_url(config)}/emby/Items/{safe_id}/Images/Primary?ts={int(time.time())}")
    actor = await actor_api._actor_profile(config, actor_id, lang)
    return {"ok": True, "actor": actor}


async def _set_actor_avatar_from_url(config: dict, actor_id: str, url: str, *, lang: str | None = None) -> dict:
    source_url = str(url or "").strip()
    if not source_url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="头像 URL 必须是 http 或 https 地址")
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, trust_env=False) as client:
        response = await client.get(source_url, headers={"Accept": "image/*,*/*;q=0.8", "User-Agent": "NOOR/actor-avatar"})
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "image/jpeg").split(";", 1)[0].strip()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="URL 返回的不是图片")
        content = response.content
    return await _set_actor_avatar_bytes(config, actor_id, content, content_type=content_type, lang=lang)


async def _update_actor_profile(config: dict, actor_id: str, req, *, lang: str | None = None) -> dict:
    return await actor_api.update_actor(actor_id, req, lang=lang)


async def _delete_actor_profile(config: dict, actor_id: str) -> dict:
    return await actor_api.delete_actor(actor_id)


async def _detect_duplicate_actors(config: dict, *, limit: int = 2000) -> list[dict]:
    result = await actor_api.actor_duplicates(limit=limit)
    return result.get("groups") or []


async def _diagnose_actor_delete(config: dict, actor_id: str) -> dict:
    return await actor_api._actor_delete_diagnostics(config, actor_id)


async def _clear_actor_mapping_records() -> dict:
    return await actor_api.clear_actor_mapping()


async def _find_actor_mapping_group(config: dict, mapping_id: str, *, lang: str | None = None) -> dict:
    return await actor_api._mapping_group(config, mapping_id, lang or "zh-CN")


async def _preview_actor_mapping_matches(
    config: dict,
    *,
    limit: int = 5000,
    only_candidates: bool = False,
    lang: str | None = None,
) -> dict:
    result = await actor_api.actor_mapping_matches(limit=limit, only_candidates=only_candidates, lang=lang)
    return {key: value for key, value in result.items() if key != "ok"}


async def _preview_actor_tmdb_metadata(config: dict, actor_id: str, *, lang: str | None = None) -> dict:
    return await actor_api.preview_actor_tmdb_metadata(actor_id, lang=lang)


async def _apply_actor_tmdb_metadata(config: dict, actor_id: str, req, *, lang: str | None = None) -> dict:
    return await actor_api.apply_actor_tmdb_metadata(actor_id, req, lang=lang)


async def _apply_actor_tmdb_backfill(config: dict, req, *, lang: str | None = None) -> dict:
    return await actor_api.apply_actor_tmdb_backfill(req, lang=lang)


async def _apply_actor_name_sync(config: dict, req, *, lang: str | None = None) -> dict:
    return await actor_api.apply_actor_name_sync(req, lang=lang)


async def _execute_actor_mapping_merge_batch(config: dict, req, *, lang: str | None = None) -> dict:
    return await actor_api.execute_actor_mapping_batch(req, lang=lang)


async def _tmdb_person_payload(config: dict, actor: dict, *, lang: str | None = None) -> dict:
    person = await actor_api._tmdb_person(config, actor, lang or "zh-CN")
    return actor_api._tmdb_proposal(person, actor)


def _actor_mapping_record_for_name_sync(actor: dict, records: list[dict], name_index: dict[str, dict]) -> tuple[dict | None, dict | None]:
    names = actor.get("identity_names") if isinstance(actor.get("identity_names"), dict) else {}
    candidates = [
        actor.get("name"),
        actor.get("sort_name"),
        names.get("emby_name") if isinstance(names, dict) else None,
        names.get("emby_sort_name") if isinstance(names, dict) else None,
        *_actor_emby_aliases(actor),
    ]
    seen: set[str] = set()
    for value in candidates:
        key = _normalize_actor_key(str(value or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        match = name_index.get(key)
        record = _mapping_match_record(match)
        if record and not _should_reject_actor_mapping_match(actor, record, match):
            return record, match
    return None, None


def _actor_target_name_for_lang(record: dict | None, lang: str | None) -> tuple[str, str]:
    if not record:
        return "", "missing_mapping"
    lowered = str(lang or "").lower()
    if lowered == "zh-tw" or "hant" in lowered or lowered == "tw":
        candidates = [("zh_tw", str(record.get("zh_tw") or ""))]
    elif lowered.startswith("zh") or lowered == "cn":
        candidates = [("zh_cn", str(record.get("zh_cn") or ""))]
    else:
        candidates = [("jp", str(record.get("jp") or ""))]
    for source, value in candidates:
        text = value.strip()
        if text:
            return text, source
    return "", "missing_mapping_name"


def _actor_group_target_name(
    group: dict,
    target_name: str | None = None,
    *,
    lang: str | None = None,
    target_actor_id: str | None = None,
) -> str:
    selected_id = str(target_actor_id or "").strip()
    if selected_id:
        for actor in group.get("actors") or []:
            if str(actor.get("id") or "").strip() == selected_id:
                selected_name = str(actor.get("name") or actor.get("display_name") or "").strip()
                if selected_name:
                    return selected_name
    explicit = str(target_name or "").strip()
    if explicit:
        return explicit
    fallback = str(group.get("display_name") or group.get("canonical_name") or group.get("jp") or group.get("zh_cn") or "").strip()
    return _localized_mapping_name(group, fallback, lang).strip()


def _actor_group_source_ids(group: dict, *, target_actor_id: str | None = None) -> list[str]:
    selected_id = str(target_actor_id or "").strip()
    out: list[str] = []
    for actor in group.get("actors") or []:
        actor_id = str(actor.get("id") or "").strip()
        if selected_id and actor_id == selected_id:
            continue
        if actor_id and actor_id not in out:
            out.append(actor_id)
    return out
