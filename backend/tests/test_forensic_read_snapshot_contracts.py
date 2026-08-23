from __future__ import annotations

import difflib
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_SNAPSHOT_DIR = (
    ROOT / "forensics" / "recovered-sources" / "original-read-snapshots"
)
RECOVERY_SNAPSHOT_DIR = ROOT / "forensics" / "recovered-sources" / "read-snapshots"
SNAPSHOT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})(?:T\d{4})?_"
    r"(?P<hash>[0-9a-f]+)_"
    r"(?P<path>.+?)_"
    r"(?P<start>\d+)-(?P<end>\d+)\.txt$"
)

# These original read-snapshot segments still have a 1.000 best-window match
# against the restored tree. They are listed explicitly instead of derived from
# recovery-session snapshots so the contract cannot silently depend on
# 2026-08-23 recovery reads.
EXACT_ORIGINAL_SNAPSHOTS = [
    "2026-06-10T1444_7d3aab38_plugins__javdb__frontend__page.js_680-720.txt",
    "2026-06-10T1601_dad03098_plugins__mdc-ng-manual__frontend__page.js_145-176.txt",
    "2026-06-10T1607_74b767fb_frontend__src__views__PluginHost.vue_94-220.txt",
    "2026-06-12T1738_4deb6230_frontend__src__views__Dashboard.vue_1040-1420.txt",
    "2026-06-12T1738_6a997eed_frontend__src__views__ResourceSearch.vue_640-735.txt",
    "2026-06-12T1738_82bd28bf_frontend__src__views__Dashboard.vue_680-760.txt",
    "2026-06-13T1021_9e0449ac_frontend__src__components__ui__Button__VuiButton.vue_1-120.txt",
    "2026-06-24T0813_33d56223_plugins__javdb__backend.py_760-830.txt",
    "2026-06-24T0824_1853a4d9_plugins__javdb__frontend__style.css_380-624.txt",
    "2026-06-24T1845_f5013144_data__plugins_config.json_64-74.txt",
    "2026-06-24T1927_433b4062_plugins__xunlei-remote__backend.py_820-940.txt",
    "2026-06-25T1635_4bb0f1ce_frontend__src__views__settings__LadaSettings.vue_1-240.txt",
    "2026-06-26T1832_ddafae2b_README.md_70-110.txt",
    "2026-06-29T1437_5f6a8b82_README.md_150-190.txt",
    "2026-06-30T1322_d67bfb33_backend__app__pipeline__facefusion__source__facefusion__filesystem.py_1-150.txt",
    "2026-07-01T0827_d98ae45e_frontend__src__components__noor__AppSidebar.vue_1-110.txt",
    "2026-07-01T0827_ec6f4635_frontend__src__App.vue_1-120.txt",
    "2026-07-01T0837_e35ed7b5_frontend__src__stores__mediaLibrary.ts_1-360.txt",
    "2026-07-01T1558_c65860e3_frontend__src__components__ui__Button__VuiButton.vue_1-140.txt",
    "2026-07-04T1656_c2926bbc_frontend__src__views__ActorManagementView.vue_560-575.txt",
    "2026-07-04T1657_0c3d73a1_frontend__src__views__ActorManagementView.vue_1040-1185.txt",
    "2026-07-06T1626_687724bf_backend__app__pipeline__whisper__engine.py_430-455.txt",
    "2026-07-07T0856_bcb3780d_frontend__src__composables__useWhisperProfiles.ts_1-230.txt",
    "2026-07-07T1747_e0676029_frontend__src__components__noor__MediaDetailPanel.vue_1-260.txt",
    "2026-07-07T1748_7947a3ea_frontend__src__views__settings__FaceFusionSettings.vue_1-85.txt",
    "2026-07-07T1748_f8adb1e4_frontend__src__views__settings__FaceFusionSettings.vue_1080-1165.txt",
    "2026-07-07T1757_986cb175_frontend__src__views__Home.vue_430-450.txt",
    "2026-07-07T1909_8ecede67_frontend__src__components__noor__FaceFusionPanel.vue_260-315.txt",
    "2026-07-08T0841_b3dddada_backend__app__pipeline__facefusion__source__facefusion__choices.py_117-150.txt",
    "2026-07-08T0843_aba5e2fe_frontend__src__components__noor__FaceFusionPanel.vue_1-25.txt",
    "2026-07-08T1604_bfd74bfe_frontend__src__components__noor__FaceFusionPanel.vue_365-430.txt",
    "2026-07-08T1626_2a7f28d3_frontend__src__components__noor__FaceFusionPanel.vue_1660-1745.txt",
    "2026-07-10T0848_958551b8_frontend__src__views__settings__FaceFusionSettings.vue_1180-1460.txt",
    "2026-07-25T1714_27c115fb_plugins__xunlei-remote__backend.py_1-280.txt",
    "2026-07-25T1714_323aecad_plugins__xunlei-remote__backend.py_540-625.txt",
]


def _best_window(
    lines: list[str],
    snapshot_lines: list[str],
    start: int,
    end: int,
    *,
    max_drift: int,
) -> float:
    best = 0.0
    for offset in range(-max_drift, max_drift + 1):
        candidate_start = start + offset
        candidate_end = end + offset
        if candidate_start < 1 or candidate_end > len(lines):
            continue
        score = difflib.SequenceMatcher(
            None,
            lines[candidate_start - 1:candidate_end],
            snapshot_lines,
        ).ratio()
        best = max(best, score)
    return best


@pytest.mark.skipif(
    not (ROOT / "forensics").exists(),
    reason="recovery evidence is kept in noor-restored",
)
def test_original_read_snapshots_remain_the_authoritative_evidence_source() -> None:
    assert ORIGINAL_SNAPSHOT_DIR.is_dir()
    assert RECOVERY_SNAPSHOT_DIR.is_dir()

    original_snapshots = list(ORIGINAL_SNAPSHOT_DIR.glob("*.txt"))
    recovery_final_snapshots = [
        path
        for path in RECOVERY_SNAPSHOT_DIR.glob("*.txt")
        if path.name.startswith("2026-08-23_")
    ]

    assert recovery_final_snapshots
    assert not [
        path for path in original_snapshots if path.name.startswith("2026-08-23_")
    ]


@pytest.mark.skipif(
    not (ROOT / "forensics").exists(),
    reason="recovery evidence is kept in noor-restored",
)
def test_exact_original_read_snapshot_contracts_still_match_current_tree() -> None:
    checked = 0
    for snapshot_name in EXACT_ORIGINAL_SNAPSHOTS:
        snapshot_path = ORIGINAL_SNAPSHOT_DIR / snapshot_name
        assert snapshot_path.is_file(), f"original snapshot is missing: {snapshot_name}"

        parsed = SNAPSHOT_RE.fullmatch(snapshot_path.name)
        assert parsed
        source_path = parsed.group("path").replace("__", "/")
        start = int(parsed.group("start"))
        end = int(parsed.group("end"))

        current_path = ROOT / source_path
        assert current_path.is_file(), f"final snapshot path is missing: {source_path}"

        current_lines = current_path.read_text(encoding="utf-8", errors="replace").splitlines()
        snapshot_lines = snapshot_path.read_text(encoding="utf-8", errors="replace").splitlines()
        slice_score = (
            difflib.SequenceMatcher(
                None,
                current_lines[start - 1:end],
                snapshot_lines,
            ).ratio()
            if start <= len(current_lines)
            else 0.0
        )
        best_score = _best_window(current_lines, snapshot_lines, start, end, max_drift=200)
        score = max(slice_score, best_score)
        assert score >= 0.999, (
            f"{snapshot_path.name} drifted: slice={slice_score:.3f} best={best_score:.3f}"
        )
        checked += 1

    assert checked == len(EXACT_ORIGINAL_SNAPSHOTS)
