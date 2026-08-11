from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import PROJECT_ROOT
from app.core.database import async_session_maker
from app.knowledge.models import KnowledgeActionState, KnowledgeEdge, KnowledgeEntity
from app.plugins.contracts import PluginManifest, PluginTestResult

PLUGIN_ID = "av-recommend"
DATA_FILE = PROJECT_ROOT / "data" / "av_recommend" / "feedback.json"
CACHE_TTL = 300
_CACHE: dict[str, Any] = {"ts": 0, "key": "", "value": None}
_pool_lock = asyncio.Lock()
_scheduler_task: asyncio.Task[None] | None = None
_scheduler_stop: asyncio.Event | None = None

CODE_RE = re.compile(r"\b(FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|[A-Z]{2,8}[-_ ]?\d{2,7}|\d{6}[-_]\d{2,5})\b", re.I)
GENERIC_CATEGORY_KEYWORDS = (
    "单体作品",
    "精选综合",
    "美少女电影",
    "高清",
    "高画质",
    "独家",
    "推荐",
    "热门",
    "有码",
    "无码",
)


def _pool_path() -> Path:
    return PROJECT_ROOT / "data" / "av_recommend" / "candidate_pool.json"


def _subscription_path() -> Path:
    return PROJECT_ROOT / "data" / "subscription_core" / "subscriptions.json"


def _pool() -> dict[str, Any]:
    try:
        data = json.loads(_pool_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_pool(pool: dict[str, Any]) -> None:
    path = _pool_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pool["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _pool_scan_due(pool: dict[str, Any], interval_minutes: int = 360) -> bool:
    previous = (pool.get("last_full_scan") or {}).get("at")
    try:
        value = dt.datetime.fromisoformat(str(previous).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - value.astimezone(dt.timezone.utc)).total_seconds() >= interval_minutes * 60
    except (TypeError, ValueError):
        return True


def _merge_candidate(existing: dict[str, Any] | None, item: dict[str, Any], source: str, label: str) -> dict[str, Any]:
    current = dict(existing or {})
    if not current:
        current.update(item)
        current["first_seen_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    else:
        for key, value in item.items():
            if value not in (None, "", [], {}) and (not current.get(key) or key in {"magnets_count", "has_cnsub", "is_cracked"}):
                current[key] = max(int(current.get(key) or 0), int(value or 0)) if key == "magnets_count" else bool(current.get(key) or value) if key in {"has_cnsub", "is_cracked"} else value
    tags = current.get("source_tags") if isinstance(current.get("source_tags"), list) else []
    if not any(isinstance(tag, dict) and tag.get("id") == source for tag in tags):
        tags.append({"id": source, "label": label, "date": dt.date.today().isoformat()})
    current["source_tags"] = tags[:16]
    current["last_seen_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    current["is_today_increment"] = bool(current.get("first_seen_at", "").startswith(dt.date.today().isoformat()))
    return current


def _candidate_pool_stats(pool: dict[str, Any]) -> dict[str, Any]:
    items = pool.get("items") if isinstance(pool.get("items"), dict) else {}
    return {
        "total": len(items),
        "today_increment": sum(bool(item.get("is_today_increment")) for item in items.values() if isinstance(item, dict)),
        "last_full_scan": pool.get("last_full_scan") or {},
        "background": pool.get("background") or {},
    }


def _subscription_codes() -> set[str]:
    try:
        data = json.loads(_subscription_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    rows = data.get("subscriptions") if isinstance(data, dict) else data
    return {_norm_code(row.get("code") if isinstance(row, dict) else row) for row in (rows or []) if _norm_code(row.get("code") if isinstance(row, dict) else row)}


def _manifest() -> PluginManifest:
    return PluginManifest(**json.loads((Path(__file__).with_name("plugin.json")).read_text(encoding="utf-8")))


manifest = _manifest()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _norm_code(value: Any) -> str:
    text = str(value or "")
    match = CODE_RE.search(text)
    if not match:
        return ""
    raw = re.sub(r"[_ ]+", "-", match.group(1).upper())
    fc2 = re.match(r"FC2-?(?:PPV-?)?(\d{4,9})$", raw, re.I)
    if fc2:
        return f"FC2-PPV-{fc2.group(1)}"
    compact = re.match(r"^([A-Z]{2,8})(\d{2,7})$", raw)
    if compact:
        return f"{compact.group(1)}-{compact.group(2)}"
    return raw


def _norm_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _feedback_codes(entries: Any) -> set[str]:
    return {_norm_code(x.get("code") if isinstance(x, dict) else x) for x in (entries or []) if _norm_code(x.get("code") if isinstance(x, dict) else x)}


def _feedback_counter(entries: Any, key: str) -> Counter:
    counter: Counter = Counter()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        for value in entry.get(key) or []:
            text = str(value or "").strip()
            if text:
                counter[text] += 1
    return counter


def _ensure_store() -> dict[str, Any]:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        data = {"version": 1, "ignored": [], "liked": [], "disliked": []}
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid feedback store")
        data.setdefault("ignored", [])
        data.setdefault("liked", [])
        data.setdefault("disliked", [])
        return data
    except Exception:
        backup = DATA_FILE.with_suffix(f".{int(time.time())}.bak")
        try:
            DATA_FILE.replace(backup)
        except Exception:
            pass
        return _ensure_store()


def _save_store(data: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def _text_has_subtitle(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
    return bool(re.search(r"中字|中文字幕|中文|字幕|sub", text, re.I))


def _text_has_cracked(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
    return bool(re.search(r"破解|无码破解|uncensored|crack|leak|流出", text, re.I))


def _generic_category_factor(name: Any) -> float:
    text = str(name or "").strip()
    if not text:
        return 0.0
    if any(keyword in text for keyword in GENERIC_CATEGORY_KEYWORDS):
        return 0.28
    if len(text) <= 1:
        return 0.35
    return 1.0


def _entity_payload(entity: KnowledgeEntity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "type": entity.entity_type,
        "key": entity.key,
        "label": entity.label,
        "summary": entity.summary,
        "data": entity.data or {},
        "source": entity.source,
        "confidence": entity.confidence,
    }


async def _library_profile() -> dict[str, Any]:
    empty_profile = {
        "media_count": 0,
        "codes": set(),
        "media_by_code": {},
        "actors": Counter(),
        "genres": Counter(),
        "tags": Counter(),
        "studios": Counter(),
        "actor_category": Counter(),
        "local_features": {},
        "top_media": [],
    }
    async with async_session_maker() as db:
        try:
            media_rows = await db.execute(select(KnowledgeEntity).where(KnowledgeEntity.entity_type == "media_item"))
        except SQLAlchemyError:
            return empty_profile
        media = list(media_rows.scalars().all())
        media_ids = [item.id for item in media]
        profile = {
            "media_count": len(media),
            "codes": set(),
            "media_by_code": {},
            "actors": Counter(),
            "genres": Counter(),
            "tags": Counter(),
            "studios": Counter(),
            "actor_category": Counter(),
            "local_features": {},
            "top_media": [_entity_payload(item) for item in media[:8]],
        }
        if not media_ids:
            return profile
        try:
            rows = await db.execute(
                select(KnowledgeEdge, KnowledgeEntity)
                .join(KnowledgeEntity, KnowledgeEntity.id == KnowledgeEdge.target_entity_id)
                .where(KnowledgeEdge.source_entity_id.in_(media_ids))
            )
        except SQLAlchemyError:
            return profile
        media_by_id = {item.id: item for item in media}
        relations_by_media: dict[str, dict[str, set[str]]] = defaultdict(lambda: {
            "actors": set(),
            "categories": set(),
            "studios": set(),
        })
        for edge, target in rows.all():
            rel = edge.relation_type
            if rel == "HAS_CODE":
                code = _norm_code(target.label or target.key)
                if code:
                    profile["codes"].add(code)
                    profile["media_by_code"][code] = _entity_payload(media_by_id.get(edge.source_entity_id)) if media_by_id.get(edge.source_entity_id) else None
            elif rel == "HAS_ACTOR":
                profile["actors"][target.label] += 1
                relations_by_media[edge.source_entity_id]["actors"].add(target.label)
            elif rel == "HAS_GENRE":
                profile["genres"][target.label] += 1
                relations_by_media[edge.source_entity_id]["categories"].add(target.label)
            elif rel == "HAS_TAG":
                profile["tags"][target.label] += 1
                relations_by_media[edge.source_entity_id]["categories"].add(target.label)
            elif rel in {"HAS_STUDIO", "HAS_LABEL"}:
                profile["studios"][target.label] += 1
                relations_by_media[edge.source_entity_id]["studios"].add(target.label)
        for rels in relations_by_media.values():
            for actor in rels["actors"]:
                for category in rels["categories"]:
                    profile["actor_category"][(actor, category)] += 1
        for item in media:
            data = item.data or {}
            code = _norm_code(json.dumps(data, ensure_ascii=False) + " " + item.label)
            if code:
                profile["local_features"][code] = {
                    "has_subtitle": _text_has_subtitle(data),
                    "is_cracked": _text_has_cracked(data),
                }
        return profile


def _top(counter: Counter, limit: int = 12) -> list[dict[str, Any]]:
    return [{"name": str(name), "count": int(count)} for name, count in counter.most_common(limit)]


def _names(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("label") or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            out.append(name)
    return out


def _unique_names(items: Any, limit: int = 20) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for name in _names(items) if isinstance(items, list) else [str(x or "").strip() for x in (items or [])]:
        value = str(name or "").strip()
        key = _norm_key(value)
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _combined_category_count(name: str, genre_counter: Counter, tag_counter: Counter) -> int:
    return max(int(genre_counter.get(name, 0)), int(tag_counter.get(name, 0)))


def _preference_confidence(count: int, media_count: int) -> float:
    """Return a bounded confidence curve for a media-library signal.

    A single hit should be a clue, not a strong conclusion. Repeated hits become
    meaningful, but the curve saturates so one very common actor/tag does not
    dominate the whole recommendation page.
    """
    if count <= 0 or media_count <= 0:
        return 0.0
    frequency = min(1.0, count / max(media_count, 1))
    repeat = min(1.0, math.log2(count + 1) / 5.0)
    return max(0.0, min(1.0, repeat * 0.78 + frequency * 0.22))


def _score_bucket(value: float) -> str:
    if value >= 28:
        return "strong"
    if value >= 14:
        return "medium"
    if value > 0:
        return "weak"
    return "none"


async def _javdb_candidates(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        from app.plugins.runtime import runtime
        if not runtime.is_enabled("javdb"):
            return [], ["JavDB 插件未启用，暂时无法生成候选推荐。"]
        candidate_limit = max(12, min(int(config.get("candidate_limit") or 48), 120))
        detail_limit = max(0, min(int(config.get("detail_limit") or 36), 80))
        requests = [
            ("latest", {"page": 1, "limit": candidate_limit, "type": "all", "filter_by": "magnets", "filters": ["magnets"], "sort_by": "update"}),
            ("latest", {"page": 1, "limit": max(24, candidate_limit // 2), "type": "all", "filter_by": "magnets", "filters": ["magnets"], "sort_by": "release"}),
            # A recommendation engine should not only chase the newest feed.
            # Blend in DBOnline's own recommend/ranking lists as candidates, but
            # keep them small so they do not slow down the plugin.
            ("recommend", {"page": 1, "limit": max(18, candidate_limit // 3)}),
            ("rankings", {"page": 1, "limit": max(18, candidate_limit // 3), "period": "weekly", "type": 0}),
        ]
        by_code: dict[str, dict[str, Any]] = {}
        for action, payload in requests:
            try:
                data = await runtime.handle_action("javdb", action, payload)
                for item in data.get("items") or []:
                    code = _norm_code(item.get("code") or item.get("number") or item.get("display_title") or item.get("title"))
                    if not code:
                        continue
                    current = by_code.get(code)
                    if not current:
                        next_item = dict(item)
                        # Match the JavDB plugin media card: the horizontal
                        # cover is cover_url/thumb_url, not preview screenshots.
                        next_item["fanart_url"] = next_item.get("cover_url") or next_item.get("thumb_url") or ""
                        by_code[code] = next_item
                    else:
                        current["magnets_count"] = max(int(current.get("magnets_count") or 0), int(item.get("magnets_count") or 0))
                        current["has_cnsub"] = bool(current.get("has_cnsub") or item.get("has_cnsub") or item.get("play_subtitle"))
                        current["is_cracked"] = bool(current.get("is_cracked") or item.get("is_cracked"))
                        if not current.get("fanart_url"):
                            current["fanart_url"] = current.get("cover_url") or current.get("thumb_url") or item.get("cover_url") or item.get("thumb_url") or ""
            except Exception as exc:
                warnings.append(f"JavDB {action} 拉取失败：{exc}")
        items = list(by_code.values())
        semaphore = asyncio.Semaphore(6)

        async def enrich(item: dict[str, Any]) -> dict[str, Any]:
            code = _norm_code(item.get("code") or item.get("number") or item.get("display_title"))
            if not code:
                return item
            async with semaphore:
                try:
                    detail = await runtime.handle_action("javdb", "video", {"code": code})
                    data = detail.get("data") if isinstance(detail, dict) else {}
                    if isinstance(data, dict):
                        item["detail"] = data
                        item["actors"] = _names(data.get("actors"))
                        item["categories"] = _names(data.get("categories"))
                        item["maker"] = data.get("maker") or data.get("publisher") or ""
                        item["cover_url"] = data.get("cover_url") or item.get("cover_url")
                        item["fanart_url"] = item.get("cover_url") or data.get("cover_url") or item.get("thumb_url") or data.get("thumb_url") or ""
                        item["has_cnsub"] = bool(item.get("has_cnsub") or _text_has_subtitle(data))
                        item["is_cracked"] = bool(item.get("is_cracked") or _text_has_cracked(data))
                        magnets = data.get("magnets") if isinstance(data.get("magnets"), list) else []
                        if magnets:
                            item["magnets_count"] = max(int(item.get("magnets_count") or 0), len(magnets))
                            item["best_resource_size_mb"] = max([float(x.get("size_mb") or 0) for x in magnets if isinstance(x, dict)] or [0])
                except Exception:
                    pass
            return item

        enriched = await asyncio.gather(*(enrich(item) for item in items[:detail_limit]))
        by_code.update({_norm_code(item.get("code") or item.get("number")): item for item in enriched if _norm_code(item.get("code") or item.get("number"))})
        return list(by_code.values()), warnings
    except Exception as exc:
        return [], [f"候选拉取失败：{exc}"]


async def _scan_candidate_pool(config: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    from app.plugins.runtime import runtime

    if not runtime.is_enabled("javdb"):
        return {"ok": False, "message": "JavDB 插件未启用"}
    async with _pool_lock:
        pool = _pool()
        background = pool.get("background") if isinstance(pool.get("background"), dict) else {}
        if background.get("running") and not force:
            return {"ok": True, "skipped": True, "reason": "running", "pool": _candidate_pool_stats(pool)}
        pool["background"] = {**background, "running": True, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_error": ""}
        _save_pool(pool)

    pages = max(1, min(int(config.get("full_scan_pages") or 5), 30))
    requests: list[tuple[str, str, dict[str, Any]]] = [
        ("latest", "最新更新", {"page": 1, "limit": 48, "type": "all", "filter_by": "magnets", "sort_by": "update"}),
        ("rankings", "日榜", {"page": 1, "limit": 24, "period": "daily", "type": 0}),
        ("rankings", "周榜", {"page": 1, "limit": 24, "period": "weekly", "type": 0}),
        ("rankings", "月榜", {"page": 1, "limit": 24, "period": "monthly", "type": 0}),
        ("recommend", "JavDB 推荐", {"page": 1, "limit": 24}),
    ]
    requests.extend(("videos", f"完整库 P{page}", {"page": page, "limit": 80, "sort": "update", "order": "desc"}) for page in range(1, pages + 1))
    scanned = added = updated = 0
    warnings: list[str] = []
    try:
        for action, label, request_payload in requests:
            try:
                response = await runtime.handle_action("javdb", action, request_payload)
            except Exception as exc:
                warnings.append(f"{label}: {exc}")
                continue
            values = response.get("items") if isinstance(response, dict) else []
            async with _pool_lock:
                pool = _pool()
                items = pool.get("items") if isinstance(pool.get("items"), dict) else {}
                for value in values or []:
                    if not isinstance(value, dict):
                        continue
                    code = _norm_code(value)
                    if not code:
                        continue
                    existed = code in items
                    items[code] = _merge_candidate(items.get(code), value, f"{action}:{label}", label)
                    scanned += 1
                    added += 0 if existed else 1
                    updated += 1 if existed else 0
                pool["items"] = items
                _save_pool(pool)
        async with _pool_lock:
            pool = _pool()
            pool["last_full_scan"] = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "pages": pages, "scanned": scanned, "added": added, "updated": updated, "warnings": warnings[:8]}
            pool["background"] = {**(pool.get("background") or {}), "running": False, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_error": ""}
            _save_pool(pool)
            return {"ok": True, "scanned": scanned, "added": added, "updated": updated, "warnings": warnings, "pool": _candidate_pool_stats(pool)}
    except Exception as exc:
        async with _pool_lock:
            pool = _pool()
            pool["background"] = {**(pool.get("background") or {}), "running": False, "failed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_error": str(exc)}
            _save_pool(pool)
        raise


async def _scheduler_loop() -> None:
    global _scheduler_stop
    _scheduler_stop = asyncio.Event()
    while not _scheduler_stop.is_set():
        try:
            from app.plugins.runtime import runtime
            config = runtime.get_config(PLUGIN_ID)
            minutes = max(30, min(int(config.get("scan_interval_minutes") or 360), 1440))
            if _pool_scan_due(_pool(), minutes):
                await _scan_candidate_pool(config)
        except asyncio.CancelledError:
            raise
        except Exception:
            minutes = 30
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(_scheduler_stop.wait(), timeout=minutes * 60)


async def start_background(_config: dict[str, Any] | None = None) -> None:
    global _scheduler_task
    if not _scheduler_task or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())


async def stop_background() -> None:
    global _scheduler_task, _scheduler_stop
    if _scheduler_stop:
        _scheduler_stop.set()
    if _scheduler_task:
        _scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scheduler_task
    _scheduler_task = None
    _scheduler_stop = None


def _candidate_score(item: dict[str, Any], profile: dict[str, Any], config: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any] | None:
    code = _norm_code(item.get("code") or item.get("number") or item.get("display_title") or item.get("title"))
    ignored = feedback.get("ignored_codes") or set()
    liked = feedback.get("liked_codes") or set()
    disliked = feedback.get("disliked_codes") or set()
    disliked_actors: Counter = feedback.get("disliked_actors") or Counter()
    disliked_categories: Counter = feedback.get("disliked_categories") or Counter()
    liked_actors: Counter = feedback.get("liked_actors") or Counter()
    liked_categories: Counter = feedback.get("liked_categories") or Counter()
    if not code or code in ignored or code in disliked:
        return None
    in_library = code in profile.get("codes", set()) or bool((item.get("library") or {}).get("in_library") if isinstance(item.get("library"), dict) else False)
    actors = _unique_names(item.get("actors") or [], 12)
    categories = _unique_names(item.get("categories") or [], 16)
    maker = str(item.get("maker") or "").strip()
    score = 0.0
    reasons: list[str] = []
    personalized_score = 0.0
    actionability_score = 0.0
    quality_score = 0.0
    penalty_score = 0.0

    actor_counter: Counter = profile.get("actors") or Counter()
    genre_counter: Counter = profile.get("genres") or Counter()
    tag_counter: Counter = profile.get("tags") or Counter()
    studio_counter: Counter = profile.get("studios") or Counter()
    actor_category_counter: Counter = profile.get("actor_category") or Counter()
    media_count = max(int(profile.get("media_count") or 0), 1)

    actor_hits = [(name, actor_counter.get(name, 0)) for name in actors if actor_counter.get(name, 0) > 0]
    if actor_hits:
        best_name, best_count = max(actor_hits, key=lambda x: x[1])
        confidence = _preference_confidence(best_count, media_count)
        boost = min(32, (3 if best_count <= 1 else 7) + math.log2(best_count + 1) * 7.2 + confidence * 6)
        score += boost
        personalized_score += boost
        reasons.append(f"{'演员偏好' if best_count > 1 else '演员线索'}：{best_name} 已有 {best_count} 部")
        if len(actor_hits) >= 2:
            score += min(8, len(actor_hits) * 2.5)
            personalized_score += min(8, len(actor_hits) * 2.5)
            reasons.append(f"多演员命中：{len(actor_hits)} 位")

    feedback_actor_boost = 0.0
    feedback_actor_penalty = 0.0
    for actor in actors:
        feedback_actor_boost += min(8, liked_actors.get(actor, 0) * 4)
        # A single dislike is a weak signal; repeated selected dislike is a real
        # user preference. Keep it soft to avoid "误杀" an actor that only
        # appeared in a bad title once.
        disliked_count = disliked_actors.get(actor, 0)
        if disliked_count:
            feedback_actor_penalty += min(18, 4 + disliked_count * 6)
    if feedback_actor_boost:
        score += feedback_actor_boost
        personalized_score += feedback_actor_boost
        reasons.append("正反馈演员")
    if feedback_actor_penalty:
        score -= feedback_actor_penalty
        penalty_score += feedback_actor_penalty
        reasons.append("负反馈演员降权")

    category_hits = []
    for name in categories:
        count = _combined_category_count(name, genre_counter, tag_counter)
        if count > 0:
            category_hits.append((name, count, _generic_category_factor(name)))
    if category_hits:
        sorted_hits = sorted(category_hits, key=lambda x: x[1] * x[2], reverse=True)
        names = "/".join(name for name, _, factor in sorted_hits[:3] if factor >= 0.5)
        boost = min(24, sum(min(6.5, math.sqrt(count) * 2.9 + _preference_confidence(count, media_count) * 2) * factor for _, count, factor in sorted_hits[:6]))
        score += boost
        personalized_score += boost
        if names:
            reasons.append(f"类型匹配：{names}")

    feedback_category_boost = 0.0
    feedback_category_penalty = 0.0
    for category in categories:
        factor = _generic_category_factor(category)
        feedback_category_boost += min(6, liked_categories.get(category, 0) * 3 * factor)
        disliked_count = disliked_categories.get(category, 0)
        if disliked_count:
            feedback_category_penalty += min(16, (3 + disliked_count * 5) * factor)
    if feedback_category_boost:
        score += feedback_category_boost
        personalized_score += feedback_category_boost
        reasons.append("正反馈类型")
    if feedback_category_penalty:
        score -= feedback_category_penalty
        penalty_score += feedback_category_penalty
        reasons.append("负反馈类型降权")

    combo_hits = []
    for actor in actors:
        for category in categories:
            count = actor_category_counter.get((actor, category), 0)
            factor = _generic_category_factor(category)
            if count > 0 and factor >= 0.5:
                actor_count = max(actor_counter.get(actor, 0), 1)
                category_count = max(_combined_category_count(category, genre_counter, tag_counter), 1)
                lift = count / math.sqrt(actor_count * category_count)
                combo_hits.append((actor, category, count, factor, lift))
    if combo_hits:
        actor, category, count, factor, lift = max(combo_hits, key=lambda x: (x[2] * x[3], x[4]))
        boost = min(24, (5 if count <= 1 else 9) + math.log2(count + 1) * 5 * factor + min(5, lift * 7))
        score += boost
        personalized_score += boost
        reasons.append(f"组合偏好：{actor} + {category} 出现 {count} 次")

    # If the candidate has no familiar actor but several strong preferred tags,
    # mark it as a controlled discovery rather than letting it look random.
    if not actor_hits and category_hits:
        strong_category_count = sum(1 for _, count, factor in category_hits if count >= 2 and factor >= 0.5)
        if strong_category_count >= 2:
            discovery_boost = min(8, strong_category_count * 2.5)
            score += discovery_boost
            personalized_score += discovery_boost
            reasons.append("类型探索")

    if maker and studio_counter.get(maker, 0):
        count = studio_counter.get(maker, 0)
        boost = min(9, 3 + math.log2(count + 1) * 3)
        score += boost
        personalized_score += boost
        reasons.append(f"厂牌匹配：{maker}")

    magnets_count = int(item.get("magnets_count") or 0)
    if magnets_count > 0:
        boost = 6 + min(5, magnets_count)
        score += boost
        actionability_score += boost
        reasons.append(f"有 {magnets_count} 个磁链")

    if item.get("has_cnsub"):
        boost = 9 if config.get("prefer_subtitle", True) else 5
        score += boost
        actionability_score += boost
        reasons.append("中字资源")
    if item.get("is_cracked"):
        boost = 10 if config.get("prefer_cracked", True) else 5
        score += boost
        actionability_score += boost
        reasons.append("破解特征")

    size_mb = float(item.get("best_resource_size_mb") or 0)
    if size_mb > 0:
        boost = min(4, max(0, math.log(max(size_mb, 1), 2) - 10))
        score += boost
        quality_score += boost
        if size_mb >= 4096:
            reasons.append(f"资源体积 {size_mb / 1024:.1f}GB")

    if code in liked:
        score += 20
        reasons.append("已标记喜欢")
    release = str(item.get("release_date") or item.get("date") or "")
    if release.startswith("2026"):
        score += 4
        quality_score += 4
        reasons.append("近期作品")
    elif release.startswith("2025"):
        score += 2
        quality_score += 2

    if profile.get("media_count", 0) < 5:
        score += min(12, float(item.get("score") or 0) * 2)
        if not reasons:
            reasons.append("媒体库样本较少，按资源可用性推荐")

    if media_count >= 10 and personalized_score < 10:
        score -= 12
        penalty_score += 12
        reasons.append("个性化命中较弱")

    # Generic-only candidates are often popular feed noise. If all category
    # labels are broad labels and no actor/studio signal exists, keep them from
    # floating to the top only because they have resources.
    meaningful_categories = [x for x in categories if _generic_category_factor(x) >= 0.5]
    if media_count >= 10 and not actor_hits and not maker and not meaningful_categories:
        score -= 10
        penalty_score += 10
        reasons.append("标签过泛降权")

    local_features = (profile.get("local_features") or {}).get(code) or {}
    rec_type = "upgrade" if in_library else "subscribe"
    if in_library:
        current_has_sub = bool(local_features.get("has_subtitle"))
        current_cracked = bool(local_features.get("is_cracked"))
        improved = []
        if item.get("has_cnsub") and not current_has_sub:
            improved.append("补中字")
        if item.get("is_cracked") and not current_cracked:
            improved.append("补破解")
        if size_mb >= 4096:
            improved.append("更高体积版本")
        if not improved:
            return None
        score += 10
        reasons.insert(0, "洗版：" + " / ".join(improved[:3]))

    score = max(0, min(92, round(score)))
    if score <= 0:
        return None
    match_bucket = _score_bucket(personalized_score)
    detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
    return {
        "code": code,
        "title": item.get("title") or item.get("display_title") or code,
        "display_title": item.get("display_title") or f"{code} {item.get('title') or ''}".strip(),
        "cover_url": item.get("cover_url") or item.get("thumb_url") or "",
        "fanart_url": item.get("fanart_url") or item.get("cover_url") or item.get("thumb_url") or "",
        "release_date": release,
        "actors": actors[:6],
        "categories": categories[:8],
        "maker": maker,
        "score": score,
        "personalized_score": round(personalized_score, 1),
        "actionability_score": round(actionability_score, 1),
        "quality_score": round(quality_score, 1),
        "penalty_score": round(penalty_score, 1),
        "match_level": match_bucket,
        "confidence": max(0, min(100, round(personalized_score * 1.6 + actionability_score * 0.45 - penalty_score * 0.7))),
        "score_breakdown": {
            "preference": round(personalized_score, 1),
            "resources": round(actionability_score, 1),
            "quality": round(quality_score, 1),
            "penalty": round(penalty_score, 1),
        },
        "type": rec_type,
        "in_library": bool(in_library),
        "magnets_count": magnets_count,
        "has_cnsub": bool(item.get("has_cnsub")),
        "is_cracked": bool(item.get("is_cracked")),
        "best_resource_size_mb": size_mb,
        "reasons": reasons[:5],
        "source_tags": list(item.get("source_tags") or []),
        "is_today_increment": bool(item.get("is_today_increment")),
        "series": item.get("series") or detail.get("series") or "",
        "director": item.get("director") or detail.get("director") or "",
        "title_traits": list(item.get("title_traits") or []),
        "source": "javdb",
        "source_label": "JavDB",
        "route": f"/plugins/javdb?code={code}",
        "raw": {"id": item.get("id"), "library": item.get("library") or {}},
    }


def _resource_features(resource: dict[str, Any]) -> dict[str, bool]:
    features = resource.get("features") if isinstance(resource.get("features"), dict) else {}
    requirements = resource.get("requirements") if isinstance(resource.get("requirements"), dict) else {}
    tags = " ".join(str(x) for x in (resource.get("tags") or []))
    text = "\n".join([
        str(resource.get("title") or ""),
        str(resource.get("subtitle") or ""),
        str(resource.get("provider_label") or ""),
        tags,
        json.dumps(features, ensure_ascii=False),
    ])
    return {
        "has_subtitle": bool(features.get("has_subtitle") or re.search(r"中字|中文字幕|中文|字幕|sub", text, re.I)),
        "is_cracked": bool(features.get("is_cracked") or features.get("new_model_uncensored_crack") or re.search(r"破解|无码破解|uncensored|crack|leak|流出", text, re.I)),
        "is_private_tracker": bool(features.get("is_private_tracker") or requirements.get("accepts_private_tracker")),
    }


async def _enrich_recommendation_resources(config: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if not items:
        return warnings
    try:
        from app.plugins.runtime import runtime
    except Exception as exc:
        return [f"资源插件运行时不可用：{exc}"]
    enrich_limit = max(0, min(int(config.get("resource_enrich_limit") or 16), 48))
    if enrich_limit <= 0:
        return warnings
    targets = items[:enrich_limit]
    semaphore = asyncio.Semaphore(4)

    async def enrich_one(item: dict[str, Any]) -> None:
        code = str(item.get("code") or "").strip()
        if not code:
            return
        async with semaphore:
            try:
                result = await runtime.search_resources(
                    {"keyword": code, "provider_timeout_seconds": 5},
                    limit_per_plugin=8,
                )
            except Exception as exc:
                warnings.append(f"{code} 资源确认失败：{exc}")
                return
        resources: list[dict[str, Any]] = []
        groups = result if isinstance(result, list) else [result]
        for group in groups:
            if not isinstance(group, dict):
                continue
            provider = str(group.get("provider") or "")
            provider_name = str(group.get("provider_name") or provider or "资源")
            for resource in group.get("items") or []:
                if not isinstance(resource, dict):
                    continue
                row = dict(resource)
                row.setdefault("provider", provider)
                row.setdefault("provider_label", provider_name)
                resources.append(row)
        if not resources:
            item["resource_summary"] = {"total": 0, "providers": []}
            return
        provider_counts: Counter = Counter()
        total_size = 0
        best_size = 0
        has_subtitle = bool(item.get("has_cnsub"))
        is_cracked = bool(item.get("is_cracked"))
        has_private = False
        has_public = False
        compatible_downloaders: set[str] = set()
        for res in resources:
            provider = str(res.get("provider_label") or res.get("provider") or "资源").strip()
            provider_counts[provider] += 1
            size = int(res.get("size_bytes") or 0)
            total_size += max(0, size)
            best_size = max(best_size, size)
            feats = _resource_features(res)
            has_subtitle = has_subtitle or feats["has_subtitle"]
            is_cracked = is_cracked or feats["is_cracked"]
            has_private = has_private or feats["is_private_tracker"]
            has_public = has_public or not feats["is_private_tracker"]
            for downloader_id in res.get("compatible_downloaders") or []:
                if downloader_id:
                    compatible_downloaders.add(str(downloader_id))
        providers = [{"name": name, "count": count} for name, count in provider_counts.most_common()]
        item["resource_summary"] = {
            "total": len(resources),
            "providers": providers,
            "best_size_bytes": best_size,
            "total_size_bytes": total_size,
            "has_private": has_private,
            "has_public": has_public,
            "compatible_downloaders": sorted(compatible_downloaders),
        }
        # Resource availability is actionability, not taste. Keep it a small
        # secondary boost so it cannot dominate actor/category preference.
        score_boost = min(6, len(resources)) + min(3, best_size / 1024 / 1024 / 1024 * 0.45)
        if has_subtitle and not item.get("has_cnsub"):
            score_boost += 4
            item["has_cnsub"] = True
            item.setdefault("reasons", []).append("资源确认：中字")
        if is_cracked and not item.get("is_cracked"):
            score_boost += 5
            item["is_cracked"] = True
            item.setdefault("reasons", []).append("资源确认：破解")
        if providers:
            item.setdefault("reasons", []).append("资源来源：" + " / ".join(f"{p['name']}×{p['count']}" for p in providers[:3]))
        if best_size > 0:
            item["best_resource_size_mb"] = max(float(item.get("best_resource_size_mb") or 0), best_size / 1024 / 1024)
        breakdown = item.get("score_breakdown") if isinstance(item.get("score_breakdown"), dict) else {}
        breakdown["resources"] = round(float(breakdown.get("resources") or 0) + score_boost, 1)
        item["score_breakdown"] = breakdown
        item["actionability_score"] = round(float(item.get("actionability_score") or 0) + score_boost, 1)
        item["confidence"] = max(0, min(100, round(float(item.get("confidence") or 0) + score_boost * 0.45)))
        cap = 100 if float(item.get("personalized_score") or 0) >= 22 else 82
        item["score"] = max(0, min(cap, int(round(float(item.get("score") or 0) + score_boost))))
        item["reasons"] = list(dict.fromkeys(item.get("reasons") or []))[:6]

    await asyncio.gather(*(enrich_one(item) for item in targets))
    return warnings[:8]


def _diversify_recommendations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep strong recommendations but avoid a front page monopolized by one actor/tag."""
    remaining = list(items)
    selected: list[dict[str, Any]] = []
    actor_seen: Counter = Counter()
    category_seen: Counter = Counter()
    while remaining:
        best_index = 0
        best_value = -9999.0
        for index, item in enumerate(remaining):
            value = float(item.get("score") or 0)
            actors = [str(x) for x in item.get("actors") or []]
            categories = [str(x) for x in item.get("categories") or [] if _generic_category_factor(x) >= 0.5]
            actor_penalty = sum(actor_seen.get(actor, 0) for actor in actors[:3]) * 7
            category_penalty = sum(category_seen.get(category, 0) for category in categories[:3]) * 2
            adjusted = value - actor_penalty - category_penalty
            if adjusted > best_value:
                best_value = adjusted
                best_index = index
        picked = remaining.pop(best_index)
        picked["diversity_rank"] = len(selected) + 1
        selected.append(picked)
        for actor in (picked.get("actors") or [])[:3]:
            actor_seen[str(actor)] += 1
        for category in (picked.get("categories") or [])[:4]:
            if _generic_category_factor(category) >= 0.5:
                category_seen[str(category)] += 1
    return selected


async def _recommendations(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    source_mode = str(payload.get("source_mode") or "latest").strip().lower()
    if source_mode not in {"latest", "full"}:
        source_mode = "latest"
    store = _ensure_store()
    feedback = {
        "ignored_codes": _feedback_codes(store.get("ignored")),
        "liked_codes": _feedback_codes(store.get("liked")),
        "disliked_codes": _feedback_codes(store.get("disliked")),
        "liked_actors": _feedback_counter(store.get("liked"), "actors"),
        "liked_categories": _feedback_counter(store.get("liked"), "categories"),
        "disliked_actors": _feedback_counter(store.get("disliked"), "actors"),
        "disliked_categories": _feedback_counter(store.get("disliked"), "categories"),
    }
    cache_key = json.dumps({
        "config": config,
        "ignored": sorted(feedback["ignored_codes"]),
        "liked": sorted(feedback["liked_codes"]),
        "disliked": sorted(feedback["disliked_codes"]),
        "liked_actors": dict(feedback["liked_actors"]),
        "liked_categories": dict(feedback["liked_categories"]),
        "disliked_actors": dict(feedback["disliked_actors"]),
        "disliked_categories": dict(feedback["disliked_categories"]),
        "source_mode": source_mode,
    }, sort_keys=True, ensure_ascii=False)
    if not payload.get("refresh") and _CACHE.get("value") is not None and _CACHE.get("key") == cache_key and time.time() - float(_CACHE.get("ts") or 0) < CACHE_TTL:
        return _CACHE["value"]

    profile = await _library_profile()
    pool = _pool()
    pool_items = pool.get("items") if isinstance(pool.get("items"), dict) else {}
    if source_mode == "full":
        candidates = [dict(item) for item in pool_items.values() if isinstance(item, dict)]
        warnings: list[str] = []
        if not candidates:
            warnings.append("完整候选池尚未建立，请先执行候选池扫描。")
    else:
        candidates, warnings = await _javdb_candidates(config)
        # Reuse persisted source and first-seen metadata without replacing the
        # fresher fields returned by the latest feed.
        for item in candidates:
            code = _norm_code(item.get("code") or item.get("number") or item.get("display_title") or item.get("title"))
            persisted = pool_items.get(code) if code else None
            if isinstance(persisted, dict):
                item["source_tags"] = list(persisted.get("source_tags") or [])
                item["is_today_increment"] = bool(persisted.get("is_today_increment"))

    excluded_codes = set(profile.get("codes") or set())
    excluded_codes.update(_subscription_codes())
    candidates = [
        item for item in candidates
        if _norm_code(item.get("code") or item.get("number") or item.get("display_title") or item.get("title")) not in excluded_codes
        and not bool((item.get("library") or {}).get("in_library") if isinstance(item.get("library"), dict) else False)
    ]
    scored = []
    for item in candidates:
        rec = _candidate_score(item, profile, config, feedback)
        if rec:
            scored.append(rec)
    scored.sort(key=lambda x: (x["score"], x.get("magnets_count") or 0, x.get("release_date") or ""), reverse=True)
    resource_warnings = await _enrich_recommendation_resources(config, scored)
    if resource_warnings:
        warnings.extend(resource_warnings)
    scored.sort(key=lambda x: (x["score"], (x.get("resource_summary") or {}).get("total") or 0, x.get("magnets_count") or 0, x.get("release_date") or ""), reverse=True)
    scored = _diversify_recommendations(scored)
    limit = max(1, min(int(payload.get("limit") or 48), 100))
    result = {
        "ok": True,
        "generated_at": _now_ms(),
        "source_mode": source_mode,
        "source_label": "完整推荐" if source_mode == "full" else "最新推荐",
        "items": scored[:limit],
        "total": len(scored),
        "profile": {
            "media_count": profile.get("media_count") or 0,
            "code_count": len(profile.get("codes") or []),
            "top_actors": _top(profile.get("actors") or Counter(), 10),
            "top_genres": _top(profile.get("genres") or Counter(), 10),
            "top_tags": _top(profile.get("tags") or Counter(), 10),
            "top_studios": _top(profile.get("studios") or Counter(), 8),
        },
        "stats": {
            "candidates": len(candidates),
            "candidate_pool_total": _candidate_pool_stats(pool)["total"],
            "candidate_pool_today": _candidate_pool_stats(pool)["today_increment"],
            "today_increment": sum(1 for item in candidates if item.get("is_today_increment")),
            "ignored": len([x for x in feedback["ignored_codes"] if x]),
            "disliked": len([x for x in feedback["disliked_codes"] if x]),
        },
        "candidate_meta": {"pool": _candidate_pool_stats(pool)},
        "warnings": warnings,
    }
    _CACHE.update({"ts": time.time(), "key": cache_key, "value": result})
    return result


async def test(config: dict[str, Any]) -> PluginTestResult:
    try:
        from app.plugins.runtime import runtime
        if not runtime.is_enabled("javdb"):
            return PluginTestResult(ok=False, message="JavDB 插件未启用")
        profile = await _library_profile()
        return PluginTestResult(ok=True, message="recommendation ready", details={"media_count": profile.get("media_count", 0)})
    except Exception as exc:
        return PluginTestResult(ok=False, message=f"recommendation failed: {exc}")


async def handle_action(action: str, config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if action in {"recommendations", "overview"}:
        return await _recommendations(config, payload or {})
    if action == "profile":
        profile = await _library_profile()
        return {
            "ok": True,
            "profile": {
                "media_count": profile.get("media_count") or 0,
                "code_count": len(profile.get("codes") or []),
                "top_actors": _top(profile.get("actors") or Counter(), 20),
                "top_genres": _top(profile.get("genres") or Counter(), 20),
                "top_tags": _top(profile.get("tags") or Counter(), 20),
                "top_studios": _top(profile.get("studios") or Counter(), 12),
            },
        }
    if action == "scan_candidate_pool":
        return await _scan_candidate_pool(config, force=bool(payload.get("force")))
    if action == "candidate_pool":
        return {"ok": True, "pool": _candidate_pool_stats(_pool())}
    if action == "feedback":
        code = _norm_code(payload.get("code"))
        kind = str(payload.get("kind") or "ignore").strip()
        if not code:
            raise ValueError("缺少番号")
        data = _ensure_store()
        key = "ignored" if kind == "ignore" else "liked" if kind == "like" else "disliked"
        row = {
            "code": code,
            "created_at": _now_ms(),
            "reason": str(payload.get("reason") or ""),
            "actors": [str(x).strip() for x in (payload.get("actors") or []) if str(x or "").strip()][:8],
            "categories": [str(x).strip() for x in (payload.get("categories") or []) if str(x or "").strip()][:12],
        }
        data[key] = [x for x in data.get(key, []) if _norm_code(x.get("code") if isinstance(x, dict) else x) != code]
        data[key].insert(0, row)
        _save_store(data)
        _CACHE["value"] = None
        return {"ok": True, "code": code, "kind": kind}
    if action == "reset_feedback":
        data = _ensure_store()
        data["ignored"] = []
        data["liked"] = []
        data["disliked"] = []
        _save_store(data)
        _CACHE["value"] = None
        return {"ok": True}
    raise ValueError(f"unsupported action: {action}")


def background_tasks(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or {}
    pool = _pool()
    stats = _candidate_pool_stats(pool)
    background = stats.get("background") or {}
    last_scan = stats.get("last_full_scan") or {}
    interval = max(30, min(int(config.get("scan_interval_minutes") or 360), 1440))
    running = bool(background.get("running"))
    failed = bool(background.get("last_error"))
    status = "failed" if failed else ("running" if running else "idle")
    return [{
        "id": "av-recommend.candidate-pool",
        "title": "完整推荐候选池",
        "status": status,
        "last_run_at": background.get("started_at") or last_scan.get("at") or None,
        "last_finished_at": background.get("finished_at") or last_scan.get("at") or None,
        "summary": f"{stats['total']} 个候选 · 今日新增 {stats['today_increment']} · 每 {interval} 分钟更新",
        "detail": background.get("last_error") or (f"最近扫描 {last_scan.get('scanned', 0)} 项" if last_scan else "等待首次扫描"),
        "metrics": {
            "candidate_pool_total": stats["total"],
            "today_increment": stats["today_increment"],
            "interval_minutes": interval,
        },
    }]
