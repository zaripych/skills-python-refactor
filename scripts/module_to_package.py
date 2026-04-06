"""Convert a Python module into a package and split globals into submodules.

Uses rope's ModuleToPackage to convert e.g. models.py → models/__init__.py,
then moves specified globals from __init__.py into dedicated submodules
using MoveGlobal, leaving __init__.py as a re-export facade (or empty).

Usage:
    uv run python module_to_package.py \
        --project-root /path/to/project \
        source_file.py '{"DeviceInfo": "info", "DeviceStatus": "status"}'

The JSON mapping describes which globals go to which submodule names.
Globals not listed in the mapping are assigned to the first mapped symbol
that references them. Globals referenced by no mapped symbol stay in
__init__.py.

Supports --diff via the bootstrap.
"""

import ast
import json
import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run, _rm_empty_dir
from rope.refactor.topackage import ModuleToPackage
from rope.refactor.move import create_move

from move_globals import _find_offset, _remove_symbol_import


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Source .py file to convert")
    parser.add_argument(
        "mapping",
        type=str,
        help="JSON object mapping symbol names to target submodule names, "
        'e.g. \'{"Foo": "foo", "Bar": "bar"}\'',
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Source folder relative to project root (e.g. src). Auto-detected if omitted.",
    )


def _collect_name_refs(node: ast.AST) -> set[str]:
    """Collect all Name references within an AST node (excluding the node's own definition name)."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            # Walk the value chain to find the root Name
            val = child.value
            while isinstance(val, ast.Attribute):
                val = val.value
            if isinstance(val, ast.Name):
                names.add(val.id)
    return names


def _defined_name(node: ast.stmt) -> str | None:
    """Return the name defined by a top-level statement, or None."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _build_dependency_map(source: str, all_globals: set[str]) -> dict[str, set[str]]:
    """For each global, find which other globals it references in its body."""
    tree = ast.parse(source)
    deps: dict[str, set[str]] = {}
    for node in tree.body:
        name = _defined_name(node)
        if name is None or name not in all_globals:
            continue
        refs = _collect_name_refs(node)
        deps[name] = (refs & all_globals) - {name}
    return deps


def _compute_full_mapping(
    source: str,
    resource,
    scope,
    mapping: dict[str, str],
) -> dict[str, str]:
    """Expand the user mapping to include unspecified globals that mapped symbols depend on.

    Unspecified globals are assigned to the submodule of the first mapped symbol
    that references them (iteration order of mapping). If multiple mapped symbols
    reference the same unspecified global, the first one wins.
    """
    # Collect all locally-defined globals in the module
    all_globals: set[str] = set()
    for name in scope.get_defined_names():
        pyname = scope[name]
        def_mod, _ = pyname.get_definition_location()
        if def_mod is not None and def_mod.get_resource() == resource:
            all_globals.add(name)

    unspecified = all_globals - set(mapping)
    if not unspecified:
        return dict(mapping)

    deps = _build_dependency_map(source, all_globals)

    # For each mapped symbol, find all transitive dependencies
    full_mapping = dict(mapping)
    claimed: set[str] = set(mapping)

    for symbol, submodule in mapping.items():
        # BFS for transitive deps
        queue = list(deps.get(symbol, set()))
        visited: set[str] = set()
        while queue:
            dep = queue.pop(0)
            if dep in visited or dep in claimed:
                continue
            visited.add(dep)
            if dep in unspecified:
                full_mapping[dep] = submodule
                claimed.add(dep)
                print(f"  Auto-assigning {dep} to {submodule} (dependency of {symbol})")
            # Follow transitive deps
            queue.extend(deps.get(dep, set()) - visited)

    return full_mapping


def _resolve_pkg_dotted(ctx: RefactorContext, init_path: Path) -> str:
    """Derive the dotted package name from the __init__.py path."""
    project_root = Path(ctx.project.root.real_path)
    pkg_dir = init_path.parent
    rel = pkg_dir.relative_to(project_root)

    source_folders = sorted(
        [sf.path for sf in ctx.project.get_source_folders()],
        key=len,
        reverse=True,
    )
    rel_str = str(rel)
    for sf in source_folders:
        if rel_str == sf or rel_str.startswith(sf + "/"):
            rel = rel.relative_to(sf)
            break
    return ".".join(rel.parts)


def refactor(ctx: RefactorContext) -> None:
    mapping: dict[str, str] = json.loads(ctx.args.mapping)
    if not mapping:
        raise ValueError("Mapping is empty — nothing to do")

    source_path: Path = ctx.args.source
    resource = ctx.get_resource(source_path)

    # Validate all mapped symbols exist and are locally defined
    pymodule = ctx.project.get_pymodule(resource)
    scope = pymodule.get_scope()
    defined = scope.get_defined_names()
    missing = []
    for symbol in mapping:
        if symbol not in defined:
            missing.append(f"{symbol} (not found)")
        elif scope[symbol].get_definition_location()[0].get_resource() != resource:
            missing.append(f"{symbol} (imported, not locally defined)")
    if missing:
        raise ValueError(f"Cannot move from {source_path}: {', '.join(missing)}")

    # Expand mapping with unspecified dependency globals
    source_text = resource.read()
    full_mapping = _compute_full_mapping(source_text, resource, scope, mapping)

    # Ensure packages exist for import resolution
    ctx.ensure_packages(resource)

    # Step 1: Convert module to package
    # Remove leftover empty directory from a previous interrupted/diff run
    pkg_dir = Path(ctx.project.root.real_path) / source_path.with_suffix("")
    _rm_empty_dir(pkg_dir)
    ctx.project.validate()

    print(f"Converting {source_path} to package")
    changes = ModuleToPackage(ctx.project, resource).get_changes()
    ctx.do(changes)

    # After ModuleToPackage, the source is now a package with __init__.py
    init_path = Path(ctx.project.root.real_path) / (
        str(source_path.with_suffix("")) + "/__init__.py"
    )
    pkg_dotted = _resolve_pkg_dotted(ctx, init_path)

    # Group symbols by destination submodule, preserving order
    submodule_symbols: dict[str, list[str]] = {}
    for symbol, submodule_name in full_mapping.items():
        submodule_symbols.setdefault(submodule_name, []).append(symbol)

    # Step 2: Move symbols to their target submodules
    for submodule_name, symbols in submodule_symbols.items():
        dest_dotted = f"{pkg_dotted}.{submodule_name}"
        dest_file = ctx.ensure_module(dest_dotted, source_root=ctx.args.source_root)

        for symbol in symbols:
            # Remove stale import of this symbol from destination before moving
            _remove_symbol_import(ctx, dest_file, symbol)

            # Re-fetch resource after each move (content changes between moves)
            init_resource = ctx.get_resource(init_path)
            found = _find_offset(ctx.project, init_resource, symbol)
            if found is None:
                raise ValueError(
                    f"Symbol {symbol} disappeared from {init_resource.path} during move"
                )
            offset, lineno = found
            print(f"Moving {symbol} to {dest_dotted} (line {lineno}, offset {offset})")

            mover = create_move(ctx.project, init_resource, offset)
            changes = mover.get_changes(dest=dest_dotted)
            ctx.do(changes)

    # Step 3: Delete __init__.py if it's empty (only whitespace/imports left over)
    init_resource = ctx.get_resource(init_path)
    init_content = init_resource.read().strip()
    if init_content == "":
        init_path.unlink()
        ctx.project.validate()
        print(f"Deleted empty {init_resource.path}")


if __name__ == "__main__":
    run(
        refactor,
        description="Convert module to package and split globals into submodules",
        setup_args=setup_args,
    )
