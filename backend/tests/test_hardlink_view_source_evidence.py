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


def test_media_path_scans_do_not_block_the_api_event_loop() -> None:
    helper = (ROOT / "backend" / "app" / "api" / "endpoints" / "media_library_hardlinks.py").read_text(encoding="utf-8")
    api = (ROOT / "backend" / "app" / "api" / "endpoints" / "media_library.py").read_text(encoding="utf-8")
    local_library = (ROOT / "backend" / "app" / "api" / "local_library.py").read_text(encoding="utf-8")

    assert "await asyncio.to_thread(scan_single_group_fn" in helper
    assert "return await asyncio.to_thread(load_and_enrich)" in api
    assert "return await asyncio.to_thread(save_and_enrich)" in api
    assert "count, elapsed = await asyncio.to_thread(build)" in local_library
