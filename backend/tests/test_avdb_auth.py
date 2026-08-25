from __future__ import annotations

import importlib.util
from pathlib import Path


def _backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "avdb" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_avdb_backend", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_access_token_uses_bearer_and_takes_precedence_over_legacy_api_key() -> None:
    headers = _backend()._headers({"access_token": "token", "api_key": "legacy"})

    assert headers["Authorization"] == "Bearer token"
    assert "X-API-Key" not in headers


def test_legacy_api_key_remains_supported() -> None:
    headers = _backend()._headers({"api_key": "legacy"})

    assert headers["X-API-Key"] == "legacy"
    assert "Authorization" not in headers


def test_resource_features_are_detected_from_title_when_tags_are_empty() -> None:
    item = _backend()._normalize({
        "id": 1,
        "title": "PRED-878 [无码破解] 中文字幕",
        "download_url": "https://avdb.test/torrent/1",
        "tags": [],
    }, 0)

    assert item is not None
    assert item["features"]["is_cracked"] is True
    assert item["features"]["has_subtitle"] is True
