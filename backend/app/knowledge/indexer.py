from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.endpoints import media_library, media_library_recovery
from app.api.endpoints.media_library_helpers import SUBTITLE_EXTS
from app.api.subtitles import extract_video_code
from app.core.models import Job
from app.knowledge.models import KnowledgeEdge, KnowledgeEntity
from app.knowledge.repository import KnowledgeRepository
from app.plugins.runtime import runtime as plugin_runtime


CODE_RE = re.compile(r"\b(FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|[A-Z]{2,8}[-_ ]?\d{2,7}|\d{6}[-_]\d{2,5})\b", re.I)


def _normalize_code(value: Any) -> str:
    match = CODE_RE.search(str(value or ""))
    if not match:
        return ""
    raw = re.sub(r"[_ ]+", "-", match.group(1).upper())
    fc2 = re.match(r"FC2-?(?:PPV-?)?(\d{4,9})$", raw, re.I)
    if fc2:
        return f"FC2-PPV-{fc2.group(1)}"
    compact = re.match(r"^([A-Z]{2,8})(\d{2,7})$", raw)
    return f"{compact.group(1)}-{compact.group(2)}" if compact else raw


def _clean_values(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("name") or value.get("Name") or value.get("label")
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _nfo(detail: dict[str, Any]) -> dict[str, Any]:
    value = detail.get("nfo") or {}
    return value if isinstance(value, dict) else {}


def _nfo_tags(nfo: dict[str, Any]) -> list[Any]:
    values = nfo.get("tags") or nfo.get("tag") or []
    return values if isinstance(values, list) else [values]


def _detail_user_tags(detail: dict[str, Any]) -> list[Any]:
    tags = detail.get("tags") or {}
    if isinstance(tags, list):
        return tags
    if isinstance(tags, dict):
        return [key for key, enabled in tags.items() if enabled]
    return []


def _media_label(detail: dict[str, Any]) -> str:
    nfo = _nfo(detail)
    return str(nfo.get("title") or nfo.get("originaltitle") or detail.get("name") or detail.get("id") or "Unknown")


def _video_codes(detail: dict[str, Any]) -> list[str]:
    nfo = _nfo(detail)
    values = [nfo.get("num"), nfo.get("id"), nfo.get("title"), nfo.get("originaltitle"), detail.get("name"), detail.get("file_path"), detail.get("path")]
    out: list[str] = []
    for value in values:
        code = _normalize_code(value)
        if not code and value:
            code = _normalize_code(extract_video_code(str(value)))
        if code and code not in out:
            out.append(code)
    return out


def _subtitle_files(video_path: str | None) -> list[dict[str, Any]]:
    if not video_path:
        return []
    path = Path(video_path)
    if not path.parent.is_dir():
        return []
    stem = path.stem.lower()
    out: list[dict[str, Any]] = []
    try:
        for child in path.parent.iterdir():
            if not child.is_file() or child.suffix.lower() not in SUBTITLE_EXTS:
                continue
            base = child.stem.lower()
            if base in stem or stem.startswith(base) or (len(base) >= 8 and stem.startswith(base[:8])):
                out.append({"filename": child.name, "path": str(child), "ext": child.suffix.lower(), "size": child.stat().st_size})
    except OSError:
        return []
    return out


async def _index_jobs(repo: KnowledgeRepository) -> int:
    jobs = list((await repo.db.execute(select(Job))).scalars().all())
    count = 0
    for job in jobs:
        media = await repo.upsert_entity("media_item", f"emby:{job.emby_item_id}", job.emby_item_name or job.emby_item_id, data={"emby_item_id": job.emby_item_id}, source="jobs", confidence=70)
        task = await repo.upsert_entity("task", f"job:{job.id}", f"{job.job_type}:{job.status}", data={
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "input_path": job.input_path,
            "output_path": job.output_path,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result_metadata": job.result_metadata,
        }, source="jobs")
        await repo.upsert_edge(media.id, "HAS_TASK", task.id, source="jobs")
        count += 1
    return count


async def _index_plugin_contributions(repo: KnowledgeRepository, *, limit: int = 100, context: dict[str, Any] | None = None) -> dict[str, int]:
    stats = {"entities": 0, "edges": 0, "scores": 0, "anomalies": 0}
    for item in await plugin_runtime.get_knowledge_contributions(limit=limit, context=context or {}):
        source = str(item.get("source") or item.get("source_plugin") or "plugin")
        await repo.upsert_source(source, str(item.get("source_name") or source), "plugin", data={"plugin_id": item.get("source_plugin")})
        entity_map: dict[str, KnowledgeEntity] = {}
        for raw in item.get("entities") or []:
            if not isinstance(raw, dict):
                continue
            entity_type = str(raw.get("type") or raw.get("entity_type") or "").strip()
            key = str(raw.get("key") or "").strip()
            if not entity_type or not key:
                continue
            entity = await repo.upsert_entity(entity_type, key, str(raw.get("label") or key), summary=raw.get("summary"), data=raw.get("data") if isinstance(raw.get("data"), dict) else {}, source=str(raw.get("source") or source), confidence=int(raw.get("confidence") or 80))
            entity_map[str(raw.get("alias") or f"{entity_type}:{key}")] = entity
            entity_map[f"{entity_type}:{key}"] = entity
            stats["entities"] += 1
        for raw in item.get("edges") or []:
            if not isinstance(raw, dict):
                continue
            relation = str(raw.get("type") or raw.get("relation_type") or "").strip()
            source_entity = entity_map.get(str(raw.get("from") or raw.get("source_ref") or ""))
            target_entity = entity_map.get(str(raw.get("to") or raw.get("target_ref") or ""))
            if relation and source_entity and target_entity:
                await repo.upsert_edge(source_entity.id, relation, target_entity.id, source=str(raw.get("edge_source") or item.get("source_plugin") or source), confidence=int(raw.get("confidence") or 80), data=raw.get("data") if isinstance(raw.get("data"), dict) else {})
                stats["edges"] += 1
        for raw in item.get("scores") or []:
            entity = entity_map.get(str(raw.get("entity") or raw.get("entity_ref") or "")) if isinstance(raw, dict) else None
            score_type = str(raw.get("type") or raw.get("score_type") or "") if isinstance(raw, dict) else ""
            if entity and score_type:
                await repo.upsert_score(entity.id, score_type, int(raw.get("value") or 0), reason=raw.get("reason"), data=raw.get("data") if isinstance(raw.get("data"), dict) else {})
                stats["scores"] += 1
        for raw in item.get("anomalies") or []:
            entity = entity_map.get(str(raw.get("entity") or raw.get("entity_ref") or "")) if isinstance(raw, dict) else None
            if entity and raw.get("type") and raw.get("message"):
                await repo.upsert_anomaly(entity.id, str(raw["type"]), str(raw["message"]), severity=str(raw.get("severity") or "info"), source=source, data=raw.get("data") if isinstance(raw.get("data"), dict) else {})
                stats["anomalies"] += 1
    return stats


async def _media_video_codes(repo: KnowledgeRepository, *, limit: int = 300) -> list[str]:
    media = aliased(KnowledgeEntity)
    code = aliased(KnowledgeEntity)
    result = await repo.db.execute(select(code.key).distinct().join(KnowledgeEdge, KnowledgeEdge.target_entity_id == code.id).join(media, media.id == KnowledgeEdge.source_entity_id).where(code.entity_type == "video_code", media.entity_type == "media_item", KnowledgeEdge.relation_type == "HAS_CODE").limit(limit))
    return [str(value).upper() for value in result.scalars().all() if str(value or "").strip()]


async def _infer_media_torrent_links(repo: KnowledgeRepository) -> dict[str, int]:
    code = aliased(KnowledgeEntity)
    source = aliased(KnowledgeEntity)
    rows = await repo.db.execute(select(KnowledgeEdge, source, code).join(source, source.id == KnowledgeEdge.source_entity_id).join(code, code.id == KnowledgeEdge.target_entity_id).where(KnowledgeEdge.relation_type == "HAS_CODE", code.entity_type == "video_code", source.entity_type.in_(["media_item", "torrent"])))
    grouped: dict[str, dict[str, list[KnowledgeEntity]]] = {}
    for edge, entity, _ in rows.all():
        grouped.setdefault(edge.target_entity_id, {"media_item": [], "torrent": []})[entity.entity_type].append(entity)
    count = 0
    for code_id, values in grouped.items():
        for media_entity in values["media_item"]:
            for torrent in values["torrent"]:
                await repo.upsert_edge(media_entity.id, "HAS_TORRENT_CANDIDATE", torrent.id, source="knowledge-core", confidence=min(media_entity.confidence, torrent.confidence, 85), data={"reason": "shared_video_code", "video_code_entity_id": code_id})
                count += 1
    return {"inferred_edges": count}


async def _index_media_item(repo: KnowledgeRepository, item: dict[str, Any], detail: dict[str, Any] | None = None) -> dict[str, int]:
    detail = detail or item
    nfo = _nfo(detail)
    stats = {"entities": 0, "edges": 0, "subtitles": 0, "versions": 0}
    media = await repo.upsert_entity("media_item", f"emby:{detail.get('id') or item.get('id')}", _media_label(detail), summary=detail.get("name") or item.get("name"), data={
        "emby_item_id": detail.get("id") or item.get("id"),
        "name": detail.get("name") or item.get("name"),
        "file_path": detail.get("file_path") or item.get("path"),
        "poster_path": detail.get("poster_path") or item.get("poster_path"),
        "backdrop_path": detail.get("backdrop_path") or item.get("fanart_path"),
        "premiered": detail.get("premiered"),
        "date_created": detail.get("date_created") or item.get("date_created"),
        "tags": detail.get("tags") or item.get("tags") or {},
        "nfo": nfo,
    }, source="media-library")
    stats["entities"] += 1
    for code_value in _video_codes(detail):
        target = await repo.upsert_entity("video_code", code_value, code_value, source="media-library")
        await repo.upsert_edge(media.id, "HAS_CODE", target.id, source="media-library")
        stats["entities"] += 1
        stats["edges"] += 1
    relation_sets = [
        ("HAS_ACTOR", "actor", _clean_values((nfo.get("actors") or []) + (detail.get("actors") or []))),
        ("HAS_STUDIO", "studio", _clean_values((detail.get("studios") or []) + [nfo.get("maker"), nfo.get("publisher")])),
        ("HAS_LABEL", "label", _clean_values([nfo.get("label"), nfo.get("studio")])),
        ("IN_SERIES", "series", _clean_values([nfo.get("set")])),
        ("HAS_DIRECTOR", "director", _clean_values([nfo.get("director")] + (detail.get("directors") or []))),
        ("HAS_GENRE", "genre", _clean_values((detail.get("genres") or []) + (nfo.get("genres") or []))),
        ("HAS_TAG", "tag", _clean_values(_nfo_tags(nfo) + _detail_user_tags(detail))),
    ]
    for relation, entity_type, values in relation_sets:
        for value in values:
            target = await repo.upsert_entity(entity_type, value.lower(), value, source="media-library")
            await repo.upsert_edge(media.id, relation, target.id, source="media-library")
            stats["entities"] += 1
            stats["edges"] += 1
    versions = []
    if detail.get("file_path"):
        versions.append({"path": detail["file_path"], "name": os.path.basename(detail["file_path"]), "tags": detail.get("tags") or {}, "emby_item_id": detail.get("id")})
    versions.extend({"path": sibling.get("file_path"), "name": sibling.get("name") or sibling.get("label") or os.path.basename(sibling.get("file_path") or ""), "tags": sibling.get("tags") or {}, "emby_item_id": sibling.get("id")} for sibling in detail.get("siblings") or [] if sibling.get("file_path"))
    for version in versions:
        target = await repo.upsert_entity("file_version", version["path"], version["name"] or version["path"], data=version, source="media-library")
        await repo.upsert_edge(media.id, "HAS_VERSION", target.id, source="media-library")
        stats["entities"] += 1
        stats["edges"] += 1
        stats["versions"] += 1
    for subtitle in _subtitle_files(detail.get("file_path") or item.get("path")):
        target = await repo.upsert_entity("subtitle", subtitle["path"], subtitle["filename"], data={**subtitle, "source_type": "local_file"}, source="subtitle-local")
        await repo.upsert_edge(media.id, "HAS_SUBTITLE", target.id, source="subtitle-local")
        stats["entities"] += 1
        stats["edges"] += 1
        stats["subtitles"] += 1
    await repo.upsert_score(media.id, "library_quality", min(100, 35 + len(relation_sets) * 4 + stats["subtitles"] * 15 + stats["versions"] * 5), reason="媒体元数据、版本与字幕完整度")
    if not stats["subtitles"]:
        await repo.upsert_anomaly(media.id, "missing_subtitle", "未发现本地字幕", severity="warning", source="media-library")
    if stats["versions"] > 1:
        await repo.upsert_anomaly(media.id, "multi_version", f"检测到 {stats['versions']} 个媒体版本", source="media-library")
    return stats


async def rebuild_knowledge_index(db: AsyncSession, *, max_items: int | None = None, run_id: str | None = None) -> dict[str, Any]:
    repo = KnowledgeRepository(db)
    run = await db.get(__import__('app.knowledge.models', fromlist=['KnowledgeIndexRun']).KnowledgeIndexRun, run_id) if run_id else None
    if run is None:
        run = await repo.create_run(status="running", message="Knowledge Core rebuild started", stats={"phase": "preparing", "percent": 0})
    stats: dict[str, Any] = {"phase": "preparing", "percent": 0, "processed": 0, "total": max_items or 0, "media_items": 0, "entities": 0, "edges": 0, "subtitles": 0, "versions": 0, "tasks": 0, "plugin_entities": 0, "plugin_edges": 0, "inferred_edges": 0}

    async def checkpoint(phase: str, message: str, percent: int) -> None:
        stats["phase"] = phase
        stats["percent"] = max(0, min(99, percent))
        await repo.update_run(run, status="running", message=message, stats=dict(stats))

    try:
        await checkpoint("preparing", "准备重建 Knowledge Core", 2)
        await repo.clear()
        await repo.upsert_source("media-library", "媒体库", "core")
        await repo.upsert_source("subtitle-local", "本地字幕文件", "core")
        await repo.upsert_source("jobs", "任务历史", "core")
        await checkpoint("media-library", "读取媒体库", 8)
        config = media_library._load_config()
        if config.get("server_url") and config.get("api_key"):
            enabled = {value.strip() for value in str(config.get("enabled_library_ids") or "").split(",") if value.strip()}
            use_recovery_adapter = False
            try:
                libraries = await media_library._list_libraries(config)
                targets = [library for library in libraries if not enabled or library.get("id") in enabled]
            except Exception:
                # Some Emby installations reject Library/MediaFolders while
                # their authenticated user Items API remains fully available.
                use_recovery_adapter = True
                targets = [{"id": value} for value in enabled] or [{"id": None}]
            remaining = max_items
            for library in targets:
                if remaining is not None and remaining <= 0:
                    break
                offset = 0
                while True:
                    if use_recovery_adapter:
                        page_limit = min(remaining, 500) if remaining is not None else 500
                        items, total = await media_library_recovery._fetch_items(
                            config,
                            library_id=library.get("id"),
                            limit=page_limit,
                            offset=offset,
                        )
                    else:
                        page_limit = remaining or 2000
                        items, total = await media_library._list_items(config, library["id"], limit=page_limit, offset=offset, force_refresh=False)
                    stats["total"] = max_items or max(int(stats.get("total") or 0), int(total or 0))
                    if not items:
                        break
                    for item in items:
                        if remaining is not None and remaining <= 0:
                            break
                        try:
                            detail = item if use_recovery_adapter else await media_library._get_item(config, item["id"])
                        except Exception:
                            detail = None
                        item_stats = await _index_media_item(repo, item, detail)
                        for key in ("entities", "edges", "subtitles", "versions"):
                            stats[key] += item_stats[key]
                        stats["media_items"] += 1
                        stats["processed"] = stats["media_items"]
                        if stats["media_items"] == 1 or stats["media_items"] % 10 == 0:
                            await checkpoint("media-library", f"已索引 {stats['processed']} 个作品", 10 + int(min(stats["processed"], stats["total"] or 1) / max(stats["total"] or 1, 1) * 65))
                        if remaining is not None:
                            remaining -= 1
                    offset += len(items)
                    if remaining is not None and remaining <= 0:
                        break
                    if offset >= int(total or 0) or len(items) < page_limit:
                        break
                    if not use_recovery_adapter:
                        break
        await checkpoint("jobs", "读取任务历史", 78)
        stats["tasks"] = await _index_jobs(repo)
        await checkpoint("plugins", "读取插件贡献数据", 86)
        media_codes = await _media_video_codes(repo)
        stats["media_video_codes"] = len(media_codes)
        plugin_stats = await _index_plugin_contributions(repo, context={"video_codes": media_codes})
        stats["plugin_entities"] = plugin_stats["entities"]
        stats["plugin_edges"] = plugin_stats["edges"]
        stats["entities"] += plugin_stats["entities"]
        stats["edges"] += plugin_stats["edges"]
        await checkpoint("inference", "推断作品与种子关系", 91)
        inferred = await _infer_media_torrent_links(repo)
        stats["inferred_edges"] = inferred["inferred_edges"]
        stats["edges"] += inferred["inferred_edges"]
        stats["phase"] = "completed"
        stats["percent"] = 100
        await repo.finish_run(run, "completed", "Knowledge index rebuilt", stats)
        return {"ok": True, "run_id": run.id, "stats": stats}
    except Exception as exc:
        stats["phase"] = "failed"
        await repo.finish_run(run, "failed", str(exc), stats)
        raise
