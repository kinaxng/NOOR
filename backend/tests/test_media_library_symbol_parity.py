from __future__ import annotations

import ast
from pathlib import Path


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for element in target.elts:
                        if isinstance(element, ast.Name):
                            names.add(element.id)
            continue
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _top_level_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_media_library_split_keeps_all_original_public_symbols() -> None:
    root = Path(__file__).resolve().parents[2]
    original = _top_level_names(root / "forensics" / "recovered-sources" / "media_library.final-replayed.py")
    current: set[str] = set()
    for module_path in (root / "backend" / "app" / "api" / "endpoints").glob("media_library*.py"):
        current.update(_top_level_names(module_path))
    current.update(_top_level_names(root / "backend" / "app" / "api" / "endpoints" / "actors.py"))

    public_original = {name for name in original if not name.startswith("_")}
    # A standard-library import name that is not needed by the split modules.
    public_original.discard("base64")

    assert public_original <= current


def test_media_library_module_exposes_original_public_functions() -> None:
    root = Path(__file__).resolve().parents[2]
    original = _top_level_functions(root / "forensics" / "recovered-sources" / "media_library.final-replayed.py")
    from app.api.endpoints import media_library

    missing = sorted(name for name in original if not name.startswith("_") and not hasattr(media_library, name))
    assert missing == []


def test_media_library_module_exposes_all_original_functions() -> None:
    root = Path(__file__).resolve().parents[2]
    original = _top_level_functions(root / "forensics" / "recovered-sources" / "media_library.final-replayed.py")
    from app.api.endpoints import media_library

    missing = sorted(name for name in original if not hasattr(media_library, name))
    assert missing == []


def test_media_library_module_exposes_restored_actor_helpers() -> None:
    from app.api.endpoints import media_library

    for name in {
        "_actor_mapping_store_path",
        "_actor_mapping_sync_state_path",
        "_configured_mdc_ng_root_path",
        "_get_actor_profile",
        "_load_actor_mapping_records",
        "_parse_actor_mapping_xml",
        "_save_actor_mapping_records",
        "_sync_actor_mapping_from_mdc_ng",
        "get_actors",
        "get_actor_movies",
        "upload_actor_avatar",
        "set_actor_avatar_from_url",
        "preview_actor_tmdb_metadata",
        "apply_actor_tmdb_metadata",
        "sync_mdc_ng_actor_mapping",
        "clear_actor_mapping",
        "preview_actor_tmdb_backfill",
        "apply_actor_tmdb_backfill",
        "preview_actor_name_sync",
        "apply_actor_name_sync",
        "execute_actor_mapping_merge",
    }:
        assert hasattr(media_library, name), name
