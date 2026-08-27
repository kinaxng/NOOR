from pathlib import Path


def test_dashboard_exposes_intelligence_core_overview_card() -> None:
    source = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "Dashboard.vue"
    text = source.read_text(encoding="utf-8")

    assert "{ id: 'intelligence-core', label: 'Intelligence Core' }" in text
    assert "api.get('/knowledge/stats')" in text
    assert "api.get('/knowledge/resources/refresh/status')" in text
    assert "作品画像" in text
    assert "资源覆盖" in text
    assert "学习事件" in text
    assert "验证结果" in text
    assert "intelligenceFreshness" in text
    assert "intelligenceAvailability" in text
    assert "intelligencePreferenceTrend" in text
    assert "intelligenceLinkedWorks" in text
    assert "作品邻域" in text
    assert "intelligenceMappedActorRate" in text
    assert "演员关系已映射" in text
    assert "intelligenceProfileCompleteness" in text
    assert "画像完整" in text
    assert "情报新鲜" in text
    assert "近期偏好" in text
    assert "intelligenceLastLearned" in text
    assert "后台确认" in text
