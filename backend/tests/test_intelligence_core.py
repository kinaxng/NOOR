from __future__ import annotations

import asyncio
import datetime as dt
import json
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.knowledge import intelligence
from app.knowledge.models import WorkProfile
from app.knowledge.repository import KnowledgeRepository


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


def test_interest_topics_deduplicate_funnel_stages_and_capture_recent_combinations() -> None:
    now = intelligence.utcnow()
    events = [
        SimpleNamespace(work_code="AAA-001", event_type="detail_view", weight=0.18, actors=["演员甲"], categories=["人妻", "邻居"], created_at=now - dt.timedelta(days=2)),
        SimpleNamespace(work_code="AAA-001", event_type="library_imported", weight=4.0, actors=["演员甲"], categories=["人妻", "邻居"], created_at=now - dt.timedelta(days=1)),
        SimpleNamespace(work_code="AAA-002", event_type="subscription", weight=1.8, actors=["演员甲"], categories=["人妻", "职场"], created_at=now - dt.timedelta(days=4)),
        SimpleNamespace(work_code="BBB-001", event_type="library_imported", weight=4.0, actors=["演员乙"], categories=["运动"], created_at=now - dt.timedelta(days=80)),
    ]

    result = intelligence._preference_interest_topics(events)
    topic = next(item for item in result["topics"] if item["anchor"] == "人妻")

    assert result["work_count"] == 3
    assert topic["support"] == 2
    assert {item["name"] for item in topic["actors"]} == {"演员甲"}
    assert {"邻居", "职场"} <= set(topic["categories"])
    assert topic["recent_strength"] > 0


def test_interest_topics_use_media_library_as_durable_long_term_baseline() -> None:
    profiles = [
        SimpleNamespace(code="AAA-001", confidence=95, facts={"media-library": {"in_library": True, "actors": ["演员甲"]}, "javdb": {"categories": [{"name": "人妻"}, {"name": "邻居"}]}}),
        SimpleNamespace(code="AAA-002", confidence=90, facts={"media-library": {"in_library": True, "actors": ["演员甲"]}, "javdb": {"categories": [{"name": "人妻"}, {"name": "职场"}]}}),
        SimpleNamespace(code="AAA-003", confidence=90, facts={"javdb": {"categories": [{"name": "运动"}]}}),
    ]

    result = intelligence._preference_interest_topics([], profiles=profiles)
    topic = next(item for item in result["topics"] if item["anchor"] == "人妻")

    assert result["version"] == 2
    assert result["library_work_count"] == 2
    assert result["behavior_work_count"] == 0
    assert topic["support"] == 2
    assert topic["confidence"] >= 0.33
    assert topic["recent_strength"] == topic["strength"]
    assert topic["recent_reliability"] == 0


def test_profile_evidence_backfills_historical_events_without_male_cast_or_operational_tags() -> None:
    profile = SimpleNamespace(facts={
        "javdb": {
            "actors": [{"name": "女优甲", "gender": "♀"}, {"name": "男优乙", "gender": "♂"}],
            "categories": [{"name": "人妻"}, {"name": "巨乳"}],
        },
        "media-library": {
            "actors": ["女优甲"],
            "genres": ["人妻", "中文字幕", "片商名称"],
        },
    })

    evidence = intelligence._profile_preference_evidence(profile)

    assert evidence["actors"] == ["女优甲"]
    assert "人妻" in evidence["categories"]
    assert "巨乳" in evidence["categories"]
    assert "中文字幕" not in evidence["categories"]


def test_search_intent_uses_core_identities_filters_operations_and_decays(tmp_path, monkeypatch) -> None:
    asyncio.run(_search_intent_uses_core_identities_filters_operations_and_decays(tmp_path, monkeypatch))


async def _search_intent_uses_core_identities_filters_operations_and_decays(tmp_path, monkeypatch) -> None:
    now = dt.datetime(2026, 8, 28, 4, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_search_actor_alias_terms", lambda: ["吉泽明步", "吉沢明歩"])
    monkeypatch.setattr(intelligence, "actor_identity_key", lambda value: "mdc-ng:吉沢明歩" if value else "")
    monkeypatch.setattr(intelligence, "canonical_actor_name", lambda value: "吉沢明歩" if value else "")

    async def behavior():
        return {"categories": {"人妻": 3.0}}

    monkeypatch.setattr(intelligence, "preference_behavior_summary", behavior)
    recorded = await intelligence.record_search_intent("吉泽明步 人妻 破解", now=now)
    duplicate = await intelligence.record_search_intent("吉泽明步 人妻 破解", now=now + dt.timedelta(minutes=2))
    code = await intelligence.record_search_intent("PRED-878 破解", now=now)

    assert recorded["recorded"] is True
    assert recorded["actors"] == [{"identity": "mdc-ng:吉沢明歩", "label": "吉沢明歩"}]
    assert recorded["categories"] == ["人妻"]
    assert "破解" not in recorded["terms"]
    assert duplicate == {"recorded": False, "reason": "duplicate"}
    assert code == {"recorded": False, "reason": "empty-or-code"}
    stored = json.loads((tmp_path / "intelligence_search_intents.json").read_text(encoding="utf-8"))
    assert "吉泽明步" not in json.dumps(stored, ensure_ascii=False)
    fresh = intelligence.search_intent_summary(now=now)
    aged = intelligence.search_intent_summary(now=now + dt.timedelta(hours=3))
    assert fresh["actors"]["mdc-ng:吉沢明歩"] == 1.0
    assert list(fresh["combination_labels"].values()) == ["吉沢明歩 × 人妻"]
    assert aged["actors"]["mdc-ng:吉沢明歩"] == 0.5
    original_revision = fresh["revision"]
    assert await intelligence.attribute_search_intent_conversion(
        "AAA-001", "detail_view", actors=["吉沢明歩"], categories=["人妻"], title="秘密の人妻", now=now + dt.timedelta(minutes=5),
    ) == 1
    detail = intelligence.search_intent_summary(now=now + dt.timedelta(minutes=5))
    assert detail["evaluation"]["eligible_events"] == 0
    assert await intelligence.attribute_search_intent_conversion(
        "AAA-001", "subscription", actors=["吉泽明步"], categories=["已婚妇女"], title="秘密の人妻", now=now + dt.timedelta(minutes=6),
    ) == 1
    converted = intelligence.search_intent_summary(now=now + dt.timedelta(minutes=6))
    assert converted["evaluation"]["eligible_events"] == 1
    assert converted["evaluation"]["qualified_events"] == 1
    combination = next(row for row in converted["evaluation"]["signals"].values() if row["type"] == "combination")
    assert combination["qualified"] == 1
    assert converted["revision"] != original_revision


def test_search_signal_calibration_waits_for_mature_samples() -> None:
    now = dt.datetime(2026, 8, 28, 16, 0, tzinfo=dt.timezone.utc)

    def events(value: float) -> list[dict]:
        return [{
            "created_at": (now - dt.timedelta(hours=13, minutes=index)).isoformat(),
            "actors": [{"identity": "actor:one", "label": "演员一"}],
            "categories": [], "terms": [],
            "conversions": {"AAA-001": {"value": value, "matched": ["actor:actor:one"]}} if value else {},
        } for index in range(8)]

    collecting = intelligence._search_signal_metrics(events(0)[:7], now)["signals"]["actor:actor:one"]
    fading = intelligence._search_signal_metrics(events(0), now)["signals"]["actor:actor:one"]
    strengthened = intelligence._search_signal_metrics(events(0.7), now)["signals"]["actor:actor:one"]
    assert collecting["adaptation_status"] == "collecting" and collecting["weight"] == 1.0
    assert fading["adaptation_status"] == "active" and fading["weight"] < 1.0
    assert strengthened["adaptation_status"] == "active" and strengthened["weight"] > 1.0


def test_search_combination_requires_same_conversion_to_match_both_signals() -> None:
    now = dt.datetime(2026, 8, 28, 16, 0, tzinfo=dt.timezone.utc)

    def events(matched: list[str]) -> list[dict]:
        return [{
            "created_at": (now - dt.timedelta(hours=13, minutes=index)).isoformat(),
            "actors": [{"identity": "actor:one", "label": "演员一"}],
            "categories": ["人妻"], "terms": [],
            "conversions": {f"AAA-{index:03d}": {"value": 0.7, "matched": matched}},
        } for index in range(6)]

    category_only = intelligence._search_signal_metrics(events(["category:人妻"]), now)
    both = intelligence._search_signal_metrics(events(["actor:actor:one", "category:人妻"]), now)
    split_events = events([])
    for index, event in enumerate(split_events):
        event["conversions"] = {
            f"AAA-{index:03d}": {"value": 0.7, "matched": ["actor:actor:one"]},
            f"BBB-{index:03d}": {"value": 0.7, "matched": ["category:人妻"]},
        }
    split = intelligence._search_signal_metrics(split_events, now)
    weak_combo = next(row for row in category_only["signals"].values() if row["type"] == "combination")
    strong_combo = next(row for row in both["signals"].values() if row["type"] == "combination")
    split_combo = next(row for row in split["signals"].values() if row["type"] == "combination")
    assert weak_combo["qualified"] == 0 and weak_combo["weight"] < 1.0
    assert split_combo["qualified"] == 0 and split_combo["weight"] < 1.0
    assert strong_combo["qualified"] == 6 and strong_combo["weight"] > 1.0


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
            WorkProfile(code="AAA-003", title="邻家人妻日记", facts={"test": {"actors": ["演员甲"], "categories": ["人妻", "邻居"]}}, tokens=intelligence.semantic_tokens("邻家人妻日记"), confidence=86),
            WorkProfile(code="BBB-001", title="运动员纪录", facts={"test": {"actors": ["演员乙"], "categories": ["运动"]}}, tokens=intelligence.semantic_tokens("运动员纪录"), confidence=80),
        ])
        await db.commit()

    index = await intelligence.build_work_similarity_index(force=True)
    recalled = await intelligence.work_similarity_candidates({"AAA-001": 1.0}, negative_seed_weights={"AAA-003": 1.0})

    assert index["work_count"] == 4
    assert index["linked_work_count"] == 3
    assert index["fallback_actor_feature_count"] == 2
    assert {row["code"] for row in index["neighbors"]["AAA-001"]} >= {"AAA-002", "AAA-003"}
    assert index["neighbors"]["AAA-001"][0]["relation_confidence"] > 0.8
    assert "actor" in index["neighbors"]["AAA-001"][0]["relation_types"]
    assert 0.99 <= sum(index["neighbors"]["AAA-001"][0]["relation_contributions"].values()) <= 1.01
    recalled_002 = next(item for item in recalled["items"] if item["code"] == "AAA-002")
    assert recalled_002["neighbor_confidence"] > 0.8
    assert recalled_002["neighbor_evidence"][0]["reasons"]
    assert recalled["negative_seed_count"] == 1
    assert recalled_002["neighbor_negative_score"] > 0
    await engine.dispose()


def test_semantic_only_relation_has_lower_confidence_than_mapped_actor() -> None:
    semantic = intelligence._relation_confidence(0.5, [(10.0, "semantic:秘密")])
    actor = intelligence._relation_confidence(0.5, [(10.0, "actor:mdc-ng:actor-1")])

    assert semantic < 0.35
    assert actor > 0.9


def test_relation_factor_applies_bounded_contribution_weighting() -> None:
    edge = {"relation_contributions": {"actor": 0.8, "category": 0.2}}
    assert round(intelligence._edge_relation_factor(edge, {"actor": 0.925}), 3) == 0.94
    assert round(intelligence._edge_relation_factor(edge, {"actor": 9, "category": -2}), 3) == 1.15


def test_similarity_features_do_not_double_count_mdc_alias_or_code_prefix(monkeypatch, tmp_path) -> None:
    (tmp_path / "media_actor_mappings.json").write_text(json.dumps({"records": [{
        "id": "actor-1", "jp": "百田光希", "zh_cn": "百田光希", "names": ["百田光希", "百田光稀"],
    }]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)
    diagnostics = {}
    profile = WorkProfile(
        code="MIDA-727",
        title="百田光稀 秘密",
        facts={"javdb": {"actors": ["百田光希"], "categories": ["MIDA", "人妻"]}},
        tokens={"weighted": {"百田光稀": 1.8, "百田光穗": 1.7, "秘密": 1.8}},
    )

    features, _labels = intelligence._work_similarity_features(profile, diagnostics)

    assert "actor:mdc-ng:actor-1" in features
    assert "semantic:百田光稀" not in features
    assert "semantic:百田光穗" not in features
    assert "semantic:秘密" in features
    assert "category:mida" not in features
    assert "category:人妻" in features
    assert diagnostics == {"dropped_code_prefix_categories": 1, "dropped_actor_alias_terms": 1, "dropped_actor_variant_terms": 1}


def test_work_similarity_candidates_propagates_bounded_explainable_two_hop_paths(monkeypatch) -> None:
    async def fake_index(**_kwargs):
        def edge(code: str, score: float, label: str):
            return {"code": code, "score": score, "relation_confidence": 0.9, "relation_types": ["actor"], "reasons": [{"type": "actor", "label": label, "weight": 1.0}]}
        return {
            "revision": "test", "linked_work_count": 4,
            "neighbors": {
                "AAA-001": [edge("BBB-001", 80, "演员甲")],
                "BBB-001": [edge("AAA-001", 80, "演员甲"), edge("CCC-001", 70, "系列乙")],
                "CCC-001": [edge("BBB-001", 70, "系列乙")],
                "DDD-001": [edge("CCC-001", 90, "负向演员")],
            },
            "candidates": {code: {"code": code, "title": code} for code in ("AAA-001", "BBB-001", "CCC-001", "DDD-001")},
        }

    monkeypatch.setattr(intelligence, "build_work_similarity_index", fake_index)
    result = asyncio.run(intelligence.work_similarity_candidates({"AAA-001": 1.0}, negative_seed_weights={"DDD-001": 1.0}))
    by_code = {item["code"]: item for item in result["items"]}

    assert by_code["BBB-001"]["neighbor_hop_count"] == 1
    assert by_code["CCC-001"]["neighbor_hop_count"] == 2
    assert by_code["CCC-001"]["neighbor_evidence"][0]["path"] == ["AAA-001", "BBB-001", "CCC-001"]
    assert by_code["CCC-001"]["neighbor_negative_score"] > 0
    assert result["propagation"] == {
        "max_hops": 2,
        "positive_restart_probability": 0.65,
        "negative_restart_probability": 0.8,
        "multi_hop_candidates": 1,
        "relation_weights": {},
        "seed_limit": 160,
    }


def test_equal_weight_seed_order_uses_stable_hash_not_code_prefix() -> None:
    weights = {f"AAA-{index:03d}": 0.75 for index in range(200)}
    selected = intelligence._rank_seed_weights(weights, 20)

    assert selected == intelligence._rank_seed_weights(dict(reversed(list(weights.items()))), 20)
    assert [code for code, _weight in selected] != sorted(weights)[:20]


def test_temporal_backtest_uses_historical_cutoffs_and_requires_cross_split_gain(monkeypatch) -> None:
    codes = [f"AAA-{index:03d}" for index in range(100)]

    async def fake_index(**_kwargs):
        neighbors = {code: [] for code in codes}
        for index, code in enumerate(codes[:-1]):
            neighbors[code].append({"code": codes[index + 1], "score": 90})
        return {
            "revision": "temporal-test",
            "neighbors": neighbors,
            "candidates": {code: {"code": code} for code in codes},
        }

    monkeypatch.setattr(intelligence, "build_work_similarity_index", fake_index)
    monkeypatch.setattr(intelligence, "_similarity_temporal_cache", {})
    start = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    timeline = {
        code: (start + dt.timedelta(days=index)).isoformat().replace("+00:00", ".0000000Z")
        for index, code in enumerate(codes)
    }
    result = asyncio.run(intelligence.work_similarity_temporal_backtest(
        timeline, target_limit=80, minimum_history=10,
    ))

    assert result["timeline_works"] == 100
    assert result["evaluated"] == 71
    assert result["split"] == {"train": 49, "validation": 22}
    assert result["policies"]["durable"]["overall"]["hit_at_20"] == 1.0
    assert result["policies"]["temporal"]["overall"]["hit_at_20"] == 1.0
    assert result["recommended_policy"] == "durable"


def test_work_similarity_recall_evaluation_reports_leave_one_out_metrics(monkeypatch) -> None:
    def edge(code: str, score: float, relation: str = "actor") -> dict:
        return {"code": code, "score": score, "relation_types": [relation]}

    async def fake_index(**_kwargs):
        return {
            "revision": "evaluation-test",
            "neighbors": {
                "AAA-001": [edge("BBB-001", 90), edge("XXX-001", 80, "category")],
                "BBB-001": [edge("AAA-001", 90), edge("CCC-001", 70)],
                "CCC-001": [edge("BBB-001", 70)],
                "XXX-001": [edge("AAA-001", 80, "category")],
            },
            "candidates": {code: {"code": code} for code in ("AAA-001", "BBB-001", "CCC-001", "DDD-001", "XXX-001")},
        }

    monkeypatch.setattr(intelligence, "build_work_similarity_index", fake_index)
    monkeypatch.setattr(intelligence, "_similarity_evaluation_cache", {})
    result = asyncio.run(intelligence.work_similarity_recall_evaluation(
        {"AAA-001", "BBB-001", "CCC-001", "DDD-001"},
        {"AAA-001": 1, "BBB-001": 1, "CCC-001": 1, "DDD-001": 1},
    ))

    assert result["evaluated"] == 4
    assert result["eligible"] == 3
    assert result["coverage"] == 0.75
    assert result["hit_rate"]["@10"] == 0.75
    assert result["mrr"] == 0.625
    assert result["median_rank"] == 1
    assert result["relation_hits_at_50"] == {"actor": 3}
    assert result["relation_counterfactual"]["recommended_weights"] == {}
    assert result["relation_counterfactual"]["recommended_delta"] == {"overall": 0.0, "train": 0.0, "validation": 0.0}
    assert result["sample_misses"] == [{
        "code": "DDD-001", "reason": "no_neighbor_path",
        "profile_gaps": ["actors", "categories", "title", "maker"],
    }]


def test_fused_work_profile_resolves_sources_and_preserves_image_candidates(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)
    profile = WorkProfile(
        code="TEST-100",
        title="TEST-100",
        original_title="原始标题",
        translated_title="中文标题",
        aliases=["别名"],
        facts={
            "weak-source": {"actors": ["演员甲"], "categories": ["剧情"], "cover_url": "http://example.test/raw.jpg", "maker": "弱片商"},
            "javdb": {"actors": ["演员甲", "演员乙"], "categories": ["人妻"], "cover_url": "/api/image?url=https%3A%2F%2Fcdn.test%2Fcover.jpg", "maker": "可信片商"},
        },
        source_evidence=[{"source": "weak-source", "confidence": 40}, {"source": "javdb", "confidence": 85}],
        confidence=85,
    )

    fused = intelligence.fused_work_profile(profile)

    assert fused["title"] == "中文标题"
    assert fused["actors"] == ["演员甲", "演员乙"]
    assert fused["categories"] == ["人妻", "剧情"]
    assert fused["maker"] == "可信片商"
    assert fused["cover_url"].startswith("/api/image?")
    assert len(fused["image_candidates"]) == 2
    assert fused["field_sources"]["cover_url"] == "javdb"
    assert all(fused["completeness"].values())


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


def test_actor_entities_use_mdc_ng_identity_and_preserve_source_aliases(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.knowledge.repository.canonical_actor_entity",
        lambda value: {
            "key": "mdc-ng:actor-1",
            "label": "吉沢明歩",
            "identity": "mdc-ng:actor-1",
            "alias": str(value),
        },
    )

    class FakeSession:
        def __init__(self) -> None:
            self.entity = None

        async def get(self, _model, _entity_id):
            return self.entity

        def add(self, entity) -> None:
            self.entity = entity

    async def scenario() -> None:
        db = FakeSession()
        repo = KnowledgeRepository(db)  # type: ignore[arg-type]
        first = await repo.upsert_entity("actor", "吉泽明步", "吉泽明步", source="javdb", data={})
        second = await repo.upsert_entity("actor", "吉澤明步", "吉澤明步", source="media-library", data={})
        assert first is second
        assert second.key == "mdc-ng:actor-1"
        assert second.label == "吉沢明歩"
        assert second.data["identity"] == "mdc-ng:actor-1"
        assert second.data["aliases"] == ["吉泽明步", "吉澤明步"]

    asyncio.run(scenario())


def test_preference_drift_unifies_mdc_ng_aliases(monkeypatch, tmp_path) -> None:
    mapping = tmp_path / "media_actor_mappings.json"
    mapping.write_text(json.dumps({"records": [{
        "id": "actor-1", "jp": "三宮つばき", "zh_cn": "三宫椿", "names": ["三宮つばき", "三宫椿"],
    }]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(intelligence, "data_path", lambda *_parts: mapping)
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)
    now = intelligence.utcnow()
    events = [
        SimpleNamespace(created_at=now - dt.timedelta(days=40), weight=1.0, actors=["三宫椿"], categories=["剧情"]),
        SimpleNamespace(created_at=now - dt.timedelta(days=39), weight=1.0, actors=["其他演员"], categories=["剧情"]),
        SimpleNamespace(created_at=now - dt.timedelta(days=3), weight=1.0, actors=["三宮つばき"], categories=["人妻"]),
        SimpleNamespace(created_at=now - dt.timedelta(days=2), weight=1.0, actors=["三宫椿"], categories=["人妻"]),
    ]

    trends = intelligence._preference_drift_model(events, window_days=30)

    assert "mdc-ng:actor-1" in trends["actors"]["deltas"]
    assert trends["actors"]["rising"][0]["name"] == "三宫椿"
    assert trends["categories"]["rising"][0]["name"] == "人妻"


def test_work_search_cache_invalidation_is_debounced(monkeypatch) -> None:
    monkeypatch.setattr(intelligence.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(intelligence, "_work_search_cache", {"documents": [{"code": "TEST-001"}], "expires_at": 1120.0})

    intelligence._invalidate_work_search_cache(delay_seconds=30)

    assert intelligence._work_search_cache["expires_at"] == 1030.0


def test_actor_alias_inference_requires_repeated_unambiguous_title_evidence(monkeypatch, tmp_path) -> None:
    (tmp_path / "media_actor_mappings.json").write_text(json.dumps({"records": [{
        "id": "actor-1", "jp": "吉沢明歩", "zh_cn": "吉沢明歩", "names": ["吉沢明歩"],
    }, {
        "id": "actor-2", "jp": "其他演员", "zh_cn": "其他演员", "names": ["其他演员"],
    }]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)
    profiles = [
        SimpleNamespace(code="AAA-001", title="中文标题 吉泽明步", original_title="", translated_title="", aliases=[], facts={"media-library": {"actors": ["吉沢明歩"]}}, confidence=90),
        SimpleNamespace(code="AAA-002", title="另一标题 吉泽明步", original_title="", translated_title="", aliases=[], facts={"media-library": {"actors": ["吉沢明歩"]}}, confidence=90),
        SimpleNamespace(code="AAA-003", title="证据不足 吉澤明步", original_title="", translated_title="", aliases=[], facts={"media-library": {"actors": ["吉沢明歩"]}}, confidence=90),
        SimpleNamespace(code="AAA-004", title="多人作品 吉泽明步", original_title="", translated_title="", aliases=[], facts={"media-library": {"actors": ["吉沢明歩", "其他演员"]}}, confidence=90),
    ]

    result = intelligence.infer_actor_aliases(profiles)
    learned = json.loads((tmp_path / "intelligence_actor_aliases.json").read_text(encoding="utf-8"))

    assert result["accepted"] == 1
    assert learned["accepted"][0]["alias"] == "吉泽明步"
    assert learned["accepted"][0]["work_count"] == 2
    assert learned["candidates"][0]["alias"] == "吉澤明步"
    assert intelligence.actor_identity_key("吉泽明步") == "mdc-ng:actor-1"


def test_preference_summary_uses_short_lived_memory_snapshot(monkeypatch) -> None:
    asyncio.run(_preference_summary_uses_short_lived_memory_snapshot(monkeypatch))


async def _preference_summary_uses_short_lived_memory_snapshot(monkeypatch) -> None:
    calls = 0

    async def fake_uncached(*, max_age_days: int):
        nonlocal calls
        calls += 1
        return {"event_count": calls, "max_age_days": max_age_days}

    monkeypatch.setattr(intelligence, "_preference_behavior_summary_uncached", fake_uncached)
    monkeypatch.setattr(intelligence, "_preference_summary_cache", {"expires_at": 0.0, "key": "", "value": None})

    first = await intelligence.preference_behavior_summary(max_age_days=30)
    second = await intelligence.preference_behavior_summary(max_age_days=30)

    assert first == second == {"event_count": 1, "max_age_days": 30}
    assert calls == 1


def test_resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch) -> None:
    asyncio.run(_resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch))


async def _resource_observations_build_shared_work_intelligence(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'intelligence.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(intelligence, "async_session_maker", sessions)
    monkeypatch.setattr(intelligence, "data_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(intelligence, "_actor_alias_cache", None)
    monkeypatch.setattr(intelligence, "_work_search_cache", {"expires_at": 0.0, "documents": []})
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
    searched = await intelligence.search_work_intelligence("测试演员 破解", limit=5)
    assert searched["match_mode"] == "all_terms"
    assert searched["items"][0]["code"] == "PRED-878"
    assert {item["kind"] for item in searched["items"][0]["match_evidence"]} == {"actor", "resource"}
    assert searched["items"][0]["resource_summary"]["has_cracked"] is True
    assert (await intelligence.record_search_intent("剧情"))["recorded"] is True
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
    search_learning = intelligence.search_intent_summary()["evaluation"]
    assert search_learning["eligible_events"] == 1
    assert search_learning["qualified_events"] == 1
    assert search_learning["verified_events"] == 1
    behavior = await intelligence.preference_behavior_summary()
    assert behavior["event_count"] == 3
    assert behavior["codes"]["PRED-878"] > 5.9
    assert behavior["actors"]["测试演员"] > 5.9
    assert behavior["code_stages"]["PRED-878"]["stage"] == "library_imported"
    assert behavior["code_stages"]["PRED-878"]["value"] == 1.0
    assert behavior["code_stages"]["PRED-878"]["verified"] is True
    assert "trends" in behavior
    assert behavior["revision"].startswith("3:")
    assert await intelligence.clear_preference_events(source="av-recommend") == 2
    assert (await intelligence.preference_behavior_summary())["event_count"] == 1
    assert await intelligence.clear_preference_events(source="subscription-core") == 1
    await engine.dispose()
