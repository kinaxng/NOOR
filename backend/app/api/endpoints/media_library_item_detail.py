"""Implementation helpers for Emby media-library item detail requests.

Reconstructed from preserved Python 3.13 bytecode.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable
from urllib.parse import urlencode, urljoin


_VARIANT_MARKER_RE = re.compile(
    r"(^|[-_.\s])(restored-u|u\d*|c\d*|chs|cht|cn|tw|zh|字幕|中文|破解|流出|uncensored|leaked)(?=$|[-_.\s])",
    re.IGNORECASE,
)


def _sibling_variant_penalty(item: dict) -> int:
    path = (item.get("file_path") or "").lower()
    name = (item.get("name") or item.get("label") or "").lower()
    basename = os.path.splitext(os.path.basename(path))[0] if path else name
    penalty = 0
    if _VARIANT_MARKER_RE.search(basename):
        penalty += 60
    if ".restored-u" in path:
        penalty += 120
    return penalty


def _sort_siblings(items: list[dict]) -> list[dict]:
    def sort_key(item: dict) -> tuple:
        path = item.get("file_path") or ""
        name = item.get("name") or item.get("label") or ""
        return (
            bool(path),
            -_sibling_variant_penalty(item),
            -(len(os.path.basename(path)) if path else len(name)),
            name.lower(),
        )

    return sorted(items, key=sort_key, reverse=True)


def build_stream_url_for_server_impl(
    server_url: str,
    api_key: str,
    item_id: str,
    media_source_id: str | None = None,
    container: str | None = None,
) -> str:
    _ = (server_url, api_key)
    normalized_container = (container or "").strip().lower()
    if normalized_container and not re.fullmatch(r"[a-z0-9]+", normalized_container):
        normalized_container = ""
    params: dict[str, str] = {}
    if media_source_id:
        params["media_source_id"] = media_source_id
    if normalized_container:
        params["container"] = normalized_container
    query = f"?{urlencode(params)}" if params else ""
    return f"/api/media-library/stream/{item_id}{query}"


def build_direct_stream_upstream_url_impl(
    server_url: str,
    api_key: str,
    item_id: str,
    media_source_id: str | None = None,
    container: str | None = None,
    play_session_id: str | None = None,
) -> str:
    normalized_container = (container or "").strip().lower()
    if normalized_container and not re.fullmatch(r"[a-z0-9]+", normalized_container):
        normalized_container = ""
    suffix = f".{normalized_container}" if normalized_container else ""
    params = {"static": "true", "api_key": api_key or ""}
    if media_source_id:
        params["MediaSourceId"] = media_source_id
    if normalized_container:
        params["Container"] = normalized_container
    if play_session_id:
        params["PlaySessionId"] = play_session_id
    return f"{server_url}/emby/Videos/{item_id}/stream{suffix}?{urlencode(params)}"


def _append_query_value(url: str, key: str, value: str | None) -> str:
    if not value or f"{key}=" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={value}"


def _normalize_emby_url(server_url: str, url: str | None) -> str | None:
    if not url:
        return None
    return urljoin(f"{server_url.rstrip('/')}/", url.lstrip("/"))


def _select_playback_source(sources: list[dict], media_source_id: str | None = None) -> dict | None:
    if not sources:
        return None
    if media_source_id:
        for source in sources:
            if source.get("Id") == media_source_id:
                return source
    for source in sources:
        if source.get("SupportsDirectPlay") or source.get("SupportsDirectStream"):
            return source
    return sources[0]


async def resolve_playback_stream_url_impl(
    config: dict,
    item_id: str,
    media_source_id: str | None = None,
    container: str | None = None,
    *,
    httpx_module: Any,
    server_url_fn: Callable[[dict], str],
    headers_fn: Callable[[str], dict],
) -> dict:
    server_url = server_url_fn(config)
    api_key = config.get("api_key", "")
    user_id = config.get("user_id", "")
    fallback_url = build_direct_stream_upstream_url_impl(
        server_url,
        api_key,
        item_id,
        media_source_id=media_source_id,
        container=container,
    )
    fallback = {
        "url": fallback_url,
        "play_method": "direct_stream_fallback",
        "play_session_id": None,
        "media_source_id": media_source_id,
        "container": container,
        "is_transcode": False,
    }
    if not server_url or not api_key or not user_id:
        return fallback

    try:
        async with httpx_module.AsyncClient(timeout=20.0, trust_env=False) as client:
            response = await client.post(
                f"{server_url}/emby/Items/{item_id}/PlaybackInfo",
                headers={**headers_fn(api_key), "content-type": "application/json"},
                json={
                    "UserId": user_id,
                    "StartTimeTicks": 0,
                    "IsPlayback": False,
                    "AutoOpenLiveStream": True,
                    "MaxStreamingBitrate": 120000000,
                },
            )
        if response.status_code != 200:
            return {**fallback, "play_method": f"playbackinfo_http_{response.status_code}"}
        data = response.json()
    except Exception:
        return {**fallback, "play_method": "playbackinfo_error"}

    play_session_id = data.get("PlaySessionId")
    source = _select_playback_source(data.get("MediaSources", []), media_source_id)
    if not source:
        return {
            **fallback,
            "url": _append_query_value(fallback_url, "PlaySessionId", play_session_id),
            "play_session_id": play_session_id,
        }

    resolved_media_source_id = source.get("Id") or media_source_id
    resolved_container = source.get("Container") or container
    direct_url = _normalize_emby_url(server_url, source.get("DirectStreamUrl"))
    if direct_url:
        direct_url = _append_query_value(direct_url, "api_key", api_key)
        direct_url = _append_query_value(direct_url, "PlaySessionId", play_session_id)
        return {
            "url": direct_url,
            "play_method": "direct_play" if source.get("SupportsDirectPlay") else "direct_stream",
            "play_session_id": play_session_id,
            "media_source_id": resolved_media_source_id,
            "container": resolved_container,
            "is_transcode": False,
        }

    transcode_url = _normalize_emby_url(server_url, source.get("TranscodingUrl") or data.get("TranscodingUrl"))
    if transcode_url:
        transcode_url = _append_query_value(transcode_url, "api_key", api_key)
        transcode_url = _append_query_value(transcode_url, "PlaySessionId", play_session_id)
        return {
            "url": transcode_url,
            "play_method": "transcode",
            "play_session_id": play_session_id,
            "media_source_id": resolved_media_source_id,
            "container": resolved_container,
            "is_transcode": True,
        }

    return {
        "url": build_direct_stream_upstream_url_impl(
            server_url,
            api_key,
            item_id,
            media_source_id=resolved_media_source_id,
            container=resolved_container,
            play_session_id=play_session_id,
        ),
        "play_method": "direct_stream_fallback",
        "play_session_id": play_session_id,
        "media_source_id": resolved_media_source_id,
        "container": resolved_container,
        "is_transcode": False,
    }


def get_main_nfo_impl(file_path: str | None) -> str | None:
    if not file_path:
        return None
    folder = os.path.dirname(file_path)
    base, _ = os.path.splitext(os.path.basename(file_path))
    base_code = re.sub(
        r"[-_]?(破解|流出|中文|字幕|ch|chs|cht|cn|tw|z[ah]?|restored-u|u\d*|c\d*)[-_.]*",
        "",
        base,
        flags=re.IGNORECASE,
    ).rstrip("_-")
    if not base_code:
        return None
    candidate = os.path.join(folder, f"{base_code}.nfo")
    return candidate if os.path.isfile(candidate) else None


async def get_siblings_impl(
    config: dict,
    parent_id: str | None,
    current_id: str,
    *,
    httpx_module: Any,
    server_url_fn: Callable[[dict], str],
    headers_fn: Callable[[str], dict],
    map_path_fn: Callable[[str | None, dict], str | None],
) -> list[dict]:
    if not parent_id or not current_id:
        return []
    try:
        async with httpx_module.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{server_url_fn(config)}/emby/Items",
                headers=headers_fn(config.get("api_key", "")),
                params={"ParentId": parent_id, "Fields": "MediaSources,Path", "Limit": 100, "Recursive": "false"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            siblings = []
            for item in data.get("Items", []):
                if item.get("Id") == current_id:
                    continue
                if item.get("Type") not in ("Movie", "Video") and item.get("MediaType") != "Video":
                    continue
                mp = None
                selected_source = None
                for src in item.get("MediaSources", []):
                    if src.get("Type") == "Default":
                        selected_source = src
                        mp = src.get("Path")
                        break
                if not mp and item.get("MediaSources"):
                    selected_source = item.get("MediaSources", [])[0]
                    mp = selected_source.get("Path")
                if not mp:
                    mp = item.get("Path")
                if mp:
                    mp = map_path_fn(mp, config)
                siblings.append({
                    "id": item.get("Id"),
                    "label": item.get("Name") or os.path.basename(mp or ""),
                    "file_path": mp,
                    "name": item.get("Name") or os.path.basename(mp or ""),
                    "media_source_id": (selected_source or {}).get("Id"),
                    "container": (selected_source or {}).get("Container") or os.path.splitext(mp or "")[1].lstrip("."),
                })
            return _sort_siblings(siblings)
    except Exception:
        return []


async def get_item_impl(
    config: dict,
    item_id: str,
    *,
    httpx_module: Any,
    server_url_fn: Callable[[dict], str],
    headers_fn: Callable[[str], dict],
    map_path_fn: Callable[[str | None, dict], str | None],
    parse_tags_fn: Callable[[str, list[str], str | None], dict],
    get_siblings_fn: Callable[[dict, str | None, str], Any],
    get_main_nfo_fn: Callable[[str | None], str | None],
) -> dict | None:
    user_id = config.get("user_id", "")
    api_key = config.get("api_key", "")
    fields = "MediaSources,Path,DateCreated,PremiereDate,Studios,Genres,ParentId,ImageTags,BackdropImageTags,People"

    async def _fetch(url: str):
        async with httpx_module.AsyncClient(timeout=30.0) as client:
            return await client.get(url, headers=headers_fn(api_key), params={"Fields": fields})

    if user_id:
        resp = await _fetch(f"{server_url_fn(config)}/emby/Users/{user_id}/Items/{item_id}")
        if resp.status_code == 200:
            data = resp.json()
        elif resp.status_code == 404:
            resp = await _fetch(f"{server_url_fn(config)}/emby/Items/{item_id}")
            if resp.status_code == 404 or resp.status_code != 200:
                return None
            data = resp.json()
        else:
            resp.raise_for_status()
            data = resp.json()
    else:
        resp = await _fetch(f"{server_url_fn(config)}/emby/Items/{item_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

    file_path = None
    media_source_id = None
    media_container = None
    media_sources = data.get("MediaSources", [])
    if media_sources:
        selected_source = None
        for source in media_sources:
            if source.get("Type") == "Default":
                selected_source = source
                file_path = source.get("Path")
                break
        if not file_path and media_sources:
            selected_source = media_sources[0]
            file_path = selected_source.get("Path")
        if selected_source:
            media_source_id = selected_source.get("Id")
            media_container = selected_source.get("Container") or os.path.splitext(file_path or "")[1].lstrip(".")
    if file_path:
        file_path = map_path_fn(file_path, config)

    siblings = await get_siblings_fn(config, data.get("ParentId"), item_id)
    main_nfo = get_main_nfo_fn(file_path) if file_path else None
    studios = [s.get("Name") for s in data.get("Studios", []) if s.get("Name")]
    actors = [
        {"name": person.get("Name"), "role": person.get("Role")}
        for person in data.get("People", [])
        if person.get("Name") and person.get("Type") == "Actor"
    ]

    sibling_tags = []
    for sibling in siblings:
        if sibling.get("id"):
            sibling["stream_url"] = build_stream_url_for_server_impl(
                server_url_fn(config),
                api_key,
                sibling["id"],
                sibling.get("media_source_id"),
                sibling.get("container"),
            )
        sibling_path = sibling.get("file_path")
        sibling_name = sibling.get("name") or sibling.get("label") or ""
        sibling_tag = parse_tags_fn(sibling_name, studios, sibling_path)
        sibling["tags"] = sibling_tag
        sibling_tags.append(sibling_tag)

    poster_url = None
    current_img_tags = data.get("ImageTags", {})
    if current_img_tags.get("Primary"):
        tag = current_img_tags["Primary"]
        poster_url = f"{server_url_fn(config)}/emby/Items/{item_id}/Images/Primary?tag={tag}"
    else:
        main_poster_url = None
        for sib in siblings:
            sib_path = (sib.get("file_path") or "").lower()
            if re.search(r"[-_](u\d*|c\d*|破解|流出|中文|字幕|restored-u)", sib_path):
                continue
            sib_id = sib.get("id")
            if not sib_id:
                continue
            try:
                async with httpx_module.AsyncClient(timeout=10.0) as img_client:
                    if user_id:
                        sib_resp = await img_client.get(
                            f"{server_url_fn(config)}/emby/Users/{user_id}/Items",
                            headers=headers_fn(config.get("api_key", "")),
                            params={"ids": sib_id, "Fields": "ImageTags"},
                        )
                    else:
                        sib_resp = await img_client.get(
                            f"{server_url_fn(config)}/emby/Items",
                            headers=headers_fn(config.get("api_key", "")),
                            params={"ids": sib_id, "Fields": "ImageTags"},
                        )
                    if sib_resp.status_code == 200:
                        sib_items = sib_resp.json().get("Items", [])
                        if sib_items:
                            sib_img_tags = sib_items[0].get("ImageTags", {})
                            main_tag = sib_img_tags.get("Primary")
                            if main_tag:
                                main_poster_url = f"{server_url_fn(config)}/emby/Items/{sib_items[0]['Id']}/Images/Primary?tag={main_tag}"
                if main_poster_url:
                    break
            except Exception:
                continue
        if main_poster_url:
            poster_url = main_poster_url
        elif current_img_tags.get("Thumb"):
            poster_url = f"{server_url_fn(config)}/emby/Items/{item_id}/Images/Thumb?tag={current_img_tags['Thumb']}"

    backdrop_url = None
    tags = data.get("BackdropImageTags", [])
    if tags:
        backdrop_url = f"{server_url_fn(config)}/emby/Items/{item_id}/Images/Backdrop?tag={tags[0]}"
    elif data.get("ImageTags", {}).get("Thumb"):
        backdrop_url = f"{server_url_fn(config)}/emby/Items/{item_id}/Images/Thumb?tag={data['ImageTags']['Thumb']}"

    tags = parse_tags_fn(data.get("Name", ""), studios, file_path)
    if any(sibling_tag.get("has_chinese") for sibling_tag in sibling_tags):
        tags["has_chinese"] = True
    if any(sibling_tag.get("is_cracked") for sibling_tag in sibling_tags):
        tags["is_cracked"] = True
    if any(sibling_tag.get("is_uncensored") for sibling_tag in sibling_tags):
        tags["is_uncensored"] = True
    if any(sibling_tag.get("is_leaked") for sibling_tag in sibling_tags):
        tags["is_leaked"] = True
    if any(sibling_tag.get("release_type_key") == "leaked" for sibling_tag in sibling_tags):
        tags["release_type_key"] = "leaked"
        tags["release_type"] = "流出"
    elif any(sibling_tag.get("release_type_key") == "uncensored" for sibling_tag in sibling_tags) and not tags.get("release_type_key"):
        tags["release_type_key"] = "uncensored"
        tags["release_type"] = "无码"

    return {
        "id": data["Id"],
        "name": data.get("Name", "Unknown"),
        "media_type": data.get("MediaType", "Video"),
        "file_path": file_path,
        "stream_url": build_stream_url_for_server_impl(
            server_url_fn(config), api_key, item_id, media_source_id, media_container,
        ),
        "date_created": data.get("DateCreated"),
        "premiered": data.get("PremiereDate"),
        "studios": studios,
        "genres": data.get("Genres", []),
        "poster_path": poster_url,
        "backdrop_path": backdrop_url,
        "tags": tags,
        "actors": actors,
        "siblings": siblings,
        "variant_count": len(siblings) + (1 if file_path else 0),
        "main_nfo": main_nfo,
    }
