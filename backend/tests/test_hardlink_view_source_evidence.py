from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend" / "src" / "views" / "HardlinkView.vue"


def test_hardlink_view_keeps_original_mdc_source_action() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    assert "loadMdcManualAvailability" in text
    assert "mdcManualAvailable" in text
    assert "/plugins/mdc-ng-manual/actions/create" in text
    assert "reorganizeSource" in text

    assert "loadHardlinkSourceActions" not in text
    assert "hardlinkSourceActions" not in text
    assert "runHardlinkSourceAction" not in text
    assert "applyRouteSearchQuery" not in text
    assert "useRoute," not in text
    assert "route.query" not in text


def test_hardlink_empty_state_has_component_owned_icon_geometry() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    assert 'class="hardlink-empty-icon"' in text
    assert ".hardlink-empty-icon" in text
    assert "width: 4rem" in text
    assert "height: 4rem" in text
