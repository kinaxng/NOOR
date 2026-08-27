from __future__ import annotations

import hashlib
import asyncio
import contextlib
import itertools
import json
import re
import unicodedata
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import async_session_maker
from app.core.models import utcnow
from app.core.runtime_paths import data_path
from app.knowledge.codes import extract_video_code_candidates
from app.knowledge.models import PreferenceEvent, ResourceObservation, ResourceRefreshState, WorkProfile, stable_id

_refresh_queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
_refresh_counter = itertools.count()
_refresh_queued: set[str] = set()
_refresh_workers: list[asyncio.Task[None]] = []
_refresh_planner_task: asyncio.Task[None] | None = None
_refresh_planner_stop: asyncio.Event | None = None
_refresh_planner_last: dict[str, Any] = {}
_actor_alias_cache: tuple[float, frozenset[str], dict[str, str], dict[str, str]] | None = None
_similarity_cache: tuple[str, dict[str, Any]] | None = None
_work_search_cache: dict[str, Any] = {"expires_at": 0.0, "documents": []}
_work_search_lock = asyncio.Lock()
WORK_SIMILARITY_VERSION = 6
WORK_PROFILE_FUSION_VERSION = 1
SIMILARITY_CATEGORY_STOPWORDS = {
    "单体作品", "精选综合", "高清", "高画质", "有码", "无码", "中文字幕", "字幕", "中文",
    "身体", "本番", "作品", "影片", "电影", "独家", "推荐", "热门", "has_chinese",
    "release_type", "release_type_key", "is_leaked", "is_cracked", "torrent",
}
SEMANTIC_PROFILE_VERSION = 8
SEMANTIC_STOPWORDS = {
    "これ", "それ", "この", "その", "ため", "から", "まで", "より", "そして", "また", "作品", "動画",
    "一个", "一种", "这个", "那个", "以及", "然后", "作品", "影片", "电影", "高清", "高画质",
}
SEMANTIC_LATIN_STOPWORDS = {
    "fanza", "dmm", "javdb", "avdb", "video", "movie", "sample", "preview", "sex",
}
PREFERENCE_EVENT_WEIGHTS = {
    "detail_view": 0.18,
    "subscription": 1.8,
    "download_intent": 1.25,
    "download_submitted": 0.8,
    "library_imported": 4.0,
    "upgrade_completed": 4.5,
    "upgrade_cleanup_failed": 0.0,
}
PREFERENCE_EVENT_HALF_LIFE_DAYS = {
    "detail_view": 14,
    "subscription": 90,
    "download_intent": 45,
    "download_submitted": 45,
    "library_imported": 365,
    "upgrade_completed": 365,
    "upgrade_cleanup_failed": 30,
}
OUTCOME_ATTEMPT_EVENTS = {"subscription", "download_intent", "download_submitted"}
OUTCOME_VERIFIED_EVENTS = {"library_imported", "upgrade_completed"}
PREFERENCE_EVENT_STAGE_VALUES = {
    "detail_view": 0.15,
    "subscription": 0.60,
    "download_intent": 0.75,
    "download_submitted": 0.85,
    "library_imported": 1.0,
    "upgrade_completed": 1.0,
}


def _invalidate_work_search_cache(*, delay_seconds: float = 30.0) -> None:
    """Debounce index rebuilds while background providers continuously write facts."""
    if not _work_search_cache.get("documents"):
        _work_search_cache["expires_at"] = 0.0
        return
    scheduled = time.monotonic() + max(0.0, delay_seconds)
    current = float(_work_search_cache.get("expires_at") or scheduled)
    _work_search_cache["expires_at"] = min(current, scheduled)


def canonical_work_code(value: Any) -> str:
    candidates = extract_video_code_candidates(str(value or ""))
    if not candidates:
        return ""
    first = candidates[0].upper()
    # The general extractor intentionally preserves a one-letter suffix as a
    # candidate because some callers need the exact filename spelling.  Core
    # identities represent the work, not its local version: -C/-U and similar
    # filename marks therefore collapse to the immediately following base code.
    if re.search(r"-[A-Z]$", first) and len(candidates) > 1:
        base = first.rsplit("-", 1)[0]
        if candidates[1].upper() == base:
            return base
    return first


def _normalize_actor_name(value: Any) -> str:
    return re.sub(r"[\s\u3000・·._\-]", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def _actor_alias_data() -> tuple[frozenset[str], dict[str, str], dict[str, str]]:
    """Load MDC-NG actor aliases and their preferred NOOR display names."""
    global _actor_alias_cache
    path = data_path("media_actor_mappings.json")
    try:
        mtime = path.stat().st_mtime
        if _actor_alias_cache and len(_actor_alias_cache) == 4 and _actor_alias_cache[0] == mtime:
            return _actor_alias_cache[1], _actor_alias_cache[2], _actor_alias_cache[3]
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset(), {}, {}
    names: set[str] = set()
    identities: dict[str, str] = {}
    identity_keys: dict[str, str] = {}
    for record in payload.get("records") or []:
        if not isinstance(record, dict):
            continue
        values = [record.get("jp"), record.get("zh_cn"), record.get("zh_tw"), *(record.get("names") or []), *(record.get("aliases") or [])]
        values = [str(value).strip() for value in values if str(value or "").strip()]
        preferred = str(record.get("zh_cn") or record.get("jp") or record.get("zh_tw") or (values[0] if values else "")).strip()
        record_id = str(record.get("id") or "").strip()
        identity_key = f"mdc-ng:{record_id}" if record_id else f"name:{_normalize_actor_name(preferred)}"
        names.update(values)
        if preferred:
            for value in values:
                normalized = _normalize_actor_name(value)
                identities.setdefault(normalized, preferred)
                identity_keys.setdefault(normalized, identity_key)
    result = frozenset(names)
    _actor_alias_cache = (mtime, result, identities, identity_keys)
    return result, identities, identity_keys


def actor_alias_names() -> frozenset[str]:
    """Return all known actor names from the synchronized MDC-NG mapping."""
    return _actor_alias_data()[0]


def actor_alias_revision() -> str:
    """Cheap cache revision that changes whenever the synchronized mapping changes."""
    path = data_path("media_actor_mappings.json")
    try:
        stat = path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return "missing"


def actor_alias_stats() -> dict[str, int | str]:
    names, _labels, identity_keys = _actor_alias_data()
    return {
        "identity_count": len(set(identity_keys.values())),
        "alias_count": len(names),
        "revision": actor_alias_revision(),
    }


def canonical_actor_name(value: Any) -> str:
    """Resolve any MDC-NG alias to one stable display name."""
    name = str(value or "").strip()
    return _actor_alias_data()[1].get(_normalize_actor_name(name), name)


def actor_identity_key(value: Any) -> str:
    """Return the stable MDC-NG actor id, with a deterministic fallback."""
    normalized = _normalize_actor_name(value)
    if not normalized:
        return ""
    return _actor_alias_data()[2].get(normalized, f"name:{normalized}")


async def record_preference_event(
    code: str,
    event_type: str,
    *,
    source: str = "unknown",
    actors: list[Any] | None = None,
    categories: list[Any] | None = None,
    data: dict[str, Any] | None = None,
    enqueue_refresh: bool = True,
) -> bool:
    canonical = canonical_work_code(code)
    kind = str(event_type or "").strip()
    if not canonical or kind not in PREFERENCE_EVENT_WEIGHTS:
        return False
    now = utcnow()
    cooldown = timedelta(hours=6 if kind == "detail_view" else 24)
    async with async_session_maker() as db:
        evidence_id = str((data or {}).get("evidence_id") or "").strip()
        event_id = stable_id("preference-event", source, kind, evidence_id) if evidence_id else stable_id("preference-event", canonical, kind, source, now.isoformat())
        if evidence_id and await db.get(PreferenceEvent, event_id):
            return False
        latest = (await db.execute(
            select(PreferenceEvent)
            .where(PreferenceEvent.work_code == canonical, PreferenceEvent.event_type == kind, PreferenceEvent.source == source)
            .order_by(PreferenceEvent.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest and latest.created_at >= now - cooldown:
            return False
        profile = await db.get(WorkProfile, canonical)
        if profile:
            for facts in (profile.facts or {}).values():
                if not isinstance(facts, dict):
                    continue
                if not actors:
                    actors = list(facts.get("actors") or facts.get("actresses") or [])
                if not categories:
                    categories = list(facts.get("categories") or facts.get("genres") or facts.get("tags") or [])
                if actors and categories:
                    break
        def evidence_name(value: Any) -> str:
            if isinstance(value, dict):
                return str(value.get("name") or value.get("label") or "").strip()
            return str(value or "").strip()
        actor_names = list(dict.fromkeys(canonical_actor_name(evidence_name(value)) for value in (actors or []) if evidence_name(value)))[:12]
        category_names = list(dict.fromkeys(evidence_name(value) for value in (categories or []) if evidence_name(value)))[:20]
        event = PreferenceEvent(
            id=event_id,
            work_code=canonical,
            event_type=kind,
            source=source,
            weight=PREFERENCE_EVENT_WEIGHTS[kind],
            actors=actor_names,
            categories=category_names,
            data=data or {},
            created_at=now,
        )
        db.add(event)
        await db.commit()
    refresh_priority = {"subscription": 5, "download_intent": 8, "detail_view": 24}.get(kind)
    if enqueue_refresh and refresh_priority is not None:
        await enqueue_resource_refresh([canonical], priority=refresh_priority)
    return True


async def preference_behavior_summary(*, max_age_days: int = 365) -> dict[str, Any]:
    now = utcnow()
    cutoff = now - timedelta(days=max_age_days)
    try:
        async with async_session_maker() as db:
            events = list((await db.execute(select(PreferenceEvent).where(PreferenceEvent.created_at >= cutoff))).scalars())
    except SQLAlchemyError:
        return {"codes": {}, "actors": {}, "actor_identities": {}, "categories": {}, "code_stages": {}, "event_count": 0, "revision": "0:none"}
    codes: dict[str, float] = {}
    actors: dict[str, float] = {}
    actor_identities: dict[str, float] = {}
    categories: dict[str, float] = {}
    code_stages: dict[str, dict[str, Any]] = {}
    for event in events:
        age_days = max(0.0, (now - event.created_at).total_seconds() / 86400)
        half_life = PREFERENCE_EVENT_HALF_LIFE_DAYS.get(event.event_type, 30)
        effective = float(event.weight or 0) * math.pow(0.5, age_days / half_life)
        codes[event.work_code] = codes.get(event.work_code, 0.0) + effective
        for actor in event.actors or []:
            name = canonical_actor_name(actor)
            actors[name] = actors.get(name, 0.0) + effective
            identity = actor_identity_key(actor)
            if identity:
                actor_identities[identity] = actor_identities.get(identity, 0.0) + effective
        for category in event.categories or []:
            name = str(category).strip()
            if name:
                categories[name] = categories.get(name, 0.0) + effective
        stage_value = float(PREFERENCE_EVENT_STAGE_VALUES.get(event.event_type, 0.0))
        previous = code_stages.get(event.work_code)
        if stage_value > 0 and (
            not previous
            or stage_value > float(previous.get("value") or 0)
            or (stage_value == float(previous.get("value") or 0) and event.created_at.isoformat() > str(previous.get("at") or ""))
        ):
            code_stages[event.work_code] = {
                "stage": event.event_type,
                "value": stage_value,
                "verified": event.event_type in OUTCOME_VERIFIED_EVENTS,
                "at": event.created_at.isoformat(),
                "source": event.source,
            }
    latest = max((event.created_at for event in events), default=None)
    return {
        "codes": codes,
        "actors": actors,
        "actor_identities": actor_identities,
        "categories": categories,
        "code_stages": code_stages,
        "event_count": len(events),
        "outcomes": _preference_outcome_model(events),
        "trends": _preference_drift_model(events),
        "revision": f"{len(events)}:{latest.isoformat() if latest else 'none'}",
    }


def _bayesian_rate(successes: int, trials: int) -> float:
    return (max(0, successes) + 2) / (max(0, trials) + 4)


def _preference_outcome_model(events: list[PreferenceEvent]) -> dict[str, Any]:
    """Build a conservative conversion model from intent to verified outcomes."""
    by_code: dict[str, dict[str, Any]] = {}
    for event in events:
        row = by_code.setdefault(event.work_code, {"attempt": False, "verified": False, "actors": set(), "categories": set()})
        row["attempt"] = bool(row["attempt"] or event.event_type in OUTCOME_ATTEMPT_EVENTS)
        row["verified"] = bool(row["verified"] or event.event_type in OUTCOME_VERIFIED_EVENTS)
        row["actors"].update(actor_identity_key(actor) for actor in (event.actors or []) if actor_identity_key(actor))
        row["categories"].update(str(category).strip() for category in (event.categories or []) if str(category or "").strip())
    trials = {code for code, row in by_code.items() if row["attempt"] or row["verified"]}
    verified = {code for code in trials if by_code[code]["verified"]}

    def dimension_rates(key: str) -> dict[str, dict[str, float | int]]:
        dimension_trials: dict[str, set[str]] = {}
        dimension_verified: dict[str, set[str]] = {}
        for code in trials:
            for value in by_code[code][key]:
                dimension_trials.setdefault(value, set()).add(code)
                if code in verified:
                    dimension_verified.setdefault(value, set()).add(code)
        return {
            value: {
                "trials": len(codes),
                "verified": len(dimension_verified.get(value, set())),
                "rate": round(_bayesian_rate(len(dimension_verified.get(value, set())), len(codes)), 4),
                "reliability": round(min(1.0, len(codes) / 6), 4),
            }
            for value, codes in dimension_trials.items()
        }

    return {
        "trials": len(trials),
        "verified": len(verified),
        "rate": round(_bayesian_rate(len(verified), len(trials)), 4),
        "actors": dimension_rates("actors"),
        "categories": dimension_rates("categories"),
    }


def _preference_drift_model(events: list[PreferenceEvent], *, window_days: int = 30) -> dict[str, Any]:
    """Contrast recent and prior tastes using stable MDC-NG actor identities."""
    now = utcnow()
    boundary = now - timedelta(days=window_days)
    cutoff = boundary - timedelta(days=window_days)
    buckets: dict[str, dict[str, dict[str, float]]] = {
        "recent": {"actors": {}, "categories": {}},
        "prior": {"actors": {}, "categories": {}},
    }
    actor_labels: dict[str, str] = {}
    for event in events:
        if event.created_at < cutoff:
            continue
        bucket = buckets["recent" if event.created_at >= boundary else "prior"]
        for actor in event.actors or []:
            identity = actor_identity_key(actor)
            if identity:
                bucket["actors"][identity] = bucket["actors"].get(identity, 0.0) + float(event.weight or 0)
                actor_labels.setdefault(identity, canonical_actor_name(actor))
        for category in event.categories or []:
            name = str(category or "").strip()
            if name:
                bucket["categories"][name] = bucket["categories"].get(name, 0.0) + float(event.weight or 0)

    def dimension(name: str) -> dict[str, Any]:
        recent = buckets["recent"][name]
        prior = buckets["prior"][name]
        recent_total = sum(recent.values()) or 1.0
        prior_total = sum(prior.values()) or 1.0
        deltas: dict[str, float] = {}
        rows: list[dict[str, Any]] = []
        for key in set(recent) | set(prior):
            current_share = recent.get(key, 0.0) / recent_total
            previous_share = prior.get(key, 0.0) / prior_total
            delta = current_share - previous_share
            deltas[key] = round(delta, 6)
            rows.append({
                "name": actor_labels.get(key, key),
                "identity": key if name == "actors" else "",
                "share": round(current_share, 4),
                "previous_share": round(previous_share, 4),
                "delta": round(delta, 4),
            })
        return {
            "deltas": deltas,
            "rising": sorted((row for row in rows if row["delta"] > 0 and row["share"] > 0), key=lambda row: (row["delta"], row["share"]), reverse=True)[:8],
            "fading": sorted((row for row in rows if row["delta"] < 0 and row["previous_share"] > 0), key=lambda row: row["delta"])[:8],
        }

    return {
        "window_days": window_days,
        "recent_events": sum(1 for event in events if event.created_at >= boundary),
        "prior_events": sum(1 for event in events if cutoff <= event.created_at < boundary),
        "actors": dimension("actors"),
        "categories": dimension("categories"),
    }


async def preference_learning_metrics(*, window_days: int = 30) -> dict[str, Any]:
    """Summarize outcome calibration and recent-vs-prior preference drift."""
    now = utcnow()
    cutoff = now - timedelta(days=window_days * 2)
    async with async_session_maker() as db:
        events = list((await db.execute(select(PreferenceEvent).where(PreferenceEvent.created_at >= cutoff))).scalars())
    trends = _preference_drift_model(events, window_days=window_days)

    return {
        "window_days": window_days,
        "recent_events": trends["recent_events"],
        "prior_events": trends["prior_events"],
        "rising_actors": trends["actors"]["rising"][:5],
        "rising_categories": trends["categories"]["rising"][:5],
        "fading_actors": trends["actors"]["fading"][:5],
        "fading_categories": trends["categories"]["fading"][:5],
        "trends": trends,
        "outcomes": _preference_outcome_model(events),
    }


async def clear_preference_events(*, source: str | None = None) -> int:
    statement = delete(PreferenceEvent)
    if source:
        statement = statement.where(PreferenceEvent.source == source)
    async with async_session_maker() as db:
        result = await db.execute(statement)
        await db.commit()
    return int(result.rowcount or 0)


def semantic_tokens(*values: Any) -> dict[str, Any]:
    text = unicodedata.normalize("NFKC", " ".join(str(value or "") for value in values if value))
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b(?:FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|[A-Z]{2,10}[-_ ]?\d{2,7})\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?:4k|8k|fhd|uhd|1080p|2160p|hdr|60fps)\b", " ", text, flags=re.I)
    latin = list(dict.fromkeys(
        part.casefold()
        for part in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
        if part.casefold() not in SEMANTIC_LATIN_STOPWORDS
    ))
    normalized_cjk = re.sub(r"(?:した|して|する|される|され|れる|られ|ない|です|ます|から|まで|より|そして|また|その|この|の|に|を|が|と|で|へ|的|了|过|与)", " ", text)
    cjk_runs = re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,16}", normalized_cjk)
    cjk: list[str] = []
    weighted: dict[str, float] = {}
    def informative(term: str) -> bool:
        return len(re.findall(r"[\u30a0-\u30ff\u3400-\u9fffA-Za-z]", term)) >= 2
    for run in cjk_runs:
        pure_hiragana = bool(re.fullmatch(r"[\u3040-\u309f]+", run))
        if pure_hiragana:
            continue
        if run not in SEMANTIC_STOPWORDS and informative(run):
            cjk.append(run)
            weighted[run] = max(weighted.get(run, 0), 1.8 if len(run) <= 8 else 1.2)
    for term in latin:
        weighted[term] = max(weighted.get(term, 0), 1.0)
    return {"version": SEMANTIC_PROFILE_VERSION, "latin": latin[:80], "cjk": list(dict.fromkeys(cjk))[:320], "weighted": dict(sorted(weighted.items(), key=lambda row: (-row[1], row[0]))[:400])}


def _work_similarity_file():
    return data_path("work_similarity_index.json")


def _fact_names(facts: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = facts.get(key)
        rows = raw if isinstance(raw, list) else [raw] if raw else []
        for row in rows:
            name = str((row.get("name") or row.get("label") or "") if isinstance(row, dict) else row or "").strip()
            if name and name not in values:
                values.append(name)
    return values


def _work_similarity_features(profile: WorkProfile) -> tuple[dict[str, float], dict[str, str]]:
    features: dict[str, float] = {}
    labels: dict[str, str] = {}
    for facts in (profile.facts or {}).values():
        if not isinstance(facts, dict):
            continue
        actor_names = _fact_names(facts, "actors", "actresses")
        actor_name_keys = {_normalize_actor_name(name) for name in actor_names}
        groups = [
            ("actor", actor_names, 4.2),
            ("series", _fact_names(facts, "series"), 4.0),
            ("director", _fact_names(facts, "director", "directors"), 3.0),
            ("studio", _fact_names(facts, "maker", "publisher", "studio", "label"), 2.4),
            ("category", _fact_names(facts, "categories", "genres", "tags"), 1.5),
        ]
        for kind, names, weight in groups:
            for name in names[:20]:
                actual_kind, actual_name, actual_weight = kind, name, weight
                if kind == "category":
                    normalized_label = unicodedata.normalize("NFKC", name).strip()
                    prefix_match = re.match(r"^(?:系列|シリーズ)\s*[:：]\s*(.+)$", normalized_label, re.I)
                    studio_match = re.match(r"^(?:片商|发行|發行|メーカー|レーベル)\s*[:：]\s*(.+)$", normalized_label, re.I)
                    if prefix_match:
                        actual_kind, actual_name, actual_weight = "series", prefix_match.group(1).strip(), 4.0
                    elif studio_match:
                        actual_kind, actual_name, actual_weight = "studio", studio_match.group(1).strip(), 2.4
                    elif (
                        normalized_label.casefold() in {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}
                        or re.fullmatch(r"(?:has|is)_[a-z0-9_]+", normalized_label, re.I)
                        or _normalize_actor_name(normalized_label) in actor_name_keys
                    ):
                        continue
                value = actor_identity_key(actual_name) if actual_kind == "actor" else unicodedata.normalize("NFKC", actual_name).casefold()
                key = f"{actual_kind}:{value}"
                features[key] = max(features.get(key, 0), actual_weight)
                labels[key] = canonical_actor_name(actual_name) if actual_kind == "actor" else actual_name
    weighted_terms = (profile.tokens or {}).get("weighted") if isinstance(profile.tokens, dict) else {}
    for term, raw_weight in sorted((weighted_terms or {}).items(), key=lambda row: float(row[1] or 0), reverse=True)[:80]:
        normalized = unicodedata.normalize("NFKC", str(term)).casefold().strip()
        if len(normalized) < 2 or normalized in {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}:
            continue
        key = f"semantic:{normalized}"
        features[key] = max(features.get(key, 0), min(1.2, float(raw_weight or 0) * 0.55))
        labels[key] = str(term)
    return features, labels


def _profile_source_scores(profile: WorkProfile) -> dict[str, float]:
    scores = {"media-library": 0.95, "javdb": 0.9, "mdc-ng": 0.9}
    for evidence in profile.source_evidence or []:
        if not isinstance(evidence, dict):
            continue
        source = str(evidence.get("source") or "").strip()
        if source:
            scores[source] = max(scores.get(source, 0.0), max(0.0, min(1.0, float(evidence.get("confidence") or 0) / 100)))
    return scores


def _image_stability_score(value: str) -> float:
    url = str(value or "").strip()
    if not url:
        return 0.0
    score = 0.15
    if "/api/image?" in url:
        score += 0.25
    if url.startswith("https://"):
        score += 0.18
    elif url.startswith("/"):
        score += 0.16
    if re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", url, re.I):
        score += 0.08
    return score


def fused_work_profile(profile: WorkProfile) -> dict[str, Any]:
    """Resolve source facts deterministically while preserving provenance and alternatives."""
    source_scores = _profile_source_scores(profile)
    facts_by_source = [(str(source), facts) for source, facts in (profile.facts or {}).items() if isinstance(facts, dict)]
    facts_by_source.sort(key=lambda row: (-source_scores.get(row[0], 0.5), row[0]))
    field_sources: dict[str, str] = {}

    def union_names(*keys: str, actors: bool = False) -> list[str]:
        values: list[str] = []
        identities: set[str] = set()
        for source, facts in facts_by_source:
            for name in _fact_names(facts, *keys):
                display = canonical_actor_name(name) if actors else name
                identity = actor_identity_key(display) if actors else unicodedata.normalize("NFKC", display).casefold().strip()
                if identity and identity not in identities:
                    identities.add(identity)
                    values.append(display)
                    field_sources.setdefault("actors" if actors else "categories", source)
        return values

    def best_name(field: str, *keys: str) -> str:
        for source, facts in facts_by_source:
            names = _fact_names(facts, *keys)
            if names:
                field_sources[field] = source
                return names[0]
        return ""

    image_rows: list[tuple[float, str, str]] = []
    for source, facts in facts_by_source:
        for key in ("cover_url", "poster_url", "thumb_url", "image"):
            url = str(facts.get(key) or "").strip()
            if url and not any(existing[1] == url for existing in image_rows):
                image_rows.append((source_scores.get(source, 0.5) + _image_stability_score(url), url, source))
    image_rows.sort(key=lambda row: (-row[0], row[2], row[1]))
    cover_url = image_rows[0][1] if image_rows else ""
    if image_rows:
        field_sources["cover_url"] = image_rows[0][2]

    title_candidates = [
        (3, str(profile.translated_title or "").strip(), "translated_title"),
        (2, str(profile.original_title or "").strip(), "original_title"),
        (1, str(profile.title or "").strip(), "title"),
        *[(0, str(alias or "").strip(), "alias") for alias in profile.aliases or []],
    ]
    valid_titles = [row for row in title_candidates if row[1] and row[1].upper() != str(profile.code or "").upper()]
    _priority, title, title_source = max(valid_titles, key=lambda row: (row[0], len(row[1]))) if valid_titles else (0, profile.code, "code")
    field_sources["title"] = title_source
    release_date = best_name("release_date", "release_date", "date")
    actors = union_names("actors", "actresses", actors=True)
    categories = union_names("categories", "genres", "tags")
    return {
        "code": profile.code,
        "title": title,
        "original_title": profile.original_title,
        "translated_title": profile.translated_title,
        "actors": actors,
        "categories": categories,
        "maker": best_name("maker", "maker", "publisher", "studio", "label"),
        "series": best_name("series", "series"),
        "director": best_name("director", "director", "directors"),
        "cover_url": cover_url,
        "image_candidates": [url for _score, url, _source in image_rows[:8]],
        "release_date": release_date,
        "confidence": int(profile.confidence or 0),
        "field_sources": field_sources,
        "source_count": len(facts_by_source),
        "completeness": {
            "title": title_source != "code",
            "cover": bool(cover_url),
            "actors": bool(actors),
            "categories": bool(categories),
        },
    }


def _work_profile_candidate(profile: WorkProfile) -> dict[str, Any]:
    return fused_work_profile(profile)


def _relation_reliability(feature: str) -> float:
    """Prior reliability for a shared relation, independent of cosine strength."""
    kind = feature.split(":", 1)[0]
    if kind == "actor":
        return 0.99 if feature.startswith("actor:mdc-ng:") else 0.88
    return {
        "series": 0.95,
        "director": 0.88,
        "studio": 0.82,
        "category": 0.66,
        "semantic": 0.38,
    }.get(kind, 0.45)


def _relation_confidence(similarity: float, rows: list[tuple[float, str]]) -> float:
    """Calibrate relation confidence so one loose title token cannot look authoritative."""
    if not rows:
        return 0.0
    total = sum(max(0.0, contribution) for contribution, _feature in rows) or 1.0
    prior = sum(max(0.0, contribution) * _relation_reliability(feature) for contribution, feature in rows) / total
    kinds = {feature.split(":", 1)[0] for _contribution, feature in rows}
    evidence_bonus = min(0.12, max(0, len(rows) - 1) * 0.035 + max(0, len(kinds) - 1) * 0.025)
    cosine_reliability = 0.55 + 0.45 * min(1.0, similarity / 0.35)
    confidence = prior * cosine_reliability + evidence_bonus
    if kinds == {"semantic"}:
        confidence *= 0.72
    return max(0.05, min(0.99, confidence))


async def build_work_similarity_index(*, force: bool = False, neighbor_limit: int = 24) -> dict[str, Any]:
    """Build a durable sparse multi-relation work-neighborhood index."""
    global _similarity_cache
    async with async_session_maker() as db:
        profiles = list((await db.execute(select(WorkProfile))).scalars())
    latest = max((profile.updated_at for profile in profiles if profile.updated_at), default=None)
    revision = f"{WORK_SIMILARITY_VERSION}:{SEMANTIC_PROFILE_VERSION}:{actor_alias_revision()}:{len(profiles)}:{latest.isoformat() if latest else 'none'}"
    if not force and _similarity_cache and _similarity_cache[0] == revision:
        return _similarity_cache[1]
    path = _work_similarity_file()
    if not force and path.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("revision") == revision:
                _similarity_cache = (revision, saved)
                return saved

    raw_features: dict[str, dict[str, float]] = {}
    feature_labels: dict[str, str] = {}
    postings: dict[str, list[str]] = defaultdict(list)
    candidates: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        code = canonical_work_code(profile.code)
        if not code:
            continue
        features, labels = _work_similarity_features(profile)
        combined = raw_features.setdefault(code, {})
        for feature, weight in features.items():
            combined[feature] = max(combined.get(feature, 0), weight)
        feature_labels.update(labels)
        current_candidate = candidates.get(code)
        candidate = _work_profile_candidate(profile)
        if current_candidate is None or int(candidate.get("confidence") or 0) > int(current_candidate.get("confidence") or 0):
            candidates[code] = candidate
    for code, features in raw_features.items():
        for feature in features:
            postings[feature].append(code)
    work_count = max(len(raw_features), 1)
    weighted: dict[str, dict[str, float]] = defaultdict(dict)
    feature_cap = max(40, int(work_count * 0.15))
    for feature, codes in postings.items():
        document_frequency = len(set(codes))
        if document_frequency < 2 or document_frequency > feature_cap:
            continue
        idf = math.log((work_count + 1) / (document_frequency + 1)) + 1
        for code in set(codes):
            weighted[code][feature] = raw_features[code][feature] * idf
    norms = {code: math.sqrt(sum(value * value for value in values.values())) for code, values in weighted.items()}
    dots: dict[tuple[str, str], float] = defaultdict(float)
    shared: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for feature, codes in postings.items():
        eligible = sorted({code for code in codes if feature in weighted.get(code, {})})
        for index, left in enumerate(eligible):
            for right in eligible[index + 1:]:
                contribution = weighted[left][feature] * weighted[right][feature]
                pair = (left, right)
                dots[pair] += contribution
                shared[pair].append((contribution, feature))
    neighbors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (left, right), dot in dots.items():
        denominator = norms.get(left, 0) * norms.get(right, 0)
        if denominator <= 0:
            continue
        similarity = dot / denominator
        if similarity < 0.08:
            continue
        strongest = sorted(shared[(left, right)], reverse=True)[:5]
        relation_confidence = _relation_confidence(similarity, strongest)
        reasons = []
        for contribution, feature in strongest:
            kind = feature.split(":", 1)[0]
            reasons.append({"type": kind, "label": feature_labels.get(feature, feature.split(":", 1)[-1]), "weight": round(contribution, 3)})
        calibrated_score = similarity * relation_confidence * 100
        relation_types = sorted({reason["type"] for reason in reasons})
        shared_payload = {
            "score": round(calibrated_score, 2),
            "cosine_similarity": round(similarity, 4),
            "relation_confidence": round(relation_confidence, 3),
            "relation_types": relation_types,
            "reasons": reasons,
        }
        row_left = {"code": right, **shared_payload}
        row_right = {"code": left, **shared_payload}
        neighbors[left].append(row_left)
        neighbors[right].append(row_right)
    for code in list(neighbors):
        neighbors[code] = sorted(neighbors[code], key=lambda row: row["score"], reverse=True)[:neighbor_limit]
    result = {
        "version": WORK_SIMILARITY_VERSION,
        "profile_fusion_version": WORK_PROFILE_FUSION_VERSION,
        "revision": revision,
        "generated_at": utcnow().isoformat(),
        "work_count": len(raw_features),
        "feature_count": sum(1 for feature, codes in postings.items() if 2 <= len(set(codes)) <= feature_cap),
        "linked_work_count": len(neighbors),
        "mapped_actor_feature_count": sum(1 for feature in postings if feature.startswith("actor:mdc-ng:")),
        "fallback_actor_feature_count": sum(1 for feature in postings if feature.startswith("actor:name:")),
        "neighbors": dict(neighbors),
        "candidates": candidates,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    _similarity_cache = (revision, result)
    return result


async def work_similarity_candidates(seed_weights: dict[str, float], *, negative_seed_weights: dict[str, float] | None = None, limit: int = 160) -> dict[str, Any]:
    index = await build_work_similarity_index()
    seeds = {canonical_work_code(code): float(weight) for code, weight in seed_weights.items() if canonical_work_code(code)}
    scores: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed_code, seed_weight in sorted(seeds.items(), key=lambda row: row[1], reverse=True)[:80]:
        for neighbor in (index.get("neighbors") or {}).get(seed_code, []):
            code = neighbor["code"]
            if code in seeds:
                continue
            contribution = float(neighbor.get("score") or 0) / 100 * max(0.1, seed_weight)
            scores[code] += contribution
            evidence[code].append({
                "seed_code": seed_code,
                "contribution": round(contribution, 3),
                "relation_confidence": float(neighbor.get("relation_confidence") or 0),
                "relation_types": neighbor.get("relation_types") or [],
                "reasons": neighbor.get("reasons") or [],
            })
    negative_scores: dict[str, float] = defaultdict(float)
    negative_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    negative_seeds = {canonical_work_code(code): max(0.0, float(weight)) for code, weight in (negative_seed_weights or {}).items() if canonical_work_code(code)}
    for seed_code, seed_weight in sorted(negative_seeds.items(), key=lambda row: row[1], reverse=True)[:80]:
        for neighbor in (index.get("neighbors") or {}).get(seed_code, []):
            code = neighbor["code"]
            if code in seeds or code in negative_seeds:
                continue
            contribution = float(neighbor.get("score") or 0) / 100 * max(0.1, seed_weight)
            negative_scores[code] += contribution
            negative_evidence[code].append({
                "seed_code": seed_code,
                "contribution": round(contribution, 3),
                "relation_confidence": float(neighbor.get("relation_confidence") or 0),
                "relation_types": neighbor.get("relation_types") or [],
                "reasons": neighbor.get("reasons") or [],
            })
    ranked = sorted(scores, key=lambda code: scores[code], reverse=True)[:max(1, min(limit, 500))]
    items = []
    for code in ranked:
        candidate = dict((index.get("candidates") or {}).get(code) or {"code": code, "title": code})
        candidate["neighbor_score"] = round(scores[code], 3)
        candidate["neighbor_evidence"] = sorted(evidence[code], key=lambda row: row["contribution"], reverse=True)[:5]
        total_contribution = sum(float(row.get("contribution") or 0) for row in evidence[code]) or 1.0
        candidate["neighbor_confidence"] = round(sum(float(row.get("contribution") or 0) * float(row.get("relation_confidence") or 0) for row in evidence[code]) / total_contribution, 3)
        candidate["neighbor_negative_score"] = round(negative_scores.get(code, 0.0), 3)
        candidate["neighbor_negative_evidence"] = sorted(negative_evidence.get(code, []), key=lambda row: row["contribution"], reverse=True)[:3]
        items.append(candidate)
    return {"revision": index.get("revision"), "items": items, "seed_count": len(seeds), "negative_seed_count": len(negative_seeds), "linked_work_count": index.get("linked_work_count", 0)}


def work_similarity_status() -> dict[str, Any]:
    payload = _similarity_cache[1] if _similarity_cache else None
    if payload is None:
        with contextlib.suppress(OSError, json.JSONDecodeError):
            payload = json.loads(_work_similarity_file().read_text(encoding="utf-8"))
    payload = payload or {}
    return {
        "version": payload.get("version"),
        "profile_fusion_version": payload.get("profile_fusion_version") or WORK_PROFILE_FUSION_VERSION,
        "revision": payload.get("revision"),
        "generated_at": payload.get("generated_at"),
        "work_count": int(payload.get("work_count") or 0),
        "feature_count": int(payload.get("feature_count") or 0),
        "linked_work_count": int(payload.get("linked_work_count") or 0),
        "mapped_actor_feature_count": int(payload.get("mapped_actor_feature_count") or 0),
        "fallback_actor_feature_count": int(payload.get("fallback_actor_feature_count") or 0),
    }


async def upgrade_semantic_profiles() -> int:
    upgraded = 0
    async with async_session_maker() as db:
        profiles = list((await db.execute(select(WorkProfile))).scalars())
        for profile in profiles:
            if int((profile.tokens or {}).get("version") or 0) >= SEMANTIC_PROFILE_VERSION:
                continue
            profile.tokens = semantic_tokens(profile.title, profile.original_title, profile.translated_title, *(profile.aliases or []))
            upgraded += 1
        if upgraded:
            await db.commit()
    return upgraded


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
    _invalidate_work_search_cache()
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
    _invalidate_work_search_cache()
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
    priority = max(0, min(int(priority), 100))
    now = utcnow()
    async with async_session_maker() as db:
        for raw in codes:
            code = canonical_work_code(raw)
            if not code:
                continue
            state = await db.get(ResourceRefreshState, code)
            if code in _refresh_queued:
                if state and priority < int(state.priority or 100):
                    state.priority = priority
                    state.requested_at = now
                    await _refresh_queue.put((priority, next(_refresh_counter), code))
                    accepted += 1
                continue
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
        queued_priority, _sequence, code = await _refresh_queue.get()
        processed = False
        try:
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if not state or state.status != "queued" or int(state.priority or 100) != queued_priority:
                    continue
                state.status = "running"
                state.started_at = utcnow()
                await db.commit()
                processed = True
            from app.plugins.runtime import runtime
            await runtime.search_resources({"keyword": code, "provider_timeout_seconds": 12}, limit_per_plugin=24)
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if state:
                    state.status = "completed"
                    state.completed_at = utcnow()
                    state.attempts = 0
                    state.error = ""
                    await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with async_session_maker() as db:
                state = await db.get(ResourceRefreshState, code)
                if state:
                    state.status = "failed"
                    state.attempts = int(state.attempts or 0) + 1
                    state.error = str(exc)[:1000]
                    state.completed_at = utcnow()
                    await db.commit()
        finally:
            if processed:
                _refresh_queued.discard(code)
            _refresh_queue.task_done()


def _profile_needs_version_intelligence(profile: WorkProfile) -> bool:
    for facts in (profile.facts or {}).values():
        if not isinstance(facts, dict) or not facts.get("in_library"):
            continue
        tags = " ".join(str(value) for value in [*(facts.get("tags") or []), *(facts.get("categories") or []), *(facts.get("genres") or [])])
        has_cracked = bool(facts.get("is_cracked") or "破解" in tags)
        has_subtitle = bool(facts.get("has_subtitle") or re.search(r"中字|字幕|中文", tags, re.I))
        return not (has_cracked and has_subtitle)
    return False


async def plan_resource_refreshes(*, limit: int = 12) -> dict[str, Any]:
    """Schedule a bounded high-value batch without repeating fresh provider checks."""
    global _refresh_planner_last
    now = utcnow()
    limit = max(1, min(int(limit), 50))
    behavior = await preference_behavior_summary()
    behavior_codes = behavior.get("codes") or {}
    async with async_session_maker() as db:
        profiles = list((await db.execute(select(WorkProfile))).scalars())
        observations = list((await db.execute(select(ResourceObservation.work_code, func.max(ResourceObservation.expires_at)).group_by(ResourceObservation.work_code))).all())
        states = {state.work_code: state for state in (await db.execute(select(ResourceRefreshState))).scalars()}
    fresh_until: dict[str, datetime] = {}
    for raw_code, expires_at in observations:
        code = canonical_work_code(raw_code)
        if code and expires_at and (code not in fresh_until or expires_at > fresh_until[code]):
            fresh_until[code] = expires_at
    canonical_states: dict[str, ResourceRefreshState] = {}
    for raw_code, state in states.items():
        code = canonical_work_code(raw_code)
        current = canonical_states.get(code)
        state_time = state.completed_at or state.started_at or state.queued_at
        current_time = (current.completed_at or current.started_at or current.queued_at) if current else None
        if code and (current is None or (state_time and (current_time is None or state_time > current_time))):
            canonical_states[code] = state
    ranked_by_code: dict[str, tuple[int, float, str, str]] = {}
    for profile in profiles:
        code = canonical_work_code(profile.code)
        if not code:
            continue
        if fresh_until.get(code) and fresh_until[code] > now:
            continue
        state = canonical_states.get(code)
        if state and state.status in {"queued", "running"}:
            continue
        if state and state.status == "failed" and state.completed_at:
            retry_minutes = min(360, 15 * (2 ** min(int(state.attempts or 1) - 1, 5)))
            if state.completed_at + timedelta(minutes=retry_minutes) > now:
                continue
        behavior_strength = float(behavior_codes.get(code) or 0)
        if behavior_strength > 0:
            priority, reason = max(4, 14 - int(min(10, behavior_strength * 2))), "behavior"
        elif _profile_needs_version_intelligence(profile):
            priority, reason = 28, "library_version_gap"
        elif profile.updated_at and profile.updated_at >= now - timedelta(days=14):
            priority, reason = 42, "recent_profile"
        else:
            priority, reason = 65, "coverage"
        recency = profile.updated_at.timestamp() if profile.updated_at else 0.0
        candidate = (priority, -recency, code, reason)
        current = ranked_by_code.get(code)
        if current is None or candidate < current:
            ranked_by_code[code] = candidate
    ranked = list(ranked_by_code.values())
    ranked.sort()
    selected = ranked[:limit]
    accepted = 0
    reason_counts: dict[str, int] = {}
    for priority, _recency, code, reason in selected:
        accepted += await enqueue_resource_refresh([code], priority=priority)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    result = {"planned_at": now.isoformat(), "considered": len(ranked), "selected": len(selected), "accepted": accepted, "reasons": reason_counts}
    _refresh_planner_last = result
    return result


async def _resource_refresh_planner() -> None:
    assert _refresh_planner_stop is not None
    while not _refresh_planner_stop.is_set():
        with contextlib.suppress(Exception):
            await plan_resource_refreshes(limit=12)
        with contextlib.suppress(Exception):
            await build_work_similarity_index()
        try:
            await asyncio.wait_for(_refresh_planner_stop.wait(), timeout=3600)
        except asyncio.TimeoutError:
            pass


async def start_resource_refresh_workers(count: int = 3) -> None:
    global _refresh_planner_task, _refresh_planner_stop
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
    if not _refresh_planner_task or _refresh_planner_task.done():
        _refresh_planner_stop = asyncio.Event()
        _refresh_planner_task = asyncio.create_task(_resource_refresh_planner())


async def stop_resource_refresh_workers() -> None:
    global _refresh_planner_task, _refresh_planner_stop
    if _refresh_planner_stop:
        _refresh_planner_stop.set()
    if _refresh_planner_task:
        _refresh_planner_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _refresh_planner_task
    _refresh_planner_task = None
    _refresh_planner_stop = None
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
    return {"counts": counts, "queue_size": _refresh_queue.qsize(), "planner": dict(_refresh_planner_last), "items": [{"code": row.work_code, "status": row.status, "priority": row.priority, "attempts": row.attempts, "error": row.error, "updated_at": row.updated_at.isoformat()} for row in rows]}


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
        "profile": None if profile is None else {"title": profile.title, "original_title": profile.original_title, "translated_title": profile.translated_title, "aliases": profile.aliases or [], "tokens": profile.tokens or {}, "facts": profile.facts or {}, "source_evidence": profile.source_evidence or [], "confidence": profile.confidence, "updated_at": profile.updated_at.isoformat(), "fused": fused_work_profile(profile)},
        "resources": {"groups": groups, "total": len(resources), "has_cracked": any(item.get("is_cracked") for item in features), "has_subtitle": any(item.get("has_subtitle") for item in features), "has_uncensored": any(item.get("is_uncensored") for item in features), "provider_checks": [{"provider": row.provider_id, "provider_label": row.provider_label, "status": row.status, "count": int((row.payload or {}).get("count") or 0), "error": str((row.payload or {}).get("error") or ""), "checked_at": row.last_seen_at.isoformat(), "expires_at": row.expires_at.isoformat()} for row in checks]},
    }


def _search_terms(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not text:
        return []
    parts = [part for part in re.split(r"[\s,，、/|]+", text) if part]
    return list(dict.fromkeys(parts))[:12]


def _prepare_work_search_documents(profiles: list[WorkProfile], observations: list[ResourceObservation]) -> list[dict[str, Any]]:
    resources_by_code: dict[str, list[ResourceObservation]] = defaultdict(list)
    for observation in observations:
        resources_by_code[canonical_work_code(observation.work_code)].append(observation)
    documents_by_code: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        code = canonical_work_code(profile.code)
        if not code:
            continue
        fused = fused_work_profile(profile)
        actors = list(fused.get("actors") or [])
        searchable_values = [
            code, fused.get("title"), profile.original_title, profile.translated_title,
            *(profile.aliases or []), *actors, *(fused.get("categories") or []),
            fused.get("maker"), fused.get("series"), fused.get("director"),
        ]
        resource_rows = resources_by_code.get(code, [])
        resource_features = [_features(row.payload or row.features or {}) for row in resource_rows]
        document = {
            "code": code,
            "fused": fused,
            "identity_labels": {actor_identity_key(actor): actor for actor in actors if actor_identity_key(actor)},
            "normalized_document": _normalize_actor_name(" ".join(str(value or "") for value in searchable_values)),
            "semantic": (profile.tokens.get("weighted") or {}) if isinstance(profile.tokens, dict) else {},
            "resource_features": resource_features,
            "resource_summary": {
                "total": len(resource_rows),
                "providers": sorted({row.provider_id for row in resource_rows}),
                "has_cracked": any(item.get("is_cracked") for item in resource_features),
                "has_subtitle": any(item.get("has_subtitle") for item in resource_features),
            },
        }
        completeness = fused.get("completeness") or {}
        rank = (sum(bool(completeness.get(key)) for key in ("title", "cover", "actors", "categories")), int(profile.confidence or 0))
        previous = documents_by_code.get(code)
        if previous is None or rank > previous["profile_rank"]:
            document["profile_rank"] = rank
            documents_by_code[code] = document
    return list(documents_by_code.values())


async def search_work_intelligence(query: str, *, limit: int = 30) -> dict[str, Any]:
    """Search canonical work portraits across identity, semantics and resource facts."""
    started = time.perf_counter()
    terms = _search_terms(query)
    canonical_query = canonical_work_code(query)
    if not terms and not canonical_query:
        return {"query": str(query or ""), "items": [], "total": 0, "took_ms": 0}
    now_monotonic = time.monotonic()
    if now_monotonic >= float(_work_search_cache.get("expires_at") or 0):
        async with _work_search_lock:
            if now_monotonic >= float(_work_search_cache.get("expires_at") or 0):
                async with async_session_maker() as db:
                    profiles = list((await db.execute(select(WorkProfile))).scalars())
                    observations = list((await db.execute(
                        select(ResourceObservation).where(ResourceObservation.available.is_(True), ResourceObservation.resource_key != "__provider_check__")
                    )).scalars())
                _work_search_cache.update({"expires_at": time.monotonic() + 120, "documents": _prepare_work_search_documents(profiles, observations)})
    documents = list(_work_search_cache.get("documents") or [])

    rows_by_code: dict[str, dict[str, Any]] = {}
    for document in documents:
        fused = document["fused"]
        code = document["code"]
        identity_labels = document["identity_labels"]
        resource_features = document["resource_features"]
        normalized_document = document["normalized_document"]
        semantic = document["semantic"] if isinstance(document["semantic"], dict) else {}
        matched_terms: list[dict[str, Any]] = []
        score = 0.0
        if canonical_query and code == canonical_query:
            score += 120
            matched_terms.append({"term": canonical_query, "kind": "code", "label": code, "weight": 120})
        for term in terms:
            if canonical_query and canonical_work_code(term) == code:
                continue
            normalized = _normalize_actor_name(term)
            term_identity = actor_identity_key(term)
            evidence: dict[str, Any] | None = None
            if term_identity in identity_labels:
                evidence = {"term": term, "kind": "actor", "label": identity_labels[term_identity], "identity": term_identity, "weight": 42}
            elif normalized in {"破解", "cracked", "uncensored", "流出"} and any(item.get("is_cracked") or item.get("is_uncensored") for item in resource_features):
                evidence = {"term": term, "kind": "resource", "label": "破解资源", "weight": 24}
            elif normalized in {"中文", "中字", "字幕", "chinese", "sub"} and any(item.get("has_subtitle") for item in resource_features):
                evidence = {"term": term, "kind": "resource", "label": "中文字幕", "weight": 22}
            elif normalized and normalized in normalized_document:
                evidence = {"term": term, "kind": "metadata", "label": term, "weight": 18}
            else:
                semantic_hits = [name for name in semantic if normalized and normalized in _normalize_actor_name(name)]
                if semantic_hits:
                    evidence = {"term": term, "kind": "semantic", "label": semantic_hits[0], "weight": min(16, 7 + float(semantic.get(semantic_hits[0]) or 0) * 3)}
            if evidence:
                matched_terms.append(evidence)
                score += float(evidence["weight"])
            else:
                score = -1
                break
        if score <= 0:
            continue
        completeness = fused.get("completeness") or {}
        portrait_quality = sum(bool(completeness.get(key)) for key in ("title", "cover", "actors", "categories")) / 4
        score += portrait_quality * 5 + min(5, int(document["resource_summary"]["total"]) * 0.5) + int(fused.get("confidence") or 0) / 25
        result_row = {
            **fused,
            "code": code,
            "match_score": round(score, 2),
            "match_evidence": matched_terms,
            "resource_summary": document["resource_summary"],
        }
        previous = rows_by_code.get(code)
        if previous is None or (float(result_row["match_score"]), int(result_row.get("confidence") or 0)) > (float(previous["match_score"]), int(previous.get("confidence") or 0)):
            rows_by_code[code] = result_row
    rows = list(rows_by_code.values())
    rows.sort(key=lambda row: (-float(row.get("match_score") or 0), -int(row.get("confidence") or 0), str(row.get("code") or "")))
    return {
        "query": str(query or ""),
        "items": rows[:max(1, min(int(limit), 100))],
        "total": len(rows),
        "took_ms": round((time.perf_counter() - started) * 1000, 2),
        "match_mode": "all_terms",
    }
