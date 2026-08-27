from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.endpoints.media_library_file_browser import (
    browse_directory,
    browser_roots,
    create_directory,
    delete_entries,
    rename_entry,
    resolve_browser_path,
    transfer_entries,
)


def _roots(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    source = tmp_path / "downloads" / "av"
    hardlink = tmp_path / "media" / "av"
    source.mkdir(parents=True)
    hardlink.mkdir(parents=True)
    return source, hardlink, [source.resolve(), hardlink.resolve()]


def test_browser_defaults_to_configured_source_and_hardlink_roots(tmp_path: Path):
    source, hardlink, _ = _roots(tmp_path)
    sources, hardlinks = browser_roots({"scan_groups": [{"source_dir": str(source), "hardlink_dir": str(hardlink)}]})
    assert sources == [source.resolve()]
    assert hardlinks == [hardlink.resolve()]


def test_browser_can_climb_ancestors_but_hides_unrelated_branches(tmp_path: Path):
    source, hardlink, roots = _roots(tmp_path)
    unrelated = tmp_path / "private"
    unrelated.mkdir()
    payload = browse_directory(tmp_path.resolve(), roots)
    assert {entry["name"] for entry in payload["entries"]} == {"downloads", "media"}
    assert payload["parent"] is not None
    assert resolve_browser_path(str(source.parent), roots, source) == source.parent.resolve()
    with pytest.raises(HTTPException) as exc:
        resolve_browser_path(str(unrelated), roots, source)
    assert exc.value.status_code == 403


def test_browser_reports_permissions_and_hardlink_metadata(tmp_path: Path):
    source, hardlink, roots = _roots(tmp_path)
    original = source / "ABC-123.mp4"
    linked = hardlink / "ABC-123.mp4"
    original.write_bytes(b"video")
    linked.hardlink_to(original)
    payload = browse_directory(hardlink, roots)
    item = payload["entries"][0]
    assert item["size"] == 5
    assert item["link_count"] == 2
    assert item["mode"].startswith("-")
    assert isinstance(item["readable"], bool)


def test_browser_file_operations_stay_inside_managed_roots(tmp_path: Path):
    source, hardlink, roots = _roots(tmp_path)
    file_path = source / "ABC-123.mp4"
    file_path.write_bytes(b"video")
    copied = transfer_entries("copy", [file_path], hardlink, roots)
    assert Path(copied[0]).read_bytes() == b"video"
    renamed = Path(rename_entry(Path(copied[0]), "ABC-123-C.mp4", roots))
    assert renamed.exists()
    folder = Path(create_directory(hardlink, "ABC-123", roots))
    moved = transfer_entries("move", [renamed], folder, roots)
    assert Path(moved[0]).exists()
    assert delete_entries([folder], roots) == [str(folder)]
    assert not folder.exists()


def test_browser_rejects_operations_on_root_or_outside(tmp_path: Path):
    source, hardlink, roots = _roots(tmp_path)
    with pytest.raises(HTTPException):
        delete_entries([source], roots)
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    with pytest.raises(HTTPException):
        transfer_entries("move", [outside], hardlink, roots)
    assert outside.exists()


def test_browser_delete_parent_and_child_only_removes_parent_once(tmp_path: Path):
    source, _, roots = _roots(tmp_path)
    folder = source / "ABC-123"
    folder.mkdir()
    child = folder / "ABC-123.mp4"
    child.write_bytes(b"video")
    deleted = delete_entries([folder, child], roots)
    assert deleted == [str(folder), str(child)]
    assert not folder.exists()
