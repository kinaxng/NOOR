from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import media_library_recovery


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(media_library_recovery.router)
    return app


def test_recovery_items_response_includes_pagination(monkeypatch):
    monkeypatch.setattr(media_library_recovery, "_config", lambda value=None: {"server_url": "http://emby", "api_key": "key", "user_id": "u"})

    async def fake_fetch_items(config, *, library_id, limit, offset):
        return ([{"id": "1", "name": "AAA-001", "tags": {}}], 12)

    monkeypatch.setattr(media_library_recovery, "_fetch_items", fake_fetch_items)

    response = TestClient(_app()).get("/api/media-library/items?limit=1&offset=3")

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": "1", "name": "AAA-001", "tags": {}}],
        "total": 12,
        "offset": 3,
        "limit": 1,
    }


def test_recovery_item_detail_includes_panel_contract(monkeypatch, tmp_path):
    nfo_path = tmp_path / "AAA-001.nfo"
    nfo_path.write_text(
        """
<movie>
  <title>AAA-001 中文标题</title>
  <originaltitle>AAA-001 日本語タイトル</originaltitle>
  <num>AAA-001</num>
  <year>2026</year>
  <premiered>2026-01-02</premiered>
  <studio>NOOR Studio</studio>
  <genre>制服</genre>
  <tag>邻居</tag>
</movie>
""".strip(),
        encoding="utf-8",
    )
    movie_path = str(tmp_path / "AAA-001.mp4")
    sibling_path = str(tmp_path / "AAA-001-C.mp4")
    monkeypatch.setattr(
        media_library_recovery,
        "_config",
        lambda value=None: {"server_url": "http://emby", "api_key": "key", "user_id": "u"},
    )

    async def fake_fetch_item_raw(config, item_id):
        assert item_id == "123"
        return {
            "Id": "123",
            "Name": "AAA-001",
            "Type": "Movie",
            "MediaType": "Video",
            "Path": movie_path,
            "ParentId": "folder-1",
            "DateCreated": "2026-01-03T00:00:00.0000000Z",
            "PremiereDate": "2026-01-02T00:00:00.0000000Z",
            "OriginalTitle": "AAA-001 Original",
            "Overview": "overview",
            "Genres": ["ドラマ"],
            "Studios": [{"Name": "NOOR Studio"}],
            "ImageTags": {"Primary": "poster-tag", "Thumb": "thumb-tag"},
            "BackdropImageTags": ["backdrop-tag"],
            "ProviderIds": {"Tmdb": "345"},
            "People": [
                {"Name": "演员A", "Type": "Actor", "Role": "Actor"},
                {"Name": "导演A", "Type": "Director"},
            ],
            "MediaSources": [{"Type": "Default", "Path": movie_path}],
        }

    async def fake_fetch_sibling_raws(config, parent_id, current_id):
        assert parent_id == "folder-1"
        assert current_id == "123"
        return [
            {
                "Id": "124",
                "Name": "AAA-001-C",
                "Type": "Movie",
                "MediaType": "Video",
                "Path": sibling_path,
                "MediaSources": [{"Type": "Default", "Path": sibling_path}],
            }
        ]

    monkeypatch.setattr(media_library_recovery, "_fetch_item_raw", fake_fetch_item_raw)
    monkeypatch.setattr(media_library_recovery, "_fetch_sibling_raws", fake_fetch_sibling_raws)

    response = TestClient(_app()).get("/api/media-library/item/123")

    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == movie_path
    assert data["stream_url"] == "/api/media-library/stream/123?container=mp4"
    assert data["poster_path"] == "http://emby/emby/Items/123/Images/Primary?tag=poster-tag"
    assert data["backdrop_path"] == "http://emby/emby/Items/123/Images/Backdrop?tag=backdrop-tag"
    assert data["actors"] == [{"name": "演员A", "role": "Actor"}]
    assert data["directors"] == ["导演A"]
    assert data["studios"] == ["NOOR Studio"]
    assert data["genres"] == ["ドラマ"]
    assert data["provider_ids"] == {"Tmdb": "345"}
    assert data["variant_count"] == 2
    assert data["siblings"][0]["file_path"] == sibling_path
    assert data["siblings"][0]["stream_url"] == "/api/media-library/stream/124?container=mp4"
    assert data["siblings"][0]["tags"]["has_chinese"] is True
    assert data["main_nfo"] == str(nfo_path)
    assert data["nfo"]["title"] == "AAA-001 中文标题"
    assert data["nfo"]["genres"] == ["制服", "邻居"]


def test_recovery_item_detail_returns_404(monkeypatch):
    monkeypatch.setattr(
        media_library_recovery,
        "_config",
        lambda value=None: {"server_url": "http://emby", "api_key": "key", "user_id": "u"},
    )

    async def fake_fetch_item_raw(config, item_id):
        return None

    monkeypatch.setattr(media_library_recovery, "_fetch_item_raw", fake_fetch_item_raw)

    response = TestClient(_app()).get("/api/media-library/item/missing")

    assert response.status_code == 404
