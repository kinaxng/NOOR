from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.endpoints.media_library_deletion import protect_replacement_from_delete_plan, remove_file_and_sibling_nfo


def test_replacement_cleanup_rejects_new_file_inode(tmp_path: Path):
    new_file = tmp_path / "new.mp4"
    alias = tmp_path / "alias.mp4"
    new_file.write_bytes(b"new")
    alias.hardlink_to(new_file)

    with pytest.raises(HTTPException, match="inode"):
        protect_replacement_from_delete_plan(set(), {alias}, new_file)


def test_replacement_cleanup_keeps_distinct_old_file(tmp_path: Path):
    old_file = tmp_path / "old.mp4"
    new_file = tmp_path / "new.mp4"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    dirs, files = protect_replacement_from_delete_plan(set(), {old_file}, new_file)

    assert dirs == set()
    assert files == {old_file.resolve()}


def test_cleanup_removes_exact_stem_sidecars_but_keeps_new_variant(tmp_path: Path):
    old_file = tmp_path / "TEST-002.mp4"
    old_subtitle = tmp_path / "TEST-002.zh-CN.srt"
    new_file = tmp_path / "TEST-002-U.mp4"
    new_subtitle = tmp_path / "TEST-002-U.zh-CN.srt"
    for path in (old_file, old_subtitle, new_file, new_subtitle):
        path.write_bytes(b"x")

    deleted = remove_file_and_sibling_nfo(old_file)

    assert set(deleted) == {str(old_file), str(old_subtitle)}
    assert new_file.exists()
    assert new_subtitle.exists()
