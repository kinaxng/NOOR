from __future__ import annotations

import pytest

from plugins.gfriends import backend as gfriends


def test_payload_name_candidates_preserves_spaced_actor_names():
    names = gfriends._payload_name_candidates(["倉本 すみれ", "Nozomi Kuramoto,仓本堇"])

    assert "倉本 すみれ" in names
    assert "Nozomi Kuramoto" in names
    assert "仓本堇" in names
    assert "すみれ" not in names
    assert "Kuramoto" not in names

@pytest.mark.asyncio
async def test_disabled_gfriends_avatar_action_returns_ok_false(monkeypatch):
    from app.api import plugins as plugin_api
    from app.plugins.runtime import runtime

    monkeypatch.setattr(runtime, "_manifests", {"gfriends": {}})
    monkeypatch.setattr(runtime, "is_enabled", lambda plugin_id: False)

    body = plugin_api.PluginActionPayload(payload={"name": "测试"})
    result = await plugin_api._handle_plugin_action("gfriends", "resolve", body, None)

    assert result == {
        "ok": False,
        "disabled": True,
        "message": "Gfriends 插件未启用，头像辅助不可用",
        "items": None,
    }
