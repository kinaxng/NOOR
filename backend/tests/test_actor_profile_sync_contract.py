from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints import actors


def test_actor_profile_update_does_not_save_override_when_emby_sync_fails(monkeypatch, tmp_path):
    saved: dict[str, dict] = {}

    monkeypatch.setattr(actors, "_require_config", lambda: {"server_url": "http://emby.test", "api_key": "k"})
    monkeypatch.setattr(actors, "_profile_overrides_path", lambda: tmp_path / "actor_profile_overrides.json")

    async def fake_raw_actor(config, actor_id):
        return {"Id": actor_id, "Name": "旧名", "ProviderIds": {}, "ImageTags": {}}

    async def fake_actor_profile(config, actor_id, lang):
        return {"id": actor_id, "name": "旧名"}

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("emby down")

    monkeypatch.setattr(actors, "_raw_actor", fake_raw_actor)
    monkeypatch.setattr(actors, "_actor_profile", fake_actor_profile)
    monkeypatch.setattr(actors.httpx, "AsyncClient", lambda *args, **kwargs: FailingClient())
    monkeypatch.setattr(actors, "_save_profile_overrides", lambda payload: saved.update(payload))

    with pytest.raises(HTTPException) as exc:
        actors.asyncio.run(actors.update_actor("123", actors.ActorProfileUpdateRequest(name="新名"), "zh-CN"))

    assert exc.value.status_code == 502
    assert saved == {}


def test_actor_profile_update_allows_noor_only_identity_override(monkeypatch, tmp_path):
    monkeypatch.setattr(actors, "_require_config", lambda: {"server_url": "http://emby.test", "api_key": "k"})
    monkeypatch.setattr(actors, "_profile_overrides_path", lambda: tmp_path / "actor_profile_overrides.json")

    async def fake_raw_actor(config, actor_id):
        return {"Id": actor_id, "Name": "倉本すみれ", "ProviderIds": {}, "ImageTags": {}}

    async def fake_actor_profile(config, actor_id, lang):
        return {"id": actor_id, "name": "倉本すみれ"}

    monkeypatch.setattr(actors, "_raw_actor", fake_raw_actor)
    monkeypatch.setattr(actors, "_actor_profile", fake_actor_profile)

    result = actors.asyncio.run(actors.update_actor("123", actors.ActorProfileUpdateRequest(zh_cn_name="仓本堇"), "zh-CN"))

    assert result["ok"] is True
    assert result["synced"] is False
    payload = actors._load_profile_overrides()
    assert payload["123"]["identity_names"]["zh_cn"] == "仓本堇"


def test_actor_mapping_matches_reports_reviewable_non_candidates(monkeypatch):
    async def fake_list_actors(config, **kwargs):
        return [
            {"id": "1", "name": "加瀬ななほ", "sort_name": "加瀬ななほ", "tmdb_id": "", "image_url": ""},
            {"id": "2", "name": "未映射演员", "sort_name": "未映射演员", "tmdb_id": "12345", "image_url": ""},
        ], 2

    monkeypatch.setattr(actors, "_require_config", lambda: {})
    monkeypatch.setattr(actors, "_list_actors", fake_list_actors)
    monkeypatch.setattr(actors, "_mapping_records", lambda config: [{"id": "m1", "jp": "加瀬ななほ", "zh_cn": "加濑七穗", "zh_tw": "", "names": ["加瀬ななほ", "加濑七穗"], "tmdb_id": "", "verified": True}])
    monkeypatch.setattr(actors, "_mapping_index", lambda config: {"加瀬ななほ": {"id": "m1", "jp": "加瀬ななほ", "zh_cn": "加濑七穗", "zh_tw": "", "names": ["加瀬ななほ", "加濑七穗"], "tmdb_id": "", "verified": True}})

    result = actors.asyncio.run(actors.actor_mapping_matches(only_candidates=True, lang="zh-CN"))

    assert result["groups"] == []
    assert result["rejected_actors"] == 2
    assert {item["rejected_reason"] for item in result["rejected_matches"]} == {"single_mapped_actor", "unmatched_emby_actor"}


def test_actor_mapping_path_accepts_legacy_saved_root(monkeypatch, tmp_path):
    root = tmp_path / "mdc-ng"
    expected = root / actors.MDC_NG_ACTOR_MAPPING_RELATIVE_PATH
    expected.parent.mkdir(parents=True)
    expected.write_text("<actors />", encoding="utf-8")
    settings_path = tmp_path / "actor_management_settings.json"
    settings_path.write_text(
        actors.json.dumps({"mdc_ng_path": str(root)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(actors, "_mapping_settings_path", lambda: settings_path)

    assert actors._configured_mapping_root({}) == str(root)
    assert actors._mapping_path({}) == expected


def test_actor_mapping_auto_update_schedules_stale_source(monkeypatch, tmp_path):
    root = tmp_path / "mdc-ng"
    monkeypatch.setattr(actors, "get_settings", lambda: SimpleNamespace(actor_mapping_auto_update=True))
    monkeypatch.setattr(actors.media, "_load_config", lambda: {"mdc_ng_actor_mapping_path": str(root)})
    monkeypatch.setattr(actors, "_load_json", lambda path, default: {})
    monkeypatch.setattr(actors, "_mapping_auto_update_task", None)
    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return SimpleNamespace(done=lambda: False)

    monkeypatch.setattr(actors.asyncio, "create_task", fake_create_task)

    actors._maybe_schedule_actor_mapping_auto_update()

    assert len(scheduled) == 1


def test_actor_mapping_matches_excludes_persisted_ghost_from_candidates(monkeypatch, tmp_path):
    record = {
        "id": "m1",
        "jp": "吉岡ひより",
        "zh_cn": "吉冈日和",
        "zh_tw": "吉岡日和",
        "names": ["吉岡ひより", "吉冈日和"],
        "tmdb_id": "2669350",
        "verified": True,
    }

    async def fake_list_actors(config, **kwargs):
        return [
            {"id": "active", "name": "吉冈日和", "sort_name": "吉岡ひより", "tmdb_id": "2669350", "image_url": "avatar"},
            {"id": "ghost", "name": "吉岡ひより", "sort_name": "吉岡ひより", "tmdb_id": "2669350", "image_url": "avatar"},
        ], 2

    monkeypatch.setattr(actors, "_require_config", lambda: {})
    monkeypatch.setattr(actors, "_list_actors", fake_list_actors)
    monkeypatch.setattr(actors, "_mapping_records", lambda config: [record])
    monkeypatch.setattr(actors, "_mapping_index", lambda config: {actors._normalize_name(name): record for name in record["names"]})
    monkeypatch.setattr(actors, "_actor_merge_ignored_ghosts_path", lambda: tmp_path / "ignored.json")
    actors._save_actor_merge_ignored_ghosts({"ghost"})

    result = actors.asyncio.run(actors.actor_mapping_matches(only_candidates=True, lang="zh-CN"))

    assert result["groups"] == []
    assert result["active_actors"] == 1
    ignored = [item for item in result["rejected_matches"] if item["rejected_reason"] == "ignored_person"]
    assert [item["id"] for item in ignored] == ["ghost"]


def test_actor_merge_ignored_ghost_storage_accepts_legacy_list(monkeypatch, tmp_path):
    path = tmp_path / "ignored.json"
    path.write_text('["12", "34"]', encoding="utf-8")
    monkeypatch.setattr(actors, "_actor_merge_ignored_ghosts_path", lambda: path)

    assert actors._load_actor_merge_ignored_ghosts() == {"12", "34"}

    actors._save_actor_merge_ignored_ghosts({"34", "56"})
    assert actors._load_actor_merge_ignored_ghosts() == {"34", "56"}


def test_actor_merge_people_reuses_selected_target_and_removes_sources():
    item = {
        "Id": "movie-1",
        "People": [
            {"Id": "source-1", "Name": "旧名一", "Type": "Actor", "PrimaryImageTag": "old"},
            {"Id": "target-1", "Name": "目标名", "Type": "Actor", "PrimaryImageTag": "target"},
            {"Id": "director-1", "Name": "导演", "Type": "Director"},
            {"Id": "source-2", "Name": "旧名二", "Type": "Actor"},
        ],
    }

    updated, changed = actors._actor_merge_apply_people(
        item,
        source_actor_ids={"source-1", "source-2"},
        target_actor_id="target-1",
        target_name="目标名",
    )

    assert {entry["id"] for entry in changed} == {"source-1", "source-2"}
    assert updated["People"] == [
        {"Id": "target-1", "Name": "目标名", "Type": "Actor", "PrimaryImageTag": "target"},
        {"Id": "director-1", "Name": "导演", "Type": "Director"},
    ]


def test_actor_merge_people_creates_selected_target_when_missing():
    updated, changed = actors._actor_merge_apply_people(
        {"People": [{"Id": "source-1", "Name": "旧名", "Type": "Actor"}]},
        source_actor_ids={"source-1"},
        target_actor_id="target-1",
        target_name="目标名",
    )

    assert changed[0]["id"] == "source-1"
    assert updated["People"] == [{"Id": "target-1", "Name": "目标名", "Type": "Actor"}]


def test_actor_mapping_batch_discovers_candidates_and_skips_conflicts(monkeypatch):
    monkeypatch.setattr(actors, "_require_config", lambda: {"server_url": "http://emby", "api_key": "k"})

    async def fake_matches(**kwargs):
        return {
            "groups": [
                {"mapping_id": "safe", "target_actor_id": "target-1", "display_name": "安全组", "has_tmdb_conflict": False},
                {"mapping_id": "conflict", "target_actor_id": "target-2", "display_name": "冲突组", "has_tmdb_conflict": True},
            ]
        }

    executed: list[str] = []

    async def fake_execute(config, req, lang):
        executed.append(req.mapping_id)
        return {"ok": True, "updated_count": 2, "deleted_actor_count": 1, "delete_failed_actor_ids": []}

    monkeypatch.setattr(actors, "actor_mapping_matches", fake_matches)
    monkeypatch.setattr(actors, "_execute_merge", fake_execute)

    result = actors.asyncio.run(actors.execute_actor_mapping_batch(actors.ActorMappingMergeBatchRequest(), "zh-CN"))

    assert executed == ["safe"]
    assert result["candidate_count"] == 2
    assert result["executed_count"] == 1
    assert result["skipped"] == [{"mapping_id": "conflict", "name": "冲突组", "reason": "tmdb_conflict"}]


def test_tmdb_proposal_imports_translated_names_aliases_and_social_links():
    person = {
        "id": 3453337,
        "name": "倉本すみれ",
        "also_known_as": ["仓本堇", "仓本菫", "Kuramoto Sumire"],
        "biography": "人物简介\nInstagram: https://www.instagram.com/example/\n官网: https://example.test/",
        "profile_path": "/portrait.jpg",
        "gender": 1,
        "external_ids": {
            "imdb_id": "nm123",
            "twitter_id": "@example_x",
            "instagram_id": "example_ins",
            "tiktok_id": "@example_tt",
            "youtube_id": "@example_yt",
            "wikidata_id": "Q123",
        },
        "translations": {
            "translations": [
                {"iso_639_1": "ja", "iso_3166_1": "JP", "data": {"name": "倉本すみれ"}},
                {"iso_639_1": "zh", "iso_3166_1": "CN", "data": {"name": "仓本堇"}},
                {"iso_639_1": "zh", "iso_3166_1": "TW", "data": {"name": "倉本堇"}},
            ]
        },
    }

    proposal = actors._tmdb_proposal(person, {"provider_ids": {}, "external_urls": {}})

    assert proposal["jp_name"] == "倉本すみれ"
    assert proposal["zh_cn_name"] == "仓本堇"
    assert proposal["zh_tw_name"] == "倉本堇"
    assert proposal["aliases"] == ["仓本菫", "Kuramoto Sumire"]
    assert proposal["overview"] == "人物简介"
    assert proposal["gender"] == "female"
    assert proposal["provider_ids"]["TikTok"] == "example_tt"
    assert proposal["provider_ids"]["Wikidata"] == "Q123"
    assert proposal["external_urls"]["tiktok"] == "https://www.tiktok.com/@example_tt"
    assert proposal["external_urls"]["homepage"] == "https://example.test/"


def test_actor_delete_diagnostics_reports_related_items_and_provider_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(actors, "_profile_overrides_path", lambda: tmp_path / "actor_profile_overrides.json")

    class Response:
        def __init__(self, status_code=200, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text
            self.is_error = status_code >= 400

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.is_error:
                raise RuntimeError(f"HTTP {self.status_code}")

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            if "/emby/Items/123" in url:
                return Response(payload={"Id": "123", "Name": "旧演员", "SortName": "旧演员", "CanDelete": False, "ProviderIds": {"Tmdb": "345"}})
            return Response(payload={"TotalRecordCount": 1, "Items": [{"Id": "m1", "Name": "影片", "Type": "Movie", "Path": "/data/av/m1.mp4", "ProviderIds": {"Javdb": "ABC-001"}}]})

    monkeypatch.setattr(actors.httpx, "AsyncClient", lambda *args, **kwargs: Client())

    result = actors.asyncio.run(actors._actor_delete_diagnostics({"server_url": "http://emby.test", "api_key": "k"}, "123"))

    assert result["person_exists"] is True
    assert result["provider_ids"] == {"Tmdb": "345"}
    assert result["related_total"] == 1
    assert result["related_sample"][0]["name"] == "影片"
    assert result["can_clean_delete"] is False
    assert set(result["blockers"]) == {"related_items", "can_delete_false"}


def test_actor_delete_failure_includes_diagnostics(monkeypatch, tmp_path):
    monkeypatch.setattr(actors, "_require_config", lambda: {"server_url": "http://emby.test", "api_key": "k"})
    monkeypatch.setattr(actors, "_profile_overrides_path", lambda: tmp_path / "actor_profile_overrides.json")

    async def fake_diagnostics(config, actor_id):
        return {"ok": True, "actor_id": actor_id, "person_exists": True, "related_total": 0, "blockers": []}

    class Response:
        status_code = 500
        text = "locked"
        is_error = True

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def delete(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(actors, "_actor_delete_diagnostics", fake_diagnostics)
    monkeypatch.setattr(actors.httpx, "AsyncClient", lambda *args, **kwargs: Client())

    with pytest.raises(HTTPException) as exc:
        actors.asyncio.run(actors.delete_actor("123"))

    assert exc.value.status_code == 502
    assert exc.value.detail["status_code"] == 500
    assert exc.value.detail["body"] == "locked"
    assert exc.value.detail["diagnostics_before"]["actor_id"] == "123"
    assert exc.value.detail["diagnostics_after"]["actor_id"] == "123"
