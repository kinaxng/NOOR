from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.api.endpoints import media_library_deletion as deletion
from app.api.endpoints import media_library


def _write_chain(tmp_path: Path) -> tuple[Path, Path]:
    source_dir = tmp_path / "source"
    hardlink_dir = tmp_path / "hardlinks"
    source_bucket = source_dir / "TEST-023"
    hardlink_bucket = hardlink_dir / "TEST-023"
    source_bucket.mkdir(parents=True)
    hardlink_bucket.mkdir(parents=True)
    source_file = source_bucket / "TEST-023.mp4"
    hardlink_file = hardlink_bucket / "TEST-023.mp4"
    source_file.write_bytes(b"video")
    os.link(source_file, hardlink_file)
    return source_file, hardlink_file


def test_directory_matches_target_videos_allows_recursive_video_files(tmp_path: Path):
    bucket = tmp_path / "TEST-024"
    nested = bucket / "nested"
    nested.mkdir(parents=True)
    video = bucket / "TEST-024.mp4"
    video.write_bytes(b"video")

    assert deletion.directory_matches_target_videos(bucket, {video}) is True


def test_delete_plan_from_hardlink_entry_covers_source_and_hardlink_buckets(tmp_path: Path):
    source_file, hardlink_file = _write_chain(tmp_path)
    roots = [tmp_path / "source", tmp_path / "hardlinks"]
    dirs, files = deletion.delete_plan_from_hardlink_entry(
        {
            "source_path": str(source_file),
            "hardlink_paths": [str(hardlink_file)],
        },
        code="TEST-023",
        source_roots=[roots[0]],
        hardlink_roots=[roots[1]],
    )

    assert dirs == {source_file.parent.resolve(), hardlink_file.parent.resolve()}
    assert files == set()


def test_find_inode_chain_for_path_discovers_all_hardlinks(tmp_path: Path):
    source_file, hardlink_file = _write_chain(tmp_path)
    matches = deletion.find_inode_chain_for_path(
        source_file,
        [tmp_path / "source", tmp_path / "hardlinks"],
    )

    assert source_file.resolve() in matches
    assert hardlink_file.resolve() in matches


def test_media_item_delete_plan_uses_hardlink_groups(monkeypatch, tmp_path: Path):
    source_file, hardlink_file = _write_chain(tmp_path)
    source_root = tmp_path / "source"
    hardlink_root = tmp_path / "hardlinks"
    config = {
        "scan_groups": [
            {"source_dir": str(source_root), "hardlink_dir": str(hardlink_root)},
        ]
    }

    async def fake_get_item(config, item_id):
        return {"id": item_id, "file_path": str(source_file), "name": "TEST-023"}

    monkeypatch.setattr(media_library, "_get_item", fake_get_item)
    monkeypatch.setattr(
        media_library,
        "_load_hardlink_groups",
        lambda: [{
            "code": "TEST-023",
            "entries": [{"source_path": str(source_file), "hardlink_paths": [str(hardlink_file)]}],
        }],
    )
    monkeypatch.setattr(
        media_library,
        "_allowed_scan_roots",
        lambda config: ([source_root.resolve()], [hardlink_root.resolve()]),
    )

    code, dirs, files = asyncio.run(media_library._media_item_delete_plan("item-1", config))

    assert code == "TEST-023"
    assert dirs == {source_file.parent.resolve(), hardlink_file.parent.resolve()}
    assert files == set()


def test_media_item_delete_plan_falls_back_to_inode_scan(monkeypatch, tmp_path: Path):
    source_file, hardlink_file = _write_chain(tmp_path)
    source_root = tmp_path / "source"
    hardlink_root = tmp_path / "hardlinks"
    config = {
        "scan_groups": [
            {"source_dir": str(source_root), "hardlink_dir": str(hardlink_root)},
        ]
    }

    async def fake_get_item(config, item_id):
        return {"id": item_id, "file_path": str(source_file), "name": "TEST-023"}

    monkeypatch.setattr(media_library, "_get_item", fake_get_item)
    monkeypatch.setattr(media_library, "_load_hardlink_groups", lambda: [])
    monkeypatch.setattr(
        media_library,
        "_allowed_scan_roots",
        lambda config: ([source_root.resolve()], [hardlink_root.resolve()]),
    )

    code, dirs, files = asyncio.run(media_library._media_item_delete_plan("item-1", config))

    assert code == "TEST-023"
    assert dirs == {source_file.parent.resolve(), hardlink_file.parent.resolve()}
    assert files == set()
