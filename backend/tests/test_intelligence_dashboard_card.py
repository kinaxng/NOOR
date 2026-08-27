from pathlib import Path


def test_dashboard_exposes_intelligence_core_overview_card() -> None:
    source = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "Dashboard.vue"
    text = source.read_text(encoding="utf-8")

    assert "{ id: 'intelligence-core', label: 'Intelligence Core' }" in text
    assert "api.get('/knowledge/stats')" in text
    assert "api.get('/knowledge/resources/refresh/status')" in text
    assert "作品画像" in text
    assert "资源观测" in text
    assert "后台确认" in text
