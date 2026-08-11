"""Listing and variant-deduplication helpers for the media-library router.

Reconstructed from the corresponding functions in ``media_library.pyc``.
"""
from __future__ import annotations

import os
import re
from typing import Any


_VARIANT_MARKER_RE = re.compile(
    r"(^|[-_.\s])(restored-u|u\d*|c\d*|chs|cht|cn|tw|zh|字幕|中文|破解|流出|uncensored|leaked)(?=$|[-_.\s])",
    re.IGNORECASE,
)


def item_variant_penalty(item: dict[str, Any]) -> int:
    path = (item.get("path") or "").lower()
    name = (item.get("name") or "").lower()
    tags = item.get("tags") or {}
    penalty = 0
    basename = os.path.splitext(os.path.basename(path))[0] if path else name
    if _VARIANT_MARKER_RE.search(basename):
        penalty += 60
    if ".restored-u" in path:
        penalty += 120
    if tags.get("is_cracked"):
        penalty += 40
    if tags.get("is_leaked"):
        penalty += 20
    if tags.get("has_chinese"):
        penalty += 5
    return penalty


def merge_group_metadata(representative: dict[str, Any], group: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(representative)
    merged_tags = dict(representative.get("tags") or {})
    if any((item.get("tags") or {}).get("is_cracked") for item in group):
        merged_tags["is_cracked"] = True
    if any((item.get("tags") or {}).get("has_chinese") for item in group):
        merged_tags["has_chinese"] = True
    if any((item.get("tags") or {}).get("is_leaked") for item in group):
        merged_tags["is_leaked"] = True
    release_type_key = None
    if any((item.get("tags") or {}).get("release_type_key") == "leaked" for item in group):
        release_type_key = "leaked"
    elif any((item.get("tags") or {}).get("release_type_key") == "uncensored" for item in group):
        release_type_key = "uncensored"
    if release_type_key == "leaked":
        merged_tags["release_type_key"] = "leaked"
        merged_tags["release_type"] = "流出"
    elif release_type_key == "uncensored":
        merged_tags["release_type_key"] = "uncensored"
        merged_tags["release_type"] = "无码"
    merged["tags"] = merged_tags
    merged["subtitle_count"] = max(item.get("subtitle_count") or 0 for item in group)
    merged["variant_count"] = len(group)
    return merged


def pick_group_representative(group: list[dict[str, Any]]) -> dict[str, Any]:
    def sort_key(item: dict[str, Any]) -> tuple:
        path = item.get("path") or ""
        name = item.get("name") or ""
        return (
            bool(path),
            -item_variant_penalty(item),
            bool(item.get("poster_path")),
            -(len(os.path.basename(path)) if path else len(name)),
            name,
        )

    representative = dict(max(group, key=sort_key))
    if not representative.get("poster_path"):
        fallback = next((item.get("poster_path") for item in group if item.get("poster_path")), None)
        if fallback:
            representative["poster_path"] = fallback
    return merge_group_metadata(representative, group)


def deduplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    result: list[dict[str, Any]] = []
    for item in items:
        path = item.get("path", "")
        if not path:
            result.append(item)
            continue
        folder = os.path.dirname(path)
        groups.setdefault(folder, []).append(item)
    for group in groups.values():
        result.append(group[0] if len(group) == 1 else pick_group_representative(group))
    return result


def item_matches_query(item: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    query = query.strip().lower()
    if not query:
        return True
    nfo = item.get("nfo") if isinstance(item.get("nfo"), dict) else None
    fields = [item.get("name"), item.get("path"), nfo.get("title") if nfo else None, nfo.get("originaltitle") if nfo else None, nfo.get("num") if nfo else None]
    return query in "\n".join(str(field) for field in fields if field).lower()


def apply_filter_and_paginate(items: list[dict[str, Any]], filter_name: str | None, query: str | None, offset: int, limit: int) -> tuple[list[dict[str, Any]], int]:
    filtered = []
    for item in items:
        tags = item.get("tags", {})
        matches_filter = not filter_name
        if filter_name:
            if not tags:
                matches_filter = False
            elif filter_name == "cracked":
                matches_filter = bool(tags.get("is_cracked"))
            elif filter_name == "chinese":
                matches_filter = bool(tags.get("has_chinese"))
            elif filter_name == "leaked":
                matches_filter = tags.get("release_type_key") == "leaked"
            elif filter_name == "uncensored":
                matches_filter = tags.get("release_type_key") == "uncensored"
        if matches_filter and item_matches_query(item, query):
            filtered.append(item)
    return filtered[offset:offset + limit], len(filtered)
