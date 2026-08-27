from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.knowledge import intelligence
from app.knowledge.models import WorkProfile


def test_canonical_work_code_collapses_local_version_marks() -> None:
    assert intelligence.canonical_work_code("WAAA-615-C.mp4") == "WAAA-615"
    assert intelligence.canonical_work_code("WAAA-615-U") == "WAAA-615"
    assert intelligence.canonical_work_code("FC2-PPV-4720819-C") == "FC2-PPV-4720819"
    assert intelligence.canonical_work_code("050126_001-1PON") == "1PON-050126-001"


def test_preference_outcome_model_uses_verified_funnel_with_smoothing() -> None:
    events = [
        SimpleNamespace(work_code="AAA-001", event_type="subscription", actors=["测试演员"], categories=["人妻"]),
        SimpleNamespace(work_code="AAA-001", event_type="library_imported", actors=["测试演员"], categories=["人妻"]),
        SimpleNamespace(work_code="BBB-002", event_type="download_submitted", actors=["测试演员"], categories=["NTR"]),
    ]

    model = intelligence._preference_outcome_model(events)

    assert model["trials"] == 2
    assert model["verified"] == 1
    assert model["rate"] == 0.5
    assert model["categories"]["人妻"]["rate"] == 0.6
    assert model["categories"]["NTR"]["rate"] == 0.4


def test_work_similarity_index_builds_multi_relation_neighbors(tmp_path, monkeypatch) -> None:
    asyncio.run(_work_similarity_index_builds_multi_relation_neighbors(tmp_path, monkeypatch))


async def _work_similarity_index_builds_multi_relation_neighbors(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'neighbors.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "async_session_maker", sessions)
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_similarity_cache", None)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db:
        db.add_all([
            WorkProfile(code="AAA-001", title="邻居人妻秘密", facts={"test": {"actors": ["演员甲"], "categories": ["人妻", "邻居"]}}, tokens=intelligence.semantic_tokens("邻居人妻秘密"), confidence=90),
            WorkProfile(code="AAA-002", title="隔壁人妻物语", facts={"test": {"actors": ["演员甲"], "categories": ["人妻", "邻居"]}}, tokens=intelligence.semantic_tokens("隔壁人妻物语"), confidence=88),
            WorkProfile(code="BBB-001", title="运动员纪录", facts={"test": {"actors": ["演员乙"], "categories": ["运动"]}}, tokens=intelligence.semantic_tokens("运动员纪录"), confidence=80),
        ])
        await db.commit()

    index = await intelligence.build_work_similarity_index(force=True)
    recalled = await intelligence.work_similarity_candidates({"AAA-001": 1.0})

    assert index["work_count"] == 3
    assert index["linked_work_count"] == 2
    assert index["neighbors"]["AAA-001"][0]["code"] == "AAA-002"
    assert recalled["items"][0]["code"] == "AAA-002"
    assert recalled["items"][0]["neighbor_evidence"][0]["reasons"]
    await engine.dispose()


def test_semantic_tokens_preserve_terms_and_cjk_context() -> None:
    tokens = intelligence.semantic_tokens("隣人の秘密", "邻居的秘密", "uncensored leak")
    assert "uncensored" in tokens["latin"]
    assert "隣人" in tokens["cjk"]
    assert "邻居" in tokens["cjk"]
    assert tokens["version"] == intelligence.SEMANTIC_PROFILE_VERSION
    assert tokens["weighted"]["隣人"] >= 0.7
    assert "子生徒" not in intelligence.semantic_tokens("女子生徒")["weighted"]
    assert "女子生徒" in intelligence.semantic_tokens("女子生徒")["weighted"]
    assert "fanza" not in intelligence.semantic_tokens("FANZA限定 sample sex")["weighted"]


def test_actor_alias_names_loads_mdc_ng_mapping(monkeypatch, tmp_path) -> None:
    mapping = tmp_path / "media_actor_mappings.json"
    mapping.write_text(json.dumps({"records": [{
        "id": "name:三宫椿",
        "jp": "三宮つばき", "zh_cn": "三宫椿", "zh_tw": "三宮椿",
        "names": ["三宮つばき", "三宫椿"], "aliases": ["旧名"],
    }]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(intelligence, "data_path", lambda *_parts: mapping)
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)

    assert intelligence.actor_alias_names() == frozenset({"三宮つばき", "三宫椿", "三宮椿", "旧名"})
    assert intelligence.canonical_actor_name("三宮つばき") == "三宫椿"
    assert intelligence.canonical_actor_name("三宮 椿") == "三宫椿"
    assert intelligence.actor_identity_key("三宮つばき") == "mdc-ng:name:三宫椿"
    assert intelligence.actor_identity_key("三宮 椿") == "mdc-ng:name:三宫椿"
    assert intelligence.actor_identity_key("未收录演员") == "name:未收录演员"
    assert intelligence.canonical_actor_name("未收录演员") == "未收录演员"
    assert intelligence.actor_alias_revision() != "missing"
    assert intelligence.actor_alias_stats()["identity_count"] == 1
    assert intelligence.actor_alias_stats()["alias_count"] == 4


def test_resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch) -> None:
    asyncio.run(_resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch))


async def _resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'intelligence.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "async_session_maker", sessions)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    written = await intelligence.record_resource_search(
        {"keyword": "PRED-878"},
        [
            {
                "provider": "avdb",
                "provider_label": "AVDB",
                "items": [{"id": "avdb-1", "title": "PRED-878 破解-C", "size_bytes": 123, "features": {"is_cracked": True, "has_subtitle": True}}],
            },
            {
                "provider": "mteam-plugin",
                "provider_label": "M-Team",
                "items": [{"id": "mteam-1", "title": "PRED-878", "size_bytes": 456}],
            },
        ],
        outcomes=[{"provider": "avdb", "provider_label": "AVDB", "status": "available", "count": 1}, {"provider": "missing", "status": "empty", "count": 0}],
    )
    portrait = await intelligence.work_intelligence("pred878")

    assert written == 2
    assert portrait is not None
    assert portrait["code"] == "PRED-878"
    assert portrait["resources"]["total"] == 2
    assert portrait["resources"]["has_cracked"] is True
    assert portrait["resources"]["has_subtitle"] is True
    assert {row["provider"]: row["status"] for row in portrait["resources"]["provider_checks"]} == {"avdb": "available", "missing": "empty"}
    assert [group["provider"] for group in portrait["resources"]["groups"]] == ["avdb", "mteam-plugin"]
    assert portrait["profile"]["tokens"]

    await intelligence.record_work_metadata(
        "PRED-878",
        {"title": "PRED-878 隣人の秘密", "actors": ["测试演员"], "categories": ["剧情"]},
        source="javdb",
        confidence=85,
    )
    enriched = await intelligence.work_intelligence("PRED-878")
    assert enriched["profile"]["facts"]["javdb"]["actors"] == ["测试演员"]
    assert "隣人" in enriched["profile"]["tokens"]["cjk"]
    assert await intelligence.record_preference_event(
        "PRED-878", "detail_view", source="av-recommend", actors=["测试演员"], categories=["剧情"], enqueue_refresh=False,
    ) is True
    assert await intelligence.record_preference_event(
        "PRED-878", "detail_view", source="av-recommend", actors=["测试演员"], categories=["剧情"], enqueue_refresh=False,
    ) is False
    assert await intelligence.record_preference_event(
        "PRED-878", "subscription", source="av-recommend", actors=["测试演员"], categories=["剧情"], enqueue_refresh=False,
    ) is True
    assert await intelligence.record_preference_event(
        "PRED-878", "library_imported", source="subscription-core", data={"evidence_id": "sub-1:media-1"},
    ) is True
    assert await intelligence.record_preference_event(
        "PRED-878", "library_imported", source="subscription-core", data={"evidence_id": "sub-1:media-1"},
    ) is False
    behavior = await intelligence.preference_behavior_summary()
    assert behavior["event_count"] == 3
    assert behavior["codes"]["PRED-878"] > 5.9
    assert behavior["actors"]["测试演员"] > 5.9
    assert behavior["revision"].startswith("3:")
    assert await intelligence.clear_preference_events(source="av-recommend") == 2
    assert (await intelligence.preference_behavior_summary())["event_count"] == 1
    assert await intelligence.clear_preference_events(source="subscription-core") == 1
    await engine.dispose()
