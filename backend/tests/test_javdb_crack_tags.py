from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_backend():
    path = Path(__file__).resolve().parents[2] / "plugins" / "javdb" / "backend.py"
    spec = importlib.util.spec_from_file_location("test_javdb_backend", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_javdb_crack_tags_ignore_title_only_keywords():
    backend = _load_backend()

    assert backend._is_cracked_movie({"title": "TEST-001 無碼破解"}) is False
    assert backend._detail_is_cracked({"title": "TEST-001 無碼破解"}) is False


def test_javdb_crack_tags_accept_explicit_and_resource_signals():
    backend = _load_backend()

    assert backend._is_cracked_movie({"tags": ["破解版"]}) is True
    assert backend._detail_is_cracked({"is_cracked": True}) is True
    assert backend._detail_is_cracked({"magnets": [{"name": "TEST-001 破解版"}]}) is True
