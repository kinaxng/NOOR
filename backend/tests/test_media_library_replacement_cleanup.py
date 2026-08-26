from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.endpoints.media_library_deletion import protect_replacement_from_delete_plan


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
