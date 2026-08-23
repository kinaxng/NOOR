from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_current_path(root: Path, rel: str) -> Path:
    if (
        rel.startswith("components/")
        or rel.startswith("views/")
        or rel.startswith("composables/")
        or rel.startswith("api/")
        or rel in {"main.ts", "App.vue"}
    ):
        return root / "frontend" / "src" / rel
    return root / rel


def test_byte_level_match_manifest_matches_current_tree() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = root / "forensics" / "current-byte-level-matches.tsv"
    lines = [
        line
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines[0].split("\t")[:3] == ["current_path", "sha256", "evidence"]

    for line in lines[1:]:
        rel, expected, evidence = line.split("\t", 2)
        assert evidence
        current = _resolve_current_path(root, rel)
        assert current.exists(), f"missing current file for {rel}"
        assert _sha256(current) == expected, f"byte match is stale: {rel}"
