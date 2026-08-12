from __future__ import annotations

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
