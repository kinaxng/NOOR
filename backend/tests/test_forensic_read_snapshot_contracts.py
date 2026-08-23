from __future__ import annotations

import difflib
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<hash>[0-9a-f]+)_"
    r"(?P<path>.+?)_"
    r"(?P<start>\d+)-(?P<end>\d+)\.txt$"
)


def _best_window(
    lines: list[str],
    start: int,
    end: int,
    *,
    max_drift: int,
) -> float:
    length = end - start + 1
    snapshot = lines[start - 1:end]
    best = 0.0
    for offset in range(-max_drift, max_drift + 1):
        candidate_start = start + offset
        candidate_end = end + offset
        if candidate_start < 1 or candidate_end > len(lines):
            continue
        score = difflib.SequenceMatcher(
            None,
            lines[candidate_start - 1:candidate_end],
            snapshot,
        ).ratio()
        best = max(best, score)
    return best


@pytest.mark.skipif(
    not (ROOT / "forensics").exists(),
    reason="recovery evidence is kept in noor-restored",
)
def test_final_2026_08_23_read_snapshots_still_match_current_tree() -> None:
    snapshot_dir = ROOT / "forensics" / "recovered-sources" / "read-snapshots"
    snapshots = [path for path in snapshot_dir.glob("*.txt") if path.name.startswith("2026-08-23_")]
    assert snapshots, "expected final 2026-08-23 read snapshots"

    checked = 0
    for snapshot_path in sorted(snapshots):
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
        best_score = _best_window(current_lines, start, end, max_drift=200)
        score = max(slice_score, best_score)
        assert score >= 0.999, (
            f"{snapshot_path.name} drifted: slice={slice_score:.3f} best={best_score:.3f}"
        )
        checked += 1

    assert checked == 79
