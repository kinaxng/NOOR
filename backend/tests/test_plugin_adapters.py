from __future__ import annotations

import pytest

from app.plugins import adapters
from app.plugins.contracts import PluginManifest


class FakeResponse:
    status_code = 200
    content = b"""<?xml version='1.0'?>
    <rss><channel><item>
      <title>AAA-001</title>
      <link>https://example.test/items/1</link>
      <guid>item-1</guid>
      <pubDate>Fri, 21 Aug 2026 08:00:00 GMT</pubDate>
      <description>Demo item</description>
      <enclosure url='https://example.test/items/1.torrent' />
    </item></channel></rss>"""

    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        assert url == "https://example.test/rss"
        return FakeResponse()


@pytest.mark.asyncio
async def test_generic_rss_adapter_returns_download_fields(monkeypatch):
    monkeypatch.setattr(adapters.httpx, "AsyncClient", FakeClient)
    manifest = PluginManifest(id="rss-demo", name="RSS Demo", type="rss_source")

    result = await adapters.fetch_rss_items(manifest, {"rss_url": "https://example.test/rss"})

    assert result["total"] == 1
    assert result["items"][0]["id"] == "item-1"
    assert result["items"][0]["download_url"] == "https://example.test/items/1.torrent"
    assert result["items"][0]["provider"] == "rss-demo"


@pytest.mark.asyncio
async def test_generic_downloader_adapter_fails_closed():
    with pytest.raises(ValueError, match="missing submit_download handler"):
        await adapters.submit_download(PluginManifest(id="demo"), {}, {"url": "https://example.test"})


@pytest.mark.asyncio
async def test_generic_dashboard_widget_uses_manifest_contribution():
    manifest = PluginManifest(
        id="demo",
        name="Demo",
        contributions={"dashboard_widget": {"key": "demo-card", "title": "Demo Card"}},
    )
    widget = await adapters.build_widget(manifest, {})
    assert widget is not None
    assert widget.plugin_id == "demo"
    assert widget.key == "demo-card"
