from __future__ import annotations

from pathlib import Path

import pytest

from app.api.endpoints.media_library_hardlinks import (
    build_hardlink_groups_impl,
    enrich_hardlink_groups_impl,
    hardlink_groups_path_impl,
    legacy_hardlink_groups_path_impl,
    load_hardlink_groups_impl,
    rename_hardlink_path_impl,
    save_hardlink_groups_impl,
    scan_single_group_impl,
    version_marked_stem_impl,
)


def test_version_marked_stem_normalizes_terminal_markers():
    assert version_marked_stem_impl('TEST-005', '破解') == 'TEST-005-破解'
    assert version_marked_stem_impl('TEST-005-U', 'C') == 'TEST-005-C'
    assert version_marked_stem_impl('TEST-005-C1', '破解-C') == 'TEST-005-破解-C'
    assert version_marked_stem_impl('TEST-006-破解-U', '') == 'TEST-006'


def test_rename_hardlink_path_moves_matching_sidecars(tmp_path: Path):
    root = tmp_path / 'media'; root.mkdir()
    video = root / 'TEST-005-C.mp4'; nfo = root / 'TEST-005-C.nfo'; subtitle = root / 'TEST-005-C.chs.srt'
    video.write_bytes(b'video'); nfo.write_text('full nfo'); subtitle.write_text('subtitle')

    new_path, _ = rename_hardlink_path_impl(str(video), 'TEST-005-破解-C', allowed_roots=[root], groups=[])

    assert new_path == str(root / 'TEST-005-破解-C.mp4')
    assert (root / 'TEST-005-破解-C.nfo').read_text() == 'full nfo'
    assert (root / 'TEST-005-破解-C.chs.srt').read_text() == 'subtitle'


def test_rename_hardlink_path_preserves_suffix_and_updates_cached_path(tmp_path: Path):
    root = tmp_path / 'media'
    root.mkdir()
    source = root / 'ABC-123.mp4'
    source.write_text('video')
    groups = [{'code': 'ABC-123', 'entries': [{'source_path': str(source), 'hardlink_paths': []}]}]

    new_path, updated = rename_hardlink_path_impl(
        str(source), 'ABC-123-new', allowed_roots=[root], groups=groups,
    )

    assert new_path == str(root / 'ABC-123-new.mp4')
    assert Path(new_path).read_text() == 'video'
    assert updated[0]['entries'][0]['source_path'] == new_path


@pytest.mark.parametrize('new_stem', ['../ABC-123', '', '..'])
def test_rename_hardlink_path_rejects_unsafe_name(tmp_path: Path, new_stem: str):
    root = tmp_path / 'media'
    root.mkdir()
    source = root / 'ABC-123.mp4'
    source.write_text('video')

    with pytest.raises(ValueError):
        rename_hardlink_path_impl(str(source), new_stem, allowed_roots=[root], groups=[])
    assert source.exists()


def test_enrich_hardlink_groups_marks_orphan_and_unparsed_groups():
    payload = enrich_hardlink_groups_impl([
        {
            'code': 'N/A',
            'entries': [
                {
                    'source_path': None,
                    'hardlink_paths': ['/hardlinks/a.mp4', '/hardlinks/a-2.mp4'],
                }
            ],
        },
        {
            'code': 'ABC-123',
            'entries': [
                {
                    'source_path': '/source/abc-123.mp4',
                    'hardlink_paths': ['/hardlinks/abc-123.mp4'],
                }
            ],
        },
    ])

    assert payload['summary'] == {
        'total_groups': 2,
        'total_entries': 2,
        'total_hardlinks': 3,
        'issue_groups': 1,
        'orphan_entries': 1,
        'group_count': 2,
        'entry_count': 2,
        'hardlink_count': 3,
        'issue_group_count': 1,
        'orphan_entry_count': 1,
    }

    first = payload['groups'][0]
    assert first['status'] == 'issue'
    assert 'unparsed_code' in first['issues']
    assert 'orphan_source' in first['issues']
    assert first['entries'][0]['status'] == 'issue'
    assert first['entries'][0]['issues'] == ['orphan_source']
    assert first['entry_count'] == 1
    assert first['entries'][0]['hardlink_count'] == 2

    second = payload['groups'][1]
    assert second['status'] == 'healthy'
    assert second['entry_count'] == 1
    assert len(second['entries']) == 1
    assert second['hardlink_count'] == 1


def test_enrich_hardlink_groups_includes_source_size():
    payload = enrich_hardlink_groups_impl([
        {
            'code': 'ABC-123',
            'entries': [
                {
                    'source_path': '/source/abc-123.mp4',
                    'hardlink_paths': ['/hardlinks/abc-123.mp4'],
                }
            ],
        },
    ], source_file_size_fn=lambda path: 123456 if path else None)

    assert payload['groups'][0]['entries'][0]['source_size'] == 123456


def test_hardlink_groups_path_uses_runtime_media_library_dir(tmp_path: Path):
    config_path = tmp_path / 'media_library_config.json'

    assert hardlink_groups_path_impl(lambda: config_path) == tmp_path / 'runtime' / 'media_library' / 'hardlink_groups.txt'


def test_legacy_hardlink_groups_path_uses_config_root(tmp_path: Path):
    config_path = tmp_path / 'media_library_config.json'

    assert legacy_hardlink_groups_path_impl(lambda: config_path) == tmp_path / 'hardlink_groups.txt'


def test_save_hardlink_groups_creates_runtime_dir(tmp_path: Path):
    path = tmp_path / 'runtime' / 'media_library' / 'hardlink_groups.txt'

    save_hardlink_groups_impl([
        {'code': 'ABC-123', 'entries': [{'source_path': '/source/abc.mp4', 'hardlink_paths': ['/hard/abc.mp4']}]}
    ], hardlink_groups_path_fn=lambda: path)

    assert path.read_text(encoding='utf-8') == 'ABC-123|/source/abc.mp4|/hard/abc.mp4\n'


def test_load_hardlink_groups_falls_back_to_legacy_root_file(tmp_path: Path):
    legacy_path = tmp_path / 'hardlink_groups.txt'
    new_path = tmp_path / 'runtime' / 'media_library' / 'hardlink_groups.txt'
    legacy_path.write_text('ABC-123|/source/abc.mp4|/hard/abc.mp4\n', encoding='utf-8')

    assert load_hardlink_groups_impl(hardlink_groups_path_fn=lambda: new_path) == [
        {'code': 'ABC-123', 'entries': [{'source_path': '/source/abc.mp4', 'hardlink_paths': ['/hard/abc.mp4']}]}
    ]


def test_scan_single_group_includes_source_only_entries(tmp_path: Path):
    source_root = tmp_path / 'source'
    hardlink_root = tmp_path / 'hardlinks'
    source_root.mkdir()
    hardlink_root.mkdir()

    source_only = source_root / 'TEST-024.mp4'
    source_only.write_text('video')

    pairs = scan_single_group_impl(
        str(source_root),
        str(hardlink_root),
        scan_inodes_fn=lambda path: {
            (source_only.stat().st_ino, source_only.stat().st_dev): str(source_only),
        } if path == str(source_root) else {},
    )

    assert pairs == [{'source_path': str(source_only), 'hardlink_paths': []}]


@pytest.mark.asyncio
async def test_build_hardlink_groups_uses_source_path_for_source_only_entries():
    payload = await build_hardlink_groups_impl(
        {'scan_groups': [{'source_dir': '/source', 'hardlink_dir': '/hardlinks'}]},
        scan_single_group_fn=lambda _source, _hardlink: [
            {'source_path': '/source/TEST-024/TEST-024.mp4', 'hardlink_paths': []},
        ],
        extract_code_from_path_fn=lambda path: 'TEST-024' if path and 'TEST-024' in path else 'N/A',
    )

    assert payload == [
        {
            'code': 'TEST-024',
            'entries': [{'source_path': '/source/TEST-024/TEST-024.mp4', 'hardlink_paths': []}],
        }
    ]
