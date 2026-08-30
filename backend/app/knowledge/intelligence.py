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
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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
_actor_alias_cache: tuple[str, frozenset[str], dict[str, str], dict[str, str]] | None = None
_actor_mention_cache: tuple[str, dict[str, list[tuple[str, str, str, str]]]] | None = None
_similarity_cache: tuple[str, dict[str, Any]] | None = None
_similarity_rebuild_task: asyncio.Task[dict[str, Any]] | None = None
_similarity_pending_revision = ""
_similarity_evaluation_cache: dict[str, dict[str, Any]] = {}
_similarity_temporal_cache: dict[str, dict[str, Any]] = {}
_similarity_candidate_cache: dict[str, dict[str, Any]] = {}
_work_search_cache: dict[str, Any] = {"expires_at": 0.0, "documents": []}
_work_search_lock = asyncio.Lock()
_preference_summary_cache: dict[str, Any] = {"expires_at": 0.0, "key": "", "value": None}
_preference_summary_lock = asyncio.Lock()
_search_intent_lock = asyncio.Lock()
_search_actor_terms_cache: tuple[str, list[str]] | None = None
WORK_SIMILARITY_VERSION = 16
WORK_PROFILE_FUSION_VERSION = 1


def _offline_evaluation_cache_file() -> Path:
    return data_path("intelligence_offline_evaluations.json")


def _load_offline_evaluation(kind: str, fingerprint: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(_offline_evaluation_cache_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    row = ((payload.get("entries") or {}).get(kind) or {}).get(fingerprint)
    value = row.get("value") if isinstance(row, dict) else None
    return dict(value) if isinstance(value, dict) else None


def _save_offline_evaluation(kind: str, fingerprint: str, value: dict[str, Any]) -> None:
    path = _offline_evaluation_cache_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"version": 1, "entries": {}}
    entries = payload.setdefault("entries", {}).setdefault(kind, {})
    entries[fingerprint] = {"saved_at": utcnow().isoformat(), "value": value}
    # Retain a few historical revisions for diagnostics without allowing the
    # runtime file to grow indefinitely.
    payload["entries"][kind] = dict(sorted(entries.items(), key=lambda row: str((row[1] or {}).get("saved_at") or ""), reverse=True)[:4])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _relation_policy_file() -> Path:
    return data_path("intelligence_relation_policy.json")


def _stabilize_relation_policy(revision: str, proposed: dict[str, float], *, context_key: str = "default") -> dict[str, Any]:
    """Persist an evaluation-scoped policy and require repeated revisions before replacement."""
    path = _relation_policy_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    policies = payload.get("policies") if int(payload.get("version") or 0) >= 2 and isinstance(payload.get("policies"), dict) else {}
    state = policies.get(context_key) if isinstance(policies.get(context_key), dict) else {}
    stable = {str(key): round(float(value), 3) for key, value in (state.get("stable_weights") or {}).items()}
    proposed = {str(key): round(float(value), 3) for key, value in proposed.items()}
    previous_revision = str(state.get("last_revision") or "")
    status = "stable"
    promoted = False
    if not state:
        stable = dict(proposed)
        candidate: dict[str, float] = {}
        confirmations = 0
        status = "bootstrapped" if stable else "collecting"
        promoted = bool(stable)
    else:
        candidate = {str(key): round(float(value), 3) for key, value in (state.get("candidate_weights") or {}).items()}
        confirmations = int(state.get("confirmations") or 0)
        if revision != previous_revision:
            if proposed == stable:
                candidate, confirmations, status = {}, 0, "stable"
            elif proposed == candidate:
                confirmations += 1
                status = "confirming"
                if confirmations >= 2:
                    stable, candidate, confirmations = dict(proposed), {}, 0
                    status, promoted = "promoted", True
            else:
                candidate, confirmations, status = dict(proposed), 1, "confirming"
        elif proposed != stable:
            status = "confirming"
    policy = {
        "stable_weights": stable,
        "candidate_weights": candidate,
        "confirmations": confirmations,
        "required_confirmations": 2,
        "last_revision": revision,
        "updated_at": utcnow().isoformat(),
        "status": status,
        "promoted": promoted,
        "context_key": context_key,
    }
    policies[context_key] = policy
    policies = dict(sorted(policies.items(), key=lambda row: str((row[1] or {}).get("updated_at") or ""), reverse=True)[:6])
    payload = {"version": 2, "policies": policies}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return policy
SIMILARITY_CATEGORY_STOPWORDS = {
    "单体作品", "精选综合", "高清", "高画质", "有码", "无码", "中文字幕", "字幕", "中文",
    "身体", "本番", "作品", "影片", "电影", "独家", "推荐", "热门", "has_chinese",
    "release_type", "release_type_key", "is_leaked", "is_cracked", "torrent",
    "DMM独家", "ハイビジョン", "高清晰", "高解析度",
    "破解", "中文字幕", "中字", "中文", "4K", "8K", "独占配信", "独家配信", "配信限定",
}
SEMANTIC_PROFILE_VERSION = 10
SEMANTIC_STOPWORDS = {
    "これ", "それ", "この", "その", "ため", "から", "まで", "より", "そして", "また", "作品", "動画",
    "一个", "一种", "这个", "那个", "以及", "然后", "作品", "影片", "电影", "高清", "高画质",
}
SEMANTIC_LATIN_STOPWORDS = {
    "fanza", "dmm", "javdb", "avdb", "video", "movie", "sample", "preview", "sex",
}
SEMANTIC_RELATION_STOPWORDS = {
    "mp4", "mkv", "web-dl", "webdl", "aac2", "mteam", "m-team", "uncensored-hd", "uncensored",
    "removed", "mosaic", "onejav", "com", "best", "premium", "hfr", "c_gg5", "bod", "mgs", "sod", "leak", "leaked",
    "无码破解", "新模型无码破解", "自提征用", "第一會所新片", "第一会所新片", "ダスッ",
}
SEMANTIC_RELATION_STOPWORD_KEYS = {re.sub(r"[\s_.]+", "", value) for value in SEMANTIC_RELATION_STOPWORDS}
PREFERENCE_CATEGORY_ALIASES = {
    "中出し": "中出", "中出": "中出",
    "已婚妇女": "人妻", "人妻": "人妻",
    "ドラマ": "剧情", "戏剧": "剧情", "劇情": "剧情", "剧情": "剧情",
    "強姦": "强制", "强奸": "强制", "強制": "强制",
    "调教": "调教", "調教": "调教",
    "単体作品": "单体作品", "單體作品": "单体作品",
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
SEARCH_INTENT_HALF_LIFE_SECONDS = 3 * 60 * 60
SEARCH_INTENT_MAX_AGE_SECONDS = 12 * 60 * 60
SEARCH_INTENT_EVALUATION_RETENTION_SECONDS = 30 * 24 * 60 * 60
SEARCH_INTENT_CONVERSION_VALUES = {
    "detail_view": 0.25,
    "subscription": 0.70,
    "download_intent": 0.82,
    "download_submitted": 0.90,
    "library_imported": 1.0,
    "upgrade_completed": 1.0,
}
SEARCH_INTENT_OPERATIONAL_TERMS = {
    "破解", "中文", "中字", "字幕", "流出", "无码", "無碼", "有码", "有碼", "pt",
    "avdb", "javdb", "mteam", "m-team", "source", "来源", "資源", "资源", "下载", "下載",
    "4k", "8k", "fhd", "uhd", "1080p", "2160p", "hdr",
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


def canonical_preference_category(value: Any) -> str:
    name = unicodedata.normalize("NFKC", str(value or "")).strip()
    return PREFERENCE_CATEGORY_ALIASES.get(name, name)


def _actor_alias_data() -> tuple[frozenset[str], dict[str, str], dict[str, str]]:
    """Load MDC-NG actor aliases and their preferred NOOR display names."""
    global _actor_alias_cache
    path = data_path("media_actor_mappings.json")
    try:
        revision = actor_alias_revision()
        if _actor_alias_cache and len(_actor_alias_cache) == 4 and _actor_alias_cache[0] == revision:
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
    learned_path = data_path("intelligence_actor_aliases.json")
    with contextlib.suppress(OSError, json.JSONDecodeError):
        learned = json.loads(learned_path.read_text(encoding="utf-8"))
        for record in learned.get("accepted") or []:
            if not isinstance(record, dict) or float(record.get("confidence") or 0) < 0.8:
                continue
            alias = str(record.get("alias") or "").strip()
            preferred = str(record.get("preferred") or alias).strip()
            identity_key = str(record.get("identity") or "").strip()
            normalized = _normalize_actor_name(alias)
            if alias and preferred and identity_key and normalized and normalized not in identity_keys:
                names.add(alias)
                identities[normalized] = preferred
                identity_keys[normalized] = identity_key
    result = frozenset(names)
    _actor_alias_cache = (revision, result, identities, identity_keys)
    return result, identities, identity_keys


def actor_alias_names() -> frozenset[str]:
    """Return all known actor names from the synchronized MDC-NG mapping."""
    return _actor_alias_data()[0]


def actor_alias_revision() -> str:
    """Cheap cache revision that changes whenever the synchronized mapping changes."""
    revisions = []
    for name in ("media_actor_mappings.json", "intelligence_actor_aliases.json"):
        path = data_path(name)
        try:
            stat = path.stat()
            revisions.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
        except OSError:
            revisions.append(f"{name}:missing")
    return "|".join(revisions)


def actor_alias_stats() -> dict[str, int | str]:
    names, _labels, identity_keys = _actor_alias_data()
    learned = {"accepted": [], "candidates": []}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        learned = json.loads(data_path("intelligence_actor_aliases.json").read_text(encoding="utf-8"))
    return {
        "identity_count": len(set(identity_keys.values())),
        "alias_count": len(names),
        "learned_alias_count": len(learned.get("accepted") or []),
        "alias_candidate_count": len(learned.get("candidates") or []),
        "revision": actor_alias_revision(),
    }


def _base_actor_alias_index() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Read only the MDC-NG source, excluding aliases previously learned by Core."""
    try:
        payload = json.loads(data_path("media_actor_mappings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    index: dict[str, dict[str, str]] = {}
    labels: dict[str, str] = {}
    for record in payload.get("records") or []:
        if not isinstance(record, dict):
            continue
        values = [record.get("jp"), record.get("zh_cn"), record.get("zh_tw"), *(record.get("names") or []), *(record.get("aliases") or [])]
        values = [str(value).strip() for value in values if str(value or "").strip()]
        preferred = str(record.get("zh_cn") or record.get("jp") or record.get("zh_tw") or (values[0] if values else "")).strip()
        record_id = str(record.get("id") or "").strip()
        identity = f"mdc-ng:{record_id}" if record_id else f"name:{_normalize_actor_name(preferred)}"
        labels.setdefault(identity, preferred)
        for value in values:
            normalized = _normalize_actor_name(value)
            if normalized:
                index.setdefault(normalized, {"identity": identity, "preferred": preferred, "name": value})
    return index, labels


def _actor_variant_similarity(left: str, right: str) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a == b for a, b in zip(left, right)) / len(left)


def infer_actor_aliases(profiles: list[WorkProfile], *, minimum_works: int = 2) -> dict[str, Any]:
    """Learn conservative title aliases for unambiguous MDC-NG actor identities."""
    global _actor_alias_cache, _actor_mention_cache
    base_index, identity_labels = _base_actor_alias_index()
    votes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    display_values: dict[str, str] = {}
    similarities: dict[tuple[str, str], float] = {}
    for profile in profiles:
        code = canonical_work_code(profile.code)
        mapped: dict[str, str] = {}
        for facts in (profile.facts or {}).values():
            if not isinstance(facts, dict):
                continue
            for actor in facts.get("actors") or facts.get("actresses") or []:
                name = str(actor.get("name") if isinstance(actor, dict) else actor or "").strip()
                row = base_index.get(_normalize_actor_name(name))
                if row:
                    mapped[row["identity"]] = row["preferred"]
        # Multiple mapped performers make a title-level alias assignment
        # ambiguous; those cases remain candidates for future explicit review.
        if len(mapped) != 1:
            continue
        identity, preferred = next(iter(mapped.items()))
        normalized_preferred = _normalize_actor_name(preferred)
        length = len(normalized_preferred)
        if length < 3 or length > 8:
            continue
        texts = [profile.title, profile.original_title, profile.translated_title, *(profile.aliases or [])]
        for text in texts:
            for run in re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{3,80}", unicodedata.normalize("NFKC", str(text or ""))):
                # Actor credits in scraped titles are normally a standalone
                # token or the final token. Scanning every interior n-gram
                # creates convincing-looking truncated names, so only these
                # two boundary-safe shapes are eligible for auto-learning.
                aliases = [run] if len(run) == length else [run[-length:]] if len(run) > length else []
                for alias in aliases:
                    normalized_alias = _normalize_actor_name(alias)
                    if normalized_alias == normalized_preferred or normalized_alias in base_index:
                        continue
                    similarity = _actor_variant_similarity(normalized_alias, normalized_preferred)
                    if similarity < 0.5:
                        continue
                    votes[normalized_alias][identity].add(code)
                    display_values.setdefault(normalized_alias, alias)
                    similarities[(normalized_alias, identity)] = max(similarities.get((normalized_alias, identity), 0), similarity)
    accepted: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for alias, targets in votes.items():
        ranked = sorted(targets.items(), key=lambda row: (len(row[1]), row[0]), reverse=True)
        identity, works = ranked[0]
        competing_works = set().union(*(codes for _target, codes in ranked[1:])) if len(ranked) > 1 else set()
        dominance = len(works) / max(1, len(works | competing_works))
        similarity = similarities.get((alias, identity), 0.0)
        row = {
            "alias": display_values.get(alias, alias),
            "identity": identity,
            "preferred": identity_labels.get(identity, display_values.get(alias, alias)),
            "work_count": len(works),
            "works": sorted(works)[:12],
            "dominance": round(dominance, 3),
            "similarity": round(similarity, 3),
            "confidence": round(min(0.99, 0.78 + min(0.12, len(works) * 0.025) + similarity * 0.1), 3),
            "status": "accepted" if len(works) >= minimum_works and dominance >= 0.9 else "candidate",
        }
        (accepted if row["status"] == "accepted" else candidates).append(row)
    accepted.sort(key=lambda row: (-row["work_count"], -row["confidence"], row["alias"]))
    candidates.sort(key=lambda row: (-row["work_count"], -row["dominance"], row["alias"]))
    core = {"version": 1, "accepted": accepted[:2000], "candidates": candidates[:2000]}
    path = data_path("intelligence_actor_aliases.json")
    existing_core = None
    with contextlib.suppress(OSError, json.JSONDecodeError):
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_core = {"version": existing.get("version"), "accepted": existing.get("accepted") or [], "candidates": existing.get("candidates") or []}
    if existing_core != core:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**core, "generated_at": utcnow().isoformat(), "profile_count": len(profiles)}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        _actor_alias_cache = None
        _actor_mention_cache = None
        _invalidate_work_search_cache(delay_seconds=0)
    return {"accepted": len(accepted), "candidates": len(candidates), "changed": existing_core != core, "revision": actor_alias_revision()}


async def build_actor_alias_inference(*, minimum_works: int = 2) -> dict[str, Any]:
    async with async_session_maker() as db:
        profiles = list((await db.execute(select(WorkProfile))).scalars())
    return infer_actor_aliases(profiles, minimum_works=minimum_works)


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


def canonical_actor_entity(value: Any) -> dict[str, str]:
    """Describe the canonical graph identity for an actor name.

    The mapping id is deliberately used as the entity key.  This lets Emby,
    MDC-NG and resource plugins converge on one graph node even when each
    source publishes a different script or alias for the same performer.
    """
    original = str(value or "").strip()
    identity = actor_identity_key(original)
    if not identity:
        return {"key": "", "label": "", "identity": "", "alias": ""}
    return {
        "key": identity,
        "label": canonical_actor_name(original),
        "identity": identity,
        "alias": original,
    }


def actor_mentions(value: Any, *, limit: int = 4) -> list[dict[str, str]]:
    """Resolve conservative actor mentions in an unstructured title.

    MDC-NG contains short aliases that are also ordinary title words. Only
    aliases with at least three normalized characters participate, and the
    longest spelling for each stable identity wins.
    """
    global _actor_mention_cache
    normalized_text = _normalize_actor_name(value)
    if len(normalized_text) < 3 or limit <= 0:
        return []
    revision = actor_alias_revision()
    if not _actor_mention_cache or _actor_mention_cache[0] != revision:
        try:
            payload = json.loads(data_path("media_actor_mappings.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {"records": []}
        aliases: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for record in payload.get("records") or []:
            if not isinstance(record, dict):
                continue
            primary_values = [record.get("jp"), record.get("zh_cn"), record.get("zh_tw"), *(record.get("names") or [])]
            weak_values = list(record.get("aliases") or [])
            all_values = [str(item).strip() for item in [*primary_values, *weak_values] if str(item or "").strip()]
            preferred = str(record.get("zh_cn") or record.get("jp") or record.get("zh_tw") or (all_values[0] if all_values else "")).strip()
            record_id = str(record.get("id") or "").strip()
            identity = f"mdc-ng:{record_id}" if record_id else f"name:{_normalize_actor_name(preferred)}"
            primary_keys = {_normalize_actor_name(item) for item in primary_values if str(item or "").strip()}
            for alias in all_values:
                normalized = _normalize_actor_name(alias)
                kind = "primary" if normalized in primary_keys else "alias"
                # Short stage names are often ordinary words inside Japanese
                # titles. They remain valid for explicit structured fields but
                # are unsafe for substring inference.
                if len(normalized) < 3 or (kind == "alias" and len(normalized) < 4):
                    continue
                aliases[normalized].append((identity, preferred or alias, kind))
        buckets: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
        for normalized, rows in aliases.items():
            identities = {row[0] for row in rows}
            # An alias shared by multiple MDC-NG identities cannot safely
            # identify one performer from title text alone.
            if len(identities) != 1:
                continue
            identity, label, kind = rows[0]
            buckets[normalized[0]].append((normalized, identity, label, kind))
        for rows in buckets.values():
            rows.sort(key=lambda row: len(row[0]), reverse=True)
        _actor_mention_cache = (revision, buckets)
    matches: list[tuple[int, int, int, str, str, str, str]] = []
    seen_aliases: set[tuple[str, str]] = set()
    for initial in set(normalized_text):
        for alias, identity, label, kind in _actor_mention_cache[1].get(initial, []):
            if alias in normalized_text and (identity, alias) not in seen_aliases:
                start = normalized_text.find(alias)
                matches.append((len(alias), start, start + len(alias), identity, label, alias, kind))
                seen_aliases.add((identity, alias))
    result: list[dict[str, str]] = []
    seen_identities: set[str] = set()
    occupied: list[tuple[int, int]] = []
    for _length, start, end, identity, label, alias, kind in sorted(matches, key=lambda row: (-row[0], row[1], row[3])):
        if identity in seen_identities:
            continue
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        seen_identities.add(identity)
        occupied.append((start, end))
        result.append({"name": label, "identity": identity, "alias": alias, "source": "mdc-ng-title", "match_kind": kind})
        if len(result) >= limit:
            break
    return result


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
    created = False
    async with async_session_maker() as db:
        evidence_id = str((data or {}).get("evidence_id") or "").strip()
        event_id = stable_id("preference-event", source, kind, evidence_id) if evidence_id else stable_id("preference-event", canonical, kind, source, now.isoformat())
        duplicate_evidence = bool(evidence_id and await db.get(PreferenceEvent, event_id))
        latest = (await db.execute(
            select(PreferenceEvent)
            .where(PreferenceEvent.work_code == canonical, PreferenceEvent.event_type == kind, PreferenceEvent.source == source)
            .order_by(PreferenceEvent.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        in_cooldown = bool(latest and latest.created_at >= now - cooldown)
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
        category_names = list(dict.fromkeys(canonical_preference_category(evidence_name(value)) for value in (categories or []) if evidence_name(value)))[:20]
        if not duplicate_evidence and not in_cooldown:
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
            created = True
    if created:
        _preference_summary_cache["expires_at"] = 0.0
    await attribute_search_intent_conversion(
        canonical,
        kind,
        actors=actor_names,
        categories=category_names,
        title=str(profile.title or "") if profile else "",
    )
    refresh_priority = {"subscription": 5, "download_intent": 8, "detail_view": 24}.get(kind)
    if created and enqueue_refresh and refresh_priority is not None:
        await enqueue_resource_refresh([canonical], priority=refresh_priority)
    return created


async def preference_behavior_summary(*, max_age_days: int = 365) -> dict[str, Any]:
    cache_key = f"{id(async_session_maker)}:{max_age_days}:{actor_alias_revision()}"
    if time.monotonic() < float(_preference_summary_cache.get("expires_at") or 0) and _preference_summary_cache.get("key") == cache_key:
        cached = _preference_summary_cache.get("value")
        if isinstance(cached, dict):
            return cached
    async with _preference_summary_lock:
        if time.monotonic() < float(_preference_summary_cache.get("expires_at") or 0) and _preference_summary_cache.get("key") == cache_key:
            cached = _preference_summary_cache.get("value")
            if isinstance(cached, dict):
                return cached
        result = await _preference_behavior_summary_uncached(max_age_days=max_age_days)
        # Preference events invalidate this snapshot synchronously, so a
        # one-minute read TTL only shields SQLite from background maintenance;
        # it does not delay user feedback becoming effective.
        _preference_summary_cache.update({"expires_at": time.monotonic() + 60, "key": cache_key, "value": result})
        return result


async def _preference_behavior_summary_uncached(*, max_age_days: int = 365) -> dict[str, Any]:
    now = utcnow()
    cutoff = now - timedelta(days=max_age_days)
    try:
        async with async_session_maker() as db:
            events = list((await db.execute(select(PreferenceEvent).where(PreferenceEvent.created_at >= cutoff))).scalars())
            profiles = list((await db.execute(select(WorkProfile))).scalars())
    except SQLAlchemyError:
        return {"codes": {}, "actors": {}, "actor_identities": {}, "categories": {}, "code_stages": {}, "event_count": 0, "revision": "0:none"}
    profile_evidence = {canonical_work_code(profile.code): _profile_preference_evidence(profile) for profile in profiles}
    enriched_events: list[PreferenceEvent] = []
    for event in events:
        evidence = profile_evidence.get(canonical_work_code(event.work_code)) or {}
        if (event.actors or []) and (event.categories or []):
            enriched_events.append(event)
            continue
        enriched = SimpleNamespace(
            work_code=event.work_code,
            event_type=event.event_type,
            source=event.source,
            weight=event.weight,
            actors=list(event.actors or evidence.get("actors") or []),
            categories=list(event.categories or evidence.get("categories") or []),
            created_at=event.created_at,
        )
        enriched_events.append(enriched)
    events = enriched_events
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
            name = canonical_preference_category(category)
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
        "interest_topics": _preference_interest_topics(events, profiles=profiles),
        "revision": f"{len(events)}:{latest.isoformat() if latest else 'none'}",
    }


def _profile_preference_evidence(profile: WorkProfile) -> dict[str, list[str]]:
    """Backfill old behavior events from the best currently known portrait."""
    facts = profile.facts if isinstance(profile.facts, dict) else {}

    def names(values: Any, *, reject_male: bool = False) -> list[str]:
        out: list[str] = []
        for value in values if isinstance(values, list) else []:
            if isinstance(value, dict):
                if reject_male and str(value.get("gender") or "").strip().casefold() in {"♂", "male", "m", "男"}:
                    continue
                text = str(value.get("name") or value.get("label") or "").strip()
            else:
                text = str(value or "").strip()
            if text and text not in out:
                out.append(text)
        return out

    library = facts.get("media-library") if isinstance(facts.get("media-library"), dict) else {}
    actors = names(library.get("actors") or library.get("actresses") or [])
    if not actors:
        for source in facts.values():
            if isinstance(source, dict):
                actors.extend(name for name in names(source.get("actors") or source.get("actresses") or [], reject_male=True) if name not in actors)
    categories: list[str] = []
    # Structured provider categories are less polluted by maker names and
    # operational tags than a media-library genre list.
    provider_sources = [source for key, source in facts.items() if key != "media-library" and isinstance(source, dict)]
    category_sources = provider_sources if any(names(source.get("categories") or source.get("genres") or []) for source in provider_sources) else [library]
    category_stopwords = {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}
    for source in category_sources:
        if not isinstance(source, dict):
            continue
        for name in names(source.get("categories") or source.get("genres") or []):
            canonical = canonical_preference_category(name)
            if canonical.casefold() not in category_stopwords and canonical not in categories:
                categories.append(canonical)
    return {"actors": actors[:12], "categories": categories[:24]}


def _bayesian_rate(successes: int, trials: int) -> float:
    return (max(0, successes) + 2) / (max(0, trials) + 4)


def _preference_interest_topics(events: list[PreferenceEvent], *, profiles: list[WorkProfile] | None = None, max_topics: int = 8) -> dict[str, Any]:
    """Build explainable actor/category topic mixtures from staged behavior."""
    now = utcnow()
    by_code: dict[str, dict[str, Any]] = {}
    actor_labels: dict[str, str] = {}
    category_stopwords = {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}
    library_codes: set[str] = set()
    for profile in profiles or []:
        facts = profile.facts if isinstance(profile.facts, dict) else {}
        library = facts.get("media-library") if isinstance(facts.get("media-library"), dict) else None
        if not library or not bool(library.get("in_library", True)):
            continue
        code = canonical_work_code(profile.code)
        evidence = _profile_preference_evidence(profile)
        if not code or not evidence.get("categories"):
            continue
        library_codes.add(code)
        row = by_code.setdefault(code, {"weight": 0.0, "recent_weight": 0.0, "actors": set(), "categories": set()})
        # Library presence is durable positive evidence, but one explicit
        # verified outcome remains stronger than the passive baseline.
        row["weight"] = max(float(row["weight"]), 0.75 * max(0.5, min(1.0, float(profile.confidence or 80) / 100)))
        for actor in evidence.get("actors") or []:
            identity = actor_identity_key(actor)
            if identity:
                row["actors"].add(identity)
                actor_labels.setdefault(identity, canonical_actor_name(actor))
        row["categories"].update(canonical_preference_category(category) for category in evidence.get("categories") or [] if canonical_preference_category(category).casefold() not in category_stopwords)
    for event in events:
        code = canonical_work_code(event.work_code)
        if not code:
            continue
        age_days = max(0.0, (now - event.created_at).total_seconds() / 86400)
        half_life = PREFERENCE_EVENT_HALF_LIFE_DAYS.get(event.event_type, 30)
        effective = float(event.weight or 0) * math.pow(0.5, age_days / half_life)
        row = by_code.setdefault(code, {"weight": 0.0, "recent_weight": 0.0, "actors": set(), "categories": set()})
        # One work is one preference observation. A later funnel stage may
        # strengthen it, but detail -> download -> import must not count as
        # three independent examples of the same taste.
        row["weight"] = max(float(row["weight"]), effective)
        if age_days <= 30:
            row["recent_weight"] = max(float(row["recent_weight"]), effective)
        for actor in event.actors or []:
            identity = actor_identity_key(actor)
            if identity:
                row["actors"].add(identity)
                actor_labels.setdefault(identity, canonical_actor_name(actor))
        row["categories"].update(
            canonical_preference_category(category) for category in (event.categories or [])
            if canonical_preference_category(category) and canonical_preference_category(category).casefold() not in category_stopwords
        )
    category_weights: dict[str, float] = defaultdict(float)
    category_recent: dict[str, float] = defaultdict(float)
    category_recent_codes: dict[str, set[str]] = defaultdict(set)
    category_codes: dict[str, set[str]] = defaultdict(set)
    actor_category: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    category_pairs: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for code, row in by_code.items():
        weight = float(row["weight"])
        recent_weight = float(row["recent_weight"])
        categories = sorted(row["categories"])
        actors = sorted(row["actors"])
        for category in categories:
            category_weights[category] += weight
            category_recent[category] += recent_weight
            if recent_weight > 0:
                category_recent_codes[category].add(code)
            category_codes[category].add(code)
            for actor in actors:
                actor_category[category][actor] += weight
            for related in categories:
                if related != category:
                    category_pairs[category][related] += weight
    total_weight = sum(category_weights.values()) or 1.0
    recent_total = sum(category_recent.values()) or 1.0
    candidates: list[dict[str, Any]] = []
    for anchor, weight in category_weights.items():
        support = len(category_codes[anchor])
        if support < 1 or weight <= 0:
            continue
        related = sorted(category_pairs[anchor].items(), key=lambda row: row[1], reverse=True)[:4]
        actors = sorted(actor_category[anchor].items(), key=lambda row: row[1], reverse=True)[:4]
        share = weight / total_weight
        raw_recent_share = category_recent.get(anchor, 0.0) / recent_total
        recent_support = len(category_recent_codes[anchor])
        recent_reliability = recent_support / (recent_support + 4)
        recent_share = share + (raw_recent_share - share) * recent_reliability
        actor_coverage = (float(actors[0][1]) / weight) if actors and weight > 0 else 0.0
        category_coverage = (float(related[0][1]) / weight) if related and weight > 0 else 0.0
        actor_rows = [{"identity": identity, "name": actor_labels.get(identity, identity), "weight": round(score, 3)} for identity, score in actors]
        if actor_rows and actor_coverage >= 0.25:
            topic_label = f"{actor_rows[0]['name']} · {anchor}"
        elif related and category_coverage >= 0.25:
            topic_label = f"{anchor} · {related[0][0]}"
        else:
            topic_label = anchor
        candidates.append({
            "id": stable_id("preference-topic", anchor)[:16],
            "label": topic_label,
            "anchor": anchor,
            "categories": [anchor, *[name for name, _score in related]],
            "actors": actor_rows,
            "support": support,
            "strength": round(share, 4),
            "recent_strength": round(recent_share, 4),
            "momentum": round(recent_share - share, 4),
            "recent_support": recent_support,
            "recent_reliability": round(recent_reliability, 3),
            "actor_coverage": round(actor_coverage, 3),
            "category_coverage": round(category_coverage, 3),
            "confidence": round(min(0.95, support / (support + 4)), 3),
            "evidence_codes": sorted(category_codes[anchor])[:8],
        })
    candidates.sort(key=lambda row: (float(row["strength"]) + max(0.0, float(row["momentum"])) * 0.7) * float(row["confidence"]), reverse=True)
    selected: list[dict[str, Any]] = []
    for topic in candidates:
        category_set = set(topic["categories"][:3])
        evidence_set = set(topic["evidence_codes"])
        if any(
            len(category_set & set(existing["categories"][:3])) / max(1, len(category_set | set(existing["categories"][:3]))) >= 0.8
            or (
                len(evidence_set & set(existing["evidence_codes"])) / max(1, len(evidence_set | set(existing["evidence_codes"]))) >= 0.8
                and len(category_set & set(existing["categories"][:3])) >= 2
            )
            for existing in selected
        ):
            continue
        selected.append(topic)
        if len(selected) >= max_topics:
            break
    revision_payload = json.dumps({"version": 2, "topics": selected, "library_work_count": len(library_codes)}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"version": 2, "revision": hashlib.sha256(revision_payload.encode("utf-8")).hexdigest()[:20], "topics": selected, "work_count": len(by_code), "library_work_count": len(library_codes), "behavior_work_count": len({canonical_work_code(event.work_code) for event in events if canonical_work_code(event.work_code)}), "generated_at": now.isoformat()}


def _preference_outcome_model(events: list[PreferenceEvent]) -> dict[str, Any]:
    """Build a conservative conversion model from intent to verified outcomes."""
    by_code: dict[str, dict[str, Any]] = {}
    for event in events:
        row = by_code.setdefault(event.work_code, {"attempt": False, "verified": False, "actors": set(), "categories": set()})
        row["attempt"] = bool(row["attempt"] or event.event_type in OUTCOME_ATTEMPT_EVENTS)
        row["verified"] = bool(row["verified"] or event.event_type in OUTCOME_VERIFIED_EVENTS)
        row["actors"].update(actor_identity_key(actor) for actor in (event.actors or []) if actor_identity_key(actor))
        row["categories"].update(canonical_preference_category(category) for category in (event.categories or []) if canonical_preference_category(category))
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
    """Build support-shrunk 14/90/365-day taste momentum by unique work."""
    now = utcnow()
    scale_specs = {
        "current": {"half_life": 14.0, "max_age": 60.0},
        "medium": {"half_life": 90.0, "max_age": 365.0},
        "durable": {"half_life": 365.0, "max_age": 1095.0},
    }
    actor_labels: dict[str, str] = {}
    by_work: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        age_days = max(0.0, (now - event.created_at).total_seconds() / 86400)
        if age_days > scale_specs["durable"]["max_age"]:
            continue
        code = canonical_work_code(getattr(event, "work_code", "")) or f"event:{index}"
        row = by_work.setdefault(code, {"actors": set(), "categories": set(), "weights": {}})
        for actor in event.actors or []:
            identity = actor_identity_key(actor)
            if identity:
                row["actors"].add(identity)
                actor_labels.setdefault(identity, canonical_actor_name(actor))
        for category in event.categories or []:
            name = canonical_preference_category(category)
            if name:
                row["categories"].add(name)
        for scale, spec in scale_specs.items():
            if age_days <= spec["max_age"]:
                effective = float(event.weight or 0) * math.pow(0.5, age_days / spec["half_life"])
                row["weights"][scale] = max(float(row["weights"].get(scale) or 0), effective)

    aggregates: dict[str, dict[str, dict[str, float]]] = {
        scale: {"actors": defaultdict(float), "categories": defaultdict(float)} for scale in scale_specs
    }
    supports: dict[str, dict[str, dict[str, set[str]]]] = {
        scale: {"actors": defaultdict(set), "categories": defaultdict(set)} for scale in scale_specs
    }
    scale_work_counts = {scale: 0 for scale in scale_specs}
    for code, row in by_work.items():
        for scale, weight in row["weights"].items():
            if weight <= 0:
                continue
            scale_work_counts[scale] += 1
            for dimension_name in ("actors", "categories"):
                for value in row[dimension_name]:
                    aggregates[scale][dimension_name][value] += weight
                    supports[scale][dimension_name][value].add(code)

    def dimension(name: str) -> dict[str, Any]:
        totals = {scale: sum(aggregates[scale][name].values()) or 1.0 for scale in scale_specs}
        deltas: dict[str, float] = {}
        rows: list[dict[str, Any]] = []
        keys = set().union(*(set(aggregates[scale][name]) for scale in scale_specs))
        for key in keys:
            shares = {scale: aggregates[scale][name].get(key, 0.0) / totals[scale] for scale in scale_specs}
            support = len(supports["current"][name].get(key, set()) | supports["medium"][name].get(key, set()))
            global_reliability = scale_work_counts["current"] / (scale_work_counts["current"] + 12)
            reliability = support / (support + 4) * global_reliability
            raw_delta = (shares["current"] - shares["durable"]) * 0.7 + (shares["medium"] - shares["durable"]) * 0.3
            delta = raw_delta * reliability
            deltas[key] = round(delta, 6)
            rows.append({
                "name": actor_labels.get(key, key),
                "identity": key if name == "actors" else "",
                "share": round(shares["current"], 4),
                "previous_share": round(shares["durable"], 4),
                "medium_share": round(shares["medium"], 4),
                "delta": round(delta, 4),
                "support": support,
                "reliability": round(reliability, 3),
            })
        return {
            "deltas": deltas,
            "rising": sorted((row for row in rows if row["delta"] > 0 and row["share"] > 0), key=lambda row: (row["delta"], row["share"]), reverse=True)[:8],
            "fading": sorted((row for row in rows if row["delta"] < 0 and row["previous_share"] > 0), key=lambda row: row["delta"])[:8],
        }

    return {
        "version": 2,
        "window_days": window_days,
        "recent_events": scale_work_counts["current"],
        "prior_events": max(0, scale_work_counts["medium"] - scale_work_counts["current"]),
        "scales": {
            scale: {"work_count": scale_work_counts[scale], **spec}
            for scale, spec in scale_specs.items()
        },
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
    _preference_summary_cache["expires_at"] = 0.0
    return int(result.rowcount or 0)


def _search_intent_file():
    return data_path("intelligence_search_intents.json")


def _load_search_intents() -> dict[str, Any]:
    path = _search_intent_file()
    if not path.exists():
        return {"version": 1, "events": []}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data
    return {"version": 1, "events": []}


def _save_search_intents(data: dict[str, Any]) -> None:
    path = _search_intent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _search_actor_alias_terms() -> list[str]:
    global _search_actor_terms_cache
    revision = actor_alias_revision()
    if _search_actor_terms_cache and _search_actor_terms_cache[0] == revision:
        return _search_actor_terms_cache[1]
    terms = sorted((name for name in actor_alias_names() if len(_normalize_actor_name(name)) >= 2), key=lambda name: len(_normalize_actor_name(name)), reverse=True)
    _search_actor_terms_cache = (revision, terms)
    return terms


def _search_event_conversion_value(event: dict[str, Any]) -> float:
    return max((float(row.get("value") or 0) for row in (event.get("conversions") or {}).values() if isinstance(row, dict)), default=0.0)


def _aware_search_time(value: datetime | None = None) -> datetime:
    current = value or utcnow()
    return current if current.tzinfo is not None else current.replace(tzinfo=timezone.utc)


def _search_event_signals(event: dict[str, Any]) -> list[tuple[str, str, str]]:
    signals: list[tuple[str, str, str]] = []
    signals.extend((f"actor:{row['identity']}", "actor", str(row.get("label") or row["identity"])) for row in event.get("actors") or [] if isinstance(row, dict) and row.get("identity"))
    signals.extend((f"category:{name}", "category", str(name)) for name in event.get("categories") or [] if name)
    signals.extend((f"term:{name}", "term", str(name)) for name in event.get("terms") or [] if name)
    return list(dict.fromkeys(signals))


def _search_signal_combinations(signals: list[tuple[str, str, str]]) -> list[tuple[str, str, str, tuple[str, str]]]:
    pairs: list[tuple[str, str, str, tuple[str, str]]] = []
    for left, right in itertools.combinations(signals, 2):
        if left[1] == right[1]:
            continue
        ordered = sorted((left, right), key=lambda row: (row[1], row[0]))
        keys = (ordered[0][0], ordered[1][0])
        pairs.append((f"combo:{keys[0]}|{keys[1]}", "combination", f"{ordered[0][2]} × {ordered[1][2]}", keys))
    return pairs[:12]


def _search_signal_metrics(events: list[dict[str, Any]], current: datetime) -> dict[str, Any]:
    current = _aware_search_time(current)
    metrics: dict[str, dict[str, Any]] = {}
    eligible_events = qualified_events = verified_events = 0
    for event in events:
        with contextlib.suppress(ValueError, TypeError):
            created_at = datetime.fromisoformat(str(event.get("created_at") or ""))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = max(0.0, (current - created_at).total_seconds())
            conversion = _search_event_conversion_value(event)
            if age < SEARCH_INTENT_MAX_AGE_SECONDS and conversion < 0.6:
                continue
            eligible_events += 1
            qualified_events += int(conversion >= 0.6)
            verified_events += int(conversion >= 0.95)
            qualified_matches = {
                str(signal)
                for row in (event.get("conversions") or {}).values()
                if isinstance(row, dict) and float(row.get("value") or 0) >= 0.6
                for signal in row.get("matched") or []
            }
            verified_matches = {
                str(signal)
                for row in (event.get("conversions") or {}).values()
                if isinstance(row, dict) and float(row.get("value") or 0) >= 0.95
                for signal in row.get("matched") or []
            }
            signals = _search_event_signals(event)
            combinations = _search_signal_combinations(signals)
            qualified_combinations: set[str] = set()
            verified_combinations: set[str] = set()
            for conversion_row in (event.get("conversions") or {}).values():
                if not isinstance(conversion_row, dict):
                    continue
                row_matches = {str(signal) for signal in conversion_row.get("matched") or []}
                row_value = float(conversion_row.get("value") or 0)
                for key, _kind, _label, members in combinations:
                    if row_value >= 0.6 and set(members) <= row_matches:
                        qualified_combinations.add(key)
                    if row_value >= 0.95 and set(members) <= row_matches:
                        verified_combinations.add(key)
            for key, kind, label in [*signals, *((key, kind, label) for key, kind, label, _members in combinations)]:
                row = metrics.setdefault(key, {"type": kind, "label": label, "exposed": 0, "qualified": 0, "verified": 0})
                row["exposed"] += 1
                row["qualified"] += int(key in (qualified_combinations if kind == "combination" else qualified_matches))
                row["verified"] += int(key in (verified_combinations if kind == "combination" else verified_matches))
    adaptive_signals = 0
    for row in metrics.values():
        exposed = int(row["exposed"])
        is_combination = row["type"] == "combination"
        posterior = (int(row["qualified"]) + (3 if is_combination else 2)) / (exposed + (6 if is_combination else 4))
        active = exposed >= (6 if is_combination else 8)
        row["posterior_rate"] = round(posterior, 4)
        lower, upper, slope = (0.8, 1.2, 0.6) if is_combination else (0.7, 1.3, 0.8)
        row["weight"] = round(max(lower, min(upper, 1 + (posterior - 0.5) * slope)), 3) if active else 1.0
        row["adaptation_status"] = "active" if active else "collecting"
        adaptive_signals += int(active)
    return {
        "eligible_events": eligible_events,
        "qualified_events": qualified_events,
        "verified_events": verified_events,
        "adaptive_signals": adaptive_signals,
        "signals": metrics,
    }


def search_intent_summary(*, now: datetime | None = None) -> dict[str, Any]:
    current = _aware_search_time(now)
    actors: dict[str, float] = defaultdict(float)
    actor_labels: dict[str, str] = {}
    categories: dict[str, float] = defaultdict(float)
    terms: dict[str, float] = defaultdict(float)
    combinations: dict[str, float] = defaultdict(float)
    combination_labels: dict[str, str] = {}
    retained: list[dict[str, Any]] = []
    all_events = [event for event in (_load_search_intents().get("events") or []) if isinstance(event, dict)]
    evaluation = _search_signal_metrics(all_events, current)
    signal_metrics = evaluation["signals"]
    for event in all_events:
        if not isinstance(event, dict):
            continue
        with contextlib.suppress(ValueError, TypeError):
            created_at = datetime.fromisoformat(str(event.get("created_at") or ""))
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = max(0.0, (current - created_at).total_seconds())
            if age > SEARCH_INTENT_MAX_AGE_SECONDS:
                continue
            retained.append(event)
            effective = math.pow(0.5, age / SEARCH_INTENT_HALF_LIFE_SECONDS)
            for actor in event.get("actors") or []:
                if not isinstance(actor, dict) or not actor.get("identity"):
                    continue
                identity = str(actor["identity"])
                actors[identity] += effective * float((signal_metrics.get(f"actor:{identity}") or {}).get("weight") or 1.0)
                actor_labels[identity] = str(actor.get("label") or identity)
            for category in event.get("categories") or []:
                if category:
                    name = str(category)
                    categories[name] += effective * float((signal_metrics.get(f"category:{name}") or {}).get("weight") or 1.0)
            for term in event.get("terms") or []:
                if term:
                    name = str(term)
                    terms[name] += effective * float((signal_metrics.get(f"term:{name}") or {}).get("weight") or 1.0)
            for key, _kind, label, _members in _search_signal_combinations(_search_event_signals(event)):
                combinations[key] += effective * float((signal_metrics.get(key) or {}).get("weight") or 1.0)
                combination_labels[key] = label
    latest = max((str(event.get("created_at") or "") for event in retained), default="")
    conversion_revision = max(
        (str(row.get("at") or "") for event in all_events for row in (event.get("conversions") or {}).values() if isinstance(row, dict)),
        default="",
    )
    return {
        "event_count": len(retained),
        "actors": dict(actors),
        "actor_labels": actor_labels,
        "categories": dict(categories),
        "terms": dict(terms),
        "combinations": dict(combinations),
        "combination_labels": combination_labels,
        "latest_at": latest or None,
        "evaluation": evaluation,
        "revision": hashlib.sha256(f"{len(retained)}:{latest}:{conversion_revision}:{evaluation['eligible_events']}:{evaluation['qualified_events']}".encode("utf-8")).hexdigest()[:16],
    }


async def attribute_search_intent_conversion(
    code: Any,
    event_type: str,
    *,
    actors: list[Any] | None = None,
    categories: list[Any] | None = None,
    title: str = "",
    now: datetime | None = None,
) -> int:
    value = float(SEARCH_INTENT_CONVERSION_VALUES.get(str(event_type or "")) or 0)
    canonical = canonical_work_code(code)
    if value <= 0 or not canonical:
        return 0
    current = _aware_search_time(now)
    actor_ids = {actor_identity_key(actor) for actor in actors or [] if actor_identity_key(actor)}
    category_names = {canonical_preference_category(category) for category in categories or [] if canonical_preference_category(category)}
    title_terms = set((semantic_tokens(title).get("weighted") or {}).keys())
    updated = 0
    async with _search_intent_lock:
        data = _load_search_intents()
        for event in data.get("events") or []:
            if not isinstance(event, dict):
                continue
            with contextlib.suppress(ValueError, TypeError):
                created_at = datetime.fromisoformat(str(event.get("created_at") or ""))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age = max(0.0, (current - created_at).total_seconds())
                if age > SEARCH_INTENT_MAX_AGE_SECONDS:
                    continue
                event_actor_ids = {str(row.get("identity") or "") for row in event.get("actors") or [] if isinstance(row, dict)}
                event_categories = {str(name) for name in event.get("categories") or []}
                event_terms = {str(name) for name in event.get("terms") or []}
                matched = sorted(
                    [f"actor:{name}" for name in actor_ids & event_actor_ids]
                    + [f"category:{name}" for name in category_names & event_categories]
                    + [f"term:{name}" for name in title_terms & event_terms]
                )
                if not matched:
                    continue
                conversions = event.setdefault("conversions", {})
                previous = conversions.get(canonical) if isinstance(conversions.get(canonical), dict) else {}
                if float(previous.get("value") or 0) >= value:
                    continue
                conversions[canonical] = {"stage": event_type, "value": value, "at": current.isoformat(), "matched": matched[:12]}
                updated += 1
        if updated:
            _save_search_intents(data)
    return updated


async def record_search_intent(query: Any, *, source: str = "resource-search", now: datetime | None = None) -> dict[str, Any]:
    raw = unicodedata.normalize("NFKC", str(query or "")).strip()
    current = _aware_search_time(now)
    if len(raw) < 2 or extract_video_code_candidates(raw):
        return {"recorded": False, "reason": "empty-or-code"}
    cleaned = re.sub(r"(?:来源|source)[:：]\S+", " ", raw, flags=re.I)
    tokens = [token.lstrip("-") for token in re.split(r"\s+", cleaned) if token]
    meaningful = [token for token in tokens if token.casefold() not in SEARCH_INTENT_OPERATIONAL_TERMS]
    if not meaningful:
        return {"recorded": False, "reason": "operational-only"}
    meaningful_text = " ".join(meaningful)
    normalized_query = _normalize_actor_name(meaningful_text)
    actors: list[dict[str, str]] = []
    actor_ids: set[str] = set()
    matched_actor_terms: set[str] = set()
    for alias in _search_actor_alias_terms():
        normalized_alias = _normalize_actor_name(alias)
        if normalized_alias not in normalized_query:
            continue
        identity = actor_identity_key(alias)
        if not identity or identity in actor_ids:
            continue
        actors.append({"identity": identity, "label": canonical_actor_name(alias)})
        actor_ids.add(identity)
        matched_actor_terms.add(normalized_alias)
        if len(actors) >= 4:
            break
    behavior = await preference_behavior_summary()
    category_names = set(PREFERENCE_CATEGORY_ALIASES) | set(PREFERENCE_CATEGORY_ALIASES.values()) | set((behavior.get("categories") or {}).keys())
    categories = list(dict.fromkeys(
        canonical_preference_category(name)
        for name in sorted(category_names, key=len, reverse=True)
        if len(name) >= 2 and unicodedata.normalize("NFKC", name).casefold() in meaningful_text.casefold()
        and canonical_preference_category(name).casefold() not in {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}
    ))[:8]
    weighted_terms = semantic_tokens(meaningful_text).get("weighted") or {}
    excluded = matched_actor_terms | {_normalize_actor_name(actor["label"]) for actor in actors} | {_normalize_actor_name(category) for category in categories}
    terms = [
        term for term in weighted_terms
        if term.casefold() not in SEARCH_INTENT_OPERATIONAL_TERMS
        and _normalize_actor_name(term) not in excluded
    ][:8]
    if not actors and not categories and not terms:
        return {"recorded": False, "reason": "no-preference-signal"}
    fingerprint = hashlib.sha256(f"{source}:{normalized_query}".encode("utf-8")).hexdigest()[:20]
    async with _search_intent_lock:
        data = _load_search_intents()
        events: list[dict[str, Any]] = []
        duplicate = False
        for event in data.get("events") or []:
            if not isinstance(event, dict):
                continue
            with contextlib.suppress(ValueError, TypeError):
                created_at = datetime.fromisoformat(str(event.get("created_at") or ""))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age = max(0.0, (current - created_at).total_seconds())
                if age <= SEARCH_INTENT_EVALUATION_RETENTION_SECONDS:
                    events.append(event)
                    if event.get("fingerprint") == fingerprint and age < 5 * 60:
                        duplicate = True
        if duplicate:
            return {"recorded": False, "reason": "duplicate"}
        events.append({
            "fingerprint": fingerprint,
            "source": source[:64],
            "created_at": current.isoformat(),
            "actors": actors,
            "categories": categories,
            "terms": terms,
        })
        data = {"version": 1, "events": events[-300:]}
        _save_search_intents(data)
    return {"recorded": True, "actors": actors, "categories": categories, "terms": terms}


def _cjk_semantic_segments(run: str) -> list[str]:
    groups = re.findall(r"[\u3400-\u9fff]+|[\u3040-\u309f]+|[\u30a0-\u30ffー]+", run)
    if len(run) <= 16 and len(groups) <= 2:
        return [run]
    useful = [group for group in groups if len(group) >= 2 and not re.fullmatch(r"[\u3040-\u309f]+", group)]
    combined = [
        left + right
        for left, right in zip(groups, groups[1:])
        if len(left) >= 2 and len(right) >= 2 and len(left + right) <= 12
        and not (re.fullmatch(r"[\u3040-\u309f]+", left) and re.fullmatch(r"[\u3040-\u309f]+", right))
    ]
    known = [
        term for term in set(PREFERENCE_CATEGORY_ALIASES) | set(PREFERENCE_CATEGORY_ALIASES.values())
        if len(term) >= 2 and term in run
    ]
    return list(dict.fromkeys([*useful, *combined, *known]))


def semantic_tokens(*values: Any) -> dict[str, Any]:
    text = unicodedata.normalize("NFKC", " ".join(str(value or "") for value in values if value))
    text = re.sub(r"レ[●○×xX*＊]プ", "レイプ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b(?:FC2[-_ ]?(?:PPV[-_ ]?)?\d{4,9}|[A-Z]{2,10}[-_ ]?\d{2,7})\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?:4k|8k|fhd|uhd|1080p|2160p|hdr|60fps)\b", " ", text, flags=re.I)
    latin = list(dict.fromkeys(
        part.casefold()
        for part in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
        if part.casefold() not in SEMANTIC_LATIN_STOPWORDS
        and part.casefold() not in SEMANTIC_RELATION_STOPWORDS
        and re.sub(r"[\s_.]+", "", part.casefold()) not in SEMANTIC_RELATION_STOPWORD_KEYS
    ))
    normalized_cjk = re.sub(r"(?:した|して|する|される|され|れる|られ|ない|です|ます|から|まで|より|そして|また|その|この|の|に|を|が|と|で|へ|的|了|过|与)", " ", text)
    cjk_runs = [segment for run in re.findall(r"[\u3040-\u30ff\u3400-\u9fff]{2,}", normalized_cjk) for segment in _cjk_semantic_segments(run)]
    cjk: list[str] = []
    weighted: dict[str, float] = {}
    def informative(term: str) -> bool:
        return len(re.findall(r"[\u30a0-\u30ff\u3400-\u9fffA-Za-z]", term)) >= 2
    for run in cjk_runs:
        pure_hiragana = bool(re.fullmatch(r"[\u3040-\u309f]+", run))
        if pure_hiragana:
            continue
        if run not in SEMANTIC_STOPWORDS and run.casefold() not in SEMANTIC_RELATION_STOPWORDS and informative(run):
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


def _work_similarity_features(profile: WorkProfile, diagnostics: dict[str, int] | None = None) -> tuple[dict[str, float], dict[str, str]]:
    features: dict[str, float] = {}
    labels: dict[str, str] = {}
    actor_identity_keys: set[str] = set()
    structured_actor_name_keys: set[str] = set()
    code_prefix = canonical_work_code(profile.code).split("-", 1)[0].casefold()
    for facts in (profile.facts or {}).values():
        if not isinstance(facts, dict):
            continue
        actor_names = _fact_names(facts, "actors", "actresses")
        actor_name_keys = {_normalize_actor_name(name) for name in actor_names}
        structured_actor_name_keys.update(actor_name_keys)
        actor_identity_keys.update(actor_identity_key(name) for name in actor_names if actor_identity_key(name))
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
                        or normalized_label.casefold() == code_prefix
                    ):
                        if diagnostics is not None and normalized_label.casefold() == code_prefix:
                            diagnostics["dropped_code_prefix_categories"] = int(diagnostics.get("dropped_code_prefix_categories") or 0) + 1
                        continue
                value = actor_identity_key(actual_name) if actual_kind == "actor" else unicodedata.normalize("NFKC", actual_name).casefold()
                key = f"{actual_kind}:{value}"
                features[key] = max(features.get(key, 0), actual_weight)
                labels[key] = canonical_actor_name(actual_name) if actual_kind == "actor" else actual_name
    if not actor_identity_keys:
        title_text = " ".join(str(value or "") for value in (
            profile.title, profile.original_title, profile.translated_title, *(profile.aliases or []),
        ))
        for mention in actor_mentions(title_text, limit=4):
            identity = str(mention.get("identity") or "")
            label = str(mention.get("name") or "")
            if not identity or not label:
                continue
            key = f"actor:{identity}"
            # Title inference is useful for recall but remains weaker than a
            # structured actor credit (4.2) until another provider confirms it.
            features[key] = max(features.get(key, 0), 3.2)
            labels[key] = label
            actor_identity_keys.add(identity)
            if diagnostics is not None:
                diagnostics["title_inferred_actor_features"] = int(diagnostics.get("title_inferred_actor_features") or 0) + 1
    tokens = profile.tokens if isinstance(profile.tokens, dict) else {}
    if int(tokens.get("version") or 0) < SEMANTIC_PROFILE_VERSION:
        tokens = semantic_tokens(profile.title, profile.original_title, profile.translated_title, *(profile.aliases or []))
    weighted_terms = tokens.get("weighted") if isinstance(tokens, dict) else {}
    for term, raw_weight in sorted((weighted_terms or {}).items(), key=lambda row: float(row[1] or 0), reverse=True)[:80]:
        normalized = unicodedata.normalize("NFKC", str(term)).casefold().strip()
        if len(normalized) < 2 or normalized in {value.casefold() for value in SIMILARITY_CATEGORY_STOPWORDS}:
            continue
        compact = re.sub(r"[\s_.]+", "", normalized)
        if (
            normalized in SEMANTIC_RELATION_STOPWORDS
            or compact in SEMANTIC_RELATION_STOPWORD_KEYS
            or re.fullmatch(r"(?:x|h)26[45]|hevc|avc|aac\d*|flac|(?:720|1080|2160|4320)p|[48]k|web-?dl", normalized)
            or normalized.startswith("ー")
        ):
            if diagnostics is not None:
                diagnostics["dropped_operational_semantic_terms"] = int(diagnostics.get("dropped_operational_semantic_terms") or 0) + 1
            continue
        # Titles frequently contain a different script or historical alias for
        # an actor already present in structured facts. MDC-NG resolves both to
        # one identity; counting that alias again as semantics would give the
        # same performer two independent votes in cosine similarity.
        normalized_actor_term = _normalize_actor_name(term)
        mapped_actor_duplicate = actor_identity_key(term) in actor_identity_keys
        inferred_actor_variant = any(
            _actor_variant_similarity(normalized_actor_term, actor_name_key) >= 0.75
            for actor_name_key in structured_actor_name_keys
        )
        inferred_actor_fragment = any(
            min(len(normalized_actor_term), len(actor_name_key)) >= 3
            and (actor_name_key.startswith(normalized_actor_term) or normalized_actor_term.startswith(actor_name_key))
            and min(len(normalized_actor_term), len(actor_name_key)) / max(len(normalized_actor_term), len(actor_name_key)) >= 0.6
            for actor_name_key in structured_actor_name_keys
        )
        if mapped_actor_duplicate or inferred_actor_variant or inferred_actor_fragment:
            if diagnostics is not None:
                key = "dropped_actor_alias_terms" if mapped_actor_duplicate else "dropped_actor_variant_terms" if inferred_actor_variant else "dropped_actor_fragment_terms"
                diagnostics[key] = int(diagnostics.get(key) or 0) + 1
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


def _relation_edge_allowed(similarity: float, confidence: float, kinds: set[str]) -> bool:
    """Reject evidence too weak to support a user-visible related-work edge."""
    if kinds == {"semantic"}:
        return similarity >= 0.16 and confidence >= 0.22
    return True


def _work_profiles_content_revision(profiles: list[WorkProfile]) -> str:
    """Fingerprint graph inputs while ignoring ordering and operational metadata."""
    fact_keys = {
        "actors", "actresses", "categories", "genres", "tags", "maker", "publisher", "studio", "label",
        "series", "director", "directors", "release_date", "date", "cover_url", "fanart_url",
    }

    def stable(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): stable(item) for key, item in sorted(value.items(), key=lambda row: str(row[0]))}
        if isinstance(value, (list, tuple, set)):
            rows = [stable(item) for item in value]
            keyed = {json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str): item for item in rows}
            return [keyed[key] for key in sorted(keyed)]
        if isinstance(value, str):
            return value.strip()
        return value

    digest = hashlib.sha256()
    for profile in sorted(profiles, key=lambda row: canonical_work_code(row.code)):
        facts = {
            str(source): {str(key): stable(value) for key, value in values.items() if str(key) in fact_keys}
            for source, values in (profile.facts or {}).items()
            if isinstance(values, dict)
        }
        evidence = [
            {"source": str(row.get("source") or ""), "confidence": int(row.get("confidence") or 0), "fields": stable(row.get("fields") or [])}
            for row in profile.source_evidence or []
            if isinstance(row, dict)
        ]
        payload = {
            "code": canonical_work_code(profile.code),
            "title": str(profile.title or "").strip(),
            "original_title": str(profile.original_title or "").strip(),
            "translated_title": str(profile.translated_title or "").strip(),
            "aliases": stable(profile.aliases or []),
            "tokens": stable(profile.tokens or {}),
            "facts": stable(facts),
            "evidence": stable(evidence),
            "confidence": int(profile.confidence or 0),
        }
        digest.update(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


async def build_work_similarity_index(*, force: bool = False, neighbor_limit: int = 24) -> dict[str, Any]:
    """Build a durable sparse multi-relation work-neighborhood index."""
    global _similarity_cache, _similarity_rebuild_task, _similarity_pending_revision
    async with async_session_maker() as db:
        profiles = list((await db.execute(select(WorkProfile))).scalars())
    alias_learning = infer_actor_aliases(profiles)
    content_revision = _work_profiles_content_revision(profiles)
    revision = f"{WORK_SIMILARITY_VERSION}:{SEMANTIC_PROFILE_VERSION}:{actor_alias_revision()}:{len(profiles)}:{content_revision}"
    if not force and _similarity_cache and _similarity_cache[0] == revision:
        return _similarity_cache[1]
    path = _work_similarity_file()
    if not force and path.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("revision") == revision:
                _similarity_cache = (revision, saved)
                return saved
            # A complete previous index is safer and dramatically faster than
            # rebuilding the whole graph inside an interactive request. Serve
            # it now and atomically publish the new revision in the background.
            if int(saved.get("version") or 0) == WORK_SIMILARITY_VERSION and saved.get("neighbors"):
                _similarity_cache = (str(saved.get("revision") or "stale"), saved)
                _similarity_pending_revision = revision
                if _similarity_rebuild_task is None or _similarity_rebuild_task.done():
                    async def rebuild() -> dict[str, Any]:
                        global _similarity_rebuild_task, _similarity_pending_revision
                        try:
                            return await build_work_similarity_index(force=True, neighbor_limit=neighbor_limit)
                        finally:
                            _similarity_pending_revision = ""
                            _similarity_rebuild_task = None

                    _similarity_rebuild_task = asyncio.create_task(rebuild())
                return saved

    raw_features: dict[str, dict[str, float]] = {}
    feature_labels: dict[str, str] = {}
    postings: dict[str, list[str]] = defaultdict(list)
    candidates: dict[str, dict[str, Any]] = {}
    feature_quality: dict[str, int] = {}
    for profile_index, profile in enumerate(profiles):
        if profile_index and profile_index % 48 == 0:
            await asyncio.sleep(0)
        code = canonical_work_code(profile.code)
        if not code:
            continue
        features, labels = _work_similarity_features(profile, feature_quality)
        combined = raw_features.setdefault(code, {})
        for feature, weight in features.items():
            combined[feature] = max(combined.get(feature, 0), weight)
        feature_labels.update(labels)
        current_candidate = candidates.get(code)
        candidate = _work_profile_candidate(profile)
        if current_candidate is None or int(candidate.get("confidence") or 0) > int(current_candidate.get("confidence") or 0):
            candidates[code] = candidate
    for profile_index, (code, features) in enumerate(raw_features.items()):
        if profile_index and profile_index % 96 == 0:
            await asyncio.sleep(0)
        for feature in features:
            postings[feature].append(code)
    work_count = max(len(raw_features), 1)
    weighted: dict[str, dict[str, float]] = defaultdict(dict)
    feature_cap = max(40, int(work_count * 0.15))
    for feature_index, (feature, codes) in enumerate(postings.items()):
        if feature_index and feature_index % 96 == 0:
            await asyncio.sleep(0)
        document_frequency = len(set(codes))
        if document_frequency < 2 or document_frequency > feature_cap:
            continue
        idf = math.log((work_count + 1) / (document_frequency + 1)) + 1
        for code in set(codes):
            weighted[code][feature] = raw_features[code][feature] * idf
    norms = {code: math.sqrt(sum(value * value for value in values.values())) for code, values in weighted.items()}
    dots: dict[tuple[str, str], float] = defaultdict(float)
    shared: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    pair_operations = 0
    for feature, codes in postings.items():
        eligible = sorted({code for code in codes if feature in weighted.get(code, {})})
        for index, left in enumerate(eligible):
            for right in eligible[index + 1:]:
                pair_operations += 1
                if pair_operations % 256 == 0:
                    await asyncio.sleep(0)
                contribution = weighted[left][feature] * weighted[right][feature]
                pair = (left, right)
                dots[pair] += contribution
                shared[pair].append((contribution, feature))
    neighbors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edge_quality: Counter = Counter()
    for pair_index, ((left, right), dot) in enumerate(dots.items()):
        if pair_index and pair_index % 256 == 0:
            await asyncio.sleep(0)
        denominator = norms.get(left, 0) * norms.get(right, 0)
        if denominator <= 0:
            continue
        similarity = dot / denominator
        if similarity < 0.08:
            continue
        strongest = sorted(shared[(left, right)], reverse=True)[:5]
        contributions_by_type: dict[str, float] = defaultdict(float)
        for contribution, feature in shared[(left, right)]:
            contributions_by_type[feature.split(":", 1)[0]] += max(0.0, contribution)
        contribution_total = sum(contributions_by_type.values()) or 1.0
        relation_confidence = _relation_confidence(similarity, strongest)
        reasons = []
        for contribution, feature in strongest:
            kind = feature.split(":", 1)[0]
            reasons.append({"type": kind, "label": feature_labels.get(feature, feature.split(":", 1)[-1]), "weight": round(contribution, 3)})
        calibrated_score = similarity * relation_confidence * 100
        relation_types = sorted({reason["type"] for reason in reasons})
        edge_quality["evaluated_pairs"] += 1
        if not _relation_edge_allowed(similarity, relation_confidence, set(relation_types)):
            edge_quality["pruned_semantic_only"] += 1
            continue
        edge_quality["retained_pairs"] += 1
        shared_payload = {
            "score": round(calibrated_score, 2),
            "cosine_similarity": round(similarity, 4),
            "relation_confidence": round(relation_confidence, 3),
            "relation_types": relation_types,
            "relation_contributions": {
                kind: round(value / contribution_total, 4)
                for kind, value in sorted(contributions_by_type.items())
            },
            "reasons": reasons,
        }
        row_left = {"code": right, **shared_payload}
        row_right = {"code": left, **shared_payload}
        neighbors[left].append(row_left)
        neighbors[right].append(row_right)
    for neighbor_index, code in enumerate(list(neighbors)):
        if neighbor_index and neighbor_index % 128 == 0:
            await asyncio.sleep(0)
        neighbors[code] = sorted(neighbors[code], key=lambda row: row["score"], reverse=True)[:neighbor_limit]
    result = {
        "version": WORK_SIMILARITY_VERSION,
        "profile_fusion_version": WORK_PROFILE_FUSION_VERSION,
        "revision": revision,
        "generated_at": utcnow().isoformat(),
        "source_profile_count": len(profiles),
        "work_count": len(raw_features),
        "duplicate_profile_count": max(0, len(profiles) - len(raw_features)),
        "feature_count": sum(1 for feature, codes in postings.items() if 2 <= len(set(codes)) <= feature_cap),
        "linked_work_count": len(neighbors),
        "isolated_work_count": max(0, len(raw_features) - len(neighbors)),
        "featureless_work_count": sum(not values for values in raw_features.values()),
        "graph_coverage_percent": round(len(neighbors) / max(len(raw_features), 1) * 100, 1),
        "mapped_actor_feature_count": sum(1 for feature in postings if feature.startswith("actor:mdc-ng:")),
        "actor_alias_learning": alias_learning,
        "fallback_actor_feature_count": sum(1 for feature in postings if feature.startswith("actor:name:")),
        "feature_quality": feature_quality,
        "edge_quality": {key: int(value) for key, value in edge_quality.items()},
        "neighbors": dict(neighbors),
        "candidates": candidates,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    _similarity_cache = (revision, result)
    return result


def _edge_relation_factor(edge: dict[str, Any], relation_weights: dict[str, float] | None) -> float:
    if not relation_weights:
        return 1.0
    shares = edge.get("relation_contributions") if isinstance(edge.get("relation_contributions"), dict) else {}
    if not shares:
        relation_types = [str(kind) for kind in edge.get("relation_types") or [] if str(kind or "")]
        shares = {kind: 1 / len(relation_types) for kind in relation_types} if relation_types else {}
    covered = min(1.0, sum(max(0.0, float(share or 0)) for share in shares.values()))
    factor = 1.0 - covered
    for kind, share in shares.items():
        factor += max(0.0, float(share or 0)) * max(0.75, min(1.25, float(relation_weights.get(str(kind)) or 1.0)))
    return max(0.75, min(1.25, factor))


def _rank_seed_weights(source_weights: dict[str, float], limit: int) -> list[tuple[str, float]]:
    """Keep strong signals first and break equal library baselines without code-prefix bias."""
    return sorted(
        source_weights.items(),
        key=lambda row: (-float(row[1]), hashlib.sha256(str(row[0]).encode()).hexdigest()),
    )[:max(1, int(limit))]


async def work_similarity_candidates(seed_weights: dict[str, float], *, negative_seed_weights: dict[str, float] | None = None, relation_weights: dict[str, float] | None = None, limit: int = 160) -> dict[str, Any]:
    index = await build_work_similarity_index()
    # Recommendation behavior weights decay continuously. Quantizing to one
    # percent prevents meaningless per-second changes from invalidating an
    # otherwise identical graph walk, while still reacting to real preference,
    # seed-set, relation-weight and Core-revision changes.
    seeds = {canonical_work_code(code): round(float(weight), 2) for code, weight in seed_weights.items() if canonical_work_code(code)}
    negative_seeds = {canonical_work_code(code): round(max(0.0, float(weight)), 2) for code, weight in (negative_seed_weights or {}).items() if canonical_work_code(code)}
    neighbors_by_code = index.get("neighbors") or {}
    fingerprint = hashlib.sha256(json.dumps({
        "evaluation_version": 2,
        "revision": index.get("revision"),
        "seeds": sorted((code, round(weight, 4)) for code, weight in seeds.items()),
        "negative_seeds": sorted((code, round(weight, 4)) for code, weight in negative_seeds.items()),
        "relation_weights": sorted((str(kind), round(float(weight), 4)) for kind, weight in (relation_weights or {}).items()),
        "limit": max(1, min(limit, 500)),
    }, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    cached = _similarity_candidate_cache.get(fingerprint)
    if cached is not None:
        return dict(cached)
    persisted = _load_offline_evaluation("candidates", fingerprint)
    if persisted is not None:
        _similarity_candidate_cache[fingerprint] = persisted
        return dict(persisted)

    def propagate(source_weights: dict[str, float], *, continuation: float) -> tuple[dict[str, float], dict[str, list[dict[str, Any]]]]:
        """Two-hop personalized walk with a strong restart and hub penalty."""
        propagated_scores: dict[str, float] = defaultdict(float)
        propagated_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        blocked = set(seeds) | set(negative_seeds)
        for seed_code, seed_weight in _rank_seed_weights(source_weights, 160):
            first_neighbors = neighbors_by_code.get(seed_code, [])
            for first in first_neighbors:
                intermediate = first["code"]
                if (source_weights is seeds and intermediate in negative_seeds) or (source_weights is negative_seeds and intermediate in seeds):
                    continue
                direct_strength = float(first.get("score") or 0) / 100 * _edge_relation_factor(first, relation_weights)
                if intermediate not in blocked:
                    contribution = direct_strength * max(0.1, seed_weight)
                    propagated_scores[intermediate] += contribution
                    propagated_evidence[intermediate].append({
                        "seed_code": seed_code,
                        "path": [seed_code, intermediate],
                        "hop_count": 1,
                        "contribution": round(contribution, 3),
                        "relation_confidence": float(first.get("relation_confidence") or 0),
                        "relation_types": first.get("relation_types") or [],
                        "reasons": first.get("reasons") or [],
                    })
                second_neighbors = neighbors_by_code.get(intermediate, [])
                hub_penalty = math.sqrt(max(1, len(second_neighbors)))
                for second in second_neighbors:
                    code = second["code"]
                    if code in blocked or code in {seed_code, intermediate}:
                        continue
                    path_strength = direct_strength * (float(second.get("score") or 0) / 100) * _edge_relation_factor(second, relation_weights)
                    contribution = path_strength * max(0.1, seed_weight) * continuation / hub_penalty
                    if contribution < 0.002:
                        continue
                    propagated_scores[code] += contribution
                    propagated_evidence[code].append({
                        "seed_code": seed_code,
                        "via_code": intermediate,
                        "path": [seed_code, intermediate, code],
                        "hop_count": 2,
                        "contribution": round(contribution, 3),
                        "relation_confidence": round(min(float(first.get("relation_confidence") or 0), float(second.get("relation_confidence") or 0)) * continuation, 3),
                        "relation_types": list(dict.fromkeys([*(first.get("relation_types") or []), *(second.get("relation_types") or [])])),
                        "reasons": [
                            {"hop": 1, "code": intermediate, "relations": first.get("reasons") or []},
                            {"hop": 2, "code": code, "relations": second.get("reasons") or []},
                        ],
                    })
        return propagated_scores, propagated_evidence

    scores, evidence = propagate(seeds, continuation=0.35)
    negative_scores, negative_evidence = propagate(negative_seeds, continuation=0.20)
    ranked = sorted(scores, key=lambda code: scores[code], reverse=True)[:max(1, min(limit, 500))]
    items = []
    for code in ranked:
        candidate = dict((index.get("candidates") or {}).get(code) or {"code": code, "title": code})
        candidate["neighbor_score"] = round(scores[code], 3)
        candidate["neighbor_evidence"] = sorted(evidence[code], key=lambda row: row["contribution"], reverse=True)[:5]
        candidate["neighbor_hop_count"] = min((int(row.get("hop_count") or 1) for row in evidence[code]), default=1)
        total_contribution = sum(float(row.get("contribution") or 0) for row in evidence[code]) or 1.0
        candidate["neighbor_confidence"] = round(sum(float(row.get("contribution") or 0) * float(row.get("relation_confidence") or 0) for row in evidence[code]) / total_contribution, 3)
        candidate["neighbor_negative_score"] = round(negative_scores.get(code, 0.0), 3)
        candidate["neighbor_negative_evidence"] = sorted(negative_evidence.get(code, []), key=lambda row: row["contribution"], reverse=True)[:3]
        items.append(candidate)
    result = {
        "revision": index.get("revision"),
        "items": items,
        "seed_count": len(seeds),
        "negative_seed_count": len(negative_seeds),
        "source_profile_count": index.get("source_profile_count", 0),
        "work_count": index.get("work_count", 0),
        "duplicate_profile_count": index.get("duplicate_profile_count", 0),
        "linked_work_count": index.get("linked_work_count", 0),
        "isolated_work_count": index.get("isolated_work_count", 0),
        "featureless_work_count": index.get("featureless_work_count", 0),
        "graph_coverage_percent": index.get("graph_coverage_percent", 0),
        "edge_quality": dict(index.get("edge_quality") or {}),
        "feature_quality": dict(index.get("feature_quality") or {}),
        "propagation": {
            "max_hops": 2,
            "positive_restart_probability": 0.65,
            "negative_restart_probability": 0.80,
            "multi_hop_candidates": sum(1 for code in ranked if any(int(row.get("hop_count") or 1) > 1 for row in evidence[code])),
            "relation_weights": {kind: round(float(weight), 3) for kind, weight in sorted((relation_weights or {}).items())},
            "seed_limit": 160,
        },
    }
    _similarity_candidate_cache[fingerprint] = result
    _save_offline_evaluation("candidates", fingerprint, result)
    if len(_similarity_candidate_cache) > 4:
        _similarity_candidate_cache.pop(next(iter(_similarity_candidate_cache)))
    return dict(result)


async def work_similarity_recall_evaluation(
    target_codes: list[str] | set[str],
    seed_weights: dict[str, float] | None = None,
    *,
    target_limit: int = 240,
    seed_limit: int = 160,
) -> dict[str, Any]:
    """Run a bounded leave-one-out audit over the user's known works.

    This measures whether the sparse Core neighborhood can structurally recover
    a held-out library work. It is intentionally reported separately from live
    conversion evaluation: the held-out item's own profile remains in the item
    index, so this is a retrieval health check rather than a CTR estimate.
    """
    index = await build_work_similarity_index()
    neighbors_by_code = index.get("neighbors") or {}
    candidates = index.get("candidates") or {}
    targets = sorted({canonical_work_code(code) for code in target_codes if canonical_work_code(code)} & set(candidates))
    weights = {
        canonical_work_code(code): round(max(0.05, float(weight)), 2)
        for code, weight in (seed_weights or {}).items()
        if canonical_work_code(code)
    }
    for code in targets:
        weights.setdefault(code, 1.0)
    target_limit = max(10, min(int(target_limit or 240), 500))
    seed_limit = max(10, min(int(seed_limit or 80), 160))
    if len(targets) > target_limit:
        # Keep the holdout cohort stable across index revisions so before/after
        # coverage changes reflect the model rather than a different sample.
        targets = sorted(targets, key=lambda code: hashlib.sha256(code.encode()).hexdigest())[:target_limit]
    evaluation_context = hashlib.sha256(json.dumps({
        "evaluation_version": 3,
        "targets": targets,
        "weights": sorted((code, round(weight, 4)) for code, weight in weights.items()),
        "seed_limit": seed_limit,
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    fingerprint = hashlib.sha256(f"{index.get('revision')}:{evaluation_context}".encode()).hexdigest()
    cached = _similarity_evaluation_cache.get(fingerprint)
    if cached is not None:
        return dict(cached)
    persisted = _load_offline_evaluation("recall", fingerprint)
    if persisted is not None:
        _similarity_evaluation_cache[fingerprint] = persisted
        return dict(persisted)

    blocked_seed_codes = set(weights)
    seed_rows = _rank_seed_weights(weights, len(weights))
    hits = {10: 0, 20: 0, 50: 0}
    eligible = 0
    reciprocal_rank_sum = 0.0
    ranks: list[int] = []
    relation_hits: dict[str, int] = defaultdict(int)
    misses: list[dict[str, Any]] = []
    audit_cases: list[tuple[str, dict[str, float], dict[str, dict[str, float]]]] = []

    def profile_gaps(code: str) -> list[str]:
        candidate = candidates.get(code) if isinstance(candidates.get(code), dict) else {}
        completeness = candidate.get("completeness") if isinstance(candidate.get("completeness"), dict) else {}
        gaps: list[str] = []
        if not candidate.get("actors") and not completeness.get("actors"):
            gaps.append("actors")
        if not candidate.get("categories") and not completeness.get("categories"):
            gaps.append("categories")
        title = str(candidate.get("title") or "").strip()
        if (not title or title == code) and not completeness.get("title"):
            gaps.append("title")
        if not str(candidate.get("maker") or "").strip():
            gaps.append("maker")
        return gaps

    for target in targets:
        active_seeds = [(code, weight) for code, weight in seed_rows if code != target][:seed_limit]
        scores: dict[str, float] = defaultdict(float)
        relation_components: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        blocked = blocked_seed_codes - {target}
        for seed_code, seed_weight in active_seeds:
            for neighbor in neighbors_by_code.get(seed_code, []):
                code = canonical_work_code(neighbor.get("code"))
                if not code or code in blocked:
                    continue
                contribution = float(neighbor.get("score") or 0) / 100 * seed_weight
                scores[code] += contribution
                shares = neighbor.get("relation_contributions") if isinstance(neighbor.get("relation_contributions"), dict) else {}
                if not shares:
                    relation_types = [str(kind) for kind in neighbor.get("relation_types") or [] if str(kind or "")]
                    shares = {kind: 1 / len(relation_types) for kind in relation_types} if relation_types else {}
                for relation_type, share in shares.items():
                    relation_components[code][str(relation_type)] += contribution * max(0.0, float(share or 0))
                if code == target:
                    evidence[code].append({
                        "seed_code": seed_code,
                        "contribution": round(contribution, 4),
                        "relation_types": list(neighbor.get("relation_types") or []),
                    })
        audit_cases.append((target, dict(scores), {code: dict(values) for code, values in relation_components.items()}))
        target_score = float(scores.get(target) or 0)
        if target_score <= 0:
            misses.append({"code": target, "reason": "no_neighbor_path", "profile_gaps": profile_gaps(target)})
            continue
        eligible += 1
        ordered = sorted(scores, key=lambda code: (-scores[code], code))
        rank = ordered.index(target) + 1
        ranks.append(rank)
        reciprocal_rank_sum += 1 / rank
        for cutoff in hits:
            hits[cutoff] += int(rank <= cutoff)
        if rank <= 50:
            for relation_type in set(
                relation_type
                for row in evidence.get(target, [])
                for relation_type in row.get("relation_types") or []
            ):
                relation_hits[str(relation_type)] += 1
        elif len(misses) < 20:
            misses.append({"code": target, "reason": "rank_above_50", "rank": rank, "score": round(target_score, 4), "profile_gaps": profile_gaps(target)})

    evaluated = len(targets)

    def counterfactual_metrics(relation_weights: dict[str, float]) -> dict[str, dict[str, Any]]:
        cohorts = {
            "overall": {"evaluated": 0, "eligible": 0, "hit20": 0, "hit50": 0, "rr": 0.0},
            "train": {"evaluated": 0, "eligible": 0, "hit20": 0, "hit50": 0, "rr": 0.0},
            "validation": {"evaluated": 0, "eligible": 0, "hit20": 0, "hit50": 0, "rr": 0.0},
        }
        for target, base_scores, relation_components in audit_cases:
            cohort_name = "train" if int(hashlib.sha256(target.encode()).hexdigest()[:2], 16) % 2 == 0 else "validation"
            variant_scores = dict(base_scores)
            for code, components in relation_components.items():
                adjustment = sum(
                    float(contribution) * (max(0.75, min(1.25, float(relation_weights.get(kind) or 1.0))) - 1)
                    for kind, contribution in components.items()
                )
                variant_scores[code] = max(0.0, float(variant_scores.get(code) or 0) + adjustment)
            target_score = float(variant_scores.get(target) or 0)
            rank = 0
            if target_score > 0:
                rank = sorted(variant_scores, key=lambda code: (-variant_scores[code], code)).index(target) + 1
            for name in ("overall", cohort_name):
                metric = cohorts[name]
                metric["evaluated"] += 1
                metric["eligible"] += int(rank > 0)
                metric["hit20"] += int(0 < rank <= 20)
                metric["hit50"] += int(0 < rank <= 50)
                metric["rr"] += 1 / rank if rank > 0 else 0.0
        result_by_cohort: dict[str, dict[str, Any]] = {}
        for name, metric in cohorts.items():
            sample = int(metric["evaluated"])
            hit20 = int(metric["hit20"]) / max(sample, 1)
            hit50 = int(metric["hit50"]) / max(sample, 1)
            mrr = float(metric["rr"]) / max(sample, 1)
            result_by_cohort[name] = {
                "evaluated": sample,
                "coverage": round(int(metric["eligible"]) / max(sample, 1), 4),
                "hit_at_20": round(hit20, 4),
                "hit_at_50": round(hit50, 4),
                "mrr": round(mrr, 4),
                "utility": round(hit20 * 0.45 + hit50 * 0.35 + mrr * 0.20, 5),
            }
        return result_by_cohort

    baseline_counterfactual = counterfactual_metrics({})
    relation_trials: dict[str, dict[str, Any]] = {}
    recommended_relation_weights: dict[str, float] = {}
    for relation_type in ("actor", "series", "director", "studio", "category", "semantic"):
        trials = {
            "up": counterfactual_metrics({relation_type: 1.15}),
            "down": counterfactual_metrics({relation_type: 0.85}),
        }
        baseline_train = float(baseline_counterfactual["train"]["utility"])
        baseline_validation = float(baseline_counterfactual["validation"]["utility"])
        qualified: list[tuple[float, str]] = []
        for direction, trial in trials.items():
            train_delta = float(trial["train"]["utility"]) - baseline_train
            validation_delta = float(trial["validation"]["utility"]) - baseline_validation
            trial["delta"] = {
                "train": round(train_delta, 5),
                "validation": round(validation_delta, 5),
                "overall": round(float(trial["overall"]["utility"]) - float(baseline_counterfactual["overall"]["utility"]), 5),
            }
            if (
                trial["train"]["evaluated"] >= 30
                and trial["validation"]["evaluated"] >= 30
                and train_delta >= 0.0025
                and validation_delta >= 0.001
                and float(trial["validation"]["hit_at_20"]) >= float(baseline_counterfactual["validation"]["hit_at_20"]) - 0.004
            ):
                qualified.append((min(train_delta, validation_delta), direction))
        if qualified:
            _gain, direction = max(qualified)
            recommended_relation_weights[relation_type] = 1.075 if direction == "up" else 0.925
        relation_trials[relation_type] = trials

    def recommendation_passes(metrics: dict[str, dict[str, Any]]) -> bool:
        return (
            float(metrics["train"]["utility"]) - float(baseline_counterfactual["train"]["utility"]) >= 0.0025
            and float(metrics["validation"]["utility"]) - float(baseline_counterfactual["validation"]["utility"]) >= 0.001
            and float(metrics["validation"]["hit_at_20"]) >= float(baseline_counterfactual["validation"]["hit_at_20"]) - 0.004
        )

    recommended_evaluation = counterfactual_metrics(recommended_relation_weights)
    if recommended_relation_weights and not recommendation_passes(recommended_evaluation):
        single_candidates: list[tuple[float, str, dict[str, dict[str, Any]]]] = []
        for relation_type, weight in recommended_relation_weights.items():
            metrics = counterfactual_metrics({relation_type: weight})
            if recommendation_passes(metrics):
                minimum_gain = min(
                    float(metrics["train"]["utility"]) - float(baseline_counterfactual["train"]["utility"]),
                    float(metrics["validation"]["utility"]) - float(baseline_counterfactual["validation"]["utility"]),
                )
                single_candidates.append((minimum_gain, relation_type, metrics))
        if single_candidates:
            _gain, relation_type, recommended_evaluation = max(single_candidates)
            recommended_relation_weights = {relation_type: recommended_relation_weights[relation_type]}
        else:
            recommended_relation_weights = {}
            recommended_evaluation = baseline_counterfactual
    recommended_delta = {
        cohort: round(float(recommended_evaluation[cohort]["utility"]) - float(baseline_counterfactual[cohort]["utility"]), 5)
        for cohort in ("overall", "train", "validation")
    }
    relation_policy = _stabilize_relation_policy(
        str(index.get("revision") or ""), recommended_relation_weights, context_key=evaluation_context,
    )

    result = {
        "method": "leave_one_out_direct_core_neighborhood",
        "revision": index.get("revision"),
        "evaluated": evaluated,
        "eligible": eligible,
        "coverage": round(eligible / max(evaluated, 1), 4),
        "hit_rate": {f"@{cutoff}": round(count / max(evaluated, 1), 4) for cutoff, count in hits.items()},
        "eligible_hit_rate": {f"@{cutoff}": round(count / max(eligible, 1), 4) for cutoff, count in hits.items()},
        "mrr": round(reciprocal_rank_sum / max(evaluated, 1), 4),
        "eligible_mrr": round(reciprocal_rank_sum / max(eligible, 1), 4),
        "median_rank": sorted(ranks)[len(ranks) // 2] if ranks else 0,
        "relation_hits_at_50": dict(sorted(relation_hits.items(), key=lambda row: (-row[1], row[0]))),
        "relation_counterfactual": {
            "method": "stable_hash_train_validation_plus_minus_15_percent",
            "baseline": baseline_counterfactual,
            "trials": relation_trials,
            "recommended_weights": dict(relation_policy.get("stable_weights") or {}),
            "proposed_weights": recommended_relation_weights,
            "recommended_evaluation": recommended_evaluation,
            "recommended_delta": recommended_delta,
            "policy": relation_policy,
            "applied_shrinkage": "±7.5%",
        },
        "sample_misses": misses[:20],
        "limits": {"targets": target_limit, "seeds_per_holdout": seed_limit},
        "interpretation": "结构召回健康度；目标作品画像保留在索引中，不等同于未来点击率",
    }
    _similarity_evaluation_cache[fingerprint] = result
    _save_offline_evaluation("recall", fingerprint, result)
    if len(_similarity_evaluation_cache) > 4:
        _similarity_evaluation_cache.pop(next(iter(_similarity_evaluation_cache)))
    return dict(result)


def _parse_historical_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip().replace("Z", "+00:00")
        text = re.sub(r"(\.\d{6})\d+(?=[+-]|$)", r"\1", text)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


async def work_similarity_temporal_backtest(
    acquisition_times: dict[str, Any],
    *,
    target_limit: int = 160,
    seed_limit: int = 160,
    minimum_history: int = 20,
) -> dict[str, Any]:
    """Compare durable and recency-aware seeds on a historical acquisition timeline."""
    index = await build_work_similarity_index()
    neighbors = index.get("neighbors") or {}
    known_candidates = set(index.get("candidates") or {})
    timeline = sorted(
        (parsed, canonical_work_code(code))
        for code, value in acquisition_times.items()
        if canonical_work_code(code) in known_candidates and (parsed := _parse_historical_time(value)) is not None
    )
    deduped: list[tuple[datetime, str]] = []
    seen: set[str] = set()
    for acquired_at, code in timeline:
        if code not in seen:
            seen.add(code)
            deduped.append((acquired_at, code))
    timeline = deduped
    eligible_indices = [index for index in range(minimum_history, len(timeline)) if len(timeline) - index >= 20]
    target_limit = max(20, min(int(target_limit or 160), 320))
    if len(eligible_indices) > target_limit:
        step = (len(eligible_indices) - 1) / max(target_limit - 1, 1)
        eligible_indices = sorted({eligible_indices[round(position * step)] for position in range(target_limit)})
    fingerprint = hashlib.sha256(json.dumps({
        "revision": index.get("revision"),
        "timeline": [(value.isoformat(), code) for value, code in timeline],
        "indices": eligible_indices,
        "seed_limit": seed_limit,
    }, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if fingerprint in _similarity_temporal_cache:
        return dict(_similarity_temporal_cache[fingerprint])
    persisted = _load_offline_evaluation("temporal", fingerprint)
    if persisted is not None:
        _similarity_temporal_cache[fingerprint] = persisted
        return dict(persisted)

    metrics = {
        policy: {cohort: {"evaluated": 0, "eligible": 0, "hit20": 0, "hit50": 0, "rr": 0.0} for cohort in ("overall", "train", "validation")}
        for policy in ("durable", "temporal")
    }
    split_at = int(len(eligible_indices) * 0.7)
    for fold_position, timeline_index in enumerate(eligible_indices):
        cutoff, target = timeline[timeline_index]
        prior = timeline[:timeline_index]
        future_codes = {code for _time, code in timeline[timeline_index:]}
        cohort = "train" if fold_position < split_at else "validation"
        policy_weights = {
            "durable": {code: 1.0 for _time, code in prior},
            "temporal": {
                code: 1.0 if (age_days := max(0.0, (cutoff - acquired_at).total_seconds() / 86400)) <= 60
                else max(0.75, 0.75 + 0.25 * math.pow(0.5, (age_days - 60) / 180))
                for acquired_at, code in prior
            },
        }
        for policy, weights in policy_weights.items():
            scores: dict[str, float] = defaultdict(float)
            for seed_code, seed_weight in _rank_seed_weights(weights, seed_limit):
                for neighbor in neighbors.get(seed_code, []):
                    code = canonical_work_code(neighbor.get("code"))
                    if code in future_codes:
                        scores[code] += float(neighbor.get("score") or 0) / 100 * seed_weight
            target_score = float(scores.get(target) or 0)
            rank = 0
            if target_score > 0:
                rank = sorted(scores, key=lambda code: (-scores[code], code)).index(target) + 1
            for cohort_name in ("overall", cohort):
                row = metrics[policy][cohort_name]
                row["evaluated"] += 1
                row["eligible"] += int(rank > 0)
                row["hit20"] += int(0 < rank <= 20)
                row["hit50"] += int(0 < rank <= 50)
                row["rr"] += 1 / rank if rank else 0.0

    summarized: dict[str, dict[str, dict[str, Any]]] = {}
    for policy, cohorts in metrics.items():
        summarized[policy] = {}
        for cohort, row in cohorts.items():
            sample = int(row["evaluated"])
            hit20 = int(row["hit20"]) / max(sample, 1)
            hit50 = int(row["hit50"]) / max(sample, 1)
            mrr = float(row["rr"]) / max(sample, 1)
            summarized[policy][cohort] = {
                "evaluated": sample,
                "coverage": round(int(row["eligible"]) / max(sample, 1), 4),
                "hit_at_20": round(hit20, 4),
                "hit_at_50": round(hit50, 4),
                "mrr": round(mrr, 4),
                "utility": round(hit20 * 0.45 + hit50 * 0.35 + mrr * 0.20, 5),
            }
    deltas = {
        cohort: round(float(summarized["temporal"][cohort]["utility"]) - float(summarized["durable"][cohort]["utility"]), 5)
        for cohort in ("overall", "train", "validation")
    }
    enough = summarized["temporal"]["train"]["evaluated"] >= 30 and summarized["temporal"]["validation"]["evaluated"] >= 20
    recommended_policy = "temporal" if (
        enough and deltas["train"] >= 0.001 and deltas["validation"] >= 0.001
        and summarized["temporal"]["validation"]["hit_at_20"] >= summarized["durable"]["validation"]["hit_at_20"] - 0.004
    ) else "durable" if enough else "collecting"
    result = {
        "method": "historical_library_acquisition_behavior_cutoff",
        "metadata_snapshot": "current_core_profile",
        "timeline_works": len(timeline),
        "evaluated": len(eligible_indices),
        "split": {"train": split_at, "validation": len(eligible_indices) - split_at},
        "policies": summarized,
        "utility_delta": deltas,
        "recommended_policy": recommended_policy,
        "limits": {"targets": target_limit, "seeds_per_cutoff": seed_limit, "minimum_history": minimum_history},
        "interpretation": "行为时间截断回测；作品关系使用当前 Core 元数据快照",
    }
    _similarity_temporal_cache[fingerprint] = result
    _save_offline_evaluation("temporal", fingerprint, result)
    if len(_similarity_temporal_cache) > 4:
        _similarity_temporal_cache.pop(next(iter(_similarity_temporal_cache)))
    return dict(result)


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
        "source_profile_count": int(payload.get("source_profile_count") or 0),
        "work_count": int(payload.get("work_count") or 0),
        "duplicate_profile_count": int(payload.get("duplicate_profile_count") or 0),
        "feature_count": int(payload.get("feature_count") or 0),
        "linked_work_count": int(payload.get("linked_work_count") or 0),
        "isolated_work_count": int(payload.get("isolated_work_count") or 0),
        "featureless_work_count": int(payload.get("featureless_work_count") or 0),
        "graph_coverage_percent": float(payload.get("graph_coverage_percent") or 0),
        "mapped_actor_feature_count": int(payload.get("mapped_actor_feature_count") or 0),
        "fallback_actor_feature_count": int(payload.get("fallback_actor_feature_count") or 0),
        "feature_quality": dict(payload.get("feature_quality") or {}),
        "edge_quality": dict(payload.get("edge_quality") or {}),
        "rebuilding": bool(_similarity_rebuild_task and not _similarity_rebuild_task.done()),
        "pending_revision": _similarity_pending_revision,
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
                    # A release/torrent title describes one resource version,
                    # not the canonical work. Keep it in ResourceObservation
                    # and source evidence; using it as a work alias pollutes
                    # semantic profiles and changes the graph on every search.
                    profile = WorkProfile(code=code, title=work_title, aliases=[], tokens=semantic_tokens(work_title), facts={}, source_evidence=[evidence], confidence=55)
                    db.add(profile)
                else:
                    evidence_rows = [row for row in (profile.source_evidence or []) if isinstance(row, dict) and row.get("source") != provider_id]
                    evidence_rows.append(evidence)
                    profile.title = profile.title or work_title
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
                infer_actor_aliases(profiles)
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
