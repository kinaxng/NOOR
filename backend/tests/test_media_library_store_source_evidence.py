from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend" / "src" / "stores" / "mediaLibrary.ts"


def test_scan_hardlinks_returns_nested_summary_counts_to_view() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    assert "count: summary.total_groups ?? resp.data.total_count ?? 0" in text
    assert "totalEntries: summary.total_entries ?? resp.data.total_entries ?? 0" in text
