from __future__ import annotations

import hashlib
import asyncio
import contextlib
import itertools
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.models import utcnow
from app.knowledge.codes import extract_video_code
from app.knowledge.models import ResourceObservation, ResourceRefreshState, WorkProfile, stable_id

_refresh_queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
_refresh_counter = itertools.count()
_refresh_queued: set[str] = set()
_refresh_workers: list[asyncio.Task[None]] = []


def canonical_work_code(value: Any) -> str:
    return str(extract_video_code(str(value or "")) or "").upper()


def semantic_tokens(*values: Any) -> dict[str, list[str]]:
    text = " ".join(str(value or "") for value in values if value)
    latin = list(dict.fromkeys(part.casefold() for part in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text)))
    cjk_runs = re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,}", text)
    cjk: list[str] = []
    for run in cjk_runs:
        cjk.append(run)
        cjk.extend(run[index:index + 2] for index in range(len(run) - 1))
    return {"latin": latin[:80], "cjk": list(dict.fromkeys(cjk))[:240]}


def _resource_key(item: dict[str, Any]) -> str:
    for name in ("info_hash", "hash", "id", "url", "download_url", "magnet"):
        value = str(item.get(name) or "").strip()
        if value:
            return value[:1024]
    payload = json.dumps({key: item.get(key) for key in ("title", "size_bytes", "published_at")}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _features(item: dict[str, Any]) -> dict[str, Any]:
    supplied = item.get("features") if isinstance(item.get("features"), dict) else {}
    requirements = item.get("requirements") if isinstance(item.get("requirements"), dict) else {}
    title = str(item.get("title") or "")
    return {
        **supplied,
        "is_cracked": bool(supplied.get("is_cracked") or re.search(r"破解|crack|uncensored\s*(?:leak|crack)", title, re.I)),
        "has_subtitle": bool(supplied.get("has_subtitle") or re.search(r"中字|中文字幕|[-_.]C(?:[-_.]|$)", title, re.I)),
        "is_uncensored": bool(supplied.get("is_uncensored") or re.search(r"无码|無碼|無修正|uncensored", title, re.I)),
        "is_private_tracker": bool(supplied.get("is_private_tracker") or requirements.get("accepts_private_tracker")),
    }


async def record_resource_search(query: dict[str, Any], groups: list[dict[str, Any]], *, outcomes: list[dict[str, Any]] | None = None) -> int:
    query_text = str(query.get("code") or query.get("number") or query.get("keyword") or query.get("q") or "")
    query_code = canonical_work_code(query_text)
    now = utcnow()
    written = 0
    async with async_session_maker() as db:
        for group in groups:
            provider_id = str(group.get("provider") or "unknown")
            provider_label = str(group.get("provider_label") or group.get("provider_name") or provider_id)
            for raw in group.get("items") or []:
                if not isinstance(raw, dict):
                    continue
                code = canonical_work_code(raw.get("query_key") or raw.get("code") or raw.get("number") or raw.get("title")) or query_code
                if not code:
                    continue
                title = str(raw.get("title") or "").strip()
                metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
                work_title = str(metadata.get("video_title") or code).strip()
                profile = await db.get(WorkProfile, code)
                evidence = {"source": provider_id, "observed_at": now.isoformat(), "title": title}
                if profile is None:
                    profile = WorkProfile(code=code, title=work_title, aliases=[title] if title and title != work_title else [], tokens=semantic_tokens(work_title, title), facts={}, source_evidence=[evidence], confidence=55)
                    db.add(profile)
                else:
                    aliases = list(profile.aliases or [])
                    if title and title not in aliases:
                        aliases.append(title)
                    evidence_rows = [row for row in (profile.source_evidence or []) if isinstance(row, dict) and row.get("source") != provider_id]
                    evidence_rows.append(evidence)
                    profile.title = profile.title or title
                    profile.aliases = aliases[-40:]
                    profile.tokens = semantic_tokens(profile.title, *profile.aliases)
                    profile.source_evidence = evidence_rows[-40:]
                    profile.confidence = max(int(profile.confidence or 0), 70)

                resource_key = _resource_key(raw)
                observation_id = stable_id("resource-observation", code, provider_id, resource_key)
                observation = await db.get(ResourceObservation, observation_id)
                values = {
                    "provider_label": provider_label,
                    "title": title,
                    "status": "available",
                    "available": True,
                    "confidence": 85,
                    "features": _features(raw),
                    "payload": raw,
                    "last_seen_at": now,
                    "expires_at": now + timedelta(hours=12),
                }
                if observation is None:
                    observation = ResourceObservation(id=observation_id, work_code=code, provider_id=provider_id, resource_key=resource_key, **values)
                    db.add(observation)
                else:
                    for key, value in values.items():
                        setattr(observation, key, value)
                written += 1
        if query_code:
            for outcome in outcomes or []:
                provider_id = str(outcome.get("provider") or "unknown")
                status = str(outcome.get("status") or "failed")
                check_id = stable_id("resource-observation", query_code, provider_id, "__provider_check__")
                check = await db.get(ResourceObservation, check_id)
                ttl = timedelta(hours=12 if status == "available" else 1 if status == "empty" else 0.1667)
                values = {
                    "provider_label": str(outcome.get("provider_label") or provider_id),
                    "title": "",
                    "status": status,
                    "available": False,
                    "confidence": 100 if status in {"available", "empty"} else 30,
                    "features": {},
                    "payload": {"count": int(outcome.get("count") or 0), "error": str(outcome.get("error") or "")[:1000]},
                    "last_seen_at": now,
                    "expires_at": now + ttl,
                }
                if check is None:
                    db.add(ResourceObservation(id=check_id, work_code=query_code, provider_id=provider_id, resource_key="__provider_check__", **values))
                else:
                    for key, value in values.items():
                        setattr(check, key, value)
        await db.commit()
    return written


async def record_work_metadata(code: str, data: dict[str, Any], *, source: str, confidence: int = 80) -> str | None:
    canonical = canonical_work_code(code or data.get("code") or data.get("number") or data.get("title"))
    if not canonical:
        return None
    title = str(data.get("display_title") or data.get("title") or data.get("name") or "").strip()
    original_title = str(data.get("original_title") or data.get("originaltitle") or "").strip()
    translated_title = str(data.get("translated_title") or data.get("chinese_title") or "").strip()
    aliases = [value for value in (title, original_title, translated_title) if value]
    fact_keys = ("actors", "categories", "tags", "maker", "publisher", "studio", "series", "director", "release_date", "duration", "cover_url", "fanart_url")
    incoming_facts = {key: data.get(key) for key in fact_keys if data.get(key) not in (None, "", [], {})}
    now = utcnow()
    async with async_session_maker() as db:
        profile = await db.get(WorkProfile, canonical)
        evidence = {"source": source, "observed_at": now.isoformat(), "confidence": confidence, "fields": sorted(incoming_facts)}
        if profile is None:
            profile = WorkProfile(code=canonical, title=title, original_title=original_title, translated_title=translated_title, aliases=aliases, tokens=semantic_tokens(*aliases), facts={source: incoming_facts}, source_evidence=[evidence], confidence=confidence)
            db.add(profile)
        else:
            merged_aliases = list(profile.aliases or [])
            for alias in aliases:
                if alias not in merged_aliases:
                    merged_aliases.append(alias)
            facts = dict(profile.facts or {})
            facts[source] = incoming_facts
            evidence_rows = [row for row in (profile.source_evidence or []) if isinstance(row, dict) and row.get("source") != source]
            evidence_rows.append(evidence)
            profile.title = title or profile.title
            profile.original_title = original_title or profile.original_title
            profile.translated_title = translated_title or profile.translated_title
            profile.aliases = merged_aliases[-60:]
            profile.tokens = semantic_tokens(profile.title, profile.original_title, profile.translated_title, *profile.aliases)
            profile.facts = facts
            profile.source_evidence = evidence_rows[-60:]
            profile.confidence = max(int(profile.confidence or 0), confidence)
        await db.commit()
    return canonical


async def cached_resource_groups(code: str, *, include_stale: bool = False, limit_per_provider: int = 24) -> list[dict[str, Any]]:
    canonical = canonical_work_code(code)
    if not canonical:
        return []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_maker() as db:
        stmt = select(ResourceObservation).where(ResourceObservation.work_code == canonical, ResourceObservation.available.is_(True))
        if not include_stale:
            stmt = stmt.where(ResourceObservation.expires_at > now)
        rows = list((await db.execute(stmt.order_by(ResourceObservation.last_seen_at.desc()))).scalars())
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = grouped.setdefault(row.provider_id, {"provider": row.provider_id, "provider_label": row.provider_label or row.provider_id, "provider_name": row.provider_label or row.provider_id, "items": [], "from_intelligence_core": True})
        if len(group["items"]) < limit_per_provider:
            item = dict(row.payload or {})
            item["intelligence"] = {"status": row.status, "confidence": row.confidence, "last_seen_at": row.last_seen_at.isoformat(), "expires_at": row.expires_at.isoformat()}
            group["items"].append(item)
    for group in grouped.values():
        group["total"] = len(group["items"])
        group["has_more"] = False
    priority = {"avdb": 0, "mteam-plugin": 1, "javdb": 2}
    return sorted(grouped.values(), key=lambda group: (priority.get(group["provider"], 99), group["provider"]))


async def cached_resource_summary_map(codes: list[str]) -> dict[str, dict[str, Any]]:
    canonical_codes = {canonical_work_code(code) for code in codes}
    canonical_codes.discard("")
    if not canonical_codes:
        return {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session_maker() as db:
        rows = list((await db.execute(select(ResourceObservation).where(ResourceObservation.work_code.in_(canonical_codes), ResourceObservation.available.is_(True), ResourceObservation.expires_at > now))).scalars())
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        summary = result.setdefault(row.work_code, {"total": 0, "providers": {}, "has_cracked": False, "has_subtitle": False, "has_uncensored": False, "has_private": False, "has_public": False})
        summary["total"] += 1
        summary["providers"][row.provider_label or row.provider_id] = summary["providers"].get(row.provider_label or row.provider_id, 0) + 1
        features = row.features or {}
        summary["has_cracked"] = summary["has_cracked"] or bool(features.get("is_cracked"))
        summary["has_subtitle"] = summary["has_subtitle"] or bool(features.get("has_subtitle"))
        summary["has_uncensored"] = summary["has_uncensored"] or bool(features.get("is_uncensored"))
        private = bool(features.get("is_private_tracker"))
        summary["has_private"] = summary["has_private"] or private
        summary["has_public"] = summary["has_public"] or not private
    for summary in result.values():
        summary["providers"] = [{"name": name, "count": count} for name, count in sorted(summary["providers"].items(), key=lambda row: (-row[1], row[0]))]
    return result


async def enqueue_resource_refresh(codes: list[str], *, priority: int = 50) -> int:
    accepted = 0
    now = utcnow()
    async with async_session_maker() as db:
        for raw in codes:
            code = canonical_work_code(raw)
            if not code or code in _refresh_queued:
                continue
            state = await db.get(ResourceRefreshState, code)
            if state is None:
                state = ResourceRefreshState(work_code=code, status="queued", priority=priority, requested_at=now)
                db.add(state)
            else:
                state.status = "queued"
                state.priority = min(int(state.priority or priority), priority)
                state.requested_at = now
                state.error = ""
            _refresh_queued.add(code)
            await _refresh_queue.put((priority, next(_refresh_counter), code))
            accepted += 1
        await db.commit()
    return accepted


async def _resource_refresh_worker() -> None:
    while True:
        _priority, _sequence, code = await _refresh_queue.get()
        try:
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if state:
                    state.status = "running"
                    state.started_at = utcnow()
                    state.attempts = int(state.attempts or 0) + 1
                    await db.commit()
            from app.plugins.runtime import runtime
            await runtime.search_resources({"keyword": code, "provider_timeout_seconds": 12}, limit_per_plugin=24)
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if state:
                    state.status = "completed"
                    state.completed_at = utcnow()
                    state.error = ""
                    await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if state:
                    state.status = "failed"
                    state.error = str(exc)[:1000]
                    state.completed_at = utcnow()
                    await db.commit()
        finally:
            _refresh_queued.discard(code)
            _refresh_queue.task_done()


async def start_resource_refresh_workers(count: int = 3) -> None:
    if any(not task.done() for task in _refresh_workers):
        return
    _refresh_workers.clear()
    async with async_session_maker() as db:
        queued = list((await db.execute(select(ResourceRefreshState).where(ResourceRefreshState.status.in_(("queued", "running"))))).scalars())
    for state in queued:
        if state.work_code not in _refresh_queued:
            _refresh_queued.add(state.work_code)
            await _refresh_queue.put((int(state.priority or 50), next(_refresh_counter), state.work_code))
    _refresh_workers.extend(asyncio.create_task(_resource_refresh_worker()) for _ in range(max(1, min(count, 8))))


async def stop_resource_refresh_workers() -> None:
    workers = list(_refresh_workers)
    _refresh_workers.clear()
    for task in workers:
        task.cancel()
    for task in workers:
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def resource_refresh_status() -> dict[str, Any]:
    async with async_session_maker() as db:
        rows = list((await db.execute(select(ResourceRefreshState).order_by(ResourceRefreshState.updated_at.desc()).limit(100))).scalars())
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return {"counts": counts, "queue_size": _refresh_queue.qsize(), "items": [{"code": row.work_code, "status": row.status, "priority": row.priority, "attempts": row.attempts, "error": row.error, "updated_at": row.updated_at.isoformat()} for row in rows]}


async def work_intelligence(code: str, *, include_stale: bool = True) -> dict[str, Any] | None:
    canonical = canonical_work_code(code)
    if not canonical:
        return None
    async with async_session_maker() as db:
        profile = await db.get(WorkProfile, canonical)
        checks = list((await db.execute(select(ResourceObservation).where(ResourceObservation.work_code == canonical, ResourceObservation.resource_key == "__provider_check__").order_by(ResourceObservation.last_seen_at.desc()))).scalars())
    groups = await cached_resource_groups(canonical, include_stale=include_stale)
    if profile is None and not groups:
        return None
    resources = [item for group in groups for item in group.get("items") or []]
    features = [_features(item) for item in resources]
    return {
        "code": canonical,
        "profile": None if profile is None else {"title": profile.title, "original_title": profile.original_title, "translated_title": profile.translated_title, "aliases": profile.aliases or [], "tokens": profile.tokens or {}, "facts": profile.facts or {}, "source_evidence": profile.source_evidence or [], "confidence": profile.confidence, "updated_at": profile.updated_at.isoformat()},
        "resources": {"groups": groups, "total": len(resources), "has_cracked": any(item.get("is_cracked") for item in features), "has_subtitle": any(item.get("has_subtitle") for item in features), "has_uncensored": any(item.get("is_uncensored") for item in features), "provider_checks": [{"provider": row.provider_id, "provider_label": row.provider_label, "status": row.status, "count": int((row.payload or {}).get("count") or 0), "error": str((row.payload or {}).get("error") or ""), "checked_at": row.last_seen_at.isoformat(), "expires_at": row.expires_at.isoformat()} for row in checks]},
    }
