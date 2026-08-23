from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.endpoints import media_library
from app.api.endpoints.media_library_item_detail import (
    get_item_impl,
    parse_nfo_file_impl,
)


def test_parse_nfo_file_impl_reads_nested_actor_cdata(tmp_path: Path):
    nfo_path = tmp_path / "ABC-123.nfo"
    nfo_path.write_text(
        """
<movie>
  <title><![CDATA[ABC-123 中文标题]]></title>
  <originaltitle><![CDATA[ABC-123 日本語タイトル]]></originaltitle>
  <actor><name><![CDATA[波多野結衣]]></name><role><![CDATA[主演]]></role></actor>
  <actor><name><![CDATA[水卜さくら]]></name><role>女優</role></actor>
  <actor><name>  </name><role>ignored</role></actor>
</movie>
""".strip(),
        encoding="utf-8",
    )

    parsed = parse_nfo_file_impl(str(nfo_path))

    assert parsed["title"] == "ABC-123 中文标题"
    assert parsed["originaltitle"] == "ABC-123 日本語タイトル"
    assert parsed["actors"] == [
        {"name": "波多野結衣", "role": "主演"},
        {"name": "水卜さくら", "role": "女優"},
    ]


def test_media_library_exposes_legacy_helper_names(tmp_path: Path):
    assert media_library._normalize_code_token(" abc-123") == "ABC123"
    assert media_library._extract_code_from_path("/media/AB-123.mp4") == "AB-123"
    assert media_library._item_matches_filter({"tags": {"is_cracked": True}}, "cracked") is True
    assert media_library._item_matches_filter({"tags": {}}, "cracked") is False

    payload = media_library._paginate_filter(
        [
            {"tags": {"is_cracked": True}, "name": "ABC-123"},
            {"tags": {}, "name": "ABC-456"},
        ],
        "cracked",
        None,
        0,
        10,
    )
    assert payload == {"items": [{"tags": {"is_cracked": True}, "name": "ABC-123"}], "total": 1}

    movie = tmp_path / "ABC-123" / "a.mp4"
    movie.parent.mkdir(parents=True)
    assert media_library._parent_is_code_bucket(movie, "ABC-123") is True
    assert media_library._is_under_roots(movie, [tmp_path]) is True
    assert media_library._item_variant_penalty({"path": str(movie), "tags": {"is_cracked": True}}) == 40


@pytest.mark.asyncio
async def test_get_item_impl_uses_local_nfo_and_mapped_path(tmp_path: Path):
    movie_path = tmp_path / "ABC-123.mp4"
    nfo_path = tmp_path / "ABC-123.nfo"
    nfo_path.write_text(
        """
<movie>
  <title>ABC-123 Title</title>
  <num>ABC-123</num>
  <actor><name><![CDATA[波多野結衣]]></name></actor>
</movie>
""".strip(),
        encoding="utf-8",
    )

    item_data = {
        "Id": "123",
        "Name": "ABC-123",
        "MediaType": "Video",
        "ParentId": "folder-1",
        "DateCreated": "2026-01-03T00:00:00.0000000Z",
        "PremiereDate": "2026-01-02T00:00:00.0000000Z",
        "Studios": [{"Name": "Studio"}],
        "Genres": ["ドラマ"],
        "ImageTags": {"Primary": "poster-tag"},
        "BackdropImageTags": ["backdrop-tag"],
        "People": [{"Name": "演员A", "Type": "Actor", "Role": "Actor"}],
        "MediaSources": [{
            "Type": "Default",
            "Id": "source-1",
            "Container": "mp4",
            "Path": "/data/media/ABC-123.mp4",
        }],
    }

    class Response:
        status_code = 200

        def json(self):
            return item_data

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *args, **kwargs):
            return Response()

    class Httpx:
        AsyncClient = Client

    config = {"user_id": "user-1", "api_key": "secret"}

    def map_path(path, cfg):
        return str(tmp_path / Path(str(path).replace("/data/media/", "")))

    async def fake_siblings(cfg, parent_id, current_id):
        return []

    item = await get_item_impl(
        config,
        "123",
        httpx_module=Httpx,
        server_url_fn=lambda cfg: "http://emby",
        headers_fn=lambda api_key: {"X-Emby-Token": api_key},
        map_path_fn=map_path,
        parse_tags_fn=lambda name, studios, path: {"is_cracked": False},
        get_siblings_fn=fake_siblings,
        get_main_nfo_fn=lambda file_path: str(nfo_path) if file_path == str(movie_path) else None,
    )

    assert item is not None
    assert item["file_path"] == str(movie_path)
    assert item["main_nfo"] == str(nfo_path)
    assert item["nfo"]["title"] == "ABC-123 Title"
    assert item["nfo"]["actors"] == [{"name": "波多野結衣"}]
    assert item["actors"] == [{"name": "演员A", "role": "Actor"}]
    assert item["variant_count"] == 1
    assert item["poster_path"] == "http://emby/emby/Items/123/Images/Primary?tag=poster-tag"
    assert item["stream_url"] == "/api/media-library/stream/123?media_source_id=source-1&container=mp4"


@pytest.mark.asyncio
async def test_media_library_items_returns_503_when_adapter_not_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media_library, "_load_config", lambda: {})

    with pytest.raises(HTTPException) as exc_info:
        await media_library.get_items()

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_media_library_items_returns_502_on_upstream_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        media_library,
        "_load_config",
        lambda: {"server_url": "http://emby", "api_key": "key", "enabled_library_ids": "1"},
    )

    async def fail_list_items(config, library_id, limit=50, offset=0, **kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(media_library, "_list_items", fail_list_items)

    with pytest.raises(HTTPException) as exc_info:
        await media_library.get_items()

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_media_library_hardlink_groups_response_contract(monkeypatch: pytest.MonkeyPatch):
    groups = [{
        "code": "ABC-123",
        "entries": [{
            "source_path": "/source/abc.mp4",
            "hardlink_paths": ["/hard/abc.mp4"],
        }],
    }]
    monkeypatch.setattr(media_library, "_load_hardlink_groups", lambda: groups)
    monkeypatch.setattr(media_library, "_hardlink_groups_last_scanned_at", lambda: "2026-01-01T00:00:00+00:00")

    payload = await media_library.get_hardlink_groups()

    assert payload["last_scanned_at"] == "2026-01-01T00:00:00+00:00"
    assert payload["summary"]["total_groups"] == 1
    assert payload["summary"]["total_entries"] == 1
    assert payload["groups"][0]["status"] == "healthy"


@pytest.mark.asyncio
async def test_media_library_hardlink_scan_saves_groups(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        media_library,
        "_load_config",
        lambda: {"scan_groups": [{"name": "av", "source_dir": "/src", "hardlink_dir": "/dst"}]},
    )
    groups = [{
        "code": "ABC-123",
        "entries": [{
            "source_path": "/src/abc.mp4",
            "hardlink_paths": ["/dst/abc.mp4"],
        }],
    }]

    async def fake_build():
        return groups

    saved: list[list[dict]] = []
    monkeypatch.setattr(media_library, "_build_hardlink_groups", fake_build)
    monkeypatch.setattr(media_library, "_save_hardlink_groups", lambda value: saved.append(value))
    monkeypatch.setattr(media_library, "_hardlink_groups_last_scanned_at", lambda: None)

    payload = await media_library.scan_hardlinks()

    assert saved == [groups]
    assert payload["summary"]["total_groups"] == 1
    assert payload["summary"]["total_hardlinks"] == 1
