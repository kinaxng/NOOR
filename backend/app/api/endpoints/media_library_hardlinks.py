from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Callable

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts', '.webm', '.mpg', '.mpeg'}


def hardlink_groups_path_impl(config_path_fn: Callable[[], Path]) -> Path:
    return config_path_fn().parent / 'runtime' / 'media_library' / 'hardlink_groups.txt'


def legacy_hardlink_groups_path_impl(config_path_fn: Callable[[], Path]) -> Path:
    return config_path_fn().parent / 'hardlink_groups.txt'


def _legacy_path_for(primary_path: Path) -> Path | None:
    if primary_path.name == 'hardlink_groups.txt' and primary_path.parent.name == 'media_library' and primary_path.parent.parent.name == 'runtime':
        return primary_path.parent.parent.parent / 'hardlink_groups.txt'
    return None


def scan_inodes_impl(dir_path: str) -> dict[tuple[int, int], str]:
    result: dict[tuple[int, int], str] = {}
    if not os.path.isdir(dir_path):
        return result
    for dirpath, _dirnames, filenames in os.walk(dir_path):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() not in VIDEO_EXTS:
                continue
            full_path = os.path.join(dirpath, filename)
            try:
                stat = os.stat(full_path)
            except (OSError, PermissionError):
                continue
            if stat.st_ino:
                result.setdefault((stat.st_ino, stat.st_dev), full_path)
    return result


def scan_single_group_impl(source_dir: str, hardlink_dir: str, *, scan_inodes_fn: Callable[[str], dict[tuple[int, int], str]]) -> list[dict]:
    source_inodes = scan_inodes_fn(source_dir)
    hardlink_inodes: dict[tuple[int, int], list[str]] = {}
    if os.path.isdir(hardlink_dir):
        for dirpath, _dirnames, filenames in os.walk(hardlink_dir):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() not in VIDEO_EXTS:
                    continue
                full_path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(full_path)
                except (OSError, PermissionError):
                    continue
                if stat.st_ino:
                    hardlink_inodes.setdefault((stat.st_ino, stat.st_dev), []).append(full_path)

    results: list[dict] = []
    matched: set[tuple[int, int]] = set()
    for inode, hardlinks in hardlink_inodes.items():
        source_path = source_inodes.get(inode)
        if source_path:
            matched.add(inode)
        results.append({'source_path': source_path, 'hardlink_paths': hardlinks})
    for inode, source_path in source_inodes.items():
        if inode not in matched:
            results.append({'source_path': source_path, 'hardlink_paths': []})
    return results


def extract_code_from_path_impl(file_path: str) -> str:
    if not file_path:
        return 'N/A'
    basename = os.path.splitext(os.path.basename(file_path))[0]
    basename = re.sub(r'[-_]?(?:restored-u|restored|cracked|leaked|uncensored|uncensor|破解|流出|无码|C(?=\b)|cd\d+|C\b)', '', basename, flags=re.IGNORECASE)
    basename = basename.replace('_', '-').strip('-_')
    match = re.search(r'\b([A-Z]{2,6}-\d+)\b', basename, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r'\b(\d{3,}-\d+)\b', basename)
    if match:
        return match.group(1).upper()
    return basename.upper() or 'N/A'


def fetch_emby_item_info_impl(
    config: dict,
    emby_id: str | None,
    *,
    httpx_module: Any,
    server_url_fn: Callable[[dict], str],
    headers_fn: Callable[[str], dict],
) -> tuple[str | None, str | None]:
    if not emby_id or not config.get('api_key'):
        return None, None
    try:
        base_url = server_url_fn(config)
        api_key = config.get('api_key', '')
        user_id = config.get('user_id', '')
        url = f'{base_url}/emby/Users/{user_id}/Items/{emby_id}' if user_id else f'{base_url}/emby/Items/{emby_id}'
        response = httpx_module.Client(timeout=15.0).get(url, headers=headers_fn(api_key), params={'Fields': 'Name,ImageTags'})
        if response.status_code != 200:
            return None, None
        item = response.json()
    except Exception:
        return None, None
    tag = item.get('ImageTags', {}).get('Primary')
    poster = f'{base_url}/emby/Items/{emby_id}/Images/Primary?tag={tag}' if tag else None
    return item.get('Name'), poster


async def build_hardlink_groups_impl(config: dict, *, scan_single_group_fn: Callable[[str, str], list[dict]], extract_code_from_path_fn: Callable[[str], str]) -> list[dict]:
    groups_by_code: dict[str, list[dict]] = {}
    for group in config.get('scan_groups', []):
        source_dir, hardlink_dir = group.get('source_dir', ''), group.get('hardlink_dir', '')
        if not source_dir or not hardlink_dir:
            continue
        # Directory traversal may touch slow/NFS-backed media paths. Keep it
        # away from FastAPI's event loop so health and UI requests stay live.
        pairs = await asyncio.to_thread(scan_single_group_fn, source_dir, hardlink_dir)
        for pair in pairs:
            code_path = (pair['hardlink_paths'] or [pair['source_path']])[0]
            code = extract_code_from_path_fn(code_path) if code_path else 'N/A'
            groups_by_code.setdefault(code, []).append(pair)
    return [{'code': code, 'entries': entries} for code, entries in sorted(groups_by_code.items())]


def save_hardlink_groups_impl(groups: list[dict], *, hardlink_groups_path_fn: Callable[[], Path]) -> None:
    lines = []
    for group in groups:
        for entry in group.get('entries', []):
            lines.append(f"{group.get('code', 'N/A')}|{entry.get('source_path') or ''}|{'|'.join(entry.get('hardlink_paths', []))}")
    path = hardlink_groups_path_fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def load_hardlink_groups_impl(*, hardlink_groups_path_fn: Callable[[], Path]) -> list[dict]:
    path = hardlink_groups_path_fn()
    if not path.is_file():
        path = _legacy_path_for(path) or path
    if not path.is_file():
        return []
    groups: dict[str, list[dict]] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        parts = line.strip().split('|')
        if len(parts) >= 3:
            groups.setdefault(parts[0] or 'N/A', []).append({'source_path': parts[1], 'hardlink_paths': [item for item in parts[2:] if item]})
    return [{'code': code, 'entries': entries} for code, entries in sorted(groups.items())]


def source_file_size_impl(source_path: str | None) -> int | None:
    try:
        return os.stat(source_path).st_size if source_path else None
    except (OSError, PermissionError):
        return None


def enrich_hardlink_groups_impl(groups: list[dict], *, source_file_size_fn: Callable[[str | None], int | None] = source_file_size_impl) -> dict[str, Any]:
    enriched_groups: list[dict] = []
    total_entries = 0
    total_hardlinks = 0
    issue_groups = 0
    orphan_entries = 0

    for group in groups:
        enriched_entries: list[dict] = []
        group_hardlinks = 0
        group_orphans = 0
        is_unparsed = group.get('code', 'N/A') == 'N/A'

        for entry in group.get('entries', []):
            hardlink_paths = [item for item in (entry.get('hardlink_paths', []) or []) if item]
            hardlink_count = len(hardlink_paths)
            source_path = entry.get('source_path')
            source_size = source_file_size_fn(source_path)
            issues: list[str] = []
            if not source_path:
                issues.append('orphan_source')
                group_orphans += 1
                orphan_entries += 1

            status = 'issue' if issues else 'healthy'
            group_hardlinks += hardlink_count
            enriched_entries.append({
                'source_path': source_path,
                'hardlink_paths': hardlink_paths,
                'hardlink_count': hardlink_count,
                'source_size': source_size,
                'issues': issues,
                'status': status,
            })

        group_issues: list[str] = []
        if is_unparsed:
            group_issues.append('unparsed_code')
        if group_orphans:
            group_issues.append('orphan_source')
        total_entries += len(enriched_entries)
        total_hardlinks += group_hardlinks
        issue_groups += int(bool(group_issues))
        enriched_groups.append({
            **group,
            'entries': enriched_entries,
            'entry_count': len(enriched_entries),
            'hardlink_count': group_hardlinks,
            'orphan_count': group_orphans,
            'issue_count': len(group_issues),
            'issues': group_issues,
            'status': 'issue' if group_issues else 'healthy',
        })

    return {
        'groups': enriched_groups,
        'summary': {
            'total_groups': len(enriched_groups),
            'total_entries': total_entries,
            'total_hardlinks': total_hardlinks,
            'issue_groups': issue_groups,
            'orphan_entries': orphan_entries,
            'group_count': len(enriched_groups),
            'entry_count': total_entries,
            'hardlink_count': total_hardlinks,
            'issue_group_count': issue_groups,
            'orphan_entry_count': orphan_entries,
        },
    }
