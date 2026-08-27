from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.plugins import market


class FakeResponse:
    def __init__(self, *, payload=None, content: bytes = b"", status_code: int = 200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise market.httpx.HTTPStatusError("failed", request=None, response=None)

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses, calls, **kwargs):
        self.responses = responses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        self.calls.append(url)
        response = self.responses.get(url)
        return response if response is not None else FakeResponse(status_code=404)


def client_factory(responses, calls):
    return lambda **kwargs: FakeClient(responses, calls, **kwargs)


@pytest.mark.asyncio
async def test_fetch_repo_index_supports_github_repository(monkeypatch):
    calls: list[str] = []
    url = "https://raw.githubusercontent.com/acme/noor-plugins/main/plugins.json"
    monkeypatch.setattr(
        market.httpx,
        "AsyncClient",
        client_factory({url: FakeResponse(payload={"plugins": [{"id": "demo"}]})}, calls),
    )

    assert await market.fetch_repo_index("https://github.com/acme/noor-plugins") == [{"id": "demo"}]
    assert url in calls


@pytest.mark.asyncio
async def test_install_market_item_extracts_matching_plugin(monkeypatch, tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("repo-main/plugins/demo/plugin.json", json.dumps({"id": "demo", "name": "Demo"}))
        zf.writestr("repo-main/plugins/demo/backend.py", "VALUE = 1\n")

    calls: list[str] = []
    archive_url = "https://example.test/demo.zip"
    monkeypatch.setattr(
        market.httpx,
        "AsyncClient",
        client_factory({archive_url: FakeResponse(content=archive.getvalue())}, calls),
    )
    monkeypatch.setattr(market, "PLUGINS_DIR", tmp_path)

    target = await market.install_from_market_item({"id": "demo", "archive_url": archive_url})

    assert target == tmp_path / "demo"
    assert json.loads((target / "plugin.json").read_text())["id"] == "demo"
    assert (target / "backend.py").read_text() == "VALUE = 1\n"


def test_safe_extract_rejects_parent_traversal(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../outside.txt", "unsafe")
    with zipfile.ZipFile(io.BytesIO(archive.getvalue())) as zf:
        with pytest.raises(market.MarketError, match="unsafe path"):
            market._safe_extract(zf, tmp_path)
