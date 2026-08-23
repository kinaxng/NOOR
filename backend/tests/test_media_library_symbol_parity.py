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
