from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

spec = importlib.util.spec_from_file_location("xunlei_remote_backend", ROOT / "plugins/xunlei-remote/backend.py")
xunlei_backend = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(xunlei_backend)


class FakeResponse:
    def __init__(self, data=None, text: str = "", status_code: int = 200):
        self._data = data if data is not None else {}
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}: {self.text}")


class FakeClient:
    def __init__(self, paths=None):
        self.paths = paths or []
        self.gets: list[dict] = []
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers=None, params=None):
        self.gets.append({"url": url, "headers": headers or {}, "params": params or {}})
        if "user/me" in url:
            return FakeResponse({"sub": "user-1", "name": "测试用户"})
        if "download_paths" in url:
            return FakeResponse({"paths": self.paths})
        return FakeResponse({})

    async def post(self, url, headers=None, params=None, content=None):
        self.posts.append({"url": url, "headers": headers or {}, "params": params or {}, "content": content})
        return FakeResponse({})


def _expired_mobile_token() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": 1, "aud": "mobile"}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


def test_account_constants_and_captcha_sign():
    config = {"account_device_id": "device-abc"}
    sign = xunlei_backend._account_captcha_sign(config, "123")
    value = f"{xunlei_backend.ACCOUNT_CLIENT_ID}2.9.0pan.xunlei.comdevice-abc123"
    for item in xunlei_backend.ACCOUNT_ALGORITHMS:
        value = hashlib.md5(f"{value}{item['salt']}".encode()).hexdigest()
    assert sign == f"1.{value}"
    assert xunlei_backend.ACCOUNT_CLIENT_ID


def test_account_headers_strips_bearer_and_sets_captcha():
    config = {
        "account_access_token": "Bearer abc123",
        "account_device_id": "device-abc",
    }
    headers = xunlei_backend._account_headers(config, captcha_token="captcha-x")
    assert headers["Authorization"] == "Bearer abc123"
    assert headers["x-captcha-token"] == "captcha-x"
    assert headers["x-client-id"] == xunlei_backend.ACCOUNT_CLIENT_ID
    assert headers["x-device-id"] == "device-abc"


def test_account_user_me_uses_user_api():
    client = FakeClient()
    result = asyncio.run(xunlei_backend._account_user_me({"account_access_token": "abc"}, client))
    assert result["user"]["sub"] == "user-1"
    assert client.gets[0]["url"] == f"{xunlei_backend.ACCOUNT_USER_BASE}/v1/user/me"
    assert client.gets[0]["headers"]["Authorization"] == "Bearer abc"


def test_mobile_status_reports_expired_jwt():
    config = {
        "mobile_access_token": _expired_mobile_token(),
        "mobile_captcha_token": "captcha",
        "mobile_device_id": "device",
        "mobile_parent_folder_id": "folder",
    }
    client = FakeClient()
    result = asyncio.run(xunlei_backend._mobile_status(config, client))["mobile"]
    assert result["configured"] is True
    assert result["token_expired"] is True
    assert result["connected"] is False


def test_restore_candidates_scans_only_residual_files(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    residual = root / "ABCD-123.xtld"
    residual.write_text("partial", encoding="utf-8")
    (root / "movie.mp4").write_text("video", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    result = asyncio.run(xunlei_backend.handle_action("restore_candidates", config, {"limit": 50}))
    assert result["total"] == 1
    assert result["items"][0]["path"] == str(residual)


def test_delete_residual_deletes_only_allowed_files(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    residual = root / "ABCD-123.xltd"
    residual.write_text("partial", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    result = asyncio.run(xunlei_backend._delete_residual(config, str(residual)))
    assert result["ok"] is True
    assert not residual.exists()


def test_delete_residual_rejects_outside_root(tmp_path):
    root = tmp_path / "downloads"
    root.mkdir()
    outside = tmp_path / "outside.xltd"
    outside.write_text("partial", encoding="utf-8")
    config = {"restore_scan_roots": str(root)}
    with pytest.raises(ValueError, match="不在允许扫描目录内"):
        asyncio.run(xunlei_backend._delete_residual(config, str(outside)))


def test_explicit_savepath_fails_closed_when_unknown():
    config = {"savepath": "/volume1/data/downloads/av/"}
    client = FakeClient(paths=[])
    with pytest.raises(ValueError, match="迅雷保存路径无法解析"):
        asyncio.run(xunlei_backend._require_parent_folder_id_for_explicit_savepath(config, client, "pan-auth", "/volume1/data/downloads/av/"))


def test_plugin_json_has_account_and_mobile_schema():
    plugin = json.loads((ROOT / "plugins/xunlei-remote/plugin.json").read_text(encoding="utf-8"))
    defaults = plugin["default_config"]
    for key in ("account_access_token", "account_target", "account_parent_folder_id", "account_device_id",
                "mobile_access_token", "mobile_captcha_token", "mobile_shumei_boxid", "mobile_device_id",
                "mobile_peer_id", "mobile_target", "mobile_parent_folder_id"):
        assert key in defaults
        assert key in plugin["config_schema"]
