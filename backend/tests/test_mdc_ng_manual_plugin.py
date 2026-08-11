from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

MODULE_PATH = ROOT / "plugins" / "mdc-ng-manual" / "backend.py"
spec = importlib.util.spec_from_file_location("test_mdc_ng_manual_backend", MODULE_PATH)
mdc_manual = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mdc_manual)


def test_extract_first_json_line_reads_server_action_payload():
    text = '0:{"a":"$@1"}\n1:{"status":"SUCCESS","message":"ok","fieldErrors":{},"timestamp":1}\n'
    result = mdc_manual._extract_first_json_line(text)
    assert result["status"] == "SUCCESS"
    assert result["message"] == "ok"


def test_find_json_objects_extracts_jobs_from_next_html():
    html = 'xxx "job":{"id":6,"source_pathes":"[\\"/data/downloads/av\\"]","target_dir":"/data/media/av","link_mode":0,"finish_count":2,"skip_count":0,"error_count":0,"abort_count":0,"total_count":2,"status":2,"stage":1000,"created_at":"2026-04-11T23:37:47+08:00","started_at":"2026-04-11T23:37:47+08:00","end_at":"2026-04-11T23:37:49+08:00","error_message":null,"config_override":null} yyy'
    items = mdc_manual._find_json_objects(html, '"job":')
    assert len(items) == 1
    assert items[0]["id"] == 6
    normalized = mdc_manual._normalize_job(items[0], "http://127.0.0.1:9208")
    assert normalized["status_label"] == "已完成"
    assert normalized["source_paths"] == ["/data/downloads/av"]


def test_parse_source_paths_accepts_multiline_text_and_array():
    assert mdc_manual._parse_source_paths("/a\n\n/b\r\n/c") == ["/a", "/b", "/c"]
    assert mdc_manual._parse_source_paths(["/a", " ", "/b"]) == ["/a", "/b"]
